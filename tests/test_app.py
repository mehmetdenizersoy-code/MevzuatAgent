from io import BytesIO
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from mevzuat_agent import main
from mevzuat_agent import console
from mevzuat_agent.prompt import load_system_prompt
from mevzuat_agent.tools.clone_repositories import clone_repositories
from mevzuat_agent.tools.apply_remediation import apply_remediation
from mevzuat_agent.tools.validate_remediation import validate_remediation
from mevzuat_agent.tools.validate_remediation import _test_command
from mevzuat_agent.tools.create_github_pr import create_github_pr
from mevzuat_agent.tools.propose_remediation import propose_remediation
from mevzuat_agent.tools.build_mevzuat_rag import (
    build_mevzuat_rag,
    search_mevzuat_rag,
)
from mevzuat_agent.tools.download_mevzuat import download_mevzuat
from mevzuat_agent.tools.estimate_scan_cost import (
    ModelEstimate,
    ModelPoolEstimate,
    RepositoryScanEstimate,
    ScanCostEstimate,
    benchmark_ollama_model,
    estimate_scan_cost,
    estimate_scan_cost_for_model_pool,
)
from mevzuat_agent.tools.generate_scan_report import generate_scan_report
from mevzuat_agent.tools.prepare_remediation_plan import prepare_remediation_plan
from mevzuat_agent.tools.scan_repository import (
    RepositoryScanResult,
    ScannedFile,
    ScanFinding,
    scan_repository,
    validate_scan_findings,
)
from mevzuat_agent.tools.mevzuat_config import (
    load_mevzuat_links,
    save_mevzuat_links,
)
from mevzuat_agent.tools.validate_config import validate_config
from mevzuat_agent.workflows.scan import (
    RepositoryScanArtifacts,
    build_scan_workflow,
)


def test_main(capsys):
    with patch("builtins.input", return_value="0"):
        main()

    output = capsys.readouterr().out
    assert "MevzuatAgent" in output
    assert "Çıkış" in output
    assert "kapatıldı" in output


def test_system_prompt_defines_scope_and_user_approval_gates():
    prompt = " ".join(load_system_prompt().split())

    assert "Bu asistan yalnızca MevzuatAgent projesi" in prompt
    assert "onayı olmadan depoları klonlama" in prompt
    assert "PR açmadan önce" in prompt


def test_validate_config_accepts_expected_link_files(tmp_path):
    (tmp_path / "mevzuat_link.json").write_text(
        '{"links": ["https://example.gov.tr/law.pdf"]}',
        encoding="utf-8",
    )
    (tmp_path / "repo_link.json").write_text(
        '{"repos": ["https://github.com/example/project.git"]}',
        encoding="utf-8",
    )

    result = validate_config(tmp_path)

    assert result.is_valid
    assert result.mevzuat_links == ("https://example.gov.tr/law.pdf",)
    assert result.repository_links == ("https://github.com/example/project.git",)


def test_validate_config_reports_missing_files(tmp_path):
    result = validate_config(tmp_path)

    assert not result.is_valid
    assert result.errors == (
        "mevzuat_link.json: file not found",
        "repo_link.json: file not found",
    )


def test_validate_config_reports_invalid_json_and_urls(tmp_path):
    (tmp_path / "mevzuat_link.json").write_text(
        '{"links": ["https://[invalid"]}',
        encoding="utf-8",
    )
    (tmp_path / "repo_link.json").write_text(
        '{"repos": ["not-a-repository"]}',
        encoding="utf-8",
    )

    result = validate_config(tmp_path)

    assert not result.is_valid
    assert result.errors == (
        "mevzuat_link.json: 'links[0]' must be a valid HTTP(S) URL",
        "repo_link.json: 'repos[0]' must be a valid HTTPS or SSH URL",
    )


def test_validate_config_requires_non_empty_link_arrays(tmp_path):
    (tmp_path / "mevzuat_link.json").write_text('{"links": []}', encoding="utf-8")
    (tmp_path / "repo_link.json").write_text('{"repos": []}', encoding="utf-8")

    result = validate_config(tmp_path)

    assert not result.is_valid
    assert result.errors == (
        "mevzuat_link.json: 'links' must be a non-empty array",
        "repo_link.json: 'repos' must be a non-empty array",
    )


def test_save_and_load_mevzuat_links(tmp_path):
    config_path = tmp_path / "mevzuat_link.json"

    saved_path = save_mevzuat_links(
        ["https://example.gov.tr/law.pdf", "https://example.gov.tr/other.pdf"],
        config_path,
    )

    assert saved_path == config_path
    assert load_mevzuat_links(config_path) == (
        "https://example.gov.tr/law.pdf",
        "https://example.gov.tr/other.pdf",
    )


def test_save_mevzuat_links_rejects_invalid_url(tmp_path):
    with pytest.raises(ValueError, match=r"links\[0\] must be a valid HTTP\(S\) URL"):
        save_mevzuat_links(["file:///etc/passwd"], tmp_path / "mevzuat_link.json")

    assert not (tmp_path / "mevzuat_link.json").exists()


def test_download_mevzuat_reads_config_and_saves_document(tmp_path):
    response = BytesIO(b"law contents")
    config_path = tmp_path / "mevzuat_link.json"
    save_mevzuat_links(
        ["https://example.gov.tr/files/kanun%20no.pdf?version=1"],
        config_path,
    )

    with patch(
            "mevzuat_agent.tools.download_mevzuat.urlopen",
            return_value=response,
    ):
        result = download_mevzuat(
            tmp_path / "downloads",
            config_path=config_path,
        )

    assert not result.errors
    assert len(result.documents) == 1
    document = result.documents[0]
    assert document.path.name == "001_kanun_no.pdf"
    assert document.path.read_bytes() == b"law contents"
    assert document.size_bytes == len(b"law contents")


def test_download_mevzuat_reports_invalid_url_and_size_limit(tmp_path):
    response = BytesIO(b"too large")
    config_path = tmp_path / "mevzuat_link.json"
    save_mevzuat_links(
        ["https://example.gov.tr/law.pdf"],
        config_path,
    )

    with patch(
            "mevzuat_agent.tools.download_mevzuat.urlopen",
            return_value=response,
    ):
        result = download_mevzuat(
            tmp_path / "downloads",
            config_path=config_path,
            max_bytes=4,
        )

    assert not result.documents
    assert result.errors == ("link 1: response exceeds the 4-byte limit",)


def test_download_mevzuat_does_not_overwrite_existing_files(tmp_path):
    config_path = tmp_path / "mevzuat_link.json"
    save_mevzuat_links(["https://example.gov.tr/law.pdf"], config_path)
    output_dir = tmp_path / "downloads"
    output_dir.mkdir()
    (output_dir / "001_law.pdf").write_text("existing", encoding="utf-8")

    result = download_mevzuat(output_dir, config_path=config_path)

    assert result.errors == ("link 1: destination already exists (001_law.pdf)",)
    assert (output_dir / "001_law.pdf").read_text(encoding="utf-8") == "existing"


def test_build_mevzuat_rag_chunks_pdf_pages_and_preserves_metadata(tmp_path):
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    pdf_path = input_dir / "law.pdf"
    pdf_path.write_bytes(b"%PDF-test")
    page_text = "Madde 1: Veri sorumlusu kişisel verileri korur. " * 25

    class FakePage:
        @staticmethod
        def extract_text():
            return page_text

    class FakeReader:
        pages = [FakePage()]

    with patch(
            "mevzuat_agent.tools.build_mevzuat_rag.PdfReader",
            return_value=FakeReader(),
    ):
        result = build_mevzuat_rag(
            input_dir,
            tmp_path / "rag",
            chunk_size=120,
            chunk_overlap=20,
        )

    assert not result.errors
    assert len(result.chunks) > 1
    assert all(len(chunk.text) <= 120 for chunk in result.chunks)
    assert all(chunk.source == "law.pdf" and chunk.page == 1 for chunk in result.chunks)
    assert result.index_path.is_file()
    manifest = json.loads((tmp_path / "rag" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["chunk_count"] == len(result.chunks)


def test_search_mevzuat_rag_returns_relevant_chunks(tmp_path):
    index_path = tmp_path / "chunks.jsonl"
    index_path.write_text(
        "\n".join(
            json.dumps(chunk, ensure_ascii=False)
            for chunk in (
                {
                    "text": "Veri sorumlusu kişisel verileri hukuka uygun şekilde işler.",
                    "source": "law.pdf",
                    "page": 3,
                    "start_index": 0,
                },
                {
                    "text": "Başvuru süresi ve yetkili mahkeme farklı hükümlerle düzenlenir.",
                    "source": "regulation.pdf",
                    "page": 7,
                    "start_index": 100,
                },
            )
        )
        + "\n",
        encoding="utf-8",
    )

    results = search_mevzuat_rag("kişisel verileri veri sorumlusu", index_path, top_k=1)

    assert len(results) == 1
    assert results[0].chunk.source == "law.pdf"
    assert results[0].chunk.page == 3


def test_build_mevzuat_rag_validates_chunk_sizes(tmp_path):
    with pytest.raises(ValueError, match="chunk_overlap"):
        build_mevzuat_rag(tmp_path, tmp_path / "rag", chunk_size=100, chunk_overlap=100)


def test_clone_repositories_requires_explicit_approval(tmp_path):
    result = clone_repositories(
        tmp_path / "workspace",
        user_approved=False,
        config_path=tmp_path / "missing.json",
    )

    assert not result.checkouts
    assert result.errors == ("User approval is required before cloning repositories",)
    assert not (tmp_path / "workspace").exists()


def test_clone_repositories_reads_config_and_calls_git(tmp_path):
    config_path = tmp_path / "repo_link.json"
    config_path.write_text(
        '{"repos": ["https://github.com/example/sample.git"]}',
        encoding="utf-8",
    )
    workspace = tmp_path / "workspace"
    completed = subprocess.CompletedProcess(args=["git"], returncode=0, stdout="", stderr="")

    with patch("mevzuat_agent.tools.clone_repositories.subprocess.run", return_value=completed) as run:
        result = clone_repositories(
            workspace,
            user_approved=True,
            config_path=config_path,
        )

    assert not result.errors
    assert result.checkouts[0].source_url == "https://github.com/example/sample.git"
    assert result.checkouts[0].path == workspace / "sample"
    run.assert_called_once_with(
        ["git", "clone", "--", "https://github.com/example/sample.git", str(workspace / "sample")],
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )


def test_clone_repositories_rejects_bad_config_before_git_call(tmp_path):
    config_path = tmp_path / "repo_link.json"
    config_path.write_text('{"repos": ["file:///tmp/project"]}', encoding="utf-8")

    with patch("mevzuat_agent.tools.clone_repositories.subprocess.run") as run:
        result = clone_repositories(
            tmp_path / "workspace",
            user_approved=True,
            config_path=config_path,
        )

    assert not result.checkouts
    assert len(result.errors) == 1
    assert result.errors[0].endswith(
        "repo_link.json: 'repos[0]' must be a valid HTTPS or SSH URL"
    )
    run.assert_not_called()


def test_clone_repositories_does_not_overwrite_existing_destination(tmp_path):
    config_path = tmp_path / "repo_link.json"
    config_path.write_text('{"repos": ["git@github.com:example/sample.git"]}', encoding="utf-8")
    workspace = tmp_path / "workspace"
    existing_repo = workspace / "sample"
    existing_repo.mkdir(parents=True)

    with patch("mevzuat_agent.tools.clone_repositories.subprocess.run") as run:
        result = clone_repositories(
            workspace,
            user_approved=True,
            config_path=config_path,
        )

    assert result.errors == ("repo 1: destination already exists (sample)",)
    run.assert_not_called()


def test_estimate_scan_cost_counts_tracked_source_and_rag_context(tmp_path):
    repository = tmp_path / "demo"
    repository.mkdir()
    source_file = repository / "App.java"
    source_file.write_text("class App { String card = \"kart\"; }\n", encoding="utf-8")
    rag_index = tmp_path / "chunks.jsonl"
    rag_index.write_text(
        json.dumps(
            {
                "text": "Banka kartı kuruluşu yükümlülükleri ve kart bilgileri.",
                "source": "law.pdf",
                "page": 4,
                "start_index": 0,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    git_outputs = iter(("main", "abc123", "App.java\0README.md\0"))

    with patch(
            "mevzuat_agent.tools.estimate_scan_cost.run_git_command",
            side_effect=lambda *args: next(git_outputs),
    ):
        result = estimate_scan_cost(
            [repository],
            rag_index_path=rag_index,
            tokens_per_second=10,
            prompt_overhead_tokens_per_file=100,
            output_tokens_per_file=20,
        )

    assert not result.errors
    assert len(result.repositories) == 1
    estimate = result.repositories[0]
    assert estimate.branch_commit == "main@abc123"
    assert estimate.source_file_count == 1
    assert estimate.retrieved_chunk_count == 1
    assert estimate.estimated_input_tokens == (
            (len(source_file.read_text(encoding="utf-8")) + 3) // 4
            + (len("Banka kartı kuruluşu yükümlülükleri ve kart bilgileri.") + 3) // 4
            + 100
    )
    assert estimate.estimated_output_tokens == 20
    assert estimate.estimated_seconds == (estimate.estimated_total_tokens + 9) // 10


def test_estimate_scan_cost_respects_scan_file_limit(tmp_path):
    repository = tmp_path / "demo"
    repository.mkdir()
    (repository / "A.py").write_text("print('a')\n", encoding="utf-8")
    (repository / "B.py").write_text("print('b')\n", encoding="utf-8")
    rag_index = tmp_path / "chunks.jsonl"
    rag_index.write_text(
        json.dumps(
            {"text": "test chunk", "source": "law.pdf", "page": 1, "start_index": 0}
        )
        + "\n",
        encoding="utf-8",
    )
    git_outputs = iter(("main", "abc123", "A.py\0B.py\0"))

    with patch(
            "mevzuat_agent.tools.estimate_scan_cost.run_git_command",
            side_effect=lambda *args: next(git_outputs),
    ):
        result = estimate_scan_cost(
            [repository],
            rag_index_path=rag_index,
            max_files=1,
        )

    assert not result.errors
    assert result.repositories[0].source_file_count == 1
    assert result.repositories[0].skipped_file_count == 1


def test_estimate_scan_cost_reports_missing_rag_index(tmp_path):
    result = estimate_scan_cost(
        [tmp_path / "repo"],
        rag_index_path=tmp_path / "missing.jsonl",
    )

    assert not result.repositories
    assert result.errors == (f"{tmp_path / 'missing.jsonl'}: mevzuat RAG index not found",)


def test_estimate_scan_cost_rejects_non_positive_rate():
    with pytest.raises(ValueError, match="tokens_per_second"):
        estimate_scan_cost([], tokens_per_second=0)


def test_model_pool_estimate_recommends_fastest_installed_model(tmp_path):
    scan = ScanCostEstimate(
        model="llama3.2:1b",
        tokens_per_second_assumption=1,
        repositories=(
            RepositoryScanEstimate(
                repository="demo1",
                branch_commit="main@abc123",
                source_file_count=1,
                skipped_file_count=0,
                retrieved_chunk_count=1,
                estimated_input_tokens=900,
                estimated_output_tokens=100,
                estimated_total_tokens=1000,
                estimated_seconds=1000,
            ),
        ),
        errors=(),
    )

    with (
        patch(
            "mevzuat_agent.tools.estimate_scan_cost.estimate_scan_cost",
            return_value=scan,
        ),
        patch(
            "mevzuat_agent.tools.estimate_scan_cost.list_ollama_models",
            return_value=("gemma3:4b", "llama3.2:1b", "qwen3:4b"),
        ),
        patch(
            "mevzuat_agent.tools.estimate_scan_cost.benchmark_ollama_model",
            side_effect=(8.0, 20.0, 5.0),
        ) as benchmark,
    ):
        result = estimate_scan_cost_for_model_pool(
            ["demo1"],
        )

    assert result.recommended_model == "llama3.2:1b"
    assert [estimate.model for estimate in result.models] == [
        "llama3.2:1b",
        "gemma3:4b",
        "qwen3:4b",
    ]
    assert result.models[0].estimated_seconds < result.models[1].estimated_seconds
    assert benchmark.call_count == 3


def test_benchmark_ollama_model_uses_server_token_metrics():
    response = BytesIO(
        json.dumps({"eval_count": 24, "eval_duration": 2_000_000_000}).encode("utf-8")
    )
    with patch(
            "mevzuat_agent.tools.estimate_scan_cost.urlopen",
            return_value=response,
    ):
        speed = benchmark_ollama_model("llama3.2:1b")

    assert speed == 12.0


def test_benchmark_ollama_model_fails_if_metrics_are_missing():
    response = BytesIO(json.dumps({"response": "ok"}).encode("utf-8"))
    with (
        patch(
            "mevzuat_agent.tools.estimate_scan_cost.urlopen",
            return_value=response,
        ),
        pytest.raises(ValueError, match="valid token speed metrics"),
    ):
        benchmark_ollama_model("llama3.2:1b")


def test_scan_finding_is_accepted_only_with_code_and_mevzuat_evidence():
    response = {
        "findings": [
            {
                "severity": "HIGH",
                "title": "Unprotected card data",
                "line": 2,
                "evidence": 'var card = "4111111111111111";',
                "explanation": "Potential card data exposure.",
                "mevzuat_source": "law.pdf",
                "mevzuat_page": 4,
                "recommendation": "Review card data handling.",
                "confidence": 8,
            }
        ]
    }
    context = [{"source": "law.pdf", "page": 4, "text": "Card data protection"}]

    findings = validate_scan_findings(
        response,
        "Payments.cs",
        'class Payments {\nvar card = "4111111111111111";\n}',
        context,
    )

    assert len(findings) == 1
    assert findings[0].file == "Payments.cs"
    assert findings[0].line == 2


def test_scan_finding_rejects_unverified_code_quote():
    response = {
        "findings": [
            {
                "severity": "HIGH",
                "title": "Fabricated evidence",
                "line": 1,
                "evidence": "not in source",
                "explanation": "Claim without source proof.",
                "mevzuat_source": "law.pdf",
                "mevzuat_page": 4,
                "recommendation": "Review.",
                "confidence": 9,
            }
        ]
    }

    with pytest.raises(ValueError, match="evidence does not match"):
        validate_scan_findings(
            response,
            "Payments.cs",
            "class Payments {}",
            [{"source": "law.pdf", "page": 4, "text": "Relevant law"}],
        )


def test_scan_repository_limits_files_and_persists_result(tmp_path):
    repository = tmp_path / "demo1"
    repository.mkdir()
    (repository / "Controller.cs").write_text(
        "class Controller { void Run() {} }",
        encoding="utf-8",
    )
    index_path = tmp_path / "chunks.jsonl"
    index_path.write_text("placeholder\n", encoding="utf-8")
    output_path = tmp_path / "scan.json"
    git_outputs = iter(("master", "abc123", "Controller.cs\0README.md\0"))
    chunk = SimpleNamespace(source="law.pdf", page=2, text="Relevant mevzuat excerpt.")

    with (
        patch(
            "mevzuat_agent.tools.scan_repository.run_git_command",
            side_effect=lambda *args: next(git_outputs),
        ),
        patch(
            "mevzuat_agent.tools.scan_repository.search_mevzuat_rag",
            return_value=(SimpleNamespace(chunk=chunk),),
        ),
        patch(
            "mevzuat_agent.tools.scan_repository._ask_ollama",
            return_value='{"findings":[]}',
        ) as ask,
    ):
        result = scan_repository(
            repository,
            max_files=1,
            rag_index_path=index_path,
            output_path=output_path,
        )

    assert result.branch_commit == "master@abc123"
    assert result.files_considered == 1
    assert result.files_scanned == 1
    assert result.model == "llama3.2:1b"
    assert output_path.is_file()
    ask.assert_called_once()


def test_generate_scan_report_creates_markdown_and_escaped_html(tmp_path):
    result_path = tmp_path / "scan.json"
    result_path.write_text(
        json.dumps(
            {
                "repository": "demo1",
                "branch_commit": "master@abc123",
                "model": "llama3.2:1b",
                "scan_scope": "ilk 1 dosya",
                "scanned_at": "2026-10-29T11:00:00+00:00",
                "files_scanned": 1,
                "files_considered": 59,
                "findings": [
                    {
                        "severity": "HIGH",
                        "title": "<script>alert(1)</script>",
                        "file": "src/App.cs",
                        "line": 12,
                        "confidence": 8,
                        "mevzuat_source": "law.pdf",
                        "mevzuat_page": 4,
                        "explanation": "Kanıt <eksik> olabilir.",
                        "recommendation": "Değerlendir.",
                        "evidence": "var x = \"<unsafe>\";",
                    }
                ],
                "file_results": [
                    {
                        "path": "src/App.cs",
                        "status": "scanned",
                        "findings": [],
                        "error": None,
                    }
                ],
                "limitations": ["Kısmi tarama"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    markdown_path, html_path = generate_scan_report(result_path)

    markdown = markdown_path.read_text(encoding="utf-8")
    html_report = html_path.read_text(encoding="utf-8")
    assert "Doğrulanmış bulgu:** 1" in markdown
    assert "<script>" in markdown
    assert "&lt;script&gt;" in html_report
    assert "<script>alert(1)</script>" not in html_report
    assert "Kısmi tarama" in markdown


def test_generate_scan_report_warns_when_no_findings(tmp_path):
    result_path = tmp_path / "empty.json"
    result_path.write_text(
        json.dumps(
            {
                "repository": "demo1",
                "branch_commit": "master@abc123",
                "model": "llama3.2:1b",
                "scan_scope": "ilk 1 dosya",
                "findings": [],
                "file_results": [],
                "limitations": [
                    "Partial scan: selected 1 of 59 tracked source files.",
                    "One or more model findings failed evidence validation and were excluded.",
                ],
            }
        ),
        encoding="utf-8",
    )

    markdown_path, html_path = generate_scan_report(result_path)

    assert "kodun mevzuata uygun olduğunu kanıtlamaz" in markdown_path.read_text(
        encoding="utf-8"
    )
    assert "kodun mevzuata uygun olduğunu kanıtlamaz" in html_path.read_text(
        encoding="utf-8"
    )
    assert "Kısmi tarama" in markdown_path.read_text(encoding="utf-8")
    assert "Partial scan" not in markdown_path.read_text(encoding="utf-8")


def test_prepare_remediation_plan_selects_top_two_findings(tmp_path):
    scan_path = tmp_path / "scan.json"
    findings = [
        {
            "severity": "LOW",
            "title": "Low",
            "file": "src/Low.cs",
            "line": 1,
            "confidence": 10,
            "recommendation": "Review low",
            "evidence": "low evidence",
        },
        {
            "severity": "HIGH",
            "title": "High with lower confidence",
            "file": "src/High.cs",
            "line": 2,
            "confidence": 6,
            "recommendation": "Review high",
            "evidence": "high evidence",
        },
        {
            "severity": "HIGH",
            "title": "High with higher confidence",
            "file": "src/High2.cs",
            "line": 3,
            "confidence": 9,
            "recommendation": "Review high2",
            "evidence": "high evidence 2",
        },
    ]
    scan_path.write_text(
        json.dumps(
            {
                "repository": "demo1",
                "branch_commit": "master@abc123",
                "model": "llama3.2:1b",
                "findings": findings,
            }
        ),
        encoding="utf-8",
    )

    plan_path = prepare_remediation_plan(scan_path)
    plan = plan_path.read_text(encoding="utf-8")

    assert "High with higher confidence" in plan
    assert "High with lower confidence" in plan
    assert "## 3." not in plan
    assert "LOW" not in plan
    assert "kullanıcı onayı gerekir" in plan


def test_prepare_remediation_plan_stops_when_no_verified_findings(tmp_path):
    scan_path = tmp_path / "scan.json"
    scan_path.write_text('{"findings": []}', encoding="utf-8")

    with pytest.raises(ValueError, match="Doğrulanmış bulgu yok"):
        prepare_remediation_plan(scan_path)


def test_prepare_remediation_plan_rejects_invalid_finding(tmp_path):
    scan_path = tmp_path / "scan.json"
    scan_path.write_text(
        json.dumps({"findings": [{"severity": "UNKNOWN"}]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="önem seviyesi geçersiz"):
        prepare_remediation_plan(scan_path)


def test_apply_remediation_requires_explicit_approval(tmp_path):
    with pytest.raises(PermissionError, match="açık kullanıcı onayı"):
        apply_remediation(
            tmp_path / "repo",
            tmp_path / "scan.json",
            {"payment_rules.py": "return True\n"},
            user_approved=False,
        )


def test_apply_remediation_creates_isolated_worktree_and_reports_diff(tmp_path):
    repository = tmp_path / "repo"
    repository.mkdir()
    _run_git(repository, "init", "-b", "main")
    _run_git(repository, "config", "user.name", "Test")
    _run_git(repository, "config", "user.email", "test@example.com")
    (repository / "first.py").write_text("def first():\n    return False\n", encoding="utf-8")
    (repository / "second.py").write_text("def second():\n    return 0\n", encoding="utf-8")
    _run_git(repository, "add", "first.py", "second.py")
    _run_git(repository, "commit", "-m", "Add test sources")
    scan_path = tmp_path / "scan.json"
    scan_path.write_text(
        json.dumps(
            {
                "findings": [
                    {
                        "severity": "HIGH",
                        "confidence": 10,
                        "file": "first.py",
                        "line": 2,
                        "evidence": "    return False",
                        "mevzuat_source": "TEST_FIXTURE_NOT_LAW",
                    },
                    {
                        "severity": "MEDIUM",
                        "confidence": 9,
                        "file": "first.py",
                        "line": 2,
                        "evidence": "    return False",
                        "mevzuat_source": "TEST_FIXTURE_NOT_LAW",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    result = apply_remediation(
        repository,
        scan_path,
        {
            "first.py": "def first():\n    return True\n",
        },
        user_approved=True,
    )

    assert result.worktree_path.is_dir()
    assert result.branch.startswith("mevzuatagent/remediation-")
    assert (repository / "first.py").read_text(encoding="utf-8").endswith("False\n")
    assert (result.worktree_path / "first.py").read_text(encoding="utf-8").endswith("True\n")
    assert "return False" in result.diff
    assert "return True" in result.diff
    assert result.markdown_path.is_file()
    assert result.html_path.is_file()
    assert "YALNIZCA TEST İÇİNDİR" in result.markdown_path.read_text(encoding="utf-8")
    assert "YALNIZCA TEST İÇİNDİR" in result.html_path.read_text(encoding="utf-8")
    assert "&lt;" not in result.html_path.read_text(encoding="utf-8")
    assert _run_git(result.worktree_path, "branch", "--show-current") == result.branch
    test_path = result.worktree_path / "test_validation.py"
    test_path.write_text("def test_example():\n    assert 2 + 2 == 4\n", encoding="utf-8")

    test_result = validate_remediation(result.worktree_path, user_approved=True)

    assert test_result.status == "passed"
    assert test_result.return_code == 0
    assert test_result.markdown_path.is_file()
    assert test_result.html_path.is_file()
    assert "passed" in test_result.markdown_path.read_text(encoding="utf-8")

    test_path.write_text("def test_example():\n    assert 2 + 2 == 5\n", encoding="utf-8")
    failed_result = validate_remediation(result.worktree_path, user_approved=True)

    assert failed_result.status == "failed"
    assert failed_result.return_code != 0
    assert "failed" in failed_result.markdown_path.read_text(encoding="utf-8")


def test_validate_remediation_requires_approval_and_fixed_runner(tmp_path):
    with pytest.raises(PermissionError, match="açık kullanıcı onayı"):
        validate_remediation(tmp_path / "missing", user_approved=False)

    with pytest.raises(ValueError, match="Desteklenmeyen test aracı"):
        validate_remediation(
            tmp_path / "missing",
            user_approved=True,
            runner="arbitrary",  # type: ignore[arg-type]
        )


def test_validate_remediation_builds_fixed_dotnet_and_maven_commands(tmp_path):
    with patch("mevzuat_agent.tools.validate_remediation.shutil.which", return_value="/usr/bin/dotnet"):
        (tmp_path / "Demo.sln").write_text("", encoding="utf-8")
        assert _test_command("dotnet", tmp_path) == ("/usr/bin/dotnet", "test")

    with patch("mevzuat_agent.tools.validate_remediation.shutil.which", return_value="/usr/bin/mvn"):
        (tmp_path / "pom.xml").write_text("<project/>", encoding="utf-8")
        assert _test_command("maven", tmp_path) == ("/usr/bin/mvn", "test")


def test_propose_remediation_returns_only_verified_top_finding_files(tmp_path):
    repository = tmp_path / "repo"
    repository.mkdir()
    source = "def check():\n    return False\n"
    (repository / "rules.py").write_text(source, encoding="utf-8")
    scan_path = tmp_path / "scan.json"
    scan_path.write_text(
        json.dumps(
            {
                "findings": [
                    {
                        "severity": "HIGH",
                        "confidence": 10,
                        "file": "rules.py",
                        "line": 2,
                        "evidence": "    return False",
                        "title": "Sentetik test bulgusu",
                        "recommendation": "Test için True döndür.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    response = BytesIO(
        json.dumps(
            {
                "message": {
                    "content": json.dumps(
                        {
                            "changes": [
                                {
                                    "path": "rules.py",
                                    "content": "def check():\n    return True\n",
                                }
                            ]
                        }
                    )
                }
            }
        ).encode()
    )

    with patch("mevzuat_agent.tools.propose_remediation.urlopen", return_value=response):
        changes = propose_remediation(repository, scan_path, model="test-model")

    assert tuple(changes) == ("rules.py",)
    assert "return True" in changes["rules.py"]


def test_create_github_pr_requires_approval_and_passing_tests(tmp_path):
    from mevzuat_agent.tools.validate_remediation import RemediationTestResult

    test_result = RemediationTestResult(
        tmp_path,
        "mevzuatagent/remediation-test",
        "pytest",
        (),
        "failed",
        1,
        "failed",
        tmp_path / "tests.md",
        tmp_path / "tests.html",
    )
    with pytest.raises(PermissionError, match="açık kullanıcı onayı"):
        create_github_pr(
            tmp_path,
            test_result,
            ["rules.py"],
            user_approved=False,
            title="Fix",
            body="Details",
        )
    with pytest.raises(ValueError, match="Başarılı test raporu"):
        create_github_pr(
            tmp_path,
            test_result,
            ["rules.py"],
            user_approved=True,
            title="Fix",
            body="Details",
        )


def test_create_github_pr_pushes_only_tested_remediation_file(tmp_path):
    from mevzuat_agent.tools.validate_remediation import RemediationTestResult

    repository = tmp_path / "repo"
    repository.mkdir()
    _run_git(repository, "init", "-b", "main")
    _run_git(repository, "config", "user.name", "Test")
    _run_git(repository, "config", "user.email", "test@example.com")
    source = repository / "rules.py"
    source.write_text("def check():\n    return False\n", encoding="utf-8")
    _run_git(repository, "add", "rules.py")
    _run_git(repository, "commit", "-m", "Add source")
    remote = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    _run_git(repository, "remote", "add", "origin", str(remote))
    _run_git(repository, "push", "--set-upstream", "origin", "main")
    _run_git(repository, "remote", "set-head", "origin", "main")
    scan_path = tmp_path / "scan.json"
    scan_path.write_text(
        json.dumps(
            {
                "findings": [
                    {
                        "severity": "HIGH",
                        "confidence": 10,
                        "file": "rules.py",
                        "line": 2,
                        "evidence": "    return False",
                    },
                    {
                        "severity": "MEDIUM",
                        "confidence": 9,
                        "file": "rules.py",
                        "line": 2,
                        "evidence": "    return False",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    application = apply_remediation(
        repository,
        scan_path,
        {"rules.py": "def check():\n    return True\n"},
        user_approved=True,
    )
    test_result = RemediationTestResult(
        application.worktree_path,
        application.branch,
        "pytest",
        (),
        "passed",
        0,
        "1 passed",
        tmp_path / "tests.md",
        tmp_path / "tests.html",
    )
    real_run = subprocess.run

    def run_with_fake_gh(command, *args, **kwargs):
        if command[0] == "gh":
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="https://github.com/example/repo/pull/42\n",
                stderr="",
            )
        return real_run(command, *args, **kwargs)

    with patch("mevzuat_agent.tools.create_github_pr.subprocess.run", side_effect=run_with_fake_gh):
        pr = create_github_pr(
            application.worktree_path,
            test_result,
            ["rules.py"],
            user_approved=True,
            title="Fix synthetic test issue",
            body="Validated against synthetic fixture.",
            base_branch="main",
        )

    assert pr.url == "https://github.com/example/repo/pull/42"
    assert pr.branch == application.branch
    pushed = subprocess.run(
        ["git", "--git-dir", str(remote), "branch", "--list", application.branch],
        check=True,
        capture_output=True,
        text=True,
    )
    assert application.branch in pushed.stdout
    commit_message = _run_git(application.worktree_path, "log", "-1", "--format=%B")
    assert "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>" in commit_message


def test_apply_remediation_rejects_dirty_repository_and_unrelated_paths(tmp_path):
    repository = tmp_path / "repo"
    repository.mkdir()
    _run_git(repository, "init", "-b", "main")
    (repository / "source.py").write_text("return False\n", encoding="utf-8")
    _run_git(repository, "add", "source.py")
    _run_git(repository, "config", "user.name", "Test")
    _run_git(repository, "config", "user.email", "test@example.com")
    _run_git(repository, "commit", "-m", "Add source")
    (repository / "source.py").write_text("return True\n", encoding="utf-8")
    scan_path = tmp_path / "scan.json"
    scan_path.write_text(
        json.dumps(
            {
                "findings": [
                    {
                        "severity": "HIGH",
                        "confidence": 10,
                        "file": "source.py",
                        "line": 1,
                        "evidence": "return False",
                    },
                    {
                        "severity": "MEDIUM",
                        "confidence": 8,
                        "file": "source.py",
                        "line": 1,
                        "evidence": "return False",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="temiz olmalı"):
        apply_remediation(
            repository,
            scan_path,
            {"source.py": "return False\n"},
            user_approved=True,
        )

    _run_git(repository, "add", "source.py")
    _run_git(repository, "commit", "-m", "Update dirty source")
    scan_path.write_text(
        json.dumps(
            {
                "findings": [
                    {
                        "severity": "HIGH",
                        "confidence": 10,
                        "file": "../outside.py",
                        "line": 1,
                        "evidence": "return False",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Güvenli olmayan göreli dosya yolu"):
        apply_remediation(
            repository,
            scan_path,
            {"outside.py": "return True\n"},
            user_approved=True,
        )


def _run_git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_synthetic_demo_repositories_have_ten_verified_fixable_findings(tmp_path):
    fixture_root = Path(__file__).parents[1] / "data" / "test_repositories"
    total_findings = 0

    for demo_name in ("demo1", "demo2"):
        demo_path = fixture_root / demo_name
        scan_path = demo_path / "scan_result.json"
        result = json.loads(scan_path.read_text(encoding="utf-8"))
        source_code = (demo_path / "payment_rules.py").read_text(encoding="utf-8")

        assert len(result["findings"]) == 5
        assert all(
            finding["mevzuat_source"] == "TEST_FIXTURE_NOT_LAW"
            for finding in result["findings"]
        )
        validated = validate_scan_findings(
            {"findings": result["findings"]},
            "payment_rules.py",
            source_code,
            [{"source": "TEST_FIXTURE_NOT_LAW", "page": 1, "text": "synthetic"}],
        )
        assert len(validated) == 5

        plan_path = prepare_remediation_plan(
            scan_path,
            output_path=tmp_path / f"{demo_name}_plan.md",
        )
        plan = plan_path.read_text(encoding="utf-8")
        assert "TEST_FIXTURE_NOT_LAW" in plan
        assert "kullanıcı onayı gerekir" in plan
        total_findings += len(validated)

    assert total_findings == 10


def test_langchain_scan_workflow_requires_approval_and_generates_artifacts(tmp_path):
    repository = tmp_path / "demo"
    repository.mkdir()
    _run_git(repository, "init", "-b", "main")
    _run_git(repository, "config", "user.name", "Test")
    _run_git(repository, "config", "user.email", "test@example.com")
    source_path = repository / "payment.py"
    source_path.write_text("def can_pay():\n    return True\n", encoding="utf-8")
    _run_git(repository, "add", "payment.py")
    _run_git(repository, "commit", "-m", "Add source")
    rag_index = tmp_path / "chunks.jsonl"
    rag_index.write_text("{}\n", encoding="utf-8")
    output_dir = tmp_path / "reports"
    pool = _workflow_test_pool(repository)
    observed = {}

    def estimate(paths, **options):
        assert paths == (repository.resolve(),)
        assert options["max_files"] == 2
        return pool

    def approve(request):
        observed["request"] = request
        return "slower-model"

    def scan(path, **options):
        observed["scan_options"] = options
        output_path = options["output_path"]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(
                {
                    "repository": path.name,
                    "branch_commit": pool.scan.repositories[0].branch_commit,
                    "model": options["model"],
                    "scan_scope": "test scan",
                    "scanned_at": "2026-10-29T00:00:00+00:00",
                    "files_scanned": 1,
                    "files_considered": 1,
                    "findings": [
                        {
                            "severity": "HIGH",
                            "title": "Synthetic issue",
                            "file": "payment.py",
                            "line": 2,
                            "evidence": "    return True",
                            "explanation": "Test finding.",
                            "mevzuat_source": "TEST_FIXTURE_NOT_LAW",
                            "mevzuat_page": 1,
                            "recommendation": "Change the return value.",
                            "confidence": 10,
                        }
                    ],
                    "file_results": [],
                    "limitations": ["Synthetic fixture only."],
                }
            ),
            encoding="utf-8",
        )
        return RepositoryScanResult(
            repository=path.name,
            branch_commit=pool.scan.repositories[0].branch_commit,
            model=options["model"],
            scan_scope="test scan",
            scanned_at="2026-10-29T00:00:00+00:00",
            files_considered=1,
            files_scanned=1,
            findings=(
                ScanFinding(
                    severity="HIGH",
                    title="Synthetic issue",
                    file="payment.py",
                    line=2,
                    evidence="    return True",
                    explanation="Test finding.",
                    mevzuat_source="TEST_FIXTURE_NOT_LAW",
                    mevzuat_page=1,
                    recommendation="Change the return value.",
                    confidence=10,
                ),
            ),
            file_results=(),
            limitations=("Synthetic fixture only.",),
            output_path=output_path,
        )

    workflow = build_scan_workflow(
        approve,
        estimate_function=estimate,
        scan_function=scan,
    )
    result = workflow.invoke(
        {
            "repository_paths": [repository],
            "max_files": 2,
            "rag_index_path": rag_index,
            "output_dir": output_dir,
        }
    )

    assert result.status == "completed"
    assert result.selected_model == "slower-model"
    assert observed["request"].recommended_model == "fast-model"
    assert "MevzuatAgent" in observed["request"].system_prompt
    assert observed["scan_options"]["model"] == "slower-model"
    artifacts = result.repositories[0]
    assert artifacts.markdown_report.is_file()
    assert artifacts.html_report.is_file()
    assert artifacts.remediation_plan.is_file()


def test_langchain_scan_workflow_does_not_scan_when_user_declines(tmp_path):
    repository = tmp_path / "demo"
    repository.mkdir()
    _run_git(repository, "init", "-b", "main")
    _run_git(repository, "config", "user.name", "Test")
    _run_git(repository, "config", "user.email", "test@example.com")
    (repository / "source.py").write_text("print('test')\n", encoding="utf-8")
    _run_git(repository, "add", "source.py")
    _run_git(repository, "commit", "-m", "Add source")
    rag_index = tmp_path / "chunks.jsonl"
    rag_index.write_text("{}\n", encoding="utf-8")

    def unexpected_scan(
            repository_path,
            *,
            max_files,
            rag_index_path,
            model,
            output_path,
    ):
            pytest.fail(
                "Tarama onay reddedildiğinde tarama aracı çağrılmamalı: "
                f"{repository_path}, {max_files}, {rag_index_path}, {model}, {output_path}"
            )

    workflow = build_scan_workflow(
        lambda request: None,
        estimate_function=lambda *args, **kwargs: _workflow_test_pool(repository),
        scan_function=unexpected_scan,
    )
    result = workflow.invoke(
        {
            "repository_paths": [repository],
            "max_files": 1,
            "rag_index_path": rag_index,
            "output_dir": tmp_path / "reports",
        }
    )

    assert result.status == "scan_declined"
    assert result.selected_model is None
    assert result.repositories == ()


def test_scan_result_offers_remediation_with_repository_and_scan_path(tmp_path, monkeypatch):
    repository = tmp_path / "demo"
    scan_path = tmp_path / "scan.json"
    scan = RepositoryScanResult(
        repository="demo",
        branch_commit="main@abc123",
        model="test-model",
        scan_scope="test",
        scanned_at="2026-10-29T00:00:00+00:00",
        files_considered=1,
        files_scanned=1,
        findings=(
            ScanFinding(
                severity="HIGH",
                title="Synthetic issue",
                file="source.py",
                line=1,
                evidence="pass",
                explanation="Test finding.",
                mevzuat_source="TEST_FIXTURE_NOT_LAW",
                mevzuat_page=1,
                recommendation="Review.",
                confidence=10,
            ),
        ),
        file_results=(),
        limitations=(),
        output_path=scan_path,
    )
    artifact = RepositoryScanArtifacts(
        scan=scan,
        markdown_report=tmp_path / "scan.md",
        html_report=tmp_path / "scan.html",
        remediation_plan=None,
    )
    observed = {}
    monkeypatch.setattr(console, "_ask_yes", lambda question: True)
    monkeypatch.setattr(
        console,
        "_remediate_and_pr",
        lambda repo, path: observed.update(repository=repo, scan_path=path),
    )

    console._offer_remediation(repository, artifact)

    assert observed == {"repository": repository, "scan_path": scan_path}


def test_scan_result_without_findings_explains_model_error_and_skips_remediation(
    tmp_path, monkeypatch, capsys
):
    scan = RepositoryScanResult(
        repository="demo",
        branch_commit="main@abc123",
        model="test-model",
        scan_scope="test",
        scanned_at="2026-10-29T00:00:00+00:00",
        files_considered=1,
        files_scanned=0,
        findings=(),
        file_results=(
            ScannedFile(
                path="broken.py",
                status="error",
                findings=(),
                error="Invalid JSON response",
            ),
        ),
        limitations=(),
        output_path=tmp_path / "scan.json",
    )
    artifact = RepositoryScanArtifacts(
        scan=scan,
        markdown_report=tmp_path / "scan.md",
        html_report=tmp_path / "scan.html",
        remediation_plan=None,
    )
    monkeypatch.setattr(
        console,
        "_remediate_and_pr",
        lambda *args: pytest.fail("Bulgu yokken remediation başlatılmamalı."),
    )

    console._offer_remediation(tmp_path / "demo", artifact)

    output = capsys.readouterr().out
    assert "remediation başlatılamaz" in output
    assert "Invalid JSON response" in output
    assert "başka bir model" in output


def test_remediation_stops_when_scan_has_no_findings(tmp_path, monkeypatch, capsys):
    scan_path = tmp_path / "scan.json"
    scan_path.write_text(
        json.dumps({"findings": [], "file_results": []}),
        encoding="utf-8",
    )
    with patch(
        "mevzuat_agent.console.propose_remediation",
        side_effect=AssertionError("Bulgu yokken model çağrılmamalı."),
    ) as propose:
        console._remediate_and_pr(tmp_path, scan_path)

    propose.assert_not_called()
    assert "doğrulanmış bulgu olmadığından" in capsys.readouterr().out


def _workflow_test_pool(repository: Path) -> ModelPoolEstimate:
    branch = _run_git(repository, "rev-parse", "--abbrev-ref", "HEAD")
    commit = _run_git(repository, "rev-parse", "--short", "HEAD")
    scan = ScanCostEstimate(
        model="estimate",
        tokens_per_second_assumption=1,
        repositories=(
            RepositoryScanEstimate(
                repository=str(repository.resolve()),
                branch_commit=f"{branch}@{commit}",
                source_file_count=1,
                skipped_file_count=0,
                retrieved_chunk_count=1,
                estimated_input_tokens=100,
                estimated_output_tokens=20,
                estimated_total_tokens=120,
                estimated_seconds=120,
            ),
        ),
        errors=(),
    )
    return ModelPoolEstimate(
        scan=scan,
        models=(
            ModelEstimate("fast-model", 100.0, 120, 2),
            ModelEstimate("slower-model", 20.0, 120, 6),
        ),
        recommended_model="fast-model",
        errors=(),
    )
