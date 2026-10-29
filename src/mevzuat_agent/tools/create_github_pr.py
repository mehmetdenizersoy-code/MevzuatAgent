"""Testi geçen remediation dalı için açık onayla GitHub PR oluşturur."""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re
import subprocess

from mevzuat_agent.tools.validate_remediation import RemediationTestResult


@dataclass(frozen=True)
class PullRequestResult:
    """GitHub PR bağlantısı ve remediation dal bilgisi."""

    url: str
    branch: str
    commit: str


def create_github_pr(
    worktree_path: str | Path,
    test_result: RemediationTestResult,
    changed_paths: tuple[str, ...] | list[str],
    *,
    user_approved: bool,
    title: str,
    body: str,
    base_branch: str | None = None,
    timeout_seconds: float = 120,
) -> PullRequestResult:
    """Testi geçen ve incelenmiş dalı push edip gh ile PR açar."""
    if not user_approved:
        raise PermissionError("GitHub'a push ve PR için açık kullanıcı onayı gerekir")
    if test_result.status != "passed" or test_result.return_code != 0:
        raise ValueError("Başarılı test raporu olmadan PR açılamaz")
    if not title.strip() or not body.strip():
        raise ValueError("PR başlığı ve açıklaması boş olamaz")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds sıfırdan büyük olmalı")

    worktree = Path(worktree_path).resolve(strict=True)
    if test_result.worktree_path.resolve() != worktree:
        raise ValueError("Test raporu farklı bir worktree'ye ait")
    branch = _git(worktree, ["branch", "--show-current"], timeout_seconds)
    if not branch.startswith("mevzuatagent/remediation-") or branch != test_result.branch:
        raise ValueError("PR yalnızca test edilmiş MevzuatAgent remediation dalından açılabilir")
    top = Path(_git(worktree, ["rev-parse", "--show-toplevel"], timeout_seconds)).resolve()
    if top != worktree:
        raise ValueError("worktree_path Git worktree kökü olmalı")

    paths = {_safe_relative_path(path) for path in changed_paths}
    if not paths:
        raise ValueError("PR için en az bir değişen kaynak dosyası belirtilmeli")
    staged = _run(worktree, ["diff", "--cached", "--quiet"], timeout_seconds, allow_failure=True)
    if staged.returncode != 0:
        raise ValueError("PR öncesinde beklenmeyen stage edilmiş değişiklik var")
    status = _run(
        worktree,
        ["status", "--porcelain", "--untracked-files=all"],
        timeout_seconds,
    ).stdout.rstrip("\n")
    changed = set()
    for line in status.splitlines():
        if len(line) < 4:
            raise ValueError("Git çalışma ağacı durumu çözümlenemedi")
        state = line[:2]
        path = line[3:]
        if state[0] != " " or state[1] not in {" ", "M"}:
            raise ValueError(
                "PR öncesinde beklenmeyen staged, eklenen veya çakışmalı değişiklik var: "
                f"{line}"
            )
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        normalized = _safe_relative_path(path)
        if normalized not in paths:
            raise ValueError(f"PR kapsamı dışındaki değişiklik var: {normalized}")
        changed.add(normalized)
    if changed != paths:
        raise ValueError("PR dosya listesi çalışma ağacındaki değişikliklerle eşleşmiyor")

    target_base = base_branch
    if target_base is None:
        target_base = _git(
            worktree,
            ["symbolic-ref", "refs/remotes/origin/HEAD"],
            timeout_seconds,
        ).removeprefix("refs/remotes/origin/")
    if not target_base or target_base.startswith("-"):
        raise ValueError("PR hedef dal adı geçersiz")
    _run(worktree, ["gh", "auth", "status"], timeout_seconds)
    _run(worktree, ["diff", "--check"], timeout_seconds)
    _run(worktree, ["add", "--", *sorted(paths)], timeout_seconds)
    _run(
        worktree,
        [
            "commit",
            "-m",
            "Apply approved MevzuatAgent remediation",
            "-m",
            "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>",
        ],
        timeout_seconds,
    )
    commit = _git(worktree, ["rev-parse", "--short", "HEAD"], timeout_seconds)
    _run(worktree, ["push", "--set-upstream", "origin", branch], timeout_seconds)
    output = _run(
        worktree,
        [
            "gh",
            "pr",
            "create",
            "--base",
            target_base,
            "--head",
            branch,
            "--title",
            title.strip(),
            "--body",
            body.strip(),
        ],
        timeout_seconds,
    ).stdout.strip()
    match = re.search(r"https://github\.com/\S+/pull/\d+", output)
    if not match:
        raise RuntimeError(f"gh PR oluşturdu ancak bağlantı doğrulanamadı: {output[-300:]}")
    return PullRequestResult(match.group(), branch, commit)


def _safe_relative_path(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Değişen dosya yolu boş olamaz")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"Güvenli olmayan göreli dosya yolu: {value}")
    if "\\" in value or path.as_posix() != value:
        raise ValueError(f"Güvenli olmayan göreli dosya yolu: {value}")
    return value


def _git(worktree: Path, arguments: list[str], timeout_seconds: float) -> str:
    return _run(worktree, ["git", *arguments], timeout_seconds).stdout.strip()


def _run(
    worktree: Path,
    command: list[str],
    timeout_seconds: float,
    *,
    allow_failure: bool = False,
) -> subprocess.CompletedProcess[str]:
    try:
        if command[0] == "gh":
            actual_command = command
        elif command[0] == "git":
            actual_command = ["git", "-C", str(worktree), *command[1:]]
        else:
            actual_command = ["git", "-C", str(worktree), *command]
        process = subprocess.run(
            actual_command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"{command[0]} komutu bulunamadı") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"{command[0]} komutu zaman aşımına uğradı") from exc
    if process.returncode and not allow_failure:
        details = (process.stderr or process.stdout).strip().splitlines()
        message = details[-1][:300] if details else f"{command[0]} başarısız oldu"
        raise RuntimeError(message)
    return process
