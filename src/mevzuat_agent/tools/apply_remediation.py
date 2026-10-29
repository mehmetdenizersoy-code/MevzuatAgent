"""Onaylı kod değişikliklerini izole bir Git worktree'de uygular."""

from collections.abc import Mapping
from dataclasses import dataclass
import html
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
from uuid import uuid4

from mevzuat_agent.tools.prepare_remediation_plan import _SEVERITY_ORDER


@dataclass(frozen=True)
class RemediationResult:
    """Uygulanan düzeltme ve rapor bilgileri."""

    branch: str
    worktree_path: Path
    markdown_path: Path
    html_path: Path
    diff: str


def apply_remediation(
        repository_path: str | Path,
        scan_result_path: str | Path,
        changes: Mapping[str, str],
        *,
        user_approved: bool,
        reports_dir: str | Path | None = None,
        timeout_seconds: float = 30,
) -> RemediationResult:
    """En önemli iki bulgu için verilen dosya içeriklerini onayla uygular."""
    if not user_approved:
        raise PermissionError("Kod değişikliği için açık kullanıcı onayı gerekir")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds sıfırdan büyük olmalı")
    if not changes or any(not isinstance(content, str) for content in changes.values()):
        raise ValueError("Değişiklikler en az bir dosya için metin içeriği içermeli")

    repository = Path(repository_path).resolve()
    scan_path = Path(scan_result_path).resolve()
    if not scan_path.is_file():
        raise ValueError(f"Tarama sonucu bulunamadı: {scan_path}")
    try:
        result = json.loads(scan_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Tarama sonucu geçerli JSON değil: satır {exc.lineno}, sütun {exc.colno}"
        ) from exc
    if not isinstance(result, dict) or not isinstance(result.get("findings"), list):
        raise ValueError("Tarama sonucu bulgu listesi içermiyor")

    findings = result["findings"]
    if not findings:
        raise ValueError("Düzeltme için doğrulanmış bulgu bulunamadı")
    for index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            raise ValueError(f"{index}. bulgu geçerli bir nesne değil")
        severity = str(finding.get("severity", "")).upper()
        if severity not in _SEVERITY_ORDER:
            raise ValueError(f"{index}. bulgunun önem seviyesi geçersiz")
        if not isinstance(finding.get("confidence"), int):
            raise ValueError(f"{index}. bulgunun güven puanı geçersiz")
        for field in ("file", "evidence"):
            if not isinstance(finding.get(field), str) or not finding[field].strip():
                raise ValueError(f"{index}. bulguda '{field}' alanı eksik")
        if not isinstance(finding.get("line"), int) or finding["line"] < 1:
            raise ValueError(f"{index}. bulgunun satır numarası geçersiz")

    top_findings = sorted(
        findings,
        key=lambda item: (
            _SEVERITY_ORDER[str(item["severity"]).upper()],
            -item["confidence"],
        ),
    )[:2]
    target_files = {_safe_relative_path(item["file"]) for item in top_findings}
    change_files = {_safe_relative_path(path) for path in changes}
    if change_files != target_files:
        raise ValueError("Değişiklik dosyaları en önemli iki bulguyla tam eşleşmeli")
    normalized_changes = {
        _safe_relative_path(path): content for path, content in changes.items()
    }

    root = _git(repository, ["rev-parse", "--show-toplevel"], timeout_seconds).stdout.strip()
    if Path(root).resolve() != repository:
        raise ValueError("repository_path Git deposunun kök dizini olmalı")
    status = _git(
        repository,
        ["status", "--porcelain", "--untracked-files=all"],
        timeout_seconds,
    ).stdout
    if status:
        raise ValueError("Kaynak deponun çalışma ağacı temiz olmalı")

    for finding in top_findings:
        relative = _safe_relative_path(finding["file"])
        source = _repository_file(repository, relative)
        source_lines = source.read_text(encoding="utf-8").splitlines()
        line = finding["line"]
        if line > len(source_lines) or source_lines[line - 1].strip() != finding["evidence"].strip():
            raise ValueError(f"Bulgudaki kanıt kaynak satırla eşleşmiyor: {relative}:{line}")

    identifier = uuid4().hex[:10]
    branch = f"mevzuatagent/remediation-{identifier}"
    worktree = repository.parent / f"{repository.name}-remediation-{identifier}"
    report_root = (
        Path(reports_dir).resolve()
        if reports_dir is not None
        else repository.parent / f"{repository.name}-remediation-reports"
    )
    if report_root.is_relative_to(repository):
        raise ValueError("Diff raporları kaynak deponun dışında tutulmalı")
    markdown_path = report_root / f"remediation-{identifier}.md"
    html_path = report_root / f"remediation-{identifier}.html"

    _git(
        repository,
        ["worktree", "add", "-b", branch, str(worktree), "HEAD"],
        timeout_seconds,
    )
    try:
        for relative, content in normalized_changes.items():
            target = _repository_file(worktree, relative)
            target.write_text(content, encoding="utf-8")
        diff = _git(
            worktree,
            ["diff", "--no-ext-diff", "--no-color", "--unified=3"],
            timeout_seconds,
        ).stdout
        if not diff:
            raise ValueError("Onaylanan değişiklikler kaynak kodda fark oluşturmadı")
        report_root.mkdir(parents=True, exist_ok=True)
        test_only = any(
            item.get("mevzuat_source") == "TEST_FIXTURE_NOT_LAW"
            for item in top_findings
        )
        markdown_path.write_text(
            _render_markdown(branch, repository, worktree, diff, test_only),
            encoding="utf-8",
        )
        html_path.write_text(
            _render_html(branch, repository, worktree, diff, test_only),
            encoding="utf-8",
        )
    except Exception:
        _git(repository, ["worktree", "remove", "--force", str(worktree)], timeout_seconds)
        _git(repository, ["branch", "-D", branch], timeout_seconds)
        raise

    return RemediationResult(branch, worktree, markdown_path, html_path, diff)


def _safe_relative_path(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Dosya yolu boş olamaz")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"Güvenli olmayan göreli dosya yolu: {value}")
    if "\\" in value or re.match(r"^[A-Za-z]:", value):
        raise ValueError(f"Güvenli olmayan göreli dosya yolu: {value}")
    return path.as_posix()


def _repository_file(repository: Path, relative: str) -> Path:
    target = repository / relative
    if any(part.is_symlink() for part in (repository, *target.parents, target)):
        raise ValueError(f"Depodaki sembolik bağlantı üzerinden dosya kullanılamaz: {relative}")
    resolved = target.resolve()
    if not resolved.is_relative_to(repository.resolve()) or not resolved.is_file():
        raise ValueError(f"Depo içinde normal bir dosya bulunamadı: {relative}")
    return resolved


def _git(repository: Path, arguments: list[str], timeout_seconds: float) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repository), *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("git çalıştırılabilir dosyası bulunamadı") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"git komutu {timeout_seconds:g} saniyede tamamlanmadı") from exc
    if result.returncode:
        detail = (result.stderr or result.stdout).strip().splitlines()
        message = detail[-1][:300] if detail else "git komutu başarısız"
        raise RuntimeError(message)
    return result


def _render_markdown(
    branch: str,
    repository: Path,
    worktree: Path,
    diff: str,
    test_only: bool,
) -> str:
    fence = "`" * (max((len(match.group()) for match in re.finditer(r"`+", diff)), default=2) + 1)
    notice = (
        "> **YALNIZCA TEST İÇİNDİR.** Sentetik bulgular gerçek mevzuat tespiti "
        "veya hukukî görüş değildir."
        if test_only
        else "> Bu diff, değişikliğin mevzuata uygun olduğunu kanıtlamaz."
    )
    return "\n".join(
        [
            "# Düzeltme Diff Raporu",
            "",
            notice,
            "",
            f"- **Kaynak depo:** `{repository}`",
            f"- **İzole çalışma alanı:** `{worktree}`",
            f"- **Dal:** `{branch}`",
            "- **Durum:** Değişiklikler ayrı worktree'de uygulanmıştır; otomatik "
            "olarak commit edilmemiş veya PR açılmamıştır.",
            "",
            "## Kod farkı",
            "",
            f"{fence}diff",
            diff.rstrip(),
            fence,
            "",
        ]
    )


def _render_html(
    branch: str,
    repository: Path,
    worktree: Path,
    diff: str,
    test_only: bool,
) -> str:
    notice = (
        "<strong>YALNIZCA TEST İÇİNDİR.</strong> Sentetik bulgular gerçek mevzuat "
        "tespiti veya hukukî görüş değildir."
        if test_only
        else "Bu diff, değişikliğin mevzuata uygun olduğunu kanıtlamaz."
    )
    return f"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Düzeltme Diff Raporu</title>
<style>
* {{ box-sizing: border-box; }}
body {{ font: 15px/1.65 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; max-width: 1120px; margin: 0 auto; padding: 32px 22px 56px; color: #24344a; background: #f3f6fa; }}
main {{ background: white; border: 1px solid #e1e7ef; border-radius: 18px; padding: 30px; box-shadow: 0 14px 36px #152b481c; }}
h1 {{ color: #16345c; margin-top: 0; font-size: clamp(24px, 4vw, 34px); letter-spacing: -.03em; }}
.notice {{ color: #59400a; background: #fff4d6; border: 1px solid #f3dfa9; border-left: 4px solid #d99a00; padding: 13px 15px; border-radius: 8px; }}
pre {{ overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; color: #e8eff8; background: #172b46; padding: 18px; border-radius: 10px; }}
code {{ overflow-wrap: anywhere; }}
@media (max-width: 640px) {{ body {{ padding: 16px 12px 32px; }} main {{ padding: 18px; }} }}
</style>
</head>
<body><main>
<h1>Düzeltme Diff Raporu</h1>
<p class="notice">{notice}</p>
<p><strong>Kaynak depo:</strong> {html.escape(str(repository))}</p>
<p><strong>İzole çalışma alanı:</strong> {html.escape(str(worktree))}</p>
<p><strong>Dal:</strong> {html.escape(branch)}</p>
<p>Değişiklikler ayrı worktree'de uygulanmıştır; otomatik olarak commit edilmemiş veya PR açılmamıştır.</p>
<h2>Kod farkı</h2>
<pre>{html.escape(diff)}</pre>
</main></body>
</html>
"""
