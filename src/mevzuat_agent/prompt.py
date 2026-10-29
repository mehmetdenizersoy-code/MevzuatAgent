"""Agent sistem promptunu yükler."""

from pathlib import Path


_SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system_prompt_tr.md"


def load_system_prompt() -> str:
    """Türkçe sistem promptunu döndürür."""
    try:
        return _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"MevzuatAgent system prompt could not be loaded: {exc}") from exc
