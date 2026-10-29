"""Onaylanan depoları yerel çalışma alanına klonlar.

Depo kodunu çalıştırmaz veya uzak depoda değişiklik yapmaz.
"""

from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit


DEFAULT_REPO_CONFIG = Path("repo_link.json")


@dataclass(frozen=True)
class RepositoryCheckout:
    """Klonlanan depo bilgisi."""

    source_url: str
    path: Path


@dataclass(frozen=True)
class RepositoryCloneResult:
    """Klonlama sonuçları ve hatalar."""

    checkouts: tuple[RepositoryCheckout, ...]
    errors: tuple[str, ...]


def clone_repositories(
    workspace_dir: str | Path,
    *,
    user_approved: bool,
    config_path: str | Path = DEFAULT_REPO_CONFIG,
    timeout_seconds: float = 300,
) -> RepositoryCloneResult:
    """Depoları yalnızca kullanıcı onay verirse klonlar."""
    if not user_approved:
        return RepositoryCloneResult((), ("User approval is required before cloning repositories",))
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")

    repo_config = Path(config_path)
    try:
        repositories = _load_repository_links(repo_config)
    except ValueError as exc:
        return RepositoryCloneResult((), (str(exc),))

    workspace = Path(workspace_dir)
    workspace.mkdir(parents=True, exist_ok=True)
    checkouts: list[RepositoryCheckout] = []
    errors: list[str] = []

    for index, repo_url in enumerate(repositories, start=1):
        destination = workspace / _repository_directory_name(repo_url)
        if destination.exists():
            errors.append(f"repo {index}: destination already exists ({destination.name})")
            continue

        try:
            result = subprocess.run(
                ["git", "clone", "--", repo_url, str(destination)],
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except FileNotFoundError:
            errors.append("git: executable not found")
            break
        except subprocess.TimeoutExpired:
            errors.append(f"repo {index}: clone timed out after {timeout_seconds:g} seconds")
            continue
        except OSError as exc:
            errors.append(f"repo {index}: clone could not start ({exc.__class__.__name__})")
            continue

        if result.returncode:
            detail = (result.stderr or result.stdout).strip().splitlines()
            summary = detail[-1][:300] if detail else "git clone failed"
            errors.append(f"repo {index}: {summary}")
            continue

        checkouts.append(RepositoryCheckout(source_url=repo_url, path=destination))

    return RepositoryCloneResult(tuple(checkouts), tuple(errors))


def _load_repository_links(config_path: Path) -> tuple[str, ...]:
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"{config_path}: configuration file not found") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{config_path}: invalid JSON at line {exc.lineno}, column {exc.colno}"
        ) from exc
    except OSError as exc:
        raise ValueError(f"{config_path}: cannot read configuration file ({exc})") from exc

    if not isinstance(data, dict):
        raise ValueError(f"{config_path}: top-level JSON value must be an object")
    repositories = data.get("repos")
    if not isinstance(repositories, list) or not repositories:
        raise ValueError(f"{config_path}: 'repos' must be a non-empty array")

    validated: list[str] = []
    errors: list[str] = []
    for index, repo_url in enumerate(repositories):
        if not isinstance(repo_url, str) or not _is_repository_url(repo_url.strip()):
            errors.append(f"{config_path}: 'repos[{index}]' must be a valid HTTPS or SSH URL")
            continue
        normalized_url = repo_url.strip()
        if not _repository_directory_name(normalized_url):
            errors.append(f"{config_path}: 'repos[{index}]' has no valid repository name")
            continue
        validated.append(normalized_url)
    if errors:
        raise ValueError("; ".join(errors))
    return tuple(validated)


def _is_repository_url(value: str) -> bool:
    if any(character.isspace() for character in value):
        return False
    if value.startswith("git@"):
        return bool(re.fullmatch(r"git@[A-Za-z0-9.-]+:[^\s:]+(?:/[^\s:]+)+", value))
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return (
        parsed.scheme in {"https", "ssh"}
        and bool(parsed.hostname)
        and bool(parsed.path.strip("/"))
        and parsed.username is None
        and parsed.password is None
    )


def _repository_directory_name(repo_url: str) -> str:
    if repo_url.startswith("git@"):
        repo_name = repo_url.rsplit("/", 1)[-1]
    else:
        repo_name = urlsplit(repo_url).path.rstrip("/").rsplit("/", 1)[-1]
    if repo_name.casefold().endswith(".git"):
        repo_name = repo_name[:-4]
    return re.sub(r"[^A-Za-z0-9._-]+", "_", repo_name).strip("._")
