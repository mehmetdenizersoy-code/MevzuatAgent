"""Gerçek terminal oturumundan SVG ekran görüntüleri üretir ve raporlara ekler.

Görseller ayrı SVG dosyalarıdır; yalnızca Markdown raporları bunlara bağlanır,
HTML raporlarına görsel gömülmez. Betik tekrar çalıştırılabilir.
"""

import os
import re
import textwrap
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = ROOT / "docs" / "images"
SCAN_STEM = ROOT / "data/reports/scans/mevzuatagent-demo1-findings_9754d83b"
REMEDIATION_STEM = ROOT / "data/reports/remediation/remediation-035be68079"
PROMPT = "(.venv) (base) denizersoy@192 Final-Proje_MevzuatAgent %"
MARKER_START = "<!-- terminal-goruntuleri:basla -->"
MARKER_END = "<!-- terminal-goruntuleri:bitis -->"
WRAP = 118
LINE_HEIGHT = 22

REPO = "/Users/denizersoy/PycharmProjects/Final-Proje_MevzuatAgent"
SCANS = f"{REPO}/data/reports/scans/mevzuatagent-demo1-findings_9754d83b"

SCREENS = {
    "terminal-gercek-01-hazirlik": (
        "Temiz başlangıç, RAG hazırlama ve depo klonlama",
        f"""{PROMPT} .venv/bin/mevzuat-agent
Merhaba! Ben MevzuatAgent. Seçtiğiniz mevzuat ve Git depolarını inceleyip kanıta dayalı tarama raporları oluşturmaya yardımcı olurum.
MevzuatAgent | Mevzuat uyumluluğu kod tarama aracı
Raporlar otomatik karar değildir; mevzuat uzmanı tarafından doğrulanmalıdır.

Mevzuat seçenekleri:
  1. 1.5.5464.pdf

Siz: 1
Mevzuat kapsamı seçildi: tüm kaynaklar. Ne yapmak istersiniz?

Siz: tarama yap
Yapılandırılmış GitHub depolarının klonu bulunamadı. Önce depoları klonlayın.

Siz: devam
Pipeline adımı: Mevzuat belgelerini indirip RAG indeksini hazırlama
RAG indeksi hazır: {REPO}/data/legislation/rag/chunks.jsonl (55 parça)

Siz: devam
Pipeline adımı: repo_link.json depolarını temiz çalışma alanına klonlama
Klonlandı: {REPO}/data/repositories/mevzuatagent-demo1-findings
Klonlandı: {REPO}/data/repositories/mevzuatagent-demo2-findings""",
    ),
    "terminal-gercek-02-tarama-modelleri": (
        "Ollama model tahmini: llama3.2:1b hatası ve qwen3:4b taraması",
        """Siz: devam
Pipeline adımı: Yerel depoda tarama tahmini ve onaylı tarama
Depo numarası: 1
Taranacak kaynak dosyası sayısı (1-1) [tümü: 1]: 1

Kurulu Ollama modelleri için ölçülen tarama süresi tahminleri:
  1. llama3.2:1b: 64.96 token/sn, yaklaşık 35 saniye (en hızlı)
  2. gemma3:4b: 30.73 token/sn, yaklaşık 73 saniye
  3. qwen3:4b: 30.61 token/sn, yaklaşık 73 saniye
Taramada kullanılacak model numarası [1-3] (iptal için q): 1
llama3.2:1b ile yaklaşık 35 saniyelik bu taramayı başlatmayı onaylıyor musunuz? [e/H]: e
Tarama durumu: completed
Kaynak dosyası kapsamı: 1/1; başarıyla taranan: 0
Doğrulanmış bulgu: 0
  - payment_rules.py: Local model scan failed (ValueError): Ollama agent exceeded the maximum tool-call rounds

Siz: devam
Kurulu Ollama modelleri için ölçülen tarama süresi tahminleri:
  1. gemma3:4b: 17.61 token/sn, yaklaşık 127 saniye (en hızlı)
  2. llama3.2:1b: 11.70 token/sn, yaklaşık 191 saniye
  3. qwen3:4b: 3.83 token/sn, yaklaşık 584 saniye
Taramada kullanılacak model numarası [1-3] (iptal için q): 3
qwen3:4b ile yaklaşık 584 saniyelik bu taramayı başlatmayı onaylıyor musunuz? [e/H]: e
Tarama durumu: completed""",
    ),
    "terminal-gercek-03-tarama-bulgusu": (
        "qwen3:4b tarama raporu özeti",
        f"""Tarama raporu özeti
Depo: {REPO}/data/repositories/mevzuatagent-demo1-findings | Model: qwen3:4b
Kaynak dosyası kapsamı: 1/1; başarıyla taranan: 1
Doğrulanmış bulgu: 1

1. [CRITICAL] Ödeme planı taksit tutarını yanlış hesaplamak (payment_rules.py:24, güven 10/10)
   Kod kanıtı: def installment_amount(total: float, count: int) -> float:
   Açıklama: Mevzuat 1.5.5464.pdf sayfa 18'de vadeli ödemeler için taksit tutarını hesaplama kuralları belirtilmiştir. Ancak kodda installment_amount fonksiyonu taksit sayısına göre hesaplamak yerine toplam tutarı döndürmektedir. Bu, mevzuatın aylık eşit taksitler şeklinde hesaplanmasını engelleyen bir uyumsuzluktur.
   Öneri: installment_amount fonksiyonunda toplam tutarı taksit sayısına göre hesaplamak için mevzuatın belirtilen oranlarla çarpma ve bölme işlemlerini uygulamalı. Örneğin, 12 aylık vade için (total * 1.08) / 12 şeklinde hesaplanmalıdır.
   Mevzuat: 001_1.5.5464.pdf, sayfa 18
   Mevzuat alıntısı: ... aylık eşit taksitler şeklinde ödenecek borç tutarı; a) 6 aylık vade için 1,04, b) 12 aylık vade için 1,08, c) 24 aylık vade için 1,18, d) 36 aylık vade için 1,26, ile çarpılarak hesaplanacak tutarın ay sayısına bölünmesi suretiyle hesaplanır.
Tarama Markdown: {SCANS}.md
Tarama HTML: {SCANS}.html""",
    ),
    "terminal-gercek-04-remediation": (
        "Remediation önerisi ve izole dalda uygulama",
        f"""Yukarıdaki tarama bulgularını ve Markdown/HTML raporlarını incelediniz mi? Onayınızla remediation önerisi hazırlansın mı? [e/H]: e
Ollama en önemli iki bulgu için değişiklik önerisi hazırlıyor.
qwen3:4b geçerli öneri üretmedi; gemma3:4b modeli deneniyor.
Düzeltme önerisini üreten model: gemma3:4b
--- a/payment_rules.py
+++ b/payment_rules.py
@@ -23,9 +23,9 @@
 
 def installment_amount(total: float, count: int) -> float:
     \"\"\"Tek taksit tutarını döndürür.\"\"\"
-    return total
+    return (total * 1.08) / count
 
 
 def normalize_name(name: str) -> str:
     \"\"\"İsim alanını düzenler.\"\"\"
-    return name
+    return name
Yukarıdaki kod değişikliklerini ayrı dalda uygulamayı onaylıyor musunuz? [e/H]: e
İzole dal: mevzuatagent/remediation-035be68079
Worktree: {REPO}/data/repositories/mevzuatagent-demo1-findings-remediation-035be68079
Remediation Markdown: {REPO}/data/reports/remediation/remediation-035be68079.md
Remediation HTML: {REPO}/data/reports/remediation/remediation-035be68079.html
Remediation akışı raporlar oluşturulduktan sonra tamamlandı.""",
    ),
}

REPORT_IMAGES = {
    SCAN_STEM: (
        "terminal-gercek-01-hazirlik",
        "terminal-gercek-02-tarama-modelleri",
        "terminal-gercek-03-tarama-bulgusu",
    ),
    REMEDIATION_STEM: (
        "terminal-gercek-03-tarama-bulgusu",
        "terminal-gercek-04-remediation",
    ),
}


def _wrapped(text: str) -> list[str]:
    result: list[str] = []
    for line in text.splitlines():
        indent = len(line) - len(line.lstrip(" "))
        parts = textwrap.wrap(
            line,
            width=WRAP,
            subsequent_indent=" " * (indent + 3),
            drop_whitespace=False,
            break_long_words=True,
        )
        result.extend(parts or [""])
    return result


def _color(line: str) -> str:
    stripped = line.lstrip()
    if line.startswith(PROMPT) or stripped.startswith("Siz:"):
        return "#7dd3fc"
    if stripped.startswith("+") and not stripped.startswith("+++"):
        return "#86efac"
    if stripped.startswith("-") and not stripped.startswith("---"):
        return "#fca5a5"
    if "CRITICAL" in line or "failed" in line:
        return "#fca5a5"
    if stripped.startswith(("Klonlandı", "RAG indeksi hazır", "Tarama durumu")):
        return "#a7f3d0"
    return "#e2e8f0"


def render_svg(title: str, body: str) -> str:
    lines = _wrapped(body)
    width = 1480
    height = 100 + LINE_HEIGHT * len(lines) + 30
    text_rows = []
    for index, line in enumerate(lines):
        y = 112 + index * LINE_HEIGHT
        text_rows.append(
            f'    <text x="30" y="{y}" fill="{_color(line)}" xml:space="preserve">'
            f"{escape(line)}</text>"
        )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title">
  <title id="title">{escape(title)}</title>
  <rect width="{width}" height="{height}" rx="14" fill="#10151d"/>
  <rect width="{width}" height="48" rx="14" fill="#252c36"/>
  <rect y="34" width="{width}" height="14" fill="#252c36"/>
  <circle cx="26" cy="24" r="7" fill="#ff5f57"/>
  <circle cx="50" cy="24" r="7" fill="#febc2e"/>
  <circle cx="74" cy="24" r="7" fill="#28c840"/>
  <text x="{width // 2}" y="30" text-anchor="middle" fill="#d6dbe2" font-family="Arial, sans-serif" font-size="15">Terminal — MevzuatAgent</text>
  <text x="30" y="72" fill="#8391a3" font-family="Arial, sans-serif" font-size="13">{escape(title)} · gerçek çalıştırma çıktısı</text>
  <g font-family="Menlo, Monaco, Consolas, monospace" font-size="15">
{chr(10).join(text_rows)}
  </g>
</svg>
"""


def _markdown_section(stem: Path, names: tuple[str, ...]) -> str:
    rows = [MARKER_START, "", "## Terminal ekran görüntüleri", ""]
    for name in names:
        relative = Path(os.path.relpath(IMAGE_DIR / f"{name}.svg", stem.parent)).as_posix()
        rows += [f"![{SCREENS[name][0]}]({relative})", ""]
    rows.append(MARKER_END)
    return "\n".join(rows) + "\n"


def _strip_section(path: Path) -> None:
    content = path.read_text(encoding="utf-8")
    cleaned = _remove_section(content)
    if cleaned != content:
        path.write_text(cleaned, encoding="utf-8")


def _remove_section(content: str) -> str:
    return re.sub(
        re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END) + r"\n?",
        "",
        content,
        flags=re.DOTALL,
    )


def _inject(path: Path, section: str) -> None:
    content = path.read_text(encoding="utf-8")
    content = _remove_section(content).rstrip("\n") + "\n"
    content += section
    path.write_text(content, encoding="utf-8")


def main() -> None:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    for name, (title, body) in SCREENS.items():
        (IMAGE_DIR / f"{name}.svg").write_text(render_svg(title, body), encoding="utf-8")
    for stem, names in REPORT_IMAGES.items():
        _inject(stem.with_suffix(".md"), "\n" + _markdown_section(stem, names))
        _strip_section(stem.with_suffix(".html"))
    print(f"{len(SCREENS)} görsel üretildi: {IMAGE_DIR}")


if __name__ == "__main__":
    main()
