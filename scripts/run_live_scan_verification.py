"""Run an opt-in Ollama scan against a synthetic case and the local law RAG."""

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from urllib.error import URLError
from urllib.request import urlopen

from mevzuat_agent.tools.build_mevzuat_rag import search_mevzuat_rag
from mevzuat_agent.tools.generate_scan_report import generate_scan_report
from mevzuat_agent.tools.scan_repository import (
    DEFAULT_OLLAMA_URL,
    _expand_retrieval_query,
    scan_repository,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAG_INDEX = ROOT / "data/legislation/rag/chunks.jsonl"
FIXTURE = ROOT / "tests/fixtures/live_scan/merchant_export.py"
EXPECTED_SOURCE = "002_GeneratePdf"
EXPECTED_PAGE = 7
EXPECTED_TERMS = (
    "kart hamili",
    "yazılı rızasını almadan",
    "başkasına açıklayamaz",
)


def _check_model(ollama_url: str, model: str) -> None:
    tags_url = ollama_url.rsplit("/", 1)[0] + "/tags"
    try:
        with urlopen(tags_url, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Ollama API is unavailable at {tags_url}: {exc}") from exc
    available = {
        item.get("name")
        for item in payload.get("models", [])
        if isinstance(item, dict)
    }
    if model not in available:
        raise RuntimeError(
            f"Model '{model}' is not installed. Available models: "
            f"{', '.join(sorted(name for name in available if name)) or 'none'}"
        )


def _git(repository: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _verify_retrieval(index_path: Path) -> None:
    query = _expand_retrieval_query(FIXTURE.read_text(encoding="utf-8"))
    matches = search_mevzuat_rag(query, index_path, top_k=3)
    if not any(
        item.chunk.source == EXPECTED_SOURCE
        and item.chunk.page == EXPECTED_PAGE
        and all(term in " ".join(item.chunk.text.casefold().split()) for term in EXPECTED_TERMS)
        for item in matches
    ):
        raise RuntimeError(
            "The local RAG did not retrieve the expected Regulation Article 25 "
            "passage. Rebuild the index from the configured legislation PDFs."
        )


def _verify_findings(result) -> None:
    valid = [
        finding
        for finding in result.findings
        if finding.file == FIXTURE.name
        and finding.line == 2
        and "analytics_vendor.publish(merchant_cardholder_data)" in finding.evidence
        and finding.mevzuat_source == EXPECTED_SOURCE
        and finding.mevzuat_page == EXPECTED_PAGE
        and all(
            term in " ".join(finding.mevzuat_evidence.casefold().split())
            for term in EXPECTED_TERMS
        )
    ]
    if not valid:
        details = [
            {
                "file": finding.file,
                "line": finding.line,
                "code_evidence": finding.evidence,
                "source": finding.mevzuat_source,
                "page": finding.mevzuat_page,
                "legal_evidence": finding.mevzuat_evidence,
            }
            for finding in result.findings
        ]
        raise RuntimeError(
            "Live model did not produce the expected evidence-backed Article 25 "
            f"finding. Accepted findings: {json.dumps(details, ensure_ascii=False)}"
        )


def run_verification(
    *,
    model: str,
    ollama_url: str,
    rag_index_path: Path,
    output_dir: Path,
    timeout_seconds: float,
) -> None:
    if not rag_index_path.is_file():
        raise FileNotFoundError(
            f"RAG index not found: {rag_index_path}. Download legislation and build RAG first."
        )
    _check_model(ollama_url, model)
    print(f"[1/4] Ollama hazır; model={model}")

    _verify_retrieval(rag_index_path)
    print(
        f"[2/4] BM25 Türkçe mevzuat eşleşmesi doğrulandı; "
        f"source={EXPECTED_SOURCE}; page={EXPECTED_PAGE}; madde=25"
    )

    fixture_code = FIXTURE.read_text(encoding="utf-8")
    output_dir.mkdir(parents=True, exist_ok=True)
    scan_path = output_dir / "live_scan.json"
    with tempfile.TemporaryDirectory(prefix="mevzuat-live-verification-") as temp_dir:
        repository = Path(temp_dir) / "merchant-fixture"
        repository.mkdir()
        shutil.copyfile(FIXTURE, repository / FIXTURE.name)
        _git(repository, "init", "-q", "-b", "main")
        _git(repository, "config", "user.name", "MevzuatAgent Verification")
        _git(repository, "config", "user.email", "verification@example.invalid")
        _git(repository, "add", FIXTURE.name)
        _git(repository, "commit", "-m", "Add synthetic Article 25 test case")
        result = scan_repository(
            repository,
            max_files=1,
            rag_index_path=rag_index_path,
            model=model,
            ollama_url=ollama_url,
            output_path=scan_path,
            request_timeout_seconds=timeout_seconds,
        )

    _verify_findings(result)
    markdown_path, html_path = generate_scan_report(scan_path)
    finding = next(
        finding
        for finding in result.findings
        if finding.file == FIXTURE.name
        and finding.line == 2
        and finding.mevzuat_source == EXPECTED_SOURCE
        and finding.mevzuat_page == EXPECTED_PAGE
    )
    print(
        f"[3/4] Canlı tarama doğrulandı; files={result.files_scanned}/"
        f"{result.files_considered}; accepted_findings={len(result.findings)}"
    )
    print(
        f"      code={finding.file}:{finding.line}; "
        f"legal={finding.mevzuat_source}:p.{finding.mevzuat_page}"
    )
    print(f"[4/4] JSON/Markdown/HTML raporları üretildi: {markdown_path}, {html_path}")
    print("TEST ONLY: Kod örneği sentetiktir; bu sonuç gerçek depo bulgusu veya hukuki görüş değildir.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen3:4b", help="Kurulu Ollama modeli")
    parser.add_argument(
        "--ollama-url",
        default=DEFAULT_OLLAMA_URL,
        help="Ollama /api/chat endpoint URL",
    )
    parser.add_argument(
        "--rag-index",
        type=Path,
        default=DEFAULT_RAG_INDEX,
        help="Mevzuat BM25 chunks.jsonl yolu",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "data/reports/live_model_verification",
        help="JSON, Markdown ve HTML tarama çıktısı dizini",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=300,
        help="Dosya başına Ollama istek zaman aşımı (saniye)",
    )
    args = parser.parse_args()
    run_verification(
        model=args.model,
        ollama_url=args.ollama_url,
        rag_index_path=args.rag_index,
        output_dir=args.output_dir,
        timeout_seconds=args.timeout,
    )


if __name__ == "__main__":
    main()
