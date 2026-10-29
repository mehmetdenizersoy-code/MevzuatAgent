"""Build a sanitized report and presentation addendum from the supplied MevzuAI outputs."""

from html import escape
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PRESENTATION = ROOT / "data/temp_reference/MevzuAI_Sunum.pptx"
SOURCE_REPORTS = (
    ROOT / "data/temp_reference/birlesik_mevzuat_uyum_risk_raporu_20261024_1710.html",
    ROOT / "data/temp_reference/remediation_farklari_top5_tur2_20261024_2000.html",
)
OUTPUT_PRESENTATION = ROOT / "docs/MevzuAI_Sunum_Guncel.pptx"
OUTPUT_MARKDOWN = ROOT / "docs/MevzuAI_Birlesik_Risk_ve_Remediation_Ozeti.md"
OUTPUT_HTML = ROOT / "docs/MevzuAI_Birlesik_Risk_ve_Remediation_Ozeti.html"
EXAMPLES_DIR = ROOT / "docs/examples"
ASSETS_DIR = ROOT / "docs/assets/mevuai_evidence"
BRAND_SVG = ROOT / "docs/assets/branding/softtech-logo.svg"
BRAND_PNG = ROOT / "docs/assets/branding/softtech-logo.png"
BRAND_LIGHT_SVG = ROOT / "docs/assets/branding/softtech-logo-light-background.svg"
BRAND_LIGHT_PNG = ROOT / "docs/assets/branding/softtech-logo-light-background.png"

NAVY = RGBColor(17, 34, 64)
NAVY_LIGHT = RGBColor(29, 54, 91)
TEAL = RGBColor(0, 175, 160)
CYAN = RGBColor(53, 190, 215)
GOLD = RGBColor(248, 188, 74)
RED = RGBColor(214, 87, 94)
INK = RGBColor(34, 48, 69)
MUTED = RGBColor(99, 115, 137)
PAPER = RGBColor(247, 249, 252)
WHITE = RGBColor(255, 255, 255)
PALE_BLUE = RGBColor(231, 240, 250)
PALE_GOLD = RGBColor(255, 246, 223)

CAPTURE_WIDTH = 1800
CAPTURE_HEIGHT = 740
CAPTURE_BG = "#101827"
CAPTURE_PANEL = "#182437"
CAPTURE_MUTED = "#9aabc1"
CAPTURE_WHITE = "#eef4fb"
CAPTURE_GREEN = "#71d7a1"
CAPTURE_RED = "#ff8989"
CAPTURE_CYAN = "#71d8e6"
CAPTURE_GOLD = "#ffd37a"

FINDINGS = [
    ("KRİTİK", 24),
    ("YÜKSEK", 23),
    ("ORTA", 21),
    ("DÜŞÜK", 9),
    ("BİLGİ", 5),
]

REMEDIATIONS = [
    (
        "RISK-C05",
        "Safir.Abex · Kimlik bilgisi",
        "Kod içindeki Basic-auth sabitini kaldırıp yapılandırma/secret store "
        "üzerinden okumak; mevcut credential rotasyonu ayrıca izlenmeli.",
    ),
    (
        "RISK-C08",
        "safir-online-sobe · Eşleşme ve log",
        "ZERO_CVV merchant eşleşmesini tam eşleşmeye çevirmek; PIN/F55 benzeri "
        "hassas trace alanlarını maskelemek.",
    ),
    (
        "RISK-C09",
        "acqua-dcc-monex · DCC teklif akışı",
        "İstek kimliğiyle idempotency sağlamak ve geçersiz kur değerlerini "
        "POS'a dönmeden önce reddetmek.",
    ),
    (
        "RISK-C10",
        "acqua-cassandra-data-archiver · Arşiv",
        "S3 yüklemesini nesne metadata/boyut doğrulamasıyla teyit etmeden "
        "kaynak kayıtlarını silmemek.",
    ),
    (
        "RISK-C11",
        "acqua-rrn-generator · Sayaç",
        "Cassandra LWT [applied] sonucunu denetlemek; başarısızlıkta sınırlı "
        "yeniden deneme ve açık hata üretmek.",
    ),
]


def _markdown() -> str:
    distribution = " · ".join(f"{count} {severity}" for severity, count in FINDINGS)
    lines = [
        "# MevzuAI — Birleşik Risk ve Remediation Özeti",
        "",
        "> Kaynak: 24.10.2026 tarihli birleşik mevzuat uyum/risk raporu ve "
        "remediation tur 2 fark raporu. Bu belge, verilen raporların güvenli "
        "yönetici özetidir; bağımsız yeniden tarama değildir.",
        "",
        "## Yönetici özeti",
        "",
        "| Ölçüm | Kaynak rapordaki sonuç |",
        "|---|---:|",
        "| Taranan depo | 35 |",
        "| Toplam bulgu | 82 |",
        f"| Bulgu dağılımı | {distribution} |",
        "| Depo bazında en yüksek risk | 17 kritik · 8 yüksek · 10 orta |",
        "| Mevzuat uyum değerlendirmesi | %67 (61 değerlendirme) |",
        "| Değerlendirme kırılımı | 41 uyumlu · 10 kısmi · 10 ihlal riski |",
        "| Doğrulanmalı etiketi | 9 |",
        "| Kaynak dayanağı | 13 RAG chunk · 9 DB-RAG atfı |",
        "",
        "Kapsam raporda Kanun 5464 ve Yönetmelik 11180 olarak belirtilmiştir. "
        "Önceki raporlar girdi alınmadan taze tarama yapıldığı raporlanmıştır.",
        "",
        "## Remediation tur 2",
        "",
        "Kullanıcı onayıyla beş kritik bulgu seçilmiştir. Fark raporu toplam "
        "**5 depo, 9 dosya, +89/-10 satır** değişikliği bildirir.",
        "",
        "| Bulgu | Alan | Özetlenen değişiklik |",
        "|---|---|---|",
    ]
    for finding_id, area, change in REMEDIATIONS:
        lines.append(f"| {finding_id} | {area} | {change} |")
    lines.extend(
        [
            "",
            "## Doğrulama ve açık işler",
            "",
            "- Fark raporunda 3 konu **Doğrulanmalı** olarak işaretlenmiştir; "
            "iş kararı, ortam konfigürasyonu veya istemci davranışı ek doğrulama ister.",
            "- C06 credential rotasyonu/vault işi; C12/C13 altyapı-konfigürasyon "
            "işi olarak bu turda kapsam dışı bırakılmıştır. C14/C15 sonraki tura "
            "ertelenmiştir.",
            "- Kaynak fark raporu bir PR dalı adı verir; ancak bu özet, testlerin "
            "geçtiğini veya GitHub PR'ın açıldığını doğrulamamaktadır.",
            "- Kaynak rapordaki credential/token örnekleri bu özet ve sunuma "
            "aktarılmamıştır. Credential rotasyonu ve Git geçmişi temizliği "
            "ayrı operasyonel işlerdir.",
            "",
            "## Yorumlama sınırı",
            "",
            "Rapor sayıları ve remediation açıklamaları verilen HTML belgelerinden "
            "aktarılmıştır; bu çalışma kaynak depoları yeniden taramadı, kod "
            "farklarını bağımsız test etmedi ve hukuki uygunluk görüşü sunmaz. "
            "Düzeltmeler merge edilmeden önce ilgili depo sahipleri, güvenlik "
            "ekibi ve mevzuat uzmanı tarafından doğrulanmalıdır.",
            "",
        ]
    )
    return "\n".join(lines)


def _html_report() -> str:
    finding_rows = "".join(
        f"<tr><th>{escape(finding_id)}</th><td>{escape(area)}</td>"
        f"<td>{escape(change)}</td></tr>"
        for finding_id, area, change in REMEDIATIONS
    )
    finding_distribution = "".join(
        f'<div class="distribution"><span>{escape(severity)}</span>'
        f"<strong>{count}</strong></div>"
        for severity, count in FINDINGS
    )
    return f"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MevzuAI — Birleşik Risk ve Remediation Özeti</title>
<style>
:root{{--navy:#112240;--teal:#00afa0;--ink:#223045;--muted:#637389;
--paper:#f7f9fc;--line:#dee5ee;--blue:#e7f0fa;--gold:#fff6df;}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--paper);color:var(--ink);
font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
main{{max-width:1120px;margin:36px auto;padding:0 22px 48px}}
header{{position:relative;background:var(--navy);color:white;padding:34px 190px 34px 38px;border-radius:18px}}
.brand{{position:absolute;right:28px;top:24px;width:132px;height:auto}}
.eyebrow{{color:#35bed7;font-weight:700;letter-spacing:.1em;text-transform:uppercase}}
h1{{font-size:30px;line-height:1.2;margin:8px 0}}
header p{{color:#d7e3f0;margin:8px 0 0}}
h2{{color:var(--navy);font-size:21px;margin:30px 0 12px}}
.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:20px}}
.card{{background:white;border:1px solid var(--line);border-radius:14px;padding:18px}}
.card strong{{display:block;font-size:30px;color:var(--navy)}}
.card span{{color:var(--muted);font-size:13px}}
.distribution-grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px}}
.distribution{{background:white;border:1px solid var(--line);padding:12px 14px;
border-radius:10px;display:flex;justify-content:space-between}}
.distribution span{{font-size:13px;color:var(--muted)}}
table{{width:100%;border-collapse:collapse;background:white;border-radius:12px;
overflow:hidden;border:1px solid var(--line)}}
th,td{{padding:13px 14px;text-align:left;vertical-align:top;border-bottom:1px solid var(--line)}}
thead th{{background:var(--navy);color:white}} tbody th{{white-space:nowrap;color:var(--navy)}}
.notice{{background:var(--gold);border-left:4px solid #f8bc4a;padding:15px 18px;
border-radius:8px}} .source{{color:var(--muted);font-size:13px}}
ul{{padding-left:22px}} li{{margin:7px 0}}
@media(max-width:760px){{.cards{{grid-template-columns:repeat(2,1fr)}}
.distribution-grid{{grid-template-columns:repeat(2,1fr)}} header{{padding:25px}}}}
@media print{{body{{background:white}}main{{margin:0;max-width:none}}header{{border-radius:0}}}}
</style>
</head>
<body><main>
<header>
<img class="brand" src="assets/branding/softtech-logo.svg" alt="Softtech logosu">
<div class="eyebrow">Yönetici özeti · 24 Ekim 2026</div>
<h1>Birleşik mevzuat uyumu ve depo risk analizi</h1>
<p>Kanun 5464 ve Yönetmelik 11180 kapsamındaki kaynak raporların güvenli özeti</p>
</header>
<section class="cards" aria-label="Özet ölçümler">
<div class="card"><strong>35</strong><span>Taranan depo</span></div>
<div class="card"><strong>82</strong><span>Toplam bulgu</span></div>
<div class="card"><strong>%67</strong><span>61 değerlendirmede uyum oranı</span></div>
<div class="card"><strong>9</strong><span>Doğrulanmalı etiketi</span></div>
</section>
<h2>Bulgu dağılımı</h2>
<div class="distribution-grid">{finding_distribution}</div>
<h2>Mevzuat değerlendirmesi</h2>
<p>61 hüküm-depo değerlendirmesinin 41'i uyumlu, 10'u kısmi ve 10'u ihlal riski
olarak raporlanmıştır. Depo bazında en yüksek risk dağılımı 17 kritik, 8 yüksek
ve 10 orta seviyedir. Kaynakta 13 RAG chunk ve 9 DB-RAG atfı kullanıldığı belirtilir.</p>
<h2>Remediation tur 2 — onaylanan beş kritik bulgu</h2>
<p>Fark raporu 5 depo, 9 dosya ve toplam +89/-10 satır değişikliği bildirir.</p>
<table><thead><tr><th>Bulgu</th><th>Alan</th><th>Düzeltme özeti</th></tr></thead>
<tbody>{finding_rows}</tbody></table>
<h2>Açık doğrulama ve operasyon işleri</h2>
<ul>
<li>Fark raporunda 3 konu “Doğrulanmalı” olarak işaretlenmiştir.</li>
<li>Credential rotasyonu/vault ve altyapı-konfigürasyon işleri kod farkından
ayrı takip edilmelidir; sonraki tur bulguları bu kapsamda değildir.</li>
<li>Kaynak rapor bir PR dalı belirtir; testlerin geçtiği veya GitHub PR'ın
açıldığı bu belgelerle doğrulanmamıştır.</li>
<li>Credential/token değerleri bu özete aktarılmamıştır. Rotasyon ve Git geçmişi
temizliği ayrı operasyonel takip gerektirir.</li>
</ul>
<p class="notice"><strong>Yorumlama sınırı:</strong> Bu özet, sağlanan HTML
raporlarındaki bilgileri düzenler. Bağımsız kod taraması, test çalıştırması veya
hukuki uygunluk değerlendirmesi değildir. Merge öncesinde depo sahipleri,
güvenlik ekibi ve mevzuat uzmanı doğrulamalıdır.</p>
<p class="source">Softtech logosu görsel amaçlı kullanılmıştır; bu proje Softtech
tarafından destekleniyor veya resmen onaylanıyor anlamına gelmez.</p>
<p class="source">Kaynaklar: birlesik_mevzuat_uyum_risk_raporu_20261024_1710.html;
remediation_farklari_top5_tur2_20261024_2000.html.</p>
</main></body></html>"""


def _capture_font(size: int, bold: bool = False):
    font_path = (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
        if bold
        else "/System/Library/Fonts/Supplemental/Arial.ttf"
    )
    try:
        return ImageFont.truetype(font_path, size)
    except OSError:
        return ImageFont.load_default(size=size)


def _create_capture(
        filename: str,
        title: str,
        subtitle: str,
        lines: list[tuple[str, str]],
        footer: str,
) -> Path:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    output = ASSETS_DIR / filename
    image = Image.new("RGB", (CAPTURE_WIDTH, CAPTURE_HEIGHT), CAPTURE_BG)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (24, 20, CAPTURE_WIDTH - 24, CAPTURE_HEIGHT - 20),
        radius=22,
        fill=CAPTURE_PANEL,
        outline="#35445a",
        width=2,
    )
    for x, color in ((54, "#ff6b6b"), (88, "#ffc857"), (122, "#5bd49b")):
        draw.ellipse((x, 43, x + 17, 60), fill=color)

    draw.text((168, 37), "MEVZUATAGENT · KANIT GÖRSELİ", font=_capture_font(22, True), fill=CAPTURE_MUTED)
    draw.text((60, 100), title, font=_capture_font(36, True), fill=CAPTURE_WHITE)
    draw.text((62, 153), subtitle, font=_capture_font(22), fill=CAPTURE_CYAN)

    y = 214
    for text, color in lines:
        draw.text((68, y), text, font=_capture_font(22), fill=color)
        y += 38
    draw.line((58, CAPTURE_HEIGHT - 86, CAPTURE_WIDTH - 58, CAPTURE_HEIGHT - 86), fill="#35445a", width=2)
    draw.text(
        (62, CAPTURE_HEIGHT - 70),
        footer,
        font=_capture_font(17),
        fill=CAPTURE_GOLD,
    )
    image.save(output, optimize=True)
    return output


def _create_evidence_captures() -> dict[str, Path]:
    captures = {
        "setup": _create_capture(
            "kurulum_asamalari.png",
            "macOS kurulum akışı",
            "Görsel, install.sh içindeki gerçek adım sırasından oluşturulmuştur",
            [
                ("$ ./install.sh", CAPTURE_GREEN),
                ("01  macOS, Git ve Python 3.10+ ön koşullarını denetle", CAPTURE_WHITE),
                ("02  .venv sanal ortamını oluştur; bağımlılıkları yükle", CAPTURE_WHITE),
                ("03  JSON yapılandırmasını ve çalışma klasörlerini doğrula", CAPTURE_WHITE),
                ("04  Ollama / model kurulumu için ayrı kullanıcı onayı al", CAPTURE_WHITE),
                ("05  Mevzuatı indirip yerel BM25 indeksi oluşturmayı sor", CAPTURE_WHITE),
                ("06  repo_link.json depolarını klonlamak için onay iste", CAPTURE_WHITE),
                ("07  Uygulama ve pytest komutlarını göster", CAPTURE_WHITE),
            ],
            "KAYNAK: install.sh · Şematik ekran görselidir; gerçek kurulum oturumu kaydı değildir.",
        ),
        "repository": _create_capture(
            "sentetik_test_deposu.png",
            "Sentetik test deposu",
            "Git'te izlenen gerçek fixture yapısı · main @ a14df30",
            [
                ("mevzuatagent-test-fixtures/", CAPTURE_CYAN),
                ("├── README.md", CAPTURE_WHITE),
                ("├── demo1/  payment_rules.py · scan_result.json · remediation_plan.md", CAPTURE_WHITE),
                ("│   └── scan_result.md / scan_result.html", CAPTURE_WHITE),
                ("└── demo2/  payment_rules.py · scan_result.json · remediation_plan.md", CAPTURE_WHITE),
                ("    └── scan_result.md / scan_result.html", CAPTURE_WHITE),
                ("2 demo · toplam 10 sentetik bulgu · TEST_FIXTURE_NOT_LAW", CAPTURE_GOLD),
                ("YALNIZCA TEST İÇİNDİR — gerçek mevzuat tespiti değildir.", CAPTURE_RED),
            ],
            "KAYNAK: data/test_repositories/mevzuatagent-test-fixtures · Git ls-files / README",
        ),
        "diff": _create_capture(
            "remediation_diff_ve_test.png",
            "Remediation diff ve kabul testi",
            "Gerçek fixture raporundan alınan örnek değişiklikler · test: 2 passed",
            [
                ("demo1/payment_rules.py", CAPTURE_CYAN),
                ("-    return value", CAPTURE_RED),
                ("+    return '*' * max(0, len(value) - visible) + value[-visible:]", CAPTURE_GREEN),
                ("-    return amount >= 0", CAPTURE_RED),
                ("+    return amount > 0", CAPTURE_GREEN),
                ("$ python -m pytest -q", CAPTURE_MUTED),
                ("..                                                                       [100%]", CAPTURE_GREEN),
                ("2 passed · fixture kabul testleri · yalnız test amaçlı", CAPTURE_GOLD),
            ],
            "KAYNAK: data/e2e/reports/remediation + data/e2e/reports/tests",
        ),
        "pr": _create_capture(
            "pr_akisi_yerel_prova.png",
            "PR akışı — yerel prova",
            "GitHub ekranı değildir · gerçek PR oluşturulmamıştır",
            [
                ("$ git --git-dir=data/e2e/pr-origin.git branch -a", CAPTURE_MUTED),
                ("  main", CAPTURE_WHITE),
                ("* mevzuatagent/remediation-c4b060c129", CAPTURE_CYAN),
                ("$ gh pr create  # fake-bin/gh test ikilisi", CAPTURE_MUTED),
                ("PR CLI çağrısı yerel test stub'ına yönlendirildi", CAPTURE_WHITE),
                ("Yerel bare remote / sahte gh ile entegrasyon provası", CAPTURE_GREEN),
                ("Gerçek GitHub PR: OLUŞTURULMADI", CAPTURE_RED),
                ("Fixture testidir; GitHub'da PR numarası/URL'si yoktur.", CAPTURE_GOLD),
            ],
            "KAYNAK: data/e2e/pr-origin.git + data/e2e/fake-bin/gh · canlı GitHub işlemi yok",
        ),
    }
    return captures


def _ensure_softtech_logo() -> Path:
    if BRAND_PNG.is_file():
        return BRAND_PNG
    if not BRAND_SVG.is_file():
        raise FileNotFoundError(f"Resmî logo SVG'si bulunamadı: {BRAND_SVG}")

    BRAND_PNG.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["sips", "-s", "format", "png", str(BRAND_SVG), "--out", str(BRAND_PNG)],
        check=True,
        capture_output=True,
        text=True,
    )
    return BRAND_PNG


def _ensure_light_background_logo() -> Path:
    if not BRAND_SVG.is_file():
        raise FileNotFoundError(f"Resmî logo SVG'si bulunamadı: {BRAND_SVG}")
    light_logo = BRAND_SVG.read_text(encoding="utf-8").replace(
        'fill="white"', 'fill="#112240"'
    )
    BRAND_LIGHT_SVG.write_text(light_logo, encoding="utf-8")
    subprocess.run(
        [
            "sips",
            "-s",
            "format",
            "png",
            str(BRAND_LIGHT_SVG),
            "--out",
            str(BRAND_LIGHT_PNG),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return BRAND_LIGHT_PNG


def _set_shape_text(shape, text: str, size: int, color: RGBColor, bold: bool = False):
    frame = shape.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.margin_left = Inches(0.08)
    frame.margin_right = Inches(0.08)
    frame.margin_top = Inches(0.04)
    frame.margin_bottom = Inches(0.03)
    frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    for index, line in enumerate(text.split("\n")):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.text = line
        paragraph.font.name = "Aptos"
        paragraph.font.size = Pt(size)
        paragraph.font.bold = bold
        paragraph.font.color.rgb = color


def _add_text(slide, text, x, y, width, height, size, color=INK, bold=False):
    shape = slide.shapes.add_textbox(
        Inches(x), Inches(y), Inches(width), Inches(height)
    )
    _set_shape_text(shape, text, size, color, bold)
    return shape


def _add_box(slide, x, y, width, height, fill):
    shape = slide.shapes.add_shape(
        1, Inches(x), Inches(y), Inches(width), Inches(height)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.fill.background()
    return shape


def _new_slide(presentation, eyebrow, title, subtitle):
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    background = slide.background.fill
    background.solid()
    background.fore_color.rgb = PAPER
    _add_text(slide, eyebrow, 0.65, 0.3, 12.0, 0.25, 10, TEAL, True)
    _add_text(slide, title, 0.65, 0.65, 12.0, 0.55, 24, NAVY, True)
    _add_text(slide, subtitle, 0.68, 1.22, 12.0, 0.42, 11, MUTED)
    return slide


def _tailor_source_slides(presentation):
    replacements = {
        "Analizinizi kanıta dayandıran iş analisti ajanı":
            "Kartlı ödeme sistemleri için mevzuat uyumu ve kod tarama ajanı",
        "İş-Kod-Çözüm Analizi": "Onaylı Düzeltme",
        "+ Bulgu Düzeltme: analiz sonlarında önerilen seçenek; daha önce üretilmiş raporlardan da çalışır.":
            "+ Remediation: en fazla iki öncelikli bulgu; izole worktree, ayrı test ve PR onayları.",
        "Hassas veriler (kart numarası, şifre, token) rapora yazılmadan otomatik gizlenir.":
            "Gerçek kart verisi kullanmayın; otomatik maskeleme garantisi yoktur.",
        "Kararlar sizin: ajan her adımda sorar, onaysız işlem yapmaz  ·  v25.10.2026":
            "Kararlar sizin: ajan her adımda sorar, onaysız işlem yapmaz  ·  v29.10.2026",
        "Neden MevzuAI?": "Neden ödeme sistemlerinde MevzuAI?",
        "Doküman ve mevzuat yükü artıyor: her yeni duyuru, her kanun değişikliği kod üzerinde etki analizi istiyor.":
            "Ödeme mevzuatı ve teknik gereksinimler değişir: kod üzerindeki etkiyi izlemek gerekir.",
        "Etkisini kodda bulmak zaman alıyor: elle aramak uzun sürer, atlanan nokta bırakır.":
            "Yetkilendirme, iade ve mutabakat akışları farklı servislerde olduğundan manuel arama eksik kalabilir.",
        "Raporlar kanıtsız olabiliyor: 'muhtemelen burada' cümlesi doğrulanabilir değil.":
            "Bulgular dosya/satır kanıtı ve mevzuat kaynak/sayfa atfıyla doğrulanabilir olmalıdır.",
        "Hassas veri riski: analiz sırasında kart numarası veya şifre rapora sızabilir — bu ayrı bir güvenlik olayıdır.":
            "Kart verisinin analiz girdisine veya rapora sızması ciddi bir risktir.",
        "Düzeltme süreci uzuyor: bulgudan Pull Request'a giden yol elle işliyor.":
            "Bulgu, düzeltme, test ve PR adımları kontrollü ve ayrı onaylı ilerlemelidir.",
        "Dokümanı, mevzuatı veya olay kaydını verirsiniz — ajan kod üzerinde etkiyi uçtan uca çıkarır.":
            "Mevzuat PDF'lerini yerel RAG indeksine hazırlar; seçilen depoyu onaydan sonra inceler.",
        "Tarama önce otomatik araçlarla yapılır; ajan her eşleşmeyi kod bağlamında tek tek doğrular.":
            "Tarama tahmini dosya kapsamı, bağlam tokenları ve ölçülen model hızından yaklaşık süre çıkarır.",
        "Her sonuç kanıtlıdır: hangi dosyanın hangi satırı, hangi doküman bölümü dayanak gösterilir.":
            "Bulguda dosya/satır kanıtı ve modele sunulmuş mevzuat kaynak/sayfa atfı gösterilir.",
        "Hassas veriler rapor yazılmadan önce otomatik gizlenir — ayrı çaba istemez.":
            "Gerçek kart verisi içeren depolarda kullanmayın; otomatik veri maskeleme garantisi yoktur.",
        "Dilerseniz düzeltmeye de geçer: kritik bulgulara kod farkı üretir, onayınızla Pull Request açar.":
            "En fazla iki öncelikli bulgu izole dalda düzeltilir; test ve PR için ayrıca onay gerekir.",
        "Kısacası: ajan analizi hızlandırır, kanıtla dayandırır ve gizliliği korur — karar her zaman sizde kalır.":
            "MevzuatAgent ödeme işleyen ürün değil; yerel kod incelemesi ve kullanıcı kontrollü remediation aracıdır.",
        "Kodun güvenlik ve dolandırıcılık durum raporu":
            "Kartlı ödeme kodunda güvenlik, işlem bütünlüğü ve veri riski",
        "Bulgular önem sırasına dizilir; rapor yazılmadan hassas veriler gizlenir.":
            "Bulgular önem sırasına dizilir; hassas veri içeren depolarda taramayı başlatmayın.",
        "Gerçek ölçek: son 35-repolık taramada 24 kritik · 23 yüksek · 21 orta; uyum oranı %67.":
            "Sağlanan 35-depo raporundaki ölçüm: 24 kritik · 23 yüksek · 21 orta; bu projede yeniden taranmadı.",
        "Hukuki gereklilik kodda ne kadar sağlanmış? Tek tek denetim":
            "Seçilen mevzuat metni ile ödeme kodu arasında kanıt odaklı inceleme",
        "İstek: kanun/yönetmelik belgesi (dosya, bağlantı veya yapıştırılan metin) + repo.":
            "Girdi: mevzuat PDF'i ve kullanıcı onaylı Git repo; branch, commit ve kapsam belirlenir.",
        "Ajan hükümleri numaralar (KANUN-17, YON-21 gibi) ve konu gruplarına ayırır: sözleşme, komisyon/kesinti, fiş, iade, terminasyon...":
            "PDF sayfaları metne çıkarılır; örtüşen parçalar kaynak ve sayfa bilgisiyle yerel RAG indeksine alınır.",
        "Her hüküm kodu birden çok yöntemle aranır: alan adları, işleyiş akışı, veritabanı/yapılandırma tanımları.":
            "Kodla ilgili parçalar BM25 ile bulunur ve seçilen kaynak dosyalarıyla yerel modele verilir.",
        "Negatif kontroller zorunludur: yasak bir işlem kod ile üretilmeye çalışılabilir mi? (ör. müşteriden ek ücret alınabilir mi?)":
            "Model bulgusu, gerçek kod satırı ve modele sunulmuş mevzuat atfı eşleşmiyorsa reddedilir.",
        "Her hükme karar: UYUMLU (kanıtıyla) / UYUMSUZ / EKSİK / KODDA YOK (sessizce uyumlu sayılmaz) / PARAMETRİK (kurum kararına bağlı).":
            "Rapor; depo/commit, model, kapsam, tarih, dosya sonuçları ve doğrulanmış bulguları gösterir.",
        "En kritik ihlal sınıfı: müşteriye maliyet/ek ücret aktarımı — önce kontrol edilir.":
            "Bulgu; önem, dosya/satır, kod kanıtı, kaynak/sayfa, açıklama ve öneri içerir.",
        "Uyum oranı (%), pozitif kontroller ve kapsam dışı hükümler ayrı listelenir.":
            "Kısmi tarama, okunamayan dosya ve kanıt doğrulama hataları sınırlama olarak raporlanır.",
        "Her karar; hüküm metni + kod konumu ile dayanır. Kod okunamayan bölüm 'Doğrulanmalı' etiketlenir.":
            "Bulgu bulunmaması mevzuata tam uyum kararı değildir; incelenen kapsam sınırlı olabilir.",
        "Rapor sonunda öncelikli düzeltme yol haritası gelir.":
            "Hukuki yorum ve iş kararı, mevzuat uzmanı ve ödeme ürünü sorumlularınca doğrulanmalıdır.",
        "1) Raporu verirsiniz — az önce üretilmiş olsun ya da haftalar önce kaydedilmiş olsun; fark etmez, kaynak rapor dosyasıdır.":
            "1) Tarama raporundaki kanıtlı bulgular listelenir; en yüksek öncelikli en fazla iki bulgu seçilir.",
        "2) Ajan kanıtlı bulguları sıralar; 'kaç tanesini düzeltelim?' diye sorar (önerilen: en kritik 5).":
            "2) Kanıt ve öneri gösterilir; kullanıcı kod değişikliğinin uygulanmasını ayrıca onaylar.",
        "3) Her bulgu için bugünkü kod okunur, düzeltme tasarlanır, fark raporu hazırlanır: öncesi/sonrası ve satır farkı.":
            "3) Onaylı değişiklikler kaynak daldan ayrı bir Git worktree/branch içinde uygulanır.",
        "4) Fark raporunu görürsünüz; 'Pull Request açmayı onaylıyor musunuz?' sorusuna 'evet' demeden hiçbir kod alanına yazılmaz.":
            "4) Test çalıştırmak için yeniden onay alınır; test çıktısı ayrı Markdown ve HTML raporlanır.",
        "Onayla: düzeltmeler ayrı bir düzeltme dalına uygulanır → kayıt → gönderim → Pull Request; adresi size bildirilir.":
            "Test başarılıysa diff ve test sonucu sunulur; kullanıcı son onayı verirse GitHub PR oluşturulur.",
        "Onaysız: ajan yalnız prova yapar — koda dokunulmaz.":
            "Kaynak dal değiştirilmez; otomatik commit, merge veya zorla-gönderim yapılmaz.",
        "'Aynı bulgulara ikinci PR' engellenir: açılan her PR kayda geçer.":
            "Değişiklik dosyaları seçilen öncelikli bulgularla eşleşmelidir; kaynak repo temiz olmalıdır.",
        "Sınırlar: ana dala doğrudan yazma yok, zorla-gönderim yok, birleştirme yok.":
            "Test başarısız veya zaman aşımına uğrarsa PR akışı başarılı sayılmaz.",
        "Kanıtı olmayan bulgulara düzeltme üretilmez — 'elle düzeltme' listesine geçer.":
            "PR için GitHub CLI (`gh`), yetki ve açık son kullanıcı onayı gerekir.",
        "Mekanik güvence: kod yazma onayı betik içinde zorunludur — ajanın sözü değil, aracın kuralı.":
            "Kod değişikliği, test ve PR ayrı onay kapılarıdır; biri diğerine izin vermez.",
        "2\nBulgu sayısı": "2\nBulgu seç",
        "3\nFark raporu": "3\nUygula onayı",
        "4\nPR onayı": "4\nTest onayı",
        "5\nUygula + PR": "5\nPR onayı",
        "Çıktılar — Kurumsal Format, Çift Dosya":
            "Çıktılar — Tarama ve remediation için ayrı raporlar",
        "Her rapor bilgi (yazılabilir) + HTML (sunulabilir) olarak kaydedilir":
            "Tarama ve remediation sonuçları Markdown + HTML biçiminde üretilir",
        "Uyum + Risk Birleşik Raporu\nÜst bant ve özet rozetleri sabittir: her rapor aynı kalıpta üretilir — 35 repo, 24 kritik bulgu örneği.":
            "Tarama Raporu\nDepo/commit, model, kapsam, dosya-satır kanıtı, mevzuat atfı ve sınırlamalar.",
        "Düzeltme Fark Raporu\nBulgu başına öncesi/sonrası ve renkli satır farkı — 5 bulguluk gerçek üretim, onaya hazır.":
            "Remediation Raporu\nEn fazla iki bulgunun izole worktree diff'i; test ve PR sonucu ayrı raporlanır.",
        "HTML, bilgi dosyasından yalnız görünüm üretir: içerik değişmez. Rapor adı deseni sabittir — <konu>_<tür>_raporu_<tarih_saat>.":
            "Tarama, diff ve test raporları ayrı HTML/Markdown dosyalarıdır; yalnızca gerçekten çalıştırılan adımlar raporlanır.",
        "Tarama başlamadan ajan kapsamı ve maliyeti ölçer; onayınız olmadan tarama başlamaz":
            "Kapsam ve yaklaşık token/süre tahmini tarama öncesi gösterilir; yerel kullanım için parasal maliyet hesaplanmaz.",
        "Pilot ölçüm — orta boy tek repo": "Tahminin girdileri",
        "Kapsam: 178 dosya · 15.051 satır\nUygulanacak tarama: 66 bilinen desen\nOtomatik tarama süresi: yaklaşık 1 saniye\nAnaliz ve rapor: yaklaşık 15-20 dakika\nBağlam maliyeti: düşük (yalnız eşleşen bölümler okunur)":
            "Git'te izlenen kaynak dosyaları ve kullanıcı dosya sınırı\n"
            "Kod sorgusuyla BM25 RAG'den bulunan mevzuat parçaları\n"
            "Yaklaşık giriş tokenı + dosya başına çıktı varsayımı\n"
            "Tahmini toplam token ÷ yerel model hız ölçümü = yaklaşık süre\n"
            "Yerel Ollama için parasal maliyet üretilmez",
        "Tam kapsam — 36 repolık tarama": "Model ölçümü ve tahmin sınırları",
        "Kapsam: 5.277 dosya · 1 milyonun üzerinde satır\nUygulanacak tarama: 66 desen × repo + mevzuat hükümleri\nOtomatik tarama süresi: yaklaşık 1 dakika\nAnaliz ve rapor: yaklaşık 20-25 dakika\nBağlam maliyeti: ölçülür ve önceden bildirilir":
            "Kurulu modeller kısa bir Ollama throughput benchmark'ından geçer\n"
            "Benchmark hızı ölçer; yanıt kalitesini veya mevzuat doğruluğunu ölçmez\n"
            "Token hesabı yaklaşık karakter/token varsayımına dayanır\n"
            "Kısmi dosya kapsamı ve RAG eşleşmeleri süreyi etkiler\n"
            "Repo, branch/commit, model ve kapsam onayı olmadan tarama başlamaz",
        "Nasıl çalışır?\n1) Ajan depoyu ve dokümanı sayar (hangi dosyalar, kaç satır)   →   2) uygulanacak tarama sayısını hesaplar\n3) Süre ve maliyet tahminini tablo olarak sunar   →   4) Sorar: 'Taramaya bu kapsamla başlayayım mı? (evet / daralt / hayır)'\nSayılar gerçek ölçümdür; tahmini süre ve maliyet başında '~' ile belirtilir. Kapsam büyük gelirse 'daralt' dersiniz; envanter yeniden hesaplanır ve tablo tekrar sunulur — siz 'evet' deyene kadar.":
            "Tahmin nasıl sunulur?\n1) İzlenen repo ve seçilen dosya sınırı belirlenir   →   2) ilgili mevzuat parçaları getirilir\n3) Token varsayımı ve model hızıyla yaklaşık süre hesaplanır   →   4) kullanıcı model/kapsamı onaylar\nTahmin yaklaşık süre ve token miktarıdır; parasal ücret ya da model kalitesi garantisi değildir.",
        "2 — Bülten (Doküman) Etki Analizi": "2 — Mevzuat RAG ve belge hazırlığı",
        "Yeni duyurunun kod üzerindeki etkisi, madde madde":
            "PDF mevzuatından kaynak ve sayfa bilgili yerel arama indeksi",
        "Ne istersiniz / ajan ne yapar": "Belgeyi RAG için hazırlama",
        "İstek: doküman dosyası + isterseniz ilgili repo.\nAjan dokümanı doğal yapısından maddelere ayırır (M-01, M-02...).\nRepo verdiyseniz her maddeyi kodda arar: bugünkü durum ne, doküman ne istiyor, fark nerede?\nMadde listesi ve etki tablosunu önce size sunar; onayınız olmadan rapora geçmez.":
            "Kaynak: kullanıcı tarafından sağlanan `mevzuat_link.json` PDF bağlantıları.\n"
            "PDF sayfalarındaki metin çıkarılır; kaynak ve sayfa bilgisi saklanır.\n"
            "Metin yaklaşık 1.200 karakterlik, örtüşmeli parçalara bölünür.\n"
            "`chunks.jsonl` ve `manifest.json` yerel RAG çıktılarıdır.",
        "Her madde için ne raporlanır": "Tarama sırasında retrieval",
        "Dokümanın istediği değişiklik: teknik özet + geçerlilik tarihi + aciliyet — tarihler asla atlanmaz.\nBugünkü durum (dosya/fonksiyon/satır) ve olması gereken, adım adım.\nEtkilenen bileşenler tablosu: kod / yapılandırma / veri / test × risk × öncelik.\nYapılmazsa ne olur: hangi işlem nasıl bozulur?\nTest önerileri + efor tahmini (küçük/orta/büyük).\nRapor sonunda: öncelikli liste + en riskli 3 bileşen + sürüm önerisi + etkilenmeyen alanlar.":
            "Dosya adı ve kod metni, ilgili mevzuat parçalarını aramak için kullanılır.\n"
            "BM25 anahtar kelime araması eşleşen chunk'ları kaynak/sayfa ile döndürür.\n"
            "İlgili bağlam ve sınırlı kod içeriği yerel Ollama modeline verilir.\n"
            "Eşleşen mevzuat bulunmazsa dosya modele gönderilmez.\n"
            "Arama leksikaldir; embedding, OCR ve mevzuat güncellik garantisi yoktur.\n"
            "Atıf ve hüküm yorumu uzman tarafından doğrulanmalıdır.",
        "1\nDoküman seç": "1\nKaynak seç",
        "3\nRepo?": "3\nRAG indeks",
        "4\nMadde analizi": "4\nMevzuat ara",
        "4 — İş-Kod-Çözüm Analizi": "4 — Kartlı ödeme akışındaki risk alanları",
        "Olay/Jira/log kaydından kök nedene ve çözüm önerisine":
            "Teknik kontrol noktalarını seçilen mevzuat ve kod kanıtıyla birlikte incele",
        "İnceleme": "Ödeme yaşam döngüsünde örnek kontroller",
        "İstek: olay kaydı, Jira kaydı, log çıktısı veya iş dokümanı + repo.\nAjan 'hangi kaydı işleyelim?' diye sorar; onayınızla seçer.\nLog'tan hata kodu tablosu çıkarır: hangi kod kaç kere, hangi zaman aralığında.\nKodda aynı hata noktalarını arar; olay zamanlarını akışla eşler.\nVarsa veritabanı prosedür tanımları da incelenir (bağlantı yok — yalnız tanım metni).":
            "Ödeme başlatma ve yetkilendirme: merchant, tutar, para birimi ve kanal doğrulaması.\n"
            "Timeout/tekrar deneme: idempotency, duplicate charge ve reversal davranışı.\n"
            "Capture, iade ve mutabakat: işlem referanslarının doğru ilişkilendirilmesi.\n"
            "Kart verisi/token/kimlik bilgisi: depolama ve log kullanımının incelenmesi.\n"
            "3DS, gateway, acquirer ve issuer entegrasyonlarında hata/timeout akışları.",
        "Çözüm ve sınır": "Bulguyu raporlama ve doğrulama sınırı",
        "Kök neden analizi: birincil neden ve katkılar, kanıtla ayrılır.\nÇözüm önerisi kod farkı biçiminde: neyin nereden kaldırılıp/ekleneceği.\nTest önerisi: değişikliği doğrulayacak senaryolar.\nÖNEMLİ SINIR: ajan kodu değiştirmez — öneriyi üretir, onayınız olmadan uygulamaz.\nYalnız log verdiyseniz: desen + muhtemel bileşen verilir; 'kod doğrulaması gerekli' notu düşülür.\nHer çıkarım kanıt taşır: hangi log satırı, hangi kod satırı, hangi doküman bölümü.":
            "Bu başlıklar teknik inceleme sorularıdır; kaynak olmadan mevzuat ihlali sayılmaz.\n"
            "Raporlanan bulgu dosya/satır kod kanıtı ve sunulmuş mevzuat kaynağı taşımalıdır.\n"
            "Kanıt/atıf doğrulamasından geçmeyen model çıktısı bulgu olarak kabul edilmez.\n"
            "İş kuralı, runtime konfigürasyonu ve kurum uygulaması ayrıca teyit edilir.\n"
            "Gerçek kart sahibi verisiyle tarama yapmayın; otomatik maskeleme garantisi yoktur.\n"
            "Düzeltme, test ve PR için birbirinden bağımsız kullanıcı onayı gerekir.",
        "1\nKayıt seç": "1\nKod alanı",
        "2\nRepo?": "2\nMevzuat",
        "3\nHata tablosu": "3\nAkış analizi",
        "5\nKök neden": "5\nKanıt",
        "Temiz Başlangıç — Sıfırla ve Yeniden Tara":
            "Ayrı Onay Kapıları — Tarama, Remediation, Test, PR",
        "Ortamı sıfırlamak işleri bozmaz; döngü güvenli ve ölçülüdür":
            "Her adım ayrı onay ister; bir aşamadaki onay sonraki işlemlere aktarılmaz.",
        "Sıfırlama akışı (plan → onay → çalıştırma)": "Tarama ve düzeltme için onay akışı",
        "1) 'Sıfırla' derseniz ajan ÖNCE neyin silineceğini listeler: doküman hafızası, raporlar, geçici kopyalar, kayıtlar — hiçbir şey silmez.":
            "1) Tarama: depo, branch/commit, dosya sınırı, tahmin ve model kullanıcıya gösterilir.",
        "2) Planı okursunuz; onayınız olmadan silme başlamaz.":
            "2) Remediation: en fazla iki bulgu ve değişiklik diff'i kullanıcıya sunulur.",
        "3) Onayla: ajanın ürettiği her şey temizlenir; kod deponuz, şablonlar, araçlar ve depo kayıtları korunur.":
            "3) Kullanıcı kod yazma izni verirse değişiklik ayrı Git worktree/branch içinde uygulanır.",
        "4) Ortam hazır — yeni tarama güncel koddan, sıfırdan yürür.":
            "4) Test ve ardından GitHub PR için ayrı onay kapıları bulunur.",
        "Son ölçüm: ~430 MB üretilmiş veri, 20 kalem, tek onayla temizlendi.":
            "Onay reddedilirse adım durur; hata, başarısız test veya zaman aşımı gizlenmez.",
        "Sıfırlama sonrası pilot tarama (gerçek)": "Üretim sınırları ve kullanıcı sorumluluğu",
        "Depo yeniden çalışma kopyası alındı: güncel sürüm dalı, en yeni iş kaydı.\nTahmin sunuldu: 178 dosya · 15.051 satır · 66 desen · ~1 sn tarama.\nTarama sonucu: bilinen desenlerde temiz — önceki turda düzeltilmiş noktalar yayında olarak doğrulandı.\nYapılandırmada 1 sinyal: gizli-değer benzeri satır — 'Doğrulanmalı' etiketiyle rapora girdi (ajan karar vermedi, kanıtı bildirdi).\nBu döngü, düzeltmelerin gerçekten yayında olduğunu kanıtlar: temiz tarama = başarılı düzeltme.":
            "Tarama kaynak kodunu ve eşleşen mevzuat parçalarını yerel Ollama servisine gönderir.\n"
            "Kodda gerçek kart verisi, CVV/PIN, kimlik bilgisi veya sır bulunmamalıdır.\n"
            "Uygulama canlı ödeme sistemini çağırmaz; runtime davranışı ve konfigürasyon eksik kalabilir.\n"
            "Kısmi tarama veya bulgu çıkmaması tam uyumluluk kararı değildir.\n"
            "Uzman incelemesi, test ve PR onayları insan sorumluluğundadır.",
        "1\nSıfırla": "1\nKapsam",
        "2\nPlan gör": "2\nTahmin",
        "3\nOnayla": "3\nRemediate",
        "4\nTemiz ortam": "4\nTest",
        "5\nTaze tarama": "5\nPR onayı",
        "Nasıl Kullanılır? — Örnek Talepler": "Nasıl Kullanılır? — Menüyle Uçtan Uca Akış",
        '"C:\\repos\\odeme-gateway için risk raporu çıkar"\n"şu repoyu tara: https://.../repo.git"':
            "`mevzuat_link.json` içindeki PDF'leri indirip RAG indeksini kurun.\n"
            "`manifest.json` içinde kaynak, sayfa ve indeksleme uyarılarını inceleyin.",
        '"bultenler klasöründeki yeni duyuruyu analiz et"\n"bu dokümanın etkisini odeme reposuna bakarak çıkar"':
            "`repo_link.json` depolarını gözden geçirin; klonlama için kullanıcı onayı verin.\n"
            "Yerel depoda branch/commit ve Git çalışma ağacını kontrol edin.",
        '"mevzuat klasöründeki yönetmeliğe göre odeme-gateway reposunu denetle"\n"bu kanunun metnini repoyla karşılaştır"':
            "Tarama menüsünde depo ve dosya sınırını seçin; model başına tahmini görün.\n"
            "Kapsamı ve modeli onayladıktan sonra taramayı başlatın.",
        "İş-Kod-Çözüm": "4 · HTML/Markdown rapor",
        '"business/log altındaki hatayı incele, kök nedeni bul"\n"SISP-1234 kaydını incele, çözüm öner"':
            "Bulguları dosya/satır, kod kanıtı ve mevzuat kaynak/sayfa ile inceleyin.\n"
            "Sınırlamaları okuyun; bulgu yokluğu tam uyumluluk değildir.",
        "Bulgu Düzeltme": "5 · Remediation ve PR",
        '"bu raporun en kritik 5 bulgusunu düzelt, PR aç"\n"raporları listele, geçen haftakinden düzeltme başlat"':
            "En fazla iki öncelikli bulguyu seçip kod değişikliğini ayrıca onaylayın.\n"
            "Test ve GitHub PR için ayrı onay verin; sonucu HTML raporlardan doğrulayın.",
        "Talebiniz kapsam dışıysa ajan size dört işten uygun olana yön verir.":
            "Uygulama Türkçe terminal menüsüdür; serbest biçimli sohbet arayüzü sunmaz.",
        "Yardımcı Araçlar — 17 Yardımcı, Tek Disiplin":
            "Uygulama Bileşenleri — LangChain, Yerel Ollama, HTML/Markdown",
        "Her araç yalnız ölçer, tarar, düzenler veya biçimlendirir; hiçbiri karar vermez":
            "İndirme, tarama, dosya değişikliği, test ve PR ayrı kullanıcı onaylarına bağlıdır.",
        "Belge Girişi": "Yapılandırma",
        "PDF ve belge dosyalarını ilgili klasörden alır; tarih damgalı benzersiz kopya üretir, üzerine yazar mı diye sormaz.":
            "`mevzuat_link.json` ve `repo_link.json` içeriğini doğrular.",
        "Belge Okuyucu": "PDF İndirme",
        "PDF/DOCX belgelerini okunabilir metne çevirir; taranmış görüntü sayfalarda 'elle aktarım gerekli' uyarısı verir.":
            "Kullanıcının seçtiği mevzuat bağlantılarındaki PDF'leri indirir.",
        "Mevzuat Girişi": "RAG Parçalama",
        "Kanun ve yönetmelik ekleme, indirme ve sayfa tarama işlemlerinin tek kapısı; kurumsal ağ ayarlarıyla güvenli çalışır.":
            "PDF sayfalarını örtüşen chunk'lara böler; kaynak/sayfa metadata'sını korur.",
        "İş Kaydı": "BM25 Arama",
        "Olay kaydı, Jira kaydı ve log çıktılarını düzenli klasörlere yerleştirir; işlenen belgeleri deftere geçirir.":
            "Mevzuat parçalarını leksikal olarak arar; embedding veya OCR kullanmaz.",
        "Kayıt Yöneticisi": "Depo Klonlama",
        "Analiz ve işlenen defterlerini JSON olarak tutar; defter yalnız bilgilendirmedir, akışı asla engellemez.":
            "Depoları yalnız açık kullanıcı onayından sonra yerel çalışma alanına alır.",
        "Depo Yöneticisi": "Model Havuzu",
        "Depo keşfi ve onaylı indirme/güncelleme yazışması; commit'lenmemiş değişiklikli depoda yazma işlemi kendiliğinden durur.":
            "Yerel Ollama'da kurulu modelleri listeler ve kısa throughput ölçümü yapar.",
        "Depo Envanteri": "Tarama Tahmini",
        "Hangi dosyalar, kaç satır, hangi yapılandırma ayarları açık — tarama kapsamının ölçülebilir dayanağını üretir.":
            "Dosya ve bağlam için yaklaşık token miktarı ile model hızından süre tahmini çıkarır.",
        "Desen Taraması": "Kod Tarama",
        "Bilinen risk kalıplarını dosya ve satır etiketiyle bulur; ajandaki doğrulama bu ön taramanın üstüne kurulur.":
            "Seçilen kod ve mevzuat parçalarını yerel Ollama modeline gönderir.",
        "Tahmin Aracı": "Kanıt Doğrulama",
        "Tarama öncesi dosya/satır/süre/maliyet ölçümü yapar; 'onayınız olmadan tarama yok' kuralının ölçülebilir temelidir.":
            "Kod alıntısı ve mevzuat sayfa atfı doğrulanmayan bulguları reddeder.",
        "Veri Gizleyici": "Tarama Raporu",
        "Kart numarası, şifre ve benzeri görünümleri rapor yazılmadan önce maskeler; gerçek değer rapora hiç girmez.":
            "Tarama JSON'u, Markdown ve HTML; kapsam, dosya sonuçları ve bulguları içerir.",
        "Belge Hafızası Kurulumu": "Remediation Planı",
        "Her belgeyi konu bölümlerine ayırıp kimlikli hafızaya yerleştirir; bölümler orta boyutta tutulur.":
            "En fazla iki yüksek öncelikli bulgu için değişiklik planı hazırlar.",
        "Belge Hafızası Sorgu": "Remediation Önerisi",
        "Hafıza içinde konu bazlı arama yapar; her sonuç belge + bölüm kimliğiyle döner — dayanaksız alıntı yoktur.":
            "Yerel modelden sınırlı dosya değişikliği önerisi alır; otomatik uygulamaz.",
        "Veritabanı Tanım Arama": "İzole Uygulama",
        "Prosedür/paket tanımlarını statik metin içinde arar; veritabanına bağlanmaz, SQL çalıştırmaz.":
            "Açık onayla yalnız seçilen bulguların dosyalarını ayrı branch/worktree'de değiştirir.",
        "Rapor Biçimlendirici": "Test Doğrulama",
        "Bilgi dosyasından kurumsal HTML görünüm üretir; içeriği değiştirmez — md kaynak, html yalnız sunum katmanıdır.":
            "Kullanıcı onayıyla desteklenen test komutlarını çalıştırır; sonucu HTML/Markdown raporlar.",
        "Düzeltme / PR Aracı": "GitHub PR",
        "Onaylı düzeltmede ayrı dal açar, farkı uygular, PR açar; korunan dallara yazma ve zorla-gönderim yoktur.":
            "Başarılı test ve son kullanıcı onayından sonra `gh` ile PR açar.",
        "Sıfırlama Aracı": "LangChain İş Akışı",
        "'Sıfırla' komutunda önce plan gösterir, onaydan sonra ürettiği veriyi temizler; şablonlar, araçlar ve kayıtlar korunur.":
            "Tahmin → onay → tarama → rapor adımlarını Python `Runnable` zincirinde bağlar.",
        "Sunum Üretici": "Türkçe CLI",
        "Bu tanıtım sunumunu tek komutla üretir; slayt sablonları ve kurum logosu yerleşik gelir.":
            "Kullanıcıya belge, depo, tarama ve remediation menülerini sunar.",
        "Tüm araçlar yerel çalışır: dışa veri göndermez, ağ çağrısı yapmaz, kendisi karar vermez — karar ve onay daima sizdedir.":
            "Kod yerel Ollama servisine gönderilir; PDF indirme ve GitHub PR aşamaları ağ kullanır. Gerçek kart verisi kullanmayın.",
        "Bir repo seçin; ajan tahmini sunduktan sonra tarama yapıp yapılandırılmış rapor üretir. Raporu ekiple paylaşıp geri bildirim toplayın.":
            "Sentetik ödeme deposuyla pilot yapın; dosya kapsamı ve tahmini süreyi onaylayıp HTML raporunu inceleyin.",
        "2. Doküman havuzu": "2. Mevzuat kaynakları",
        "Bülten ve mevzuat belgelerini ilgili klasörlere girin; ajan her biri için etki ve uyum analizi üretir, yaklaşan geçerlilik tarihlerini öne çıkarır.":
            "`mevzuat_link.json` kaynaklarını seçin; indirilen PDF'leri, manifest uyarılarını ve RAG atıflarını kontrol edin.",
        "Risk raporundaki en kritik bulguları seçin; fark raporunu inceleyip onaylayın — düzeltme dalı hazır, Pull Request adresi elinizde.":
            "En fazla iki bulgu için diff'i gözden geçirin; test ve PR onaylarını ayrı verin.",
        "Her adımda aynı güvenceler geçerli: kanıt, gizlilik, tazelik, onay.":
            "Yalnız sentetik/hassas veriden arındırılmış kod kullanın; hukuki kararı uzman verir.",
        "Dört analiz akışı + bulgu düzeltme seçeneği — hepsi kanıt disipliniyle.":
            "Mevzuat PDF'leri yerel BM25 RAG indeksine alınır; kaynak ve sayfa bilgisi korunur.",
        "Tarama öncesi maliyet tahmini: ne kadar kod, ne kadar süre, ne kadar maliyet — önceden bilirsiniz.":
            "Tarama tahmini yaklaşık token ve süre sunar; yerel model için parasal maliyet çıkarılmaz.",
        "Temiz başlangıç: 'sıfırla' derseniz ortam güvenli temizlenir; analiz hep güncel koddan yürür.":
            "Kod taraması kullanıcı onaylı depo/kapsam/model ile çalışır; sınırlı veya eksik sonuçlar raporlanır.",
        "Hassas veriler otomatik gizlenir; doğrulanamayan bilgi 'Doğrulanmalı' yazar, tahmin üretmez.":
            "Gerçek kart sahibi verisi kullanmayın; otomatik veri maskeleme garantisi yoktur.",
        "Kod yazma onayınız olmadan hiçbir adım ilerlemez; her rapor bilgi + HTML çift dosyada, sabit kurumsal biçimde teslim edilir.":
            "En fazla iki bulgu izole worktree'de düzeltilir; test ve GitHub PR ayrı onay ve HTML/Markdown raporları gerektirir.",
        "Başlamak için: 'bir repo için risk raporu çıkar' yazın — gerisini ajan sıralar.":
            "Başlamak için `mevzuat-agent` terminal menüsünü açın; RAG, depo, tahminli tarama ve remediation adımlarını seçin.",
    }
    slide_replacements = {
        0: {
            "Repo Risk Raporu": "Mevzuat RAG",
            "Bülten Etki Analizi": "Ödeme Kodu Tarama",
            "Mevzuat Uyum Analizi": "Kanıtlı Rapor",
        },
        6: {"3\nRepo?": "3\nRAG indeks"},
        8: {"3\nRepo?": "3\nMevzuat"},
        15: {
            "Repo Risk Raporu": "1 · Mevzuat RAG",
            "Bülten Etki Analizi": "2 · Depo",
            "Mevzuat Uyum Analizi": "3 · Tahmin ve tarama",
        },
    }
    matched: set[str] = set()
    for slide_index, slide in enumerate(presentation.slides):
        slide_replacement = slide_replacements.get(slide_index, {})
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            source_shape_text = shape.text
            replacement_shape_text = slide_replacement.get(
                source_shape_text,
                replacements.get(source_shape_text),
            )
            if replacement_shape_text is not None:
                paragraphs = shape.text_frame.paragraphs
                replacement_lines = replacement_shape_text.split("\n")
                if len(paragraphs) != len(replacement_lines):
                    raise ValueError(
                        f"Unexpected paragraph count in source shape: {source_shape_text}"
                    )
                for paragraph, replacement_line in zip(
                        paragraphs, replacement_lines, strict=True
                ):
                    if len(paragraph.runs) != 1:
                        raise ValueError(
                            f"Unexpected formatted source paragraph: {paragraph.text}"
                        )
                    paragraph.runs[0].text = replacement_line
                matched.add(source_shape_text)
                continue
            for paragraph in shape.text_frame.paragraphs:
                source_text = "".join(run.text for run in paragraph.runs)
                replacement = slide_replacement.get(
                    source_text,
                    replacements.get(source_text),
                )
                if replacement is None:
                    continue
                if len(paragraph.runs) != 1:
                    raise ValueError(f"Unexpected formatted source paragraph: {source_text}")
                paragraph.runs[0].text = replacement
                matched.add(source_text)
    missing = replacements.keys() - matched
    if missing:
        raise ValueError(f"Source presentation text changed; not found: {sorted(missing)}")


def _add_report_slides(presentation):
    slide = _new_slide(
        presentation,
        "KAYNAK RAPORU · 24.10.2026",
        "Birleşik risk görünümü: 35 depo, 82 bulgu",
        "Kanun 5464 + Yönetmelik 11180 · Sağlanan birleşik HTML raporundaki ölçümler",
    )
    metrics = [
        ("35", "taranan depo", TEAL),
        ("82", "toplam bulgu", RED),
        ("%67", "uyum · 61 değerlendirme", CYAN),
        ("9", "Doğrulanmalı", GOLD),
    ]
    for index, (value, label, accent) in enumerate(metrics):
        x = 0.68 + index * 3.12
        _add_box(slide, x, 1.9, 2.86, 1.15, WHITE)
        _add_box(slide, x, 1.9, 0.08, 1.15, accent)
        _add_text(slide, value, x + 0.2, 2.02, 2.45, 0.48, 25, NAVY, True)
        _add_text(slide, label, x + 0.2, 2.55, 2.45, 0.3, 10, MUTED)

    distribution = "   ·   ".join(
        f"{count} {severity}" for severity, count in FINDINGS
    )
    _add_text(slide, "Bulgu dağılımı", 0.78, 3.4, 2.0, 0.3, 14, NAVY, True)
    _add_text(slide, distribution, 0.78, 3.78, 11.8, 0.42, 13, INK, True)
    _add_box(slide, 0.68, 4.55, 12.0, 1.35, PALE_BLUE)
    _add_text(
        slide,
        "61 hüküm-depo değerlendirmesi: 41 uyumlu · 10 kısmi · 10 ihlal riski\n"
        "Depo bazında en yüksek risk: 17 kritik · 8 yüksek · 10 orta\n"
        "Kaynak dayanağı: 13 RAG chunk + 9 DB-RAG atfı",
        0.93,
        4.73,
        11.45,
        0.95,
        13,
        NAVY,
    )
    _add_text(
        slide,
        "Kaynak rapor ölçümleri; bağımsız yeniden tarama veya hukuki görüş değildir.",
        0.75,
        6.35,
        11.9,
        0.3,
        10,
        MUTED,
    )

    slide = _new_slide(
        presentation,
        "REMEDIATION · TUR 2",
        "Kullanıcı onayıyla seçilen beş kritik bulgu",
        "Fark raporu: 5 depo · 9 dosya · +89 / -10 satır · test/PR sonucu bu rapordan doğrulanmıyor",
    )
    table_shape = slide.shapes.add_table(
        6, 3, Inches(0.68), Inches(1.85), Inches(12.0), Inches(4.55)
    )
    table = table_shape.table
    table.columns[0].width = Inches(1.2)
    table.columns[1].width = Inches(3.2)
    table.columns[2].width = Inches(7.6)
    rows = [("Bulgu", "Alan", "Fark raporundaki düzeltme özeti"), *REMEDIATIONS]
    for row_index, values in enumerate(rows):
        for column_index, value in enumerate(values):
            cell = table.cell(row_index, column_index)
            cell.text = value
            cell.margin_left = Inches(0.1)
            cell.margin_right = Inches(0.08)
            cell.margin_top = Inches(0.04)
            cell.margin_bottom = Inches(0.03)
            cell.fill.solid()
            cell.fill.fore_color.rgb = NAVY if row_index == 0 else (
                WHITE if row_index % 2 else PALE_BLUE
            )
            for paragraph in cell.text_frame.paragraphs:
                paragraph.font.name = "Aptos"
                paragraph.font.size = Pt(11 if row_index else 12)
                paragraph.font.bold = row_index == 0
                paragraph.font.color.rgb = WHITE if row_index == 0 else INK
    _add_text(
        slide,
        "Credential/token örnekleri sunuma aktarılmadı; rotasyon ve Git geçmişi temizliği ayrı operasyonel işlerdir.",
        0.75,
        6.58,
        12.0,
        0.3,
        9,
        MUTED,
    )

    slide = _new_slide(
        presentation,
        "KAPANIŞ · DOĞRULAMA DURUMU",
        "Fark raporu sonuç kanıtı değildir",
        "Kod farkı, test sonucu, canlı PR ve operasyonel riskler ayrı ayrı doğrulanmalıdır.",
    )
    cards = [
        (
            "Açık doğrulama",
            "3 madde kaynak raporda “Doğrulanmalı”.\n"
            "İş kararı, ortam ayarı veya istemci davranışı netleştirilmeli.",
            CYAN,
        ),
        (
            "Ayrı operasyon işleri",
            "Credential rotasyonu / vault ve altyapı-konfigürasyon işleri.\n"
            "Kod farkı bu işleri tek başına kapatmaz.",
            GOLD,
        ),
        (
            "Sonraki kapılar",
            "Testleri çalıştır ve sonuçları kaydet.\n"
            "Diff'i gözden geçir; gerçek PR durumunu GitHub'da doğrula.",
            TEAL,
        ),
    ]
    for index, (title, body, accent) in enumerate(cards):
        x = 0.68 + index * 4.05
        _add_box(slide, x, 2.0, 3.78, 2.3, WHITE)
        _add_box(slide, x, 2.0, 3.78, 0.1, accent)
        _add_text(slide, title, x + 0.18, 2.25, 3.4, 0.42, 15, NAVY, True)
        _add_text(slide, body, x + 0.18, 2.82, 3.4, 1.2, 11, INK)
    _add_box(slide, 0.68, 4.78, 12.0, 1.0, PALE_GOLD)
    _add_text(
        slide,
        "Sınır: Bu ek, verilen raporları özetler. Kaynak depolar yeniden taranmadı; "
        "testlerin geçtiği veya PR'ın açıldığı iddia edilmez.",
        0.95,
        4.98,
        11.45,
        0.6,
        12,
        NAVY,
        True,
    )
    _add_text(
        slide,
        "Güvenli paylaşım için credential/token değerleri eklerden çıkarılmıştır.",
        0.75,
        6.35,
        11.9,
        0.3,
        10,
        MUTED,
    )


def _card_payment_context_slides(presentation):
    slide = _new_slide(
        presentation,
        "PROJE ODAĞI · KARTLI ÖDEME SİSTEMLERİ",
        "Ödeme yazılımını mevzuat bağlamında, kod kanıtıyla incelemek",
        "MevzuatAgent ödeme almaz veya canlı işlem sistemine bağlanmaz; seçilen depo ve mevzuat belgelerini analiz eder.",
    )
    actors = [
        ("Kart sahibi", "Kartı / dijital cüzdanı kullanır"),
        ("İş yeri · POS", "Ödemeyi başlatır"),
        ("Gateway · Acquirer", "İsteği yönlendirir"),
        ("Kart ağı", "İşlemi ilgili tarafa taşır"),
        ("Issuer", "Yetkilendirir veya reddeder"),
    ]
    for index, (title, body) in enumerate(actors):
        x = 0.68 + index * 2.43
        _add_box(slide, x, 1.92, 2.23, 1.08, WHITE)
        _add_box(slide, x, 1.92, 0.07, 1.08, (TEAL, CYAN, GOLD, TEAL, RED)[index])
        _add_text(slide, title, x + 0.15, 2.08, 1.98, 0.32, 13, NAVY, True)
        _add_text(slide, body, x + 0.15, 2.48, 1.98, 0.35, 10, MUTED)

    _add_text(slide, "İşlem yaşam döngüsü", 0.78, 3.32, 3.2, 0.32, 15, NAVY, True)
    _add_text(
        slide,
        "Ödeme başlatma  →  doğrulama / 3-D Secure  →  yetkilendirme  →  capture ve mutabakat  →  iade / ters ibraz",
        0.78,
        3.72,
        11.7,
        0.55,
        13,
        INK,
        True,
    )
    _add_box(slide, 0.68, 4.55, 12.0, 1.28, PALE_BLUE)
    _add_text(
        slide,
        "İncelenebilecek kod alanları",
        0.9,
        4.73,
        2.8,
        0.32,
        14,
        NAVY,
        True,
    )
    _add_text(
        slide,
        "Ödeme API'leri · tutar/para birimi doğrulama · tekrar denemeler ve idempotency · "
        "token/PAN maskeleme ve loglar · 3DS/issuer entegrasyonları · RRN/STAN ve mutabakat · "
        "iade, iptal ve ters ibraz akışları",
        3.1,
        4.68,
        9.1,
        0.68,
        11,
        INK,
    )
    _add_text(
        slide,
        "Bunlar ödeme alanına özgü inceleme başlıklarıdır; tek başına mevzuat hükmü veya doğrulanmış bulgu değildir.",
        0.78,
        6.13,
        11.7,
        0.36,
        10,
        MUTED,
    )

    slide = _new_slide(
        presentation,
        "İNCELEME YÖNTEMİ · MEVZUATTAN KOD KANITINA",
        "Her ödeme riski için izlenebilir bir kanıt zinciri",
        "Kural, yalnızca seçilen mevzuat kaynağı ve depodaki somut kanıtla eşleştirildiğinde değerlendirilir.",
    )
    steps = [
        ("1 · Kaynak", "Kullanıcı mevzuat belgesini ve kapsamı seçer."),
        ("2 · RAG", "Metin parçaları kaynak, sayfa ve konum bilgisiyle aranır."),
        ("3 · Kod", "Ödeme akışındaki dosya/satır, ilgili parçayla karşılaştırılır."),
        ("4 · Rapor", "Kanıt, atıf, önem ve sınırlama kullanıcıya sunulur."),
    ]
    for index, (title, body) in enumerate(steps):
        x = 0.68 + index * 3.05
        _add_box(slide, x, 2.0, 2.78, 1.5, WHITE)
        _add_box(slide, x, 2.0, 2.78, 0.09, (TEAL, CYAN, GOLD, RED)[index])
        _add_text(slide, title, x + 0.16, 2.23, 2.46, 0.34, 15, NAVY, True)
        _add_text(slide, body, x + 0.16, 2.72, 2.46, 0.58, 11, INK)
    _add_box(slide, 0.68, 4.03, 12.0, 1.35, PALE_GOLD)
    _add_text(
        slide,
        "Ödeme alanındaki örnek kontrol soruları",
        0.92,
        4.22,
        3.6,
        0.34,
        14,
        NAVY,
        True,
    )
    _add_text(
        slide,
        "Zaman aşımı aynı ödemenin iki kez alınmasına yol açabilir mi? Hassas kart verisi loglanıyor mu? "
        "İade/iptal doğru işlemle ilişkilendiriliyor mu? Tutar ve para birimi tutarlı mı?",
        4.15,
        4.18,
        8.15,
        0.72,
        11,
        INK,
    )
    _add_text(
        slide,
        "Sorular inceleme rehberidir; PCI/şema uyumu veya hukuki uygunluk iddiası değildir. "
        "Uzman doğrulaması ve kullanıcı onayı gerekir.",
        0.78,
        5.78,
        11.7,
        0.45,
        10,
        MUTED,
    )


def _write_example_reports():
    source_dir = ROOT / "src"
    if str(source_dir) not in sys.path:
        sys.path.insert(0, str(source_dir))
    from mevzuat_agent.tools.apply_remediation import apply_remediation
    from mevzuat_agent.tools.generate_scan_report import generate_scan_report

    EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    scan_result = {
        "repository": "synthetic-card-payment-demo",
        "branch_commit": "main@fixture",
        "model": "synthetic-fixture",
        "scan_scope": "Sentetik kartlı ödeme akışı; yalnızca örnek rapor",
        "scanned_at": "2026-10-29T00:00:00+00:00",
        "files_scanned": 1,
        "files_considered": 1,
        "findings": [
            {
                "severity": "HIGH",
                "title": "Ödeme referansı maskelenmiyor",
                "file": "payment_flow.py",
                "line": 6,
                "evidence": "    return value",
                "explanation": "Örnek maskeleme işlevi değeri olduğu gibi döndürüyor.",
                "mevzuat_source": "TEST_FIXTURE_NOT_LAW",
                "mevzuat_page": 1,
                "recommendation": "Gerekli olmayan karakterleri maskeleyin; hassas veriyi loglamayın.",
                "confidence": 10,
            },
            {
                "severity": "MEDIUM",
                "title": "Sıfır tutar geçerli sayılıyor",
                "file": "payment_flow.py",
                "line": 11,
                "evidence": "    return amount >= 0",
                "explanation": "Örnek doğrulama sıfır tutarı da kabul ediyor.",
                "mevzuat_source": "TEST_FIXTURE_NOT_LAW",
                "mevzuat_page": 1,
                "recommendation": "İş kuralı ve mevzuat kaynağıyla doğrulanmış tutar sınırını uygulayın.",
                "confidence": 10,
            },
        ],
        "file_results": [
            {
                "path": "payment_flow.py",
                "status": "scanned",
                "findings": [],
                "error": None,
            }
        ],
        "limitations": [
            "Sentetik örnek; gerçek ödeme verisi, mevzuat tespiti veya hukukî görüş değildir."
        ],
    }

    with TemporaryDirectory(prefix="mevzuatagent-example-") as temp_dir:
        temp_root = Path(temp_dir)
        scan_json = temp_root / "scan.json"
        scan_json.write_text(
            json.dumps(scan_result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        generate_scan_report(
            scan_json,
            markdown_path=EXAMPLES_DIR / "ornek_tarama_raporu.md",
            html_path=EXAMPLES_DIR / "ornek_tarama_raporu.html",
        )

        repository = temp_root / "synthetic-card-payment-demo"
        repository.mkdir()
        git_commands = (
            ["git", "init", "-b", "main"],
            ["git", "config", "user.name", "MevzuatAgent Example"],
            ["git", "config", "user.email", "example@localhost"],
        )
        for command in git_commands:
            subprocess.run(
                command,
                cwd=repository,
                check=True,
                capture_output=True,
                text=True,
            )

        source_code = (
            "# Synthetic payment example\n\n"
            "def mask_reference(value: str, visible: int = 4) -> str:\n"
            '    """Mask a payment reference."""\n\n'
            "    return value\n\n"
            "def is_positive_amount(amount: float) -> bool:\n"
            '    """Check that amount is positive."""\n\n'
            "    return amount >= 0\n"
        )
        patched_code = source_code.replace(
            "    return value",
            '    return "*" * max(0, len(value) - visible) + value[-visible:]',
        ).replace("    return amount >= 0", "    return amount > 0")
        (repository / "payment_flow.py").write_text(source_code, encoding="utf-8")
        for command in (
                ["git", "add", "payment_flow.py"],
                ["git", "commit", "-m", "Add synthetic payment example"],
        ):
            subprocess.run(
                command,
                cwd=repository,
                check=True,
                capture_output=True,
                text=True,
            )

        remediation_result = apply_remediation(
            repository,
            scan_json,
            {"payment_flow.py": patched_code},
            user_approved=True,
            reports_dir=temp_root / "remediation-reports",
        )
        replacements = (
            (str(temp_root.resolve()) + "/", ""),
            (
                remediation_result.worktree_path.name,
                "synthetic-card-payment-demo-remediation-example",
            ),
            (remediation_result.branch, "mevzuatagent/remediation-example"),
        )
        remediation_markdown = remediation_result.markdown_path.read_text(
            encoding="utf-8"
        )
        remediation_html = remediation_result.html_path.read_text(encoding="utf-8")
        for original, replacement in replacements:
            remediation_markdown = remediation_markdown.replace(original, replacement)
            remediation_html = remediation_html.replace(original, replacement)
        (EXAMPLES_DIR / "ornek_remediation_raporu.md").write_text(
            remediation_markdown,
            encoding="utf-8",
        )
        (EXAMPLES_DIR / "ornek_remediation_raporu.html").write_text(
            remediation_html,
            encoding="utf-8",
        )


def _sample_report_slides(presentation):
    slide = _new_slide(
        presentation,
        "ÖRNEK ÇIKTI · HTML TARAMA RAPORU",
        "Bulgu; dosya, satır, kod kanıtı ve öneriyle sunulur",
        "Aşağıdaki kartlar docs/examples/ornek_tarama_raporu.html içindeki sentetik örnek raporun özetidir.",
    )
    metrics = [
        ("2", "örnek bulgu", TEAL),
        ("1 / 1", "incelenen dosya", CYAN),
        ("fixture", "model / kaynak", GOLD),
        ("TEST ONLY", "hukuki tespit değil", RED),
    ]
    for index, (value, label, accent) in enumerate(metrics):
        x = 0.68 + index * 3.12
        _add_box(slide, x, 1.9, 2.86, 0.92, WHITE)
        _add_box(slide, x, 1.9, 0.08, 0.92, accent)
        _add_text(slide, value, x + 0.18, 2.02, 2.52, 0.37, 19, NAVY, True)
        _add_text(slide, label, x + 0.18, 2.43, 2.52, 0.22, 9, MUTED)

    examples = [
        (
            "HIGH · Ödeme referansı maskelenmiyor",
            "payment_flow.py:6  ·  Kanıt: return value",
            "Öneri: yalnız gerekli kısmı göster; hassas değeri loglama.",
            PALE_GOLD,
        ),
        (
            "MEDIUM · Sıfır tutar geçerli sayılıyor",
            "payment_flow.py:11  ·  Kanıt: return amount >= 0",
            "Öneri: tutar sınırını iş kuralı ve kaynakla doğrula.",
            PALE_BLUE,
        ),
    ]
    for index, (title, location, recommendation, fill) in enumerate(examples):
        y = 3.15 + index * 1.25
        _add_box(slide, 0.68, y, 12.0, 1.03, fill)
        _add_text(slide, title, 0.92, y + 0.12, 11.3, 0.28, 14, NAVY, True)
        _add_text(slide, location, 0.92, y + 0.44, 5.6, 0.26, 10, INK)
        _add_text(slide, recommendation, 6.65, y + 0.44, 5.7, 0.35, 10, INK)
    _add_text(
        slide,
        "Mevzuat alanı: TEST_FIXTURE_NOT_LAW · değerler sentetiktir, gerçek bulgu değildir.",
        0.78,
        5.86,
        9.6,
        0.28,
        9,
        MUTED,
    )
    link = _add_text(
        slide,
        "HTML raporunu aç",
        10.1,
        5.83,
        2.3,
        0.3,
        10,
        TEAL,
        True,
    )
    link.text_frame.paragraphs[0].runs[0].hyperlink.address = (
        "examples/ornek_tarama_raporu.html"
    )

    slide = _new_slide(
        presentation,
        "ÖRNEK ÇIKTI · HTML REMEDIATION RAPORU",
        "Onaylı düzeltme ayrı dalda; değişiklikler görünür diff olarak",
        "docs/examples/ornek_remediation_raporu.html uygulamanın gerçek remediation rapor şablonunu kullanır.",
    )
    _add_box(slide, 0.68, 1.88, 12.0, 0.9, PALE_GOLD)
    _add_text(
        slide,
        "YALNIZCA SENTETİK TEST ÖRNEĞİ · Hukuki uygunluk, canlı sistem davranışı veya PR sonucu göstermez.",
        0.92,
        2.12,
        11.45,
        0.34,
        12,
        NAVY,
        True,
    )
    _add_text(slide, "payment_flow.py", 0.92, 3.1, 5.4, 0.32, 14, NAVY, True)
    _add_box(slide, 0.68, 3.53, 5.75, 1.68, WHITE)
    _add_text(
        slide,
        "- return value\n+ return \"*\" * max(0, len(value) - visible) + value[-visible:]\n\n"
        "- return amount >= 0\n+ return amount > 0",
        0.92,
        3.72,
        5.25,
        1.25,
        11,
        INK,
    )
    _add_box(slide, 6.68, 3.1, 6.0, 2.11, PALE_BLUE)
    _add_text(
        slide,
        "Raporda görülenler",
        6.94,
        3.31,
        5.45,
        0.34,
        14,
        NAVY,
        True,
    )
    _add_text(
        slide,
        "Kaynak depo ve izole worktree\\nRemediation dalı\\nÖnce/sonra kod farkı\\n"
        "Sentetik fixture uyarısı\\n\nTest ve PR ayrı onaylı adımlardır.",
        6.94,
        3.79,
        5.4,
        1.22,
        11,
        INK,
    )
    link = _add_text(
        slide,
        "HTML remediation raporunu aç",
        0.92,
        5.72,
        4.1,
        0.3,
        10,
        TEAL,
        True,
    )
    link.text_frame.paragraphs[0].runs[0].hyperlink.address = (
        "examples/ornek_remediation_raporu.html"
    )
    _add_text(
        slide,
        "Uygulama diff'i tek başına test başarısı veya mevzuata uygunluk kanıtı saymaz.",
        0.92,
        6.05,
        9.5,
        0.28,
        9,
        MUTED,
    )


def _add_e2e_validation_slide(presentation):
    slide = _new_slide(
        presentation,
        "UÇTAN UCA · YEREL E2E TESTİ",
        "RAG'den yerel PR provasına kadar her aşama çalıştırıldı",
        "Deterministik test: tarama için mock Ollama ve sentetik fixture; gerçek GitHub PR oluşturulmadı.",
    )
    metrics = [
        ("2 PDF", "146 mevzuat chunk", TEAL),
        ("1 dosya", "tahmin ve tarama", CYAN),
        ("2 bulgu", "sentetik / doğrulanmış", GOLD),
        ("2 / 2", "remediation testi geçti", RED),
    ]
    for index, (value, label, accent) in enumerate(metrics):
        x = 0.68 + index * 3.12
        _add_box(slide, x, 1.9, 2.86, 0.92, WHITE)
        _add_box(slide, x, 1.9, 0.08, 0.92, accent)
        _add_text(slide, value, x + 0.18, 2.02, 2.52, 0.37, 19, NAVY, True)
        _add_text(slide, label, x + 0.18, 2.43, 2.52, 0.22, 9, MUTED)

    _add_box(slide, 0.68, 3.12, 12.0, 2.3, PALE_BLUE)
    _add_text(
        slide,
        "Akış sonucu",
        0.94,
        3.32,
        5.2,
        0.34,
        14,
        NAVY,
        True,
    )
    _add_text(
        slide,
        "PDF → 146 chunk · Tahmin/onay → 2 mock model · Tarama → 1 dosya / 2 sentetik bulgu\n"
        "Remediation → 2 bulgu ayrı worktree'de düzeltildi · pytest → 2 passed\n"
        "PR provası → dal yerel bare remote'a gönderildi; GitHub CLI yanıtı mock\n"
        "Canlı llama3.2:1b denemesi → 0 dosya; model yanıtı geçersiz JSON",
        0.94,
        3.82,
        11.35,
        1.35,
        11,
        INK,
    )
    links = [
        ("E2E özeti", "examples/e2e_dogrulama_ozeti.html"),
        ("Tarama raporu", "examples/e2e_tarama_raporu.html"),
        ("Remediation diff", "examples/e2e_remediation_raporu.html"),
        ("Test raporu", "examples/e2e_test_raporu.html"),
    ]
    for index, (label, address) in enumerate(links):
        link = _add_text(
            slide,
            label,
            0.9 + index * 3.05,
            5.62,
            2.8,
            0.32,
            10,
            TEAL,
            True,
        )
        link.text_frame.paragraphs[0].runs[0].hyperlink.address = address
    _add_text(
        slide,
        "Tam E2E downstream akışı mock modelle doğrulandı; canlı model hatası güvenli biçimde remediation'ı durdurdu.",
        0.9,
        6.08,
        11.2,
        0.34,
        9,
        MUTED,
    )


def _add_evidence_slides(presentation, captures: dict[str, Path]):
    slides = [
        (
            "KURULUM · AŞAMA GÖRSELİ",
            "Kurulum aşamaları ve açık onay kapıları",
            "install.sh kaynak kodundan sıralandı; bu makinede yapılmış bir kurulum kaydı olarak sunulmaz.",
            "setup",
            "Görsel belge akışını anlatır; Ollama, model, mevzuat indirme ve klonlama adımları ayrıca onay ister.",
        ),
        (
            "TEST REPOSU · GERÇEK DOSYA YAPISI",
            "İki sentetik demo, on test bulgusu",
            "Depo ağacı mevcut test fixture Git deposundan; içerik yalnızca test için hazırlanmıştır.",
            "repository",
            "Sentetik fixture; gerçek sistem veya gerçek mevzuat bulgusu değildir.",
        ),
        (
            "REMEDIATION · DIFF + TEST",
            "Önce / sonra farkı ve kabul testi",
            "Görsel, izole remediation worktree raporundaki iki örnek değişikliği ve test raporunu gösterir.",
            "diff",
            "Test raporunda 2 sentetik kabul testi geçti; hukuki uyumluluk doğrulaması değildir.",
        ),
        (
            "PR · YEREL ENTEGRASYON PROVASI",
            "Push/PR hattı güvenli test ortamında denendi",
            "Yerel bare Git remote ve fake gh kullanıldı; gerçek GitHub PR açılmadı.",
            "pr",
            "Gerçek PR ekran görüntüsü mevcut değildir; bu görsel yerel mock provayı açıkça etiketler.",
        ),
    ]
    for eyebrow, title, subtitle, key, note in slides:
        slide = _new_slide(presentation, eyebrow, title, subtitle)
        slide.shapes.add_picture(
            str(captures[key]),
            Inches(0.68),
            Inches(1.82),
            width=Inches(12.0),
            height=Inches(4.72),
        )
        _add_text(
            slide,
            note,
            0.75,
            6.64,
            10.1,
            0.44,
            9,
            MUTED,
        )


def _add_softtech_branding(
        presentation,
        dark_background_logo: Path,
        light_background_logo: Path,
):
    slides = list(presentation.slides)
    for slide in slides[1:]:
        slide.shapes.add_picture(
            str(light_background_logo),
            Inches(10.92),
            Inches(6.98),
            width=Inches(1.05),
        )
    if slides:
        slides[0].shapes.add_picture(
            str(dark_background_logo),
            Inches(10.05),
            Inches(5.83),
            width=Inches(2.35),
        )
    _add_text(
        slides[-1],
        "Softtech logosu görsel amaçlıdır; kurumsal onay veya iş birliği beyanı değildir.",
        0.75,
        6.28,
        9.9,
        0.3,
        9,
        MUTED,
    )


def main():
    missing_sources = [
        path for path in (SOURCE_PRESENTATION, *SOURCE_REPORTS) if not path.is_file()
    ]
    if missing_sources:
        raise FileNotFoundError(
            "Kaynak belge(ler) bulunamadı; üç dosyayı data/temp_reference/ içine "
            "kopyalayın: " + ", ".join(path.name for path in missing_sources)
        )
    presentation = Presentation(str(SOURCE_PRESENTATION))
    _tailor_source_slides(presentation)
    _add_report_slides(presentation)
    _card_payment_context_slides(presentation)
    captures = _create_evidence_captures()
    _add_evidence_slides(presentation, captures)
    _write_example_reports()
    _sample_report_slides(presentation)
    _add_e2e_validation_slide(presentation)
    _add_softtech_branding(
        presentation,
        _ensure_softtech_logo(),
        _ensure_light_background_logo(),
    )
    OUTPUT_PRESENTATION.parent.mkdir(parents=True, exist_ok=True)
    presentation.save(str(OUTPUT_PRESENTATION))

    OUTPUT_MARKDOWN.write_text(_markdown(), encoding="utf-8")
    OUTPUT_HTML.write_text(_html_report(), encoding="utf-8")
    print(f"Sunum: {OUTPUT_PRESENTATION}")
    print(f"Markdown rapor: {OUTPUT_MARKDOWN}")
    print(f"HTML rapor: {OUTPUT_HTML}")


if __name__ == "__main__":
    main()
