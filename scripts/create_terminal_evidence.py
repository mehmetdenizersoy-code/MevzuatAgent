"""Render selected terminal-output excerpts from local runs and E2E reports."""

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "docs" / "assets" / "e2e_terminal"
WIDTH = 1800
HEIGHT = 650
BACKGROUND = "#0b1220"
PANEL = "#142238"
TEXT = "#e6edf7"
MUTED = "#91a4bc"
CYAN = "#68d7e8"
GREEN = "#83e1a8"
AMBER = "#ffd479"
RED = "#ff8585"


@dataclass(frozen=True)
class Evidence:
    filename: str
    badge: str
    lines: list[str]
    footer: str


EVIDENCE = (
    Evidence(
        filename="01_chat_and_rag.png",
        badge="GERÇEK YEREL UYGULAMA ÇALIŞTIRMASI",
        lines=[
            "$ printf '1\\nRAG hazırla\\ne\\nçıkış\\n' | ./.venv/bin/python -m mevzuat_agent",
            "MevzuatAgent | Mevzuat uyumluluğu kod tarama aracı",
            "Başlamak için mevzuat adını/numarasını seçin; ayrıca proje hakkında soru sorabilirsiniz.",
            "  1. 1.5.5464.pdf",
            "  2. GeneratePdf",
            "Siz: Mevzuat kapsamı seçildi: 1. Ne yapmak istersiniz?",
            "Siz: Mevcut RAG indeksi var. Yeniden oluşturulsun mu? [e/H]: e",
            "RAG indeksi hazır: data/legislation/rag/chunks.jsonl (146 parça)",
            "Bu adım sonlandı. Sonraki adıma geçmek için 'devam' yazabilirsiniz.",
            "Siz: MevzuatAgent kapatıldı.",
        ],
        footer="Canlı yerel çalıştırma • PDF kaynaklarından BM25 RAG • kullanıcı mevzuat seçimi",
    ),
    Evidence(
        filename="02_repository_and_estimate.png",
        badge="GERÇEK YEREL DEPO VE TAHMİN",
        lines=[
            "$ git -C data/e2e/clones/mevzuatagent-test-fixtures rev-parse --abbrev-ref HEAD",
            "main",
            "$ git -C data/e2e/clones/mevzuatagent-test-fixtures rev-parse --short HEAD",
            "a14df30",
            "$ python - <<'PY'  # estimate_scan_cost(..., max_files=1)",
            "repo=mevzuatagent-test-fixtures branch=main@a14df30",
            "source_files=1 retrieved_chunks=3",
            "estimated_tokens=1790 estimated_seconds=179",
            "errors=none",
        ],
        footer="Tahmin yaklaşık token/süre değeridir; yerel Ollama için parasal maliyet hesaplanmaz.",
    ),
    Evidence(
        filename="03_live_and_synthetic_scan.png",
        badge="CANLI MODEL + AYRI SENTETİK DEMO",
        lines=[
            "[CANLI ÇALIŞTIRMA] scan_repository(model='gemma3:4b', max_files=1)",
            "[CANLI OLLAMA] model=gemma3:4b; files_scanned=1/2; verified_findings=0",
            "demo1/payment_rules.py: scanned",
            "Not: Bulgu yok sonucu mevzuata uygunluk kanıtı değildir.",
            "",
            "$ printf '1\\ntarama yap\\n1\\nçıkış\\n' | ./.venv/bin/python -m mevzuat_agent",
            "[AYRI TEST FİXTURE'I] Sentetik test bulguları üretildi.",
            "Bu işlem Ollama veya gerçek mevzuat kullanmadı.",
            "JSON / Markdown / HTML raporları üretildi: data/reports/scans/demo1_synthetic.*",
            "$ ./.venv/bin/python - <<'PY'  # JSON rapor kontrolü",
            "findings=5; source=TEST_FIXTURE_NOT_LAW",
        ],
        footer="Canlı model taraması ile pozitif bulgulu sentetik fixture birbirinden ayrı tutulmuştur.",
    ),
    Evidence(
        filename="04_remediation_diff.png",
        badge="DETERMINİSTİK E2E • SENTETİK TEST",
        lines=[
            "$ sed -n '19,28p' docs/examples/e2e_remediation_raporu.md",
            " def mask_reference(value: str, visible: int = 4) -> str:",
            "     \"\"\"Ödeme başvurusunu kısaltır.\"\"\"",
            "-    return value",
            "+    return \"*\" * max(0, len(value) - visible) + value[-visible:]",
            "",
            "",
            " def is_positive_amount(amount: float) -> bool:",
            "     \"\"\"Tutarın pozitif olup olmadığını döndürür.\"\"\"",
            "-    return amount >= 0",
            "+    return amount > 0",
        ],
        footer="Kod farkı E2E test fixture'ından alınmıştır; mevzuata uygunluğu kanıtlamaz.",
    ),
    Evidence(
        filename="05_test_and_mock_pr.png",
        badge="TEST ONLY • YEREL REMOTE • MOCK GH",
        lines=[
            "$ ./.venv/bin/python - <<'PY'  # validate_remediation(..., runner='pytest')",
            "worktree=mevzuatagent-test-fixtures-remediation-c4b060c129",
            "branch=mevzuatagent/remediation-c4b060c129",
            "command=python -m pytest -q",
            "status=passed; exit_code=0",
            "2 passed, 13 warnings in 0.01s",
            "",
            "$ git --git-dir=data/e2e/pr-origin.git show-ref refs/heads/mevzuatagent/remediation-c4b060c129",
            "41d4a313989c4614fb74a92fa70006fc3356a0c4 refs/heads/mevzuatagent/remediation-c4b060c129",
            "$ PATH=data/e2e/fake-bin:$PATH gh pr create ...",
            "https://github.com/mehmetdenizersoy-code/mevzuatagent-test-fixtures/pull/999",
            "[MOCK GH] Gerçek GitHub isteği veya PR oluşturulmadı.",
        ],
        footer="Testler geçti; push yerel bare remote'a yapıldı; PR bağlantısı sahte gh yanıtıdır.",
    ),
)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        Path("/System/Library/Fonts/Menlo.ttc"),
        Path("/Library/Fonts/Menlo.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    if not text:
        return [""]
    words = text.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and draw.textlength(candidate, font=font) > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _render(item: Evidence) -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    body_font = _font(22)
    small_font = _font(17)

    draw.rounded_rectangle((24, 22, WIDTH - 24, HEIGHT - 22), radius=20, fill="#101b2c")
    draw.rounded_rectangle((24, 22, WIDTH - 24, 88), radius=20, fill=PANEL)
    draw.rectangle((24, 65, WIDTH - 24, 88), fill=PANEL)
    for index, color in enumerate((RED, AMBER, GREEN)):
        x = 56 + index * 34
        draw.ellipse((x, 44, x + 17, 61), fill=color)
    draw.text((170, 39), item.badge, font=small_font, fill=AMBER)
    draw.text((WIDTH - 520, 39), "terminal çıktısı • seçilmiş satırlar", font=small_font, fill=MUTED)

    y = 116
    line_height = 34
    for line in item.lines:
        for wrapped in _wrap(draw, line, body_font, WIDTH - 112):
            lowered = wrapped.casefold()
            color = (
                CYAN if wrapped.startswith("$ ")
                else AMBER if any(mark in lowered for mark in ("sentetik", "mock", "not:", "hukukî", "uygunluk kanıtı"))
                else GREEN if any(mark in lowered for mark in ("passed", "146 parça", "errors=none", "status=scanned"))
                else TEXT
            )
            draw.text((58, y), wrapped, font=body_font, fill=color)
            y += line_height

    footer_y = HEIGHT - 66
    draw.line((52, footer_y - 10, WIDTH - 52, footer_y - 10), fill="#263951", width=2)
    draw.text((58, footer_y + 2), item.footer, font=small_font, fill=MUTED)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    image.save(OUTPUT_DIR / item.filename, optimize=True)


def main() -> None:
    for item in EVIDENCE:
        _render(item)
    print(f"{len(EVIDENCE)} terminal çıktısı görseli oluşturuldu: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
