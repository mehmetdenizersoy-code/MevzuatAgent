"""Mevzuat bağlantılarını JSON dosyasından okur ve kaydeder."""

import json
from pathlib import Path
from urllib.parse import urlsplit


DEFAULT_CONFIG_PATH = Path("mevzuat_link.json")


def load_mevzuat_links(config_path: str | Path = DEFAULT_CONFIG_PATH) -> tuple[str, ...]:
    """Dosyadaki mevzuat bağlantılarını doğrular ve döndürür."""
    path = Path(config_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"{path}: configuration file not found") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{path}: invalid JSON at line {exc.lineno}, column {exc.colno}"
        ) from exc
    except OSError as exc:
        raise ValueError(f"{path}: cannot read configuration file ({exc})") from exc

    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level JSON value must be an object")
    links = data.get("links")
    if not isinstance(links, list) or not links:
        raise ValueError(f"{path}: 'links' must be a non-empty array")

    validated_links: list[str] = []
    for index, link in enumerate(links):
        if not isinstance(link, str) or not _is_http_url(link.strip()):
            raise ValueError(f"{path}: 'links[{index}]' must be a valid HTTP(S) URL")
        validated_links.append(link.strip())
    return tuple(validated_links)


def save_mevzuat_links(
    links: list[str] | tuple[str, ...],
    config_path: str | Path = DEFAULT_CONFIG_PATH,
) -> Path:
    """Mevzuat bağlantılarını doğrulayıp dosyaya kaydeder."""
    if not links:
        raise ValueError("At least one mevzuat URL is required")

    validated_links: list[str] = []
    for index, link in enumerate(links):
        if not isinstance(link, str) or not _is_http_url(link.strip()):
            raise ValueError(f"links[{index}] must be a valid HTTP(S) URL")
        validated_links.append(link.strip())

    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"links": validated_links}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def _is_http_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname)
