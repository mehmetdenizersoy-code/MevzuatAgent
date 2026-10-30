"""Kullanıcıyı onay kapılı MevzuatAgent işlemlerinde yönlendirir."""

import difflib
from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import re
import shutil
from typing import Callable
from urllib.parse import unquote, urlsplit
from urllib.error import URLError
from urllib.request import Request, urlopen

from mevzuat_agent.prompt import load_system_prompt
from mevzuat_agent.tools.apply_remediation import apply_remediation
from mevzuat_agent.tools.build_mevzuat_rag import build_mevzuat_rag
from mevzuat_agent.tools.clone_repositories import (
    clone_repositories,
    load_repository_links,
    save_repository_links,
)
from mevzuat_agent.tools.download_mevzuat import download_mevzuat
from mevzuat_agent.tools.estimate_scan_cost import (
    DEFAULT_OLLAMA_URL,
    ModelEstimate,
    is_source_file,
    list_ollama_models,
)
from mevzuat_agent.tools.generate_scan_report import generate_scan_report
from mevzuat_agent.tools.mevzuat_config import (
    load_mevzuat_links,
    save_mevzuat_links,
)
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
_FRESH_START = False


def run_console() -> None:
    """Sohbet arayüzünden proje sorularını yanıtlar ve pipeline'ı sürdürür."""
    global _FRESH_START, _LAW_SCOPE_CONFIRMED, _SELECTED_LAW_INDICES

    print(
        "Merhaba! Ben MevzuatAgent. Seçtiğiniz mevzuat ve Git depolarını "
        "inceleyip kanıta dayalı tarama raporları oluşturmaya yardımcı olurum."
    )
    print("MevzuatAgent | Mevzuat uyumluluğu kod tarama aracı")
    print("Raporlar otomatik karar değildir; mevzuat uzmanı tarafından doğrulanmalıdır.")
    _SELECTED_LAW_INDICES = None
    _LAW_SCOPE_CONFIRMED = False
    _FRESH_START = False
    history: list[dict[str, str]] = []
    laws = _configure_startup_links()
    if _ask_yes(
        "Önceden indirilen mevzuat/RAG verisini, eski tarama ve varsayılan "
        "remediation raporlarını, temiz yerel klonları silip baştan hazırlayayım mı?"
    ):
        try:
            _clean_previous_scan_data()
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"Temiz başlangıç yapılamadı; mevcut veriler korundu: {exc}")
            return
        _FRESH_START = True
        print(
            "Temiz başlangıç hazır. Mevzuat kapsamını seçip 'devam' yazın; "
            "indirme, RAG hazırlama ve depo klonlama sıfırdan yapılacak."
        )
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
    if re.match(r"^3[.)]?\s+.*\b(?:tara|tarama)\b", message):
        return "3"
    if re.match(r"^4[.)]?\s+.*\b(?:düzelt|remediation)\b", message):
        return "4"
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
    if _FRESH_START:
        return "2", "repo_link.json depolarını temiz çalışma alanına klonlama"
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


def _clean_previous_scan_data() -> None:
    """Önceden üretilen tarama verilerini ve temiz yerel klonları kaldırır."""
    data_root = (_ROOT / "data").resolve()
    targets = [
        _ROOT / "data/legislation/downloads",
        _ROOT / "data/legislation/raw",
        _ROOT / "data/legislation/rag",
        _ROOT / "data/reports/scans",
        _ROOT / "data/reports/remediation",
    ]

    repositories_root = _ROOT / "data/repositories"
    if repositories_root.exists():
        if repositories_root.is_symlink() or not repositories_root.is_dir():
            raise ValueError(f"Güvenli depo dizini değil: {repositories_root}")
        for repository in sorted(repositories_root.iterdir()):
            if not repository.is_dir() or repository.is_symlink():
                raise ValueError(
                    f"Depo dizininde beklenmeyen öğe var, temizlik durduruldu: {repository}"
                )
            repository_root = Path(
                run_git_command(repository, "rev-parse", "--show-toplevel")
            ).resolve()
            if repository_root != repository.resolve():
                raise ValueError(
                    f"Depo kökü doğrulanamadı, temizlik durduruldu: {repository}"
                )
            status = run_git_command(
                repository,
                "status",
                "--porcelain",
                "--untracked-files=all",
                "--ignored",
            )
            if status:
                raise ValueError(
                    f"Depoda değişiklik veya yok sayılan dosyalar var; "
                    f"korumak için temizlik durduruldu: {repository}"
                )
            worktrees = run_git_command(repository, "worktree", "list", "--porcelain")
            worktree_paths = [
                Path(line.removeprefix("worktree ")).resolve()
                for line in worktrees.splitlines()
                if line.startswith("worktree ")
            ]
            if worktree_paths != [repository.resolve()]:
                raise ValueError(
                    f"Depoya bağlı başka Git worktree'leri var; "
                    f"temizlik durduruldu: {repository}"
                )
            targets.append(repository)

    for target in targets:
        if not target.exists():
            continue
        if target.is_symlink() or not target.resolve().is_relative_to(data_root):
            raise ValueError(f"Güvenli temizlik yolu değil: {target}")

    existing_targets = [target for target in targets if target.exists()]
    if not existing_targets:
        print("Temizlenecek önceki tarama verisi bulunamadı.")
        return
    print("Temizlenecek önceki veriler:")
    for target in existing_targets:
        print(f"- {target.relative_to(_ROOT)}")
    for target in existing_targets:
        shutil.rmtree(target)
    print("Önceki indirme, RAG/chunk, rapor ve yerel depo verileri temizlendi.")


def _run_pipeline_step(step: str) -> None:
    actions: dict[str, Callable[[], None]] = {
        "1": _prepare_legislation,
        "2": _clone_repositories,
        "3": _scan_repository,
        "4": _remediate,
    }
    actions[step]()


def _configure_startup_links() -> tuple[str, ...]:
    """Mevzuat ve depo bağlantılarını listeler, kullanıcının yenilerini eklemesini sağlar."""
    law_path = _ROOT / "mevzuat_link.json"
    repo_path = _ROOT / "repo_link.json"
    laws = _load_startup_links("mevzuat", load_mevzuat_links, law_path)
    print("\nMevzuat bağlantıları:")
    _print_link_list(laws)
    laws = _offer_link_additions(
        "mevzuat",
        laws,
        law_path,
        save_mevzuat_links,
    )

    repositories = _load_startup_links("depo", load_repository_links, repo_path)
    print("\nGit depo bağlantıları:")
    _print_link_list(repositories)
    _offer_link_additions(
        "depo",
        repositories,
        repo_path,
        save_repository_links,
    )
    return laws


def _load_startup_links(
    label: str,
    loader: Callable[[Path], tuple[str, ...]],
    config_path: Path,
) -> tuple[str, ...]:
    try:
        return loader(config_path)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"{label.capitalize()} bağlantıları yüklenemedi: {exc}")
        return ()


def _print_link_list(links: tuple[str, ...]) -> None:
    if not links:
        print("  (Kayıtlı bağlantı yok)")
        return
    for index, link in enumerate(links, start=1):
        print(f"  {index}. {link}")


def _offer_link_additions(
    label: str,
    links: tuple[str, ...],
    config_path: Path,
    saver: Callable[[list[str], Path], Path],
) -> tuple[str, ...]:
    updated_links = list(links)
    while _ask_yes(f"Yeni {label} bağlantısı eklemek ister misiniz?"):
        link = input(f"{label.capitalize()} URL'si (vazgeçmek için boş bırakın): ").strip()
        if not link:
            break
        if link in updated_links:
            print("Bu bağlantı zaten listede.")
            continue
        updated_links.append(link)
        try:
            saved_path = saver(updated_links, config_path)
        except (OSError, ValueError) as exc:
            updated_links.pop()
            print(f"Bağlantı eklenemedi: {exc}")
            continue
        print(f"Bağlantı kaydedildi: {saved_path}")
    return tuple(updated_links)


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
    config_path = _ROOT / "repo_link.json"
    if not config_path.is_file():
        return []
    workspace = _ROOT / "data/repositories"
    candidates = []
    for repository_url in load_repository_links(config_path):
        repository_name = urlsplit(repository_url).path.rstrip("/").rsplit("/", 1)[-1]
        if repository_name.casefold().endswith(".git"):
            repository_name = repository_name[:-4]
        repository_path = workspace / repository_name
        if repository_path.is_dir() and (repository_path / ".git").exists():
            candidates.append(repository_path)
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
    global _FRESH_START

    download_dir = _ROOT / "data/legislation/downloads"
    rag_dir = _ROOT / "data/legislation/rag"
    index_path = rag_dir / "chunks.jsonl"
    if not _FRESH_START and index_path.is_file() and index_path.stat().st_size:
        if not _ask_yes("Mevcut RAG indeksi var. Yeniden oluşturulsun mu?"):
            print(f"Mevcut indeks korunuyor: {index_path}")
            return

    pdfs = [
        path for path in download_dir.glob("*")
        if path.is_file() and _starts_with_pdf(path)
    ] if download_dir.is_dir() else []
    if not pdfs:
        if not _FRESH_START and not _ask_yes(
            "mevzuat_link.json içindeki kaynaklardan belge indirilsin mi?"
        ):
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
    global _FRESH_START

    result = validate_config(_ROOT)
    if result.errors:
        raise ValueError("; ".join(result.errors))
    print("Klonlanacak depolar:")
    for link in result.repository_links:
        print(f"- {link}")
    if not _FRESH_START and not _ask_yes(
        "Bu depolar data/repositories içine klonlansın mı?"
    ):
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
    _FRESH_START = False


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
        print("Tarama için RAG indeksi bulunamadı; mevzuat hazırlığı başlatılıyor.")
        _prepare_legislation()
    if not rag_index.is_file():
        raise FileNotFoundError(
            f"RAG indeksi oluşturulamadı: {rag_index}. "
            "Mevzuat bağlantılarını ve indirme hatalarını kontrol edin."
        )
    rag_index = _active_rag_index()
    tracked_source_count = _count_tracked_sources(repository)
    if tracked_source_count == 0:
        raise ValueError("Depoda Git tarafından izlenen kaynak dosya yok.")
    max_files = _read_positive_integer(
        f"Taranacak kaynak dosyası sayısı (1-{tracked_source_count}) "
        f"[tümü: {tracked_source_count}]: ",
        default=tracked_source_count,
    )

    result = run_scan_workflow(
        [repository],
        max_files=max_files,
        rag_index_path=rag_index,
        output_dir=_ROOT / "data/reports/scans",
        approval_callback=_request_scan_approval,
    )
    print(f"Tarama durumu: {result.status}")
    if result.status == "scan_declined":
        print("Tarama başlatılmadı.")
        return
    for artifact in result.repositories:
        print(f"JSON: {artifact.scan.output_path}")
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
    _print_report_path("Tarama Markdown", markdown_path)
    _print_report_path("Tarama HTML", html_path)
    print(f"Örnek düzeltme planı: {plan_path}")
    if _ask_yes(
        "Sentetik bulgularla yalnızca test amaçlı bir Ollama düzeltme önerisi "
        "hazırlansın mı? Bu gerçek mevzuat remediation'ı değildir."
    ):
        models = list_ollama_models(DEFAULT_OLLAMA_URL)
        if not models:
            raise RuntimeError("Ollama'da remediation için kurulu model bulunamadı.")
        model = _select_ollama_model(models)
        _remediate(repository, output_path, model_override=model)


def _offer_remediation(repository: Path, artifact: RepositoryScanArtifacts) -> None:
    _present_scan_report(artifact)
    if artifact.scan.findings:
        if _ask_yes(
            "Yukarıdaki tarama bulgularını ve Markdown/HTML raporlarını "
            "incelediniz mi? Onayınızla remediation önerisi hazırlansın mı?"
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


def _present_scan_report(artifact: RepositoryScanArtifacts) -> None:
    """Doğrulanmış tarama bulgularını ve kaydedilmiş raporları kullanıcıya sunar."""
    scan = artifact.scan
    print("\nTarama raporu özeti")
    print(f"Depo: {scan.repository} | Model: {scan.model}")
    selected_count = len(scan.file_results)
    print(
        f"Kaynak dosyası kapsamı: {selected_count}/{scan.files_considered}; "
        f"başarıyla taranan: {scan.files_scanned}"
    )
    print(f"Doğrulanmış bulgu: {len(scan.findings)}")
    for index, finding in enumerate(scan.findings, start=1):
        print(
            f"\n{index}. [{finding.severity}] {finding.title} "
            f"({finding.file}:{finding.line}, güven {finding.confidence}/10)"
        )
        print(f"   Kod kanıtı: {finding.evidence}")
        print(f"   Açıklama: {finding.explanation}")
        print(f"   Öneri: {finding.recommendation}")
        print(
            f"   Mevzuat: {finding.mevzuat_source}, "
            f"sayfa {finding.mevzuat_page}"
        )
        if finding.mevzuat_evidence:
            print(f"   Mevzuat alıntısı: {finding.mevzuat_evidence}")
    if not scan.findings:
        print("Doğrulanmış bulgu yok; bu, mevzuata uygunluk kanıtı değildir.")
    _print_report_path("Tarama Markdown", artifact.markdown_report)
    _print_report_path("Tarama HTML", artifact.html_report)


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
    *,
    model_override: str | None = None,
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
    _print_scan_report_paths(scan_path)
    if not scan_result["findings"]:
        print("Bu taramada doğrulanmış bulgu olmadığından remediation başlatılamaz.")
        for item in scan_result.get("file_results", []):
            if isinstance(item, dict) and item.get("error"):
                print(f"- {item.get('path', 'Dosya')}: {item['error']}")
        print("Model hatası varsa 3. menüden başka bir model seçerek taramayı tekrarlayın.")
        return
    model = model_override or scan_result.get("model")
    if not isinstance(model, str) or not model:
        raise ValueError("Tarama sonucunda model adı bulunmuyor.")
    print("Ollama en önemli iki bulgu için değişiklik önerisi hazırlıyor.")
    try:
        changes, model = _propose_remediation_with_fallback(
            repository,
            scan_path,
            model,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Remediation önerisi üretilemedi; kod değiştirilmedi: {exc}")
        report_paths = _write_remediation_status_report(
            scan_path,
            status="öneri-üretilemedi",
            detail=str(exc),
        )
        _print_report_path("Remediation Markdown", report_paths[0])
        _print_report_path("Remediation HTML", report_paths[1])
        return
    print(f"Düzeltme önerisini üreten model: {model}")
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
        report_paths = _write_remediation_status_report(
            scan_path,
            status="kullanıcı-onaylamadı",
            detail="Öneri gösterildi; kullanıcı uygulama onayı vermedi. Kod değiştirilmedi.",
        )
        _print_report_path("Remediation Markdown", report_paths[0])
        _print_report_path("Remediation HTML", report_paths[1])
        return

    try:
        application = apply_remediation(
            repository,
            scan_path,
            changes,
            user_approved=True,
            reports_dir=_remediation_reports_dir(),
        )
    except (OSError, RuntimeError, ValueError, PermissionError) as exc:
        print(f"Remediation uygulanamadı: {exc}")
        report_paths = _write_remediation_status_report(
            scan_path,
            status="uygulanamadı",
            detail=str(exc),
        )
        _print_report_path("Remediation Markdown", report_paths[0])
        _print_report_path("Remediation HTML", report_paths[1])
        return
    print(f"İzole dal: {application.branch}")
    print(f"Worktree: {application.worktree_path}")
    _print_report_path("Remediation Markdown", application.markdown_path)
    _print_report_path("Remediation HTML", application.html_path)
    print(f"Markdown ve HTML raporları kaydedildi: {application.markdown_path.parent}")
    print("Remediation akışı raporlar oluşturulduktan sonra tamamlandı.")


def _propose_remediation_with_fallback(
    repository: Path,
    scan_path: Path,
    model: str,
) -> tuple[dict[str, str], str]:
    try:
        return propose_remediation(repository, scan_path, model=model), model
    except RuntimeError as first_error:
        try:
            alternate_models = tuple(
                candidate
                for candidate in list_ollama_models(DEFAULT_OLLAMA_URL)
                if candidate != model
            )
        except (OSError, RuntimeError, ValueError) as exc:
            raise RuntimeError(
                f"{first_error}; yedek model listesi alınamadı: {exc}"
            ) from exc
        if not alternate_models:
            raise

        alternate = alternate_models[0]
        print(f"{model} geçerli öneri üretmedi; {alternate} modeli deneniyor.")
        try:
            return propose_remediation(repository, scan_path, model=alternate), alternate
        except RuntimeError as fallback_error:
            raise RuntimeError(
                f"{model} ve {alternate} modelleri geçerli öneri üretemedi: "
                f"{fallback_error}"
            ) from fallback_error


def _print_scan_report_paths(scan_path: Path) -> None:
    markdown_path = scan_path.with_suffix(".md")
    html_path = scan_path.with_suffix(".html")
    if not markdown_path.is_file() or not html_path.is_file():
        try:
            markdown_path, html_path = generate_scan_report(scan_path)
        except (OSError, ValueError) as exc:
            print(f"Tarama Markdown/HTML raporları oluşturulamadı: {exc}")
            return
    _print_report_path("Tarama Markdown", markdown_path)
    _print_report_path("Tarama HTML", html_path)


def _write_remediation_status_report(
    scan_path: Path,
    *,
    status: str,
    detail: str,
) -> tuple[Path, Path]:
    report_dir = _remediation_reports_dir().expanduser().resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    report_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    markdown_path = report_dir / f"remediation-{report_id}-{status}.md"
    html_path = report_dir / f"remediation-{report_id}-{status}.html"
    scan_markdown = scan_path.with_suffix(".md").resolve()
    scan_html = scan_path.with_suffix(".html").resolve()
    markdown_path.write_text(
        "\n".join(
            (
                "# Remediation Durum Raporu",
                "",
                f"- **Durum:** {status}",
                "- **Kod değişikliği:** Uygulanmadı",
                f"- **Tarama JSON:** `{scan_path.resolve()}`",
                f"- **Tarama Markdown:** `{scan_markdown}`",
                f"- **Tarama HTML:** `{scan_html}`",
                "",
                "## Ayrıntı",
                "",
                detail,
                "",
            )
        ),
        encoding="utf-8",
    )
    html_path.write_text(
        "<!doctype html><html lang=\"tr\"><meta charset=\"utf-8\">"
        "<title>Remediation Durum Raporu</title><main>"
        "<h1>Remediation Durum Raporu</h1>"
        f"<p><strong>Durum:</strong> {html.escape(status)}</p>"
        "<p><strong>Kod değişikliği:</strong> Uygulanmadı</p>"
        f"<p><strong>Tarama JSON:</strong> {html.escape(str(scan_path.resolve()))}</p>"
        f"<p><strong>Tarama Markdown:</strong> {html.escape(str(scan_markdown))}</p>"
        f"<p><strong>Tarama HTML:</strong> {html.escape(str(scan_html))}</p>"
        f"<h2>Ayrıntı</h2><pre>{html.escape(detail)}</pre></main></html>\n",
        encoding="utf-8",
    )
    return markdown_path, html_path


def _print_report_path(label: str, path: Path) -> None:
    resolved = path.resolve()
    print(f"{label}: {resolved} ({resolved.as_uri()})")


def _select_ollama_model(models: tuple[str, ...]) -> str:
    print("Yerel Ollama modelleri:")
    for index, name in enumerate(models, start=1):
        print(f"  {index}. {name}")
    selection = _read_positive_integer(
        f"Test remediation modeli [1-{len(models)}] [1]: ",
        default=1,
    )
    if selection > len(models):
        raise ValueError("Model numarası listede yok.")
    return models[selection - 1]


def _select_scan_model(models: tuple[ModelEstimate, ...]) -> str | None:
    if not models:
        raise ValueError("Süre tahmini bulunan bir Ollama modeli yok.")
    while True:
        selection_text = input(
            f"Taramada kullanılacak model numarası [1-{len(models)}] "
            "(iptal için q): "
        ).strip()
        if selection_text.casefold() in {"q", "iptal"}:
            return None
        try:
            selection = int(selection_text)
        except ValueError:
            print("Listeden bir model numarası seçin veya q ile iptal edin.")
            continue
        if not 1 <= selection <= len(models):
            print("Model numarası listede yok; yeniden deneyin.")
            continue
        return models[selection - 1].model


def _request_scan_approval(request: ScanApprovalRequest) -> str | None:
    print("\nKurulu Ollama modelleri için ölçülen tarama süresi tahminleri:")
    for index, item in enumerate(request.estimate.models, start=1):
        marker = " (en hızlı)" if item.model == request.recommended_model else ""
        print(
            f"  {index}. {item.model}: {item.tokens_per_second:.2f} token/sn, "
            f"yaklaşık {item.estimated_seconds} saniye{marker}"
        )
    for error in request.estimate.errors:
        print(f"  Ölçüm yapılamadı; model seçilemez: {error}")
    print(
        f"Dosya kapsamı: en fazla {request.max_files}; "
        f"tahmini toplam token: {request.estimate.scan.estimated_total_tokens}"
    )
    selected_model = _select_scan_model(request.estimate.models)
    if selected_model is None:
        return None
    estimate = next(
        item for item in request.estimate.models if item.model == selected_model
    )
    if not _ask_yes(
        f"{selected_model} ile yaklaşık {estimate.estimated_seconds} saniyelik "
        "bu taramayı başlatmayı onaylıyor musunuz?"
    ):
        return None
    return selected_model


def _remediation_reports_dir() -> Path:
    configured_dir = os.environ.get("MEVZUAT_AGENT_REPORTS_DIR", "").strip()
    if configured_dir:
        return Path(configured_dir).expanduser()
    return _ROOT / "data/reports/remediation"


def _select_repository() -> Path | None:
    candidates = _local_repository_candidates()
    if not candidates:
        print(
            "Yapılandırılmış GitHub depolarının klonu bulunamadı. "
            "Önce depoları klonlayın."
        )
        return None
    print("Taranacak Git depoları:")
    for index, path in enumerate(candidates, start=1):
        print(f"{index}. {path.name}")
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
