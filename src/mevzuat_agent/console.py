"""Kullanıcıyı onay kapılı MevzuatAgent işlemlerinde yönlendirir."""

import difflib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Callable
from urllib.parse import unquote, urlsplit
from urllib.error import URLError
from urllib.request import Request, urlopen

from mevzuat_agent.prompt import load_system_prompt
from mevzuat_agent.tools.apply_remediation import apply_remediation
from mevzuat_agent.tools.build_mevzuat_rag import build_mevzuat_rag
from mevzuat_agent.tools.clone_repositories import clone_repositories
from mevzuat_agent.tools.download_mevzuat import download_mevzuat
from mevzuat_agent.tools.estimate_scan_cost import (
    DEFAULT_OLLAMA_URL,
    is_source_file,
    list_ollama_models,
)
from mevzuat_agent.tools.generate_scan_report import generate_scan_report
from mevzuat_agent.tools.mevzuat_config import load_mevzuat_links
from mevzuat_agent.tools.prepare_remediation_plan import prepare_remediation_plan
from mevzuat_agent.tools.propose_remediation import propose_remediation
from mevzuat_agent.tools.scan_repository import run_git_command
from mevzuat_agent.tools.validate_config import validate_config
from mevzuat_agent.workflows.scan import (
    RepositoryScanArtifacts,
    ScanApprovalRequest,
    run_scan_workflow,
)


_ROOT = Path(__file__).resolve().parents[2]
_SELECTED_LAW_INDICES: tuple[int, ...] | None = None
_LAW_SCOPE_CONFIRMED = False


def run_console() -> None:
    """Sohbet arayüzünden proje sorularını yanıtlar ve pipeline'ı sürdürür."""
    global _LAW_SCOPE_CONFIRMED, _SELECTED_LAW_INDICES

    print("MevzuatAgent | Mevzuat uyumluluğu kod tarama aracı")
    print("Raporlar otomatik karar değildir; mevzuat uzmanı tarafından doğrulanmalıdır.")
    print("Merhaba! MevzuatAgent projesini sorabilir veya pipeline'ı yönlendirebilirsiniz.")
    _SELECTED_LAW_INDICES = None
    _LAW_SCOPE_CONFIRMED = False
    history: list[dict[str, str]] = []
    try:
        laws = load_mevzuat_links(_ROOT / "mevzuat_link.json")
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Mevzuat bağlantıları yüklenemedi: {exc}")
        laws = ()
    if laws:
        print("Başlamak için mevzuat adını/numarasını seçin; ayrıca proje hakkında soru sorabilirsiniz.")
        _print_mevzuat_options(laws)
    print("Örnekler: '1', 'devam', 'tarama yap', 'yardım', 'çıkış'.")

    while True:
        try:
            user_message = input("\nSiz: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nMevzuatAgent kapatıldı.")
            return
        if not user_message:
            continue
        normalized = user_message.casefold().strip()
        if normalized in {"0", "çık", "çıkış", "exit", "quit"}:
            print("MevzuatAgent kapatıldı.")
            return
        if normalized in {"yardım", "help", "?"}:
            print(_chat_help())
            continue

        if not _LAW_SCOPE_CONFIRMED:
            try:
                selection = _parse_mevzuat_selection(user_message, laws)
            except ValueError as exc:
                print(f"Mevzuat seçimi anlaşılmadı: {exc}")
                _print_mevzuat_options(laws)
                continue
            if selection is not None:
                _SELECTED_LAW_INDICES = selection
                _LAW_SCOPE_CONFIRMED = True
                chosen = (
                    "tüm kaynaklar"
                    if len(selection) == len(laws)
                    else ", ".join(str(index) for index in selection)
                )
                print(f"Mevzuat kapsamı seçildi: {chosen}. Ne yapmak istersiniz?")
                continue

        action = _detect_pipeline_request(normalized)
        if action is not None:
            if not _LAW_SCOPE_CONFIRMED:
                print("Pipeline'a başlamadan önce taranacak mevzuat kapsamını seçin.")
                _print_mevzuat_options(laws)
                continue
            try:
                if action == "continue":
                    step, description = _next_pipeline_step()
                    print(f"Pipeline adımı: {description}")
                    _run_pipeline_step(step)
                else:
                    _run_pipeline_step(action)
                print("Bu adım sonlandı. Sonraki adıma geçmek için 'devam' yazabilirsiniz.")
            except (OSError, ValueError, RuntimeError, PermissionError) as exc:
                print(f"İşlem tamamlanamadı: {exc}")
            continue

        try:
            answer = _chat_response(user_message, history, laws)
        except (OSError, URLError, TimeoutError, ValueError, RuntimeError) as exc:
            print(f"Yerel sohbet modeli yanıt veremedi: {exc}")
            print("Ollama'nın çalıştığını ve en az bir model yüklü olduğunu doğrulayın.")
            continue
        print(f"MevzuatAgent: {answer}")
        history.extend(
            ({"role": "user", "content": user_message}, {"role": "assistant", "content": answer})
        )
        history = history[-12:]
        if not _LAW_SCOPE_CONFIRMED:
            print("Pipeline işlemleri için önce mevzuat kapsamını seçin (yardım için 'yardım').")


def _chat_help() -> str:
    return (
        "MevzuatAgent sohbet yardımı:\n"
        "- Önce mevzuat bağlantılarından numara seçin; ör. 1, 2 veya 1,2. * tümüdür.\n"
        "- 'devam' sıradaki pipeline adımını önerip çalıştırır.\n"
        "- 'RAG hazırla', 'depoları klonla', 'tarama yap' veya 'bulguları düzelt' "
        "ilgili aşamayı başlatır; gereken onaylar ayrıca sorulur.\n"
        "- Proje/mevzuat sorularını doğal dille sorabilirsiniz; 'çıkış' uygulamayı kapatır."
    )


def _print_mevzuat_options(links: tuple[str, ...]) -> None:
    print("Mevzuat seçenekleri:")
    for index, link in enumerate(links, start=1):
        label = unquote(Path(urlsplit(link).path).name) or link
        print(f"  {index}. {label}")
    print("Numara, virgülle ayrılmış numaralar veya * (tümü) yazın.")


def _parse_mevzuat_selection(
    message: str, links: tuple[str, ...]
) -> tuple[int, ...] | None:
    value = message.strip().casefold()
    if value in {"*", "tümü", "tum", "hepsi", "tüm mevzuatlar"}:
        return tuple(range(1, len(links) + 1))
    if re.fullmatch(r"\d+(?:\s*,\s*\d+)*", value):
        selected = tuple(sorted({int(item.strip()) for item in value.split(",")}))
        if selected and all(1 <= index <= len(links) for index in selected):
            return selected
    for index, link in enumerate(links, start=1):
        filename = unquote(Path(urlsplit(link).path).name).casefold()
        stem = Path(filename).stem
        if filename and (value == filename or filename in value or stem in value):
            return (index,)
    if re.fullmatch(r"\d+(?:\s*,\s*\d+)*", value):
        raise ValueError("Listelenen mevzuat numaralarından seçim yapın.")
    return None


def _detect_pipeline_request(message: str) -> str | None:
    if message in {"devam", "sıradaki adım", "sonraki adım", "pipeline", "akışı sürdür"}:
        return "continue"
    if any(term in message for term in ("rag hazırla", "mevzuat indir", "mevzuatı indir")):
        return "1"
    if any(term in message for term in ("klonla", "depoyu indir", "depoları indir")):
        return "2"
    if any(term in message for term in ("remediation", "bulguları düzelt", "düzeltmeyi başlat")):
        return "4"
    if any(term in message for term in ("tarama yap", "taramayı başlat", "kodu tara")):
        return "3"
    return None


def _chat_response(
    user_message: str,
    history: list[dict[str, str]],
    laws: tuple[str, ...],
) -> str:
    model = os.environ.get("MEVZUAT_AGENT_CHAT_MODEL")
    if not model:
        models = list_ollama_models(DEFAULT_OLLAMA_URL)
        if not models:
            raise RuntimeError("Ollama'da kurulu model bulunamadı.")
        model = models[0]
    try:
        step, description = _next_pipeline_step()
    except (OSError, ValueError, RuntimeError) as exc:
        step, description = "?", f"Durum belirlenemedi ({exc})"
    if not _LAW_SCOPE_CONFIRMED:
        law_status = "Henüz seçim yapılmadı; kullanıcıdan mevzuat bağlantısı seçmesini iste."
    elif _SELECTED_LAW_INDICES is not None and len(_SELECTED_LAW_INDICES) == len(laws):
        law_status = "Tüm mevzuatlar seçildi."
    else:
        law_status = f"Seçilen bağlantı numaraları: {_SELECTED_LAW_INDICES}."
    runtime_context = (
        f"Yerel uygulama durumu: {law_status} "
        f"Pipeline sıradaki adım {step}: {description}. "
        f"Mevzuat seçenekleri: {json.dumps(laws, ensure_ascii=False)}. "
        "Yalnızca yanıt üret; pipeline araçlarını bu yanıtla çalıştırdığını iddia etme. "
        "İşlem için kullanıcıya doğal dille 'devam' veya ilgili aşama komutunu yazmasını söyle. "
        "İşlemler ayrıca kullanıcı onayı gerektirir."
    )
    messages = [
        {"role": "system", "content": f"{load_system_prompt()}\n\n{runtime_context}"},
        *history[-12:],
        {"role": "user", "content": user_message},
    ]
    request_data = json.dumps(
        {
            "model": model,
            "stream": False,
            "messages": messages,
            "options": {"temperature": 0.2, "num_predict": 500},
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = Request(
        f"{DEFAULT_OLLAMA_URL.rstrip('/')}/api/chat",
        data=request_data,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=180) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("error"):
        raise RuntimeError(str(payload["error"]))
    content = payload.get("message", {}).get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Ollama boş sohbet yanıtı döndürdü.")
    return content.strip()


def _active_rag_index() -> Path:
    index_path = _ROOT / "data/legislation/rag/chunks.jsonl"
    if _SELECTED_LAW_INDICES is None:
        return index_path

    selected_prefixes = tuple(f"{index:03d}_" for index in _SELECTED_LAW_INDICES)
    selected_path = (
        _ROOT
        / "data/legislation/rag/selections"
        / f"selection_{'_'.join(str(index) for index in _SELECTED_LAW_INDICES)}.jsonl"
    )
    selected_path.parent.mkdir(parents=True, exist_ok=True)
    selected_records: list[str] = []
    with index_path.open(encoding="utf-8") as index_file:
        for line in index_file:
            record = json.loads(line)
            if isinstance(record, dict) and isinstance(record.get("source"), str):
                if record["source"].startswith(selected_prefixes):
                    selected_records.append(line)
    if not selected_records:
        raise ValueError(
            "Seçilen mevzuata ait RAG parçası bulunamadı. "
            "Mevzuat belgelerini yeniden indirip RAG indeksini hazırlayın."
        )
    selected_path.write_text("".join(selected_records), encoding="utf-8")
    return selected_path


def _next_pipeline_step() -> tuple[str, str]:
    """Mevcut yerel hazırlığa göre iş akışındaki sıradaki adımı seçer."""
    rag_index = _ROOT / "data/legislation/rag/chunks.jsonl"
    if not rag_index.is_file() or rag_index.stat().st_size == 0:
        return "1", "Mevzuat belgelerini indirip RAG indeksini hazırlama"
    if not _local_repository_candidates():
        return "2", "repo_link.json depolarını klonlama"
    try:
        target = _latest_scan_target()
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Son tarama remediation için kullanılamıyor: {exc}")
        return "3", "Yerel depoda tarama tahmini ve onaylı tarama"
    if target is not None and not _has_remediation_after(target[1]):
        return "4", "Son taramadaki en önemli bulguları remediation ile düzeltme"
    return "3", "Yerel depoda tarama tahmini ve onaylı tarama"


def _run_pipeline_step(step: str) -> None:
    actions: dict[str, Callable[[], None]] = {
        "1": _prepare_legislation,
        "2": _clone_repositories,
        "3": _scan_repository,
        "4": _remediate,
    }
    actions[step]()


def _run_manual_menu() -> bool:
    """İleri kullanıcılar için tüm mevcut işlemleri gösterir."""
    print(
        "\n"
        "1. Mevzuat belgelerini indir ve RAG indeksini hazırla\n"
        "2. repo_link.json depolarını klonla\n"
        "3. Yerel depoda tarama/tahmin yap\n"
        "4. Son taramadaki bulguları düzelt ve Markdown/HTML diff raporu oluştur\n"
        "5. Yapılandırmaları kontrol et\n"
        "0. Çıkış"
    )
    choice = input("Seçiminiz: ").strip()
    actions: dict[str, Callable[[], None]] = {
        "1": _prepare_legislation,
        "2": _clone_repositories,
        "3": _scan_repository,
        "4": _remediate,
        "5": _show_config,
    }
    if choice == "0":
        print("MevzuatAgent kapatıldı.")
        return False
    action = actions.get(choice)
    if action is None:
        print("Geçersiz seçim. Menüdeki numaralardan birini girin.")
        return True
    try:
        action()
    except (OSError, ValueError, RuntimeError, PermissionError) as exc:
        print(f"İşlem tamamlanamadı: {exc}")
    return True


def _local_repository_candidates() -> list[Path]:
    candidates = []
    for parent in (_ROOT / "data/test_repositories", _ROOT / "data/repositories"):
        if parent.is_dir():
            candidates.extend(
                path
                for path in sorted(parent.iterdir())
                if path.is_dir() and (path / ".git").exists()
            )
    return candidates


def _latest_scan_target() -> tuple[Path, Path] | None:
    """En yeni tarama raporundan depo kökünü ve JSON yolunu bulur."""
    scan_dir = _ROOT / "data/reports/scans"
    reports = sorted(
        scan_dir.glob("*.json"),
        key=lambda path: path.stat().st_mtime_ns,
    ) if scan_dir.is_dir() else []
    for scan_path in reversed(reports):
        try:
            result = json.loads(scan_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Son tarama JSON'u geçersiz: {scan_path}") from exc
        if not isinstance(result, dict) or not isinstance(result.get("findings"), list):
            raise ValueError(f"Son tarama JSON'u bulgu listesi içermiyor: {scan_path}")
        if not result["findings"]:
            continue
        model = result.get("model")
        if isinstance(model, str) and model.startswith("synthetic-fixture"):
            continue

        repository_value = result.get("repository")
        if not isinstance(repository_value, str) or not repository_value.strip():
            raise ValueError(f"Son tarama raporunda depo yolu bulunamadı: {scan_path}")
        repository = Path(repository_value).expanduser().resolve()
        if not repository.is_dir():
            raise FileNotFoundError(
                f"Son taramanın deposu bulunamadı: {repository}. Depoyu yeniden klonlayıp tarayın."
            )
        git_root = Path(run_git_command(repository, "rev-parse", "--show-toplevel")).resolve()
        if git_root != repository:
            raise ValueError(f"Tarama raporundaki yol Git deposunun kökü değil: {repository}")
        return repository, scan_path
    return None


def _has_remediation_after(scan_path: Path) -> bool:
    report_dir = _ROOT / "data/reports/remediation"
    return any(
        report.stat().st_mtime_ns > scan_path.stat().st_mtime_ns
        for report in report_dir.glob("remediation-*.md")
    ) if report_dir.is_dir() else False


def _show_config() -> None:
    result = validate_config(_ROOT)
    if result.errors:
        for error in result.errors:
            print(f"Hata: {error}")
        return
    print(f"Mevzuat bağlantısı: {len(result.mevzuat_links)}")
    print(f"Depo bağlantısı: {len(result.repository_links)}")


def _prepare_legislation() -> None:
    download_dir = _ROOT / "data/legislation/downloads"
    rag_dir = _ROOT / "data/legislation/rag"
    index_path = rag_dir / "chunks.jsonl"
    if index_path.is_file() and index_path.stat().st_size:
        if not _ask_yes("Mevcut RAG indeksi var. Yeniden oluşturulsun mu?"):
            print(f"Mevcut indeks korunuyor: {index_path}")
            return

    pdfs = [
        path for path in download_dir.glob("*")
        if path.is_file() and _starts_with_pdf(path)
    ] if download_dir.is_dir() else []
    if not pdfs:
        if not _ask_yes("mevzuat_link.json içindeki kaynaklardan belge indirilsin mi?"):
            print("Belge indirme iptal edildi.")
            return
        result = download_mevzuat(download_dir, config_path=_ROOT / "mevzuat_link.json")
        for document in result.documents:
            print(f"İndirildi: {document.path}")
        if result.errors:
            for error in result.errors:
                print(f"İndirme hatası: {error}")
            if not pdfs and not result.documents:
                return
    result = build_mevzuat_rag(download_dir, rag_dir)
    for error in result.errors:
        print(f"RAG uyarısı: {error}")
    if not result.chunks:
        raise RuntimeError("Belgelerden aranabilir mevzuat metni çıkarılamadı.")
    print(f"RAG indeksi hazır: {result.index_path} ({len(result.chunks)} parça)")


def _clone_repositories() -> None:
    result = validate_config(_ROOT)
    if result.errors:
        raise ValueError("; ".join(result.errors))
    print("Klonlanacak depolar:")
    for link in result.repository_links:
        print(f"- {link}")
    if not _ask_yes("Bu depolar data/repositories içine klonlansın mı?"):
        print("Klonlama iptal edildi.")
        return
    cloned = clone_repositories(
        _ROOT / "data/repositories",
        config_path=_ROOT / "repo_link.json",
        user_approved=True,
    )
    for checkout in cloned.checkouts:
        print(f"Klonlandı: {checkout.path}")
    if cloned.errors:
        raise RuntimeError("; ".join(cloned.errors))


def _scan_repository() -> None:
    repository = _select_repository()
    if repository is None:
        return
    if (
        repository.parent == _ROOT / "data/test_repositories"
        and (repository / "payment_rules.py").is_file()
        and (repository / "scan_result.json").is_file()
    ):
        _run_synthetic_fixture_scan(repository)
        return
    rag_index = _ROOT / "data/legislation/rag/chunks.jsonl"
    if not rag_index.is_file():
        raise FileNotFoundError(f"RAG indeksi bulunamadı: {rag_index}. Önce 1. adımı çalıştırın.")
    rag_index = _active_rag_index()
    tracked_source_count = _count_tracked_sources(repository)
    if tracked_source_count == 0:
        raise ValueError("Depoda Git tarafından izlenen kaynak dosya yok.")
    max_files = _read_positive_integer(
        f"İncelenecek dosya üst sınırı (1-{tracked_source_count}) [5]: ",
        default=min(5, tracked_source_count),
    )

    def request_approval(request: ScanApprovalRequest) -> str | None:
        print("\nModel başına tahmini tarama süresi:")
        for item in request.estimate.models:
            marker = " (en hızlı)" if item.model == request.recommended_model else ""
            print(
                f"- {item.model}: {item.tokens_per_second:.2f} token/sn, "
                f"yaklaşık {item.estimated_seconds} saniye{marker}"
            )
        for error in request.estimate.errors:
            print(f"Model ölçüm uyarısı: {error}")
        print(
            f"Dosya kapsamı: en fazla {request.max_files}; "
            f"tahmini toplam token: {request.estimate.scan.estimated_total_tokens}"
        )
        if not _ask_yes("Bu kapsam ve tahminle taramayı onaylıyor musunuz?"):
            return None
        selected = input(
            f"Model adını yazın; Enter en hızlı modeli seçer "
            f"({request.recommended_model}): "
        ).strip()
        return selected or request.recommended_model

    result = run_scan_workflow(
        [repository],
        max_files=max_files,
        rag_index_path=rag_index,
        output_dir=_ROOT / "data/reports/scans",
        approval_callback=request_approval,
    )
    print(f"Tarama durumu: {result.status}")
    if result.status == "scan_declined":
        print("Tarama başlatılmadı.")
        return
    for artifact in result.repositories:
        print(f"JSON: {artifact.scan.output_path}")
        print(f"Markdown: {artifact.markdown_report}")
        print(f"HTML: {artifact.html_report}")
        if artifact.remediation_plan:
            print(f"Plan: {artifact.remediation_plan}")
        _offer_remediation(repository, artifact)


def _run_synthetic_fixture_scan(repository: Path) -> None:
    """Bilinen test bulgularını doğrulayıp açıkça sentetik rapor olarak üretir."""
    fixture_path = repository / "scan_result.json"
    try:
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Sentetik test bulgusu JSON'u geçersiz: {fixture_path}") from exc
    if not isinstance(fixture, dict) or not isinstance(fixture.get("findings"), list):
        raise ValueError(f"Sentetik test bulgusu listesi bulunamadı: {fixture_path}")

    findings = fixture["findings"]
    grouped_findings: dict[str, list[dict]] = {}
    for item in findings:
        if not isinstance(item, dict):
            raise ValueError("Sentetik test bulgusu geçerli bir nesne değil.")
        relative_path = item.get("file")
        if not isinstance(relative_path, str) or Path(relative_path).is_absolute():
            raise ValueError("Sentetik bulgunun dosya yolu geçersiz.")
        source_path = (repository / relative_path).resolve()
        if not source_path.is_relative_to(repository.resolve()) or not source_path.is_file():
            raise ValueError(f"Sentetik bulgunun kaynak dosyası bulunamadı: {relative_path}")
        code_lines = source_path.read_text(encoding="utf-8").splitlines()
        line = item.get("line")
        evidence = item.get("evidence")
        if (
            not isinstance(line, int)
            or isinstance(line, bool)
            or line < 1
            or line > len(code_lines)
            or not isinstance(evidence, str)
            or " ".join(evidence.split()) not in " ".join(code_lines[line - 1].split())
        ):
            raise ValueError(
                f"Sentetik bulgu kanıtı kaynak kodla eşleşmiyor: {relative_path}:{line}"
            )
        grouped_findings.setdefault(relative_path, []).append(item)

    output_dir = _ROOT / "data/reports/scans"
    output_path = output_dir / f"{repository.name}_synthetic.json"
    branch = run_git_command(repository, "rev-parse", "--abbrev-ref", "HEAD")
    commit = run_git_command(repository, "rev-parse", "--short", "HEAD")
    result = {
        **fixture,
        "repository": f"sentetik-test/{repository.name}",
        "branch_commit": f"{branch}@{commit}",
        "model": "synthetic-fixture (LLM taraması yapılmadı)",
        "scan_scope": "Sentetik test: önceden tanımlı örnek bulgular",
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "files_considered": len(grouped_findings),
        "files_scanned": len(grouped_findings),
        "findings": findings,
        "file_results": [
            {
                "path": path,
                "status": "synthetic_fixture",
                "findings": items,
                "error": None,
            }
            for path, items in sorted(grouped_findings.items())
        ],
        "limitations": [
            "Sentetik test bulgularıdır; gerçek mevzuat taraması veya hukukî tespit değildir."
        ],
        "output_path": str(output_path),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path, html_path = generate_scan_report(output_path)
    plan_path = prepare_remediation_plan(
        output_path,
        output_path=output_path.with_name(f"{output_path.stem}_remediation_plan.md"),
    )
    print("Sentetik test bulguları üretildi; bu işlem Ollama veya gerçek mevzuat kullanmadı.")
    print(f"JSON: {output_path}")
    print(f"Markdown: {markdown_path}")
    print(f"HTML: {html_path}")
    print(f"Örnek düzeltme planı: {plan_path}")


def _offer_remediation(repository: Path, artifact: RepositoryScanArtifacts) -> None:
    if artifact.scan.findings:
        if _ask_yes(
            f"{len(artifact.scan.findings)} doğrulanmış bulgu var. "
            "Remediation adımına şimdi geçilsin mi?"
        ):
            _remediate(repository, artifact.scan.output_path)
        else:
            print("Remediation ertelendi. Menüden 4'ü seçerek sonra devam edebilirsiniz.")
        return

    errors = [
        f"{item.path}: {item.error}"
        for item in artifact.scan.file_results
        if item.error
    ]
    if errors:
        print("Tarama doğrulanmış bulgu üretemedi; remediation başlatılamaz.")
        for error in errors:
            print(f"  - {error}")
        print(
            "Gerçek tarama raporunda doğrulanmış bulgu yok; remediation bu sonuçla "
            "başlatılamaz."
        )
    else:
        print(
            "Doğrulanmış bulgu bulunmadı; remediation için önce "
            "kanıtlanmış bulgu içeren bir tarama gerekir."
        )
    _offer_deterministic_fixture(repository)


def _offer_deterministic_fixture(repository: Path) -> None:
    if repository.name not in {"demo1", "demo2"}:
        return
    fixture = _ROOT / "data/test_repositories" / repository.name
    if not (
        fixture.is_dir()
        and (fixture / "payment_rules.py").is_file()
        and (fixture / "scan_result.json").is_file()
    ):
        return
    print(
        "Bu demo için önceden tanımlı sentetik test bulguları mevcut. "
        "Bunlar yalnızca rapor/ekran görüntüsü provasıdır; gerçek mevzuat bulgusu değildir."
    )
    if _ask_yes("Sentetik test bulgularıyla ayrı bir örnek rapor oluşturulsun mu?"):
        _run_synthetic_fixture_scan(fixture)


def _remediate(
    repository_path: Path | None = None,
    scan_result_path: Path | None = None,
) -> None:
    if (repository_path is None) != (scan_result_path is None):
        raise ValueError("Depo ve tarama sonucu birlikte sağlanmalı.")
    if repository_path is None:
        target = _latest_scan_target()
        if target is None:
            print("Remediation için bulgulu bir tarama bulunamadı. Önce tarama yapın.")
            return
        repository, scan_path = target
        print(f"Son tarama deposu otomatik bulundu: {repository}")
        print(f"Tarama sonucu: {scan_path}")
    else:
        if scan_result_path is None:
            raise ValueError("Tarama sonucu yolu belirtilmeli.")
        repository = Path(repository_path).resolve()
        scan_path = Path(scan_result_path).resolve()
    try:
        scan_result = json.loads(scan_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Tarama JSON dosyası geçersiz: {scan_path}") from exc
    if not isinstance(scan_result, dict) or not isinstance(scan_result.get("findings"), list):
        raise ValueError("Tarama sonucu geçerli bir bulgu listesi içermiyor.")
    if not scan_result["findings"]:
        print("Bu taramada doğrulanmış bulgu olmadığından remediation başlatılamaz.")
        for item in scan_result.get("file_results", []):
            if isinstance(item, dict) and item.get("error"):
                print(f"- {item.get('path', 'Dosya')}: {item['error']}")
        print("Model hatası varsa 3. menüden başka bir model seçerek taramayı tekrarlayın.")
        return
    model = scan_result.get("model")
    if not isinstance(model, str) or not model:
        raise ValueError("Tarama sonucunda model adı bulunmuyor.")
    print("Ollama en önemli iki bulgu için değişiklik önerisi hazırlıyor.")
    changes = propose_remediation(repository, scan_path, model=model)
    for relative, new_content in changes.items():
        old_content = (repository / relative).read_text(encoding="utf-8")
        diff = difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{relative}",
            tofile=f"b/{relative}",
        )
        print("".join(diff))
    if not _ask_yes("Yukarıdaki kod değişikliklerini ayrı dalda uygulamayı onaylıyor musunuz?"):
        print("Dosya değişikliği yapılmadı.")
        return

    application = apply_remediation(
        repository,
        scan_path,
        changes,
        user_approved=True,
        reports_dir=_remediation_reports_dir(),
    )
    print(f"İzole dal: {application.branch}")
    print(f"Worktree: {application.worktree_path}")
    print(f"Diff raporu: {application.markdown_path}")
    print(f"Diff HTML: {application.html_path}")
    print(f"Markdown ve HTML raporları kaydedildi: {application.markdown_path.parent}")
    print("Remediation akışı raporlar oluşturulduktan sonra tamamlandı.")


def _remediation_reports_dir() -> Path:
    configured_dir = os.environ.get("MEVZUAT_AGENT_REPORTS_DIR", "").strip()
    if configured_dir:
        return Path(configured_dir).expanduser()
    return _ROOT / "data/reports/remediation"


def _select_repository() -> Path | None:
    candidates = _local_repository_candidates()
    if not candidates:
        print("Yerel Git deposu bulunamadı. Önce depoyu klonlayın.")
        return None
    print("Yerel depolar:")
    for index, path in enumerate(candidates, start=1):
        label = (
            " [SENTETİK TEST]"
            if path.parent == _ROOT / "data/test_repositories"
            and (path / "scan_result.json").is_file()
            else ""
        )
        print(f"{index}. {path.relative_to(_ROOT)}{label}")
    try:
        selection = int(input("Depo numarası: ").strip())
    except ValueError as exc:
        raise ValueError("Listeden geçerli bir depo numarası girin.") from exc
    if selection > len(candidates):
        raise ValueError("Depo numarası listede yok.")
    if selection <= 0:
        raise ValueError("Listeden geçerli bir depo numarası girin.")
    return candidates[selection - 1]


def _count_tracked_sources(repository: Path) -> int:
    output = run_git_command(repository, "ls-files", "-z")
    return sum(bool(path) and is_source_file(path) for path in output.split("\0"))


def _read_positive_integer(prompt: str, *, default: int | None = None) -> int:
    value = input(prompt).strip()
    if not value and default is not None:
        return default
    try:
        number = int(value)
    except ValueError as exc:
        raise ValueError("Pozitif bir tam sayı girin.") from exc
    if number <= 0:
        raise ValueError("Pozitif bir tam sayı girin.")
    return number


def _ask_yes(question: str) -> bool:
    answer = input(f"{question} [e/H]: ").strip().casefold()
    return answer in {"e", "evet"}


def _starts_with_pdf(path: Path) -> bool:
    try:
        with path.open("rb") as document:
            return document.read(5) == b"%PDF-"
    except OSError:
        return False
