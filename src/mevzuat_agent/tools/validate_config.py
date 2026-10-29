"""Mevzuat ve depo bağlantı dosyalarını doğrular.

Dosya indirmez veya depolara bağlanmaz; bulunan hataları bildirir.
"""

from dataclasses import dataclass
import json
from pathlib import Path
import re
from collections.abc import Callable
from urllib.parse import urlsplit


@dataclass(frozen=True)
class ConfigValidationResult:
    """Yapılandırma doğrulama sonucu."""

    errors: tuple[str, ...]
    mevzuat_links: tuple[str, ...] = ()
    repository_links: tuple[str, ...] = ()

    @property
    def is_valid(self) -> bool:
        """İki dosya da geçerliyse True döndürür."""
        return not self.errors


def validate_config(config_dir: str | Path = ".") -> ConfigValidationResult:
    """İki JSON dosyasını doğrular ve bağlantıları döndürür."""
    root = Path(config_dir)
    errors: list[str] = []

    mevzuat_links = _read_links(
        root / "mevzuat_link.json",
        "links",
        errors,
        _is_http_url,
        "HTTP(S)",
    )
    repository_links = _read_links(
        root / "repo_link.json",
        "repos",
        errors,
        _is_repository_url,
        "HTTPS or SSH",
    )

    return ConfigValidationResult(
        errors=tuple(errors),
        mevzuat_links=tuple(mevzuat_links),
        repository_links=tuple(repository_links),
    )


def _read_links(
    path: Path,
    key: str,
    errors: list[str],
    url_validator: Callable[[str], bool],
    supported_schemes: str,
) -> list[str]:
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        errors.append(f"{path.name}: file not found")
        return []
    except OSError as exc:
        errors.append(f"{path.name}: cannot read file ({exc})")
        return []

    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        errors.append(f"{path.name}: invalid JSON at line {exc.lineno}, column {exc.colno}")
        return []

    if not isinstance(data, dict):
        errors.append(f"{path.name}: top-level JSON value must be an object")
        return []

    links = data.get(key)
    if not isinstance(links, list) or not links:
        errors.append(f"{path.name}: '{key}' must be a non-empty array")
        return []

    valid_links: list[str] = []
    for index, value in enumerate(links):
        location = f"{path.name}: '{key}[{index}]'"
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{location} must be a non-empty URL string")
            continue
        url = value.strip()
        if not url_validator(url):
            errors.append(f"{location} must be a valid {supported_schemes} URL")
            continue
        valid_links.append(url)

    return valid_links


def _is_http_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname)


def _is_repository_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    if parsed.scheme in {"https", "ssh"} and parsed.hostname and parsed.path.strip("/"):
        return True
    return bool(re.fullmatch(r"git@[A-Za-z0-9.-]+:[^\s:]+(?:/[^\s:]+)+", value))
