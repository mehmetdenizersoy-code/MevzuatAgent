"""Onaylı testleri remediation worktree'sinde çalıştırıp raporlar."""

from dataclasses import dataclass
import html
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Literal
import uuid


TestRunner = Literal["pytest", "unittest", "dotnet", "maven", "gradle", "npm"]
_MAX_OUTPUT_CHARS = 20_000


@dataclass(frozen=True)
class RemediationTestResult:
    """Test çalıştırma ve rapor bilgileri."""

    worktree_path: Path
    branch: str
    runner: TestRunner
    command: tuple[str, ...]
    status: str
    return_code: int | None
    output: str
    markdown_path: Path
    html_path: Path


def validate_remediation(
    worktree_path: str | Path,
    *,
    user_approved: bool,
    runner: TestRunner = "pytest",
    timeout_seconds: float = 120,
    reports_dir: str | Path | None = None,
) -> RemediationTestResult:
    """Desteklenen sabit test komutlarından birini açık onayla çalıştırır."""
    if not user_approved:
        raise PermissionError("Test kodunu çalıştırmak için açık kullanıcı onayı gerekir")
    if runner not in {"pytest", "unittest", "dotnet", "maven", "gradle", "npm"}:
        raise ValueError("Desteklenmeyen test aracı")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds sıfırdan büyük olmalı")

    worktree = Path(worktree_path).resolve(strict=True)
    if not worktree.is_dir():
        raise ValueError("Test çalışma alanı bir dizin olmalı")
    branch = _git(worktree, ["branch", "--show-current"])
    if not branch.startswith("mevzuatagent/remediation-"):
        raise ValueError("Testler yalnızca MevzuatAgent remediation dalında çalıştırılabilir")
    top_level = Path(_git(worktree, ["rev-parse", "--show-toplevel"])).resolve()
    if top_level != worktree:
        raise ValueError("worktree_path Git çalışma alanının kök dizini olmalı")
    report_dir = (
        Path(reports_dir).resolve()
        if reports_dir is not None
        else worktree.parent / f"{worktree.name}-test-reports"
    )
    if report_dir.is_relative_to(worktree):
        raise ValueError("Test raporları remediation worktree'sinin dışında tutulmalı")

    command = _test_command(runner, worktree)
    try:
        process = subprocess.run(
            command,
            cwd=worktree,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        return_code = process.returncode
        output = _limit_output(
            "\n".join(part for part in (process.stdout, process.stderr) if part)
        )
        status = "passed" if return_code == 0 else "failed"
    except subprocess.TimeoutExpired as exc:
        return_code = None
        output = _limit_output(
            "\n".join(
                part
                for part in (
                    _as_text(exc.stdout),
                    _as_text(exc.stderr),
                    f"Testler {timeout_seconds:g} saniyede tamamlanmadı.",
                )
                if part
            )
        )
        status = "timeout"
    except OSError as exc:
        raise RuntimeError(f"Test aracı başlatılamadı: {exc}") from exc

    report_dir.mkdir(parents=True, exist_ok=True)
    report_id = uuid.uuid4().hex[:10]
    markdown_path = report_dir / f"tests-{report_id}.md"
    html_path = report_dir / f"tests-{report_id}.html"
    markdown_path.write_text(
        _render_markdown(worktree, branch, runner, command, status, return_code, output),
        encoding="utf-8",
    )
    html_path.write_text(
        _render_html(worktree, branch, runner, command, status, return_code, output),
        encoding="utf-8",
    )
    return RemediationTestResult(
        worktree,
        branch,
        runner,
        command,
        status,
        return_code,
        output,
        markdown_path,
        html_path,
    )


def _git(worktree: Path, arguments: list[str]) -> str:
    try:
        process = subprocess.run(
            ["git", "-C", str(worktree), *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Git worktree doğrulanamadı: {exc}") from exc
    if process.returncode:
        detail = (process.stderr or process.stdout).strip().splitlines()
        message = detail[-1][:300] if detail else "git komutu başarısız"
        raise ValueError(f"Geçerli bir remediation worktree değil: {message}")
    return process.stdout.strip()


def _test_command(runner: TestRunner, worktree: Path) -> tuple[str, ...]:
    if runner == "pytest":
        return (sys.executable, "-m", "pytest", "-q")
    if runner == "unittest":
        return (sys.executable, "-m", "unittest", "discover", "-v")
    if runner == "dotnet":
        if not any(worktree.glob("*.sln")) and not any(worktree.glob("*.slnx")):
            raise ValueError("dotnet test için depo kökünde .sln veya .slnx bulunmalı")
        executable = shutil.which("dotnet")
        if executable is None:
            raise RuntimeError("dotnet komutu bulunamadı")
        return (executable, "test")
    if runner == "maven":
        if not (worktree / "pom.xml").is_file():
            raise ValueError("maven test için depo kökünde pom.xml bulunmalı")
        executable = shutil.which("mvn")
        if executable is None:
            raise RuntimeError("mvn komutu bulunamadı")
        return (executable, "test")
    if runner == "gradle":
        if not any((worktree / name).is_file() for name in ("build.gradle", "build.gradle.kts")):
            raise ValueError("gradle test için build.gradle veya build.gradle.kts bulunmalı")
        executable = shutil.which("gradle")
        if executable is None:
            raise RuntimeError("gradle komutu bulunamadı")
        return (executable, "test")
    if runner == "npm":
        package_file = worktree / "package.json"
        if not package_file.is_file():
            raise ValueError("npm test için depo kökünde package.json bulunmalı")
        return (shutil.which("npm") or "npm", "test")
    raise ValueError("Desteklenmeyen test aracı")


def _as_text(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""


def _limit_output(value: str) -> str:
    if len(value) <= _MAX_OUTPUT_CHARS:
        return value or "Test aracı çıktı üretmedi."
    return value[:_MAX_OUTPUT_CHARS] + "\n[Çıktı rapor için kısaltıldı.]"


def _render_markdown(
    worktree: Path,
    branch: str,
    runner: TestRunner,
    command: tuple[str, ...],
    status: str,
    return_code: int | None,
    output: str,
) -> str:
    fence = "`" * (max((len(match.group()) for match in re.finditer(r"`+", output)), default=2) + 1)
    return "\n".join(
        [
            "# Düzeltme Test Raporu",
            "",
            "> Test kodu yalnızca kullanıcı onayıyla çalıştırılmıştır. Bu rapor "
            "mevzuat uyumluluğunu kanıtlamaz.",
            "",
            f"- **Çalışma alanı:** `{worktree}`",
            f"- **Dal:** `{branch}`",
            f"- **Test aracı:** `{runner}`",
            f"- **Komut:** `{_markdown(' '.join(command))}`",
            f"- **Sonuç:** **{status}**",
            f"- **Çıkış kodu:** `{return_code if return_code is not None else 'zaman aşımı'}`",
            "",
            "## Test çıktısı",
            "",
            f"{fence}text",
            output.rstrip(),
            fence,
            "",
        ]
    )


def _render_html(
    worktree: Path,
    branch: str,
    runner: TestRunner,
    command: tuple[str, ...],
    status: str,
    return_code: int | None,
    output: str,
) -> str:
    return f"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Düzeltme Test Raporu</title>
<style>
body {{ font: 16px/1.6 system-ui, sans-serif; max-width: 1000px; margin: 40px auto; padding: 0 20px; color: #172033; background: #f5f7fb; }}
main {{ background: white; border: 1px solid #e1e6ef; border-radius: 12px; padding: 24px; }}
.notice {{ background: #fff4d6; border-left: 4px solid #d99a00; padding: 12px; }}
pre {{ overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; background: #f1f4f9; padding: 16px; border-radius: 8px; }}
</style>
</head>
<body><main>
<h1>Düzeltme Test Raporu</h1>
<p class="notice">Test kodu yalnızca kullanıcı onayıyla çalıştırılmıştır. Bu rapor mevzuat uyumluluğunu kanıtlamaz.</p>
<p><strong>Çalışma alanı:</strong> {html.escape(str(worktree))}</p>
<p><strong>Dal:</strong> {html.escape(branch)}</p>
<p><strong>Test aracı:</strong> {html.escape(runner)}</p>
<p><strong>Komut:</strong> <code>{html.escape(" ".join(command))}</code></p>
<p><strong>Sonuç:</strong> {html.escape(status)}</p>
<p><strong>Çıkış kodu:</strong> {html.escape(str(return_code) if return_code is not None else "zaman aşımı")}</p>
<h2>Test çıktısı</h2>
<pre>{html.escape(output)}</pre>
</main></body>
</html>
"""


def _markdown(value: str) -> str:
    return value.replace("|", "\\|").replace("\r", " ").replace("\n", " ")
