"""Kullanıcıyı onay kapılı MevzuatAgent işlemlerinde yönlendirir."""

import difflib
import json
from pathlib import Path

from mevzuat_agent.tools.apply_remediation import apply_remediation
from mevzuat_agent.tools.build_mevzuat_rag import build_mevzuat_rag
from mevzuat_agent.tools.clone_repositories import clone_repositories
from mevzuat_agent.tools.create_github_pr import create_github_pr
from mevzuat_agent.tools.download_mevzuat import download_mevzuat
from mevzuat_agent.tools.estimate_scan_cost import is_source_file
from mevzuat_agent.tools.propose_remediation import propose_remediation
from mevzuat_agent.tools.scan_repository import run_git_command
from mevzuat_agent.tools.validate_config import validate_config
from mevzuat_agent.tools.validate_remediation import TestRunner, validate_remediation
from mevzuat_agent.workflows.scan import (
    RepositoryScanArtifacts,
    ScanApprovalRequest,
    run_scan_workflow,
)


_ROOT = Path(__file__).resolve().parents[2]


def run_console() -> None:
    """Ana menüyü gösterip onaylı kullanıcı işlemlerini çalıştırır."""
    print("MevzuatAgent | Mevzuat uyumluluğu kod tarama aracı")
    print("Raporlar otomatik karar değildir; mevzuat uzmanı tarafından doğrulanmalıdır.\n")
    while True:
        print(
            "\n"
            "1. Mevzuat belgelerini indir ve RAG indeksini hazırla\n"
            "2. repo_link.json depolarını klonla\n"
            "3. Yerel depoda tarama/tahmin yap\n"
            "4. Bulgu düzelt, test et ve onayla PR aç\n"
            "5. Yapılandırmaları kontrol et\n"
            "0. Çıkış"
        )
        choice = input("Seçiminiz: ").strip()
        try:
            if choice == "1":
                _prepare_legislation()
            elif choice == "2":
                _clone_repositories()
            elif choice == "3":
                _scan_repository()
            elif choice == "4":
                _remediate_and_pr()
            elif choice == "5":
                _show_config()
            elif choice == "0":
                print("MevzuatAgent kapatıldı.")
                return
            else:
                print("Geçersiz seçim. Menüdeki numaralardan birini girin.")
        except (OSError, ValueError, RuntimeError, PermissionError) as exc:
            print(f"İşlem tamamlanamadı: {exc}")


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
    rag_index = _ROOT / "data/legislation/rag/chunks.jsonl"
    if not rag_index.is_file():
        raise FileNotFoundError(f"RAG indeksi bulunamadı: {rag_index}. Önce 1. adımı çalıştırın.")
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


def _offer_remediation(repository: Path, artifact: RepositoryScanArtifacts) -> None:
    if artifact.scan.findings:
        if _ask_yes(
            f"{len(artifact.scan.findings)} doğrulanmış bulgu var. "
            "Remediation adımına şimdi geçilsin mi?"
        ):
            _remediate_and_pr(repository, artifact.scan.output_path)
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
            "Model yanıtı hatalı veya boşsa 3. menüden taramayı yeniden "
            "başlatıp başka bir model seçin."
        )
    else:
        print(
            "Doğrulanmış bulgu bulunmadı; remediation için önce "
            "kanıtlanmış bulgu içeren bir tarama gerekir."
        )


def _remediate_and_pr(
    repository_path: Path | None = None,
    scan_result_path: Path | None = None,
) -> None:
    if (repository_path is None) != (scan_result_path is None):
        raise ValueError("Depo ve tarama sonucu birlikte sağlanmalı.")
    repository = repository_path or _prompt_path("Git deposunun kök dizini")
    scan_path = scan_result_path or _prompt_path("Tarama JSON dosyası")
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
        reports_dir=_ROOT / "data/reports/remediation",
    )
    print(f"İzole dal: {application.branch}")
    print(f"Worktree: {application.worktree_path}")
    print(f"Diff raporu: {application.markdown_path}")
    print(f"Diff HTML: {application.html_path}")
    if not _ask_yes("Bu worktree içindeki testleri çalıştırmayı onaylıyor musunuz?"):
        print("Test çalıştırılmadı; PR açılamaz.")
        return

    runner = _select_test_runner(application.worktree_path)
    if runner is None:
        print("Bu depoda desteklenen test projesi tanınmadı; PR açılamaz.")
        return
    test_result = validate_remediation(
        application.worktree_path,
        user_approved=True,
        runner=runner,
        reports_dir=_ROOT / "data/reports/remediation",
    )
    print(f"Test durumu: {test_result.status}")
    print(f"Test raporu: {test_result.markdown_path}")
    print(f"Test HTML: {test_result.html_path}")
    if test_result.status != "passed":
        print("Testler başarıyla tamamlanmadı; PR açılmadı.")
        return

    if not _ask_yes(
        "Test raporunu ve kod farkını incelediniz mi? Değişikliği GitHub'a gönderip PR açalım mı?"
    ):
        print("GitHub'a push yapılmadı ve PR açılmadı.")
        return
    findings = _top_findings(scan_result.get("findings", []))
    title = "MevzuatAgent: " + (findings[0].get("title", "onaylı düzeltme")[:60])
    body = "\n".join(
        [
            "## Özet",
            "MevzuatAgent tarafından kullanıcı onayıyla hazırlanan düzeltme.",
            "",
            "## Sentetik veri uyarısı",
            "Bu tarama `TEST_FIXTURE_NOT_LAW` içeriyorsa sentetik testtir; hukukî tespit değildir.",
            "",
            "## Doğrulama",
            f"- Test sonucu: `{test_result.status}`",
            f"- Test raporu (yerel): `{test_result.markdown_path}`",
            f"- Düzeltme diff'i: `{application.markdown_path}`",
        ]
    )
    base = input("Hedef GitHub dalı (boşsa origin varsayılan dalı): ").strip() or None
    pull_request = create_github_pr(
        application.worktree_path,
        test_result,
        tuple(changes),
        user_approved=True,
        title=title,
        body=body,
        base_branch=base,
    )
    print(f"PR oluşturuldu: {pull_request.url}")


def _select_repository() -> Path | None:
    candidates = []
    for parent in (_ROOT / "data/repositories", _ROOT / "data/test_repositories"):
        if parent.is_dir():
            candidates.extend(
                path
                for path in sorted(parent.iterdir())
                if path.is_dir() and (path / ".git").exists()
            )
    if not candidates:
        print("Yerel Git deposu bulunamadı. Önce depoyu klonlayın.")
        return None
    print("Yerel depolar:")
    for index, path in enumerate(candidates, start=1):
        print(f"{index}. {path.relative_to(_ROOT)}")
    try:
        selection = int(input("Depo numarası: ").strip())
    except ValueError as exc:
        raise ValueError("Listeden geçerli bir depo numarası girin.") from exc
    if selection > len(candidates):
        raise ValueError("Depo numarası listede yok.")
    if selection <= 0:
        raise ValueError("Listeden geçerli bir depo numarası girin.")
    return candidates[selection - 1]


def _prompt_path(label: str) -> Path:
    value = input(f"{label}: ").strip()
    if not value:
        raise ValueError("Yol boş bırakılamaz.")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = _ROOT / path
    path = path.resolve(strict=True)
    if not path.exists():
        raise FileNotFoundError(f"Yol bulunamadı: {path}")
    return path


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


def _select_test_runner(worktree: Path) -> TestRunner | None:
    options: list[TestRunner] = []
    if any(worktree.glob("*.sln")) or any(worktree.glob("*.slnx")):
        options.append("dotnet")
    if (worktree / "pom.xml").is_file():
        options.append("maven")
    if any((worktree / name).is_file() for name in ("build.gradle", "build.gradle.kts")):
        options.append("gradle")
    if (worktree / "package.json").is_file():
        options.append("npm")
    if any(worktree.rglob("test_*.py")) or any(worktree.rglob("*_test.py")):
        options.extend(("pytest", "unittest"))
    if not options:
        print("Desteklenen test tanımları bulunamadı.")
        return None
    print("Algılanan test araçları:")
    for index, runner in enumerate(options, start=1):
        print(f"{index}. {runner}")
    choice = _read_positive_integer("Çalıştırılacak test aracı numarası: ")
    if choice > len(options):
        raise ValueError("Test aracı numarası listede yok.")
    return options[choice - 1]


def _ask_yes(question: str) -> bool:
    answer = input(f"{question} [e/H]: ").strip().casefold()
    return answer in {"e", "evet"}


def _starts_with_pdf(path: Path) -> bool:
    try:
        with path.open("rb") as document:
            return document.read(5) == b"%PDF-"
    except OSError:
        return False


def _top_findings(findings: list[dict]) -> list[dict]:
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    return sorted(
        findings,
        key=lambda item: (
            severity_order.get(str(item.get("severity", "")).upper(), 4),
            -int(item.get("confidence", 0)),
        ),
    )[:2]
