"""Mevzuat belgelerini yapılandırmadaki bağlantılardan indirir.

Dosyaları güvenli adla kaydeder, boyut sınırı uygular ve hataları bildirir.
"""

from dataclasses import dataclass
from pathlib import Path
import re
from urllib.error import URLError
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen

from mevzuat_agent.tools.mevzuat_config import (
    DEFAULT_CONFIG_PATH,
    load_mevzuat_links,
)


@dataclass(frozen=True)
class DownloadedDocument:
    """İndirilen belge bilgisi."""

    source_url: str
    path: Path
    size_bytes: int


@dataclass(frozen=True)
class DownloadResult:
    """İndirme sonuçları ve hatalar."""

    documents: tuple[DownloadedDocument, ...]
    errors: tuple[str, ...]


def download_mevzuat(
    output_dir: str | Path,
    *,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    timeout_seconds: float = 30,
    max_bytes: int = 50 * 1024 * 1024,
) -> DownloadResult:
    """mevzuat_link.json içindeki belgeleri indirir."""
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")
    if max_bytes <= 0:
        raise ValueError("max_bytes must be greater than zero")

    try:
        links = load_mevzuat_links(config_path)
    except ValueError as exc:
        return DownloadResult(documents=(), errors=(str(exc),))

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    documents: list[DownloadedDocument] = []
    errors: list[str] = []

    for index, link in enumerate(links, start=1):
        if not isinstance(link, str):
            errors.append(f"link {index}: URL must be a string")
            continue

        try:
            parsed = urlsplit(link.strip())
        except ValueError:
            errors.append(f"link {index}: only valid HTTP(S) URLs are supported")
            continue
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            errors.append(f"link {index}: only valid HTTP(S) URLs are supported")
            continue

        filename = _safe_filename(parsed.path, index)
        target = destination / filename
        if target.exists():
            errors.append(f"link {index}: destination already exists ({filename})")
            continue

        request = Request(link.strip(), headers={"User-Agent": "MevzuatAgent/0.1"})
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                content = response.read(max_bytes + 1)
            if len(content) > max_bytes:
                errors.append(f"link {index}: response exceeds the {max_bytes}-byte limit")
                continue
            target.write_bytes(content)
        except (OSError, URLError, TimeoutError, ValueError) as exc:
            errors.append(f"link {index}: download failed ({_error_summary(exc)})")
            continue

        documents.append(
            DownloadedDocument(source_url=link.strip(), path=target, size_bytes=len(content))
        )

    return DownloadResult(documents=tuple(documents), errors=tuple(errors))


def _safe_filename(url_path: str, index: int) -> str:
    name = Path(unquote(url_path)).name
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    if not safe_name:
        safe_name = "document"
    return f"{index:03d}_{safe_name}"


def _error_summary(error: Exception) -> str:
    if hasattr(error, "code"):
        return f"HTTP {error.code}"
    if isinstance(error, URLError):
        return "network or URL error"
    return error.__class__.__name__
