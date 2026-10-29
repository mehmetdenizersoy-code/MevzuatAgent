"""Türkçe ödev sunumunu oluşturur."""

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "MevzuatAgent_Odev_Sunumu_TR.pptx"

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
LINE = RGBColor(222, 229, 238)
GREEN_PALE = RGBColor(226, 246, 240)
BLUE_PALE = RGBColor(231, 240, 250)
GOLD_PALE = RGBColor(255, 246, 223)

WIDTH = 13.333
HEIGHT = 7.5


def _box(slide, x, y, width, height, color, rounded=True):
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE
    shape = slide.shapes.add_shape(
        shape_type, Inches(x), Inches(y), Inches(width), Inches(height)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    return shape


def _text(
    slide,
    text,
    x,
    y,
    width,
    height,
    *,
    size=16,
    color=INK,
    bold=False,
    align=PP_ALIGN.LEFT,
    font="Aptos",
):
    shape = slide.shapes.add_textbox(
        Inches(x), Inches(y), Inches(width), Inches(height)
    )
    frame = shape.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.margin_left = Inches(0.02)
    frame.margin_right = Inches(0.02)
    frame.margin_top = Inches(0.02)
    frame.margin_bottom = Inches(0.02)
    frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    paragraph.text = text
    paragraph.font.name = font
    paragraph.font.size = Pt(size)
    paragraph.font.bold = bold
    paragraph.font.color.rgb = color
    return shape


def _new_slide(presentation, background=PAPER):
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = background
    return slide


def _footer(slide, number, dark=False):
    color = RGBColor(185, 202, 220) if dark else MUTED
    _text(
        slide,
        "MEVZUATAGENT  •  YEREL  •  ONAYLI  •  DENETLENEBİLİR",
        0.62,
        7.08,
        10.6,
        0.2,
        size=8,
        color=color,
        bold=True,
    )
    _text(
        slide,
        f"{number:02}",
        12.15,
        7.02,
        0.55,
        0.3,
        size=10,
        color=color,
        bold=True,
        align=PP_ALIGN.RIGHT,
    )


def _header(slide, eyebrow, title, subtitle=None):
    _text(slide, eyebrow.upper(), 0.7, 0.36, 11.9, 0.25, size=9, color=TEAL, bold=True)
    _text(slide, title, 0.7, 0.72, 12.0, 0.55, size=27, color=NAVY, bold=True)
    if subtitle:
        _text(slide, subtitle, 0.72, 1.31, 11.9, 0.46, size=13, color=MUTED)


def _card(slide, x, y, width, height, title, body, accent=TEAL, fill=WHITE):
    _box(slide, x, y, width, height, fill)
    _box(slide, x, y, 0.07, height, accent, rounded=False)
    _text(slide, title, x + 0.22, y + 0.14, width - 0.42, 0.38, size=16, color=NAVY, bold=True)
    body_text = "\n".join(f"•  {line}" for line in body)
    _text(
        slide,
        body_text,
        x + 0.24,
        y + 0.6,
        width - 0.46,
        height - 0.72,
        size=12,
        color=INK,
    )


def _step(slide, x, y, width, number, title, detail, accent=TEAL):
    _box(slide, x, y, width, 1.42, WHITE)
    _box(slide, x + 0.16, y + 0.18, 0.42, 0.42, accent)
    _text(slide, str(number), x + 0.16, y + 0.18, 0.42, 0.4, size=13, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
    _text(slide, title, x + 0.7, y + 0.16, width - 0.86, 0.34, size=13, color=NAVY, bold=True)
    _text(slide, detail, x + 0.2, y + 0.67, width - 0.4, 0.55, size=10, color=MUTED)


def _title_slide(presentation):
    slide = _new_slide(presentation, NAVY)
    _box(slide, 9.55, -0.5, 4.5, 3.1, NAVY_LIGHT)
    _box(slide, 10.65, 1.25, 2.1, 2.1, TEAL)
    _box(slide, 11.25, 1.85, 0.9, 0.9, NAVY)
    _box(slide, 9.3, 4.35, 3.8, 2.5, NAVY_LIGHT)
    _text(slide, "PROJE / DÖNEM ÖDEVİ", 0.82, 0.82, 5.6, 0.35, size=11, color=CYAN, bold=True)
    _text(slide, "MevzuatAgent", 0.82, 1.6, 8.6, 0.9, size=38, color=WHITE, bold=True)
    _text(
        slide,
        "Mevzuat bilgisini yerel kod incelemesine bağlayan,\nonay kapılarıyla çalışan yapay zekâ destekli araç",
        0.86,
        2.65,
        8.1,
        1.2,
        size=21,
        color=RGBColor(215, 227, 240),
    )
    _box(slide, 0.86, 4.38, 1.45, 0.08, TEAL, rounded=False)
    _text(slide, "Python  •  Ollama  •  LangChain  •  BM25 RAG", 0.86, 4.67, 7.8, 0.4, size=13, color=WHITE, bold=True)
    _text(slide, "Sohbet arayüzü  |  Uçtan uca akış  |  Onaylı remediation ve PR", 0.86, 5.24, 8.3, 0.35, size=12, color=RGBColor(185, 202, 220))
    logo = ROOT / "docs/assets/branding/softtech-logo.png"
    if logo.is_file():
        slide.shapes.add_picture(str(logo), Inches(10.55), Inches(5.55), width=Inches(1.75))
    _footer(slide, 1, dark=True)


def _requirements_slides(presentation):
    slide = _new_slide(presentation)
    _header(slide, "01  •  Neden bu proje?", "Mevzuat bilgisini kod kararlarına yaklaştırmak", "Dağınık kaynaklar, manuel inceleme ve izlenmesi zor düzeltme adımlarını tek bir kontrollü akışta birleştirir.")
    _card(slide, 0.72, 2.05, 3.82, 2.1, "Girdi", ["Mevzuat PDF bağlantıları", "Kullanıcının seçtiği Git deposu", "Yerel Ollama model havuzu"], TEAL)
    _card(slide, 4.76, 2.05, 3.82, 2.1, "İşleme", ["Metni parçala ve yerel ara", "Kapsam/süre tahmini yap", "İlgili kod ve kaynakları incele"], CYAN)
    _card(slide, 8.8, 2.05, 3.82, 2.1, "Çıktı", ["Kanıt bağlantılı bulgular", "Markdown ve HTML raporları", "Onaylı düzeltme ve PR akışı"], GOLD)
    _box(slide, 0.72, 4.55, 11.9, 1.05, BLUE_PALE)
    _text(slide, "Temel yaklaşım", 0.98, 4.73, 1.8, 0.3, size=13, color=NAVY, bold=True)
    _text(slide, "Araç karar vermez: mevzuat uzmanının değerlendirmesine kanıt ve izlenebilir iş akışı sağlar.", 2.8, 4.68, 9.25, 0.44, size=15, color=INK, bold=True)
    _text(slide, "Hukuk danışmanı değildir; otomatik tarama sonucu hukuki uygunluğu kanıtlamaz.", 0.98, 5.93, 10.8, 0.35, size=12, color=MUTED)
    _footer(slide, 2)

    slide = _new_slide(presentation)
    _header(slide, "02  •  Gereksinimler 1–3", "Yerel model, orkestrasyon ve mevzuat RAG", "İlk üç madde veri akışını ve çalışma teknolojilerini belirler.")
    _card(slide, 0.72, 2.05, 3.82, 2.8, "1. Uygulama altyapısı", ["Python ile geliştirme; PyCharm uyumlu proje", "Ollama üzerinden yerel LLM", "LangChain Runnable ile tarama akışı"], TEAL)
    _card(slide, 4.76, 2.05, 3.82, 2.8, "2. Mevzuat belgeleri", ["mevzuat_link.json bağlantıları okunur", "PDF'ler yerel diske indirilir", "Sayfa ve kaynak bilgisi korunur"], CYAN)
    _card(slide, 8.8, 2.05, 3.82, 2.8, "3. Orta boy parçalar", ["Sayfa metni yaklaşık 1.200 karakter", "Yaklaşık 200 karakter örtüşme", "Yerel BM25 anahtar kelime araması"], GOLD)
    _box(slide, 0.72, 5.2, 11.9, 0.83, GOLD_PALE)
    _text(slide, "Doğru kapsam", 0.96, 5.35, 1.55, 0.26, size=12, color=NAVY, bold=True)
    _text(slide, "Mevcut RAG embedding/vektör veritabanı değil; BM25 indeksidir.", 2.55, 5.31, 9.6, 0.34, size=14, color=INK)
    _footer(slide, 3)

    slide = _new_slide(presentation)
    _header(slide, "03  •  Belge hazırlama", "PDF'den yerel arama indeksine", "Kaynağın konumu parçayla birlikte saklanır; tarama sırasında ilgili bağlam geri çağrılır.")
    labels = [
        ("Bağlantı", "mevzuat_link.json"),
        ("İndirme", "PDF • yerel"),
        ("Metin", "sayfa sayfa çıkarım"),
        ("Parçalama", "1.200 / 200 karakter"),
        ("İndeks", "BM25 • chunks.jsonl"),
    ]
    x_values = [0.72, 3.22, 5.72, 8.22, 10.72]
    for index, (title, detail) in enumerate(labels):
        x = x_values[index]
        _box(slide, x, 2.55, 1.9, 1.45, WHITE)
        _text(slide, f"0{index + 1}", x + 0.16, 2.72, 0.4, 0.28, size=11, color=TEAL, bold=True)
        _text(slide, title, x + 0.16, 3.08, 1.58, 0.35, size=15, color=NAVY, bold=True)
        _text(slide, detail, x + 0.16, 3.5, 1.58, 0.34, size=10, color=MUTED)
        if index < len(labels) - 1:
            _text(slide, "→", x + 1.98, 3.05, 0.45, 0.38, size=20, color=TEAL, bold=True, align=PP_ALIGN.CENTER)
    _card(slide, 0.72, 4.55, 5.78, 1.15, "Parça üstverisi", ["Kaynak PDF adı, sayfa numarası ve parça metni"], TEAL)
    _card(slide, 6.72, 4.55, 5.9, 1.15, "Sınırlar", ["OCR, belge sürüm takibi ve vektör arama yoktur"], GOLD)
    _footer(slide, 4)

    slide = _new_slide(presentation)
    _header(slide, "04  •  Gereksinimler 4–6", "Depo seçimi, tahmin ve tarama onayı", "Kod taraması kullanıcı tahminini görüp açıkça onay vermeden başlamaz.")
    _step(slide, 0.78, 2.05, 3.75, "1", "Depo seç", "repo_link.json kaynağı; klonlama öncesi kullanıcı onayı.", TEAL)
    _step(slide, 4.79, 2.05, 3.75, "2", "Model havuzunu ölç", "Kurulu Ollama modelleri kıyaslanır; tahmini süreler sunulur.", CYAN)
    _step(slide, 8.8, 2.05, 3.75, "3", "Modeli seç ve onayla", "En hızlı model önerilir; kullanıcı isterse başka modeli seçer.", GOLD)
    _box(slide, 0.78, 4.0, 11.77, 1.14, BLUE_PALE)
    _text(slide, "Tahminin kapsamı", 1.02, 4.18, 2.0, 0.32, size=14, color=NAVY, bold=True)
    _text(slide, "Kaynak dosya sayısı + ilgili mevzuat parçaları + model hız ölçümü → yaklaşık token/süre tahmini", 3.05, 4.12, 9.05, 0.52, size=14, color=INK)
    _text(slide, "Yerel çalışmada parasal API maliyeti hesaplanmaz. Tahmin, kullanıcı onayının yerini tutmaz.", 1.02, 5.55, 11.2, 0.4, size=12, color=MUTED)
    _footer(slide, 5)

    slide = _new_slide(presentation)
    _header(slide, "05  •  Uçtan uca akış", "Dokuz gereksinim, kontrollü tek bir yaşam döngüsü", "Her adımın çıktısı bir sonraki aşamanın girdisi olur; etkili işlemlerde onay kapısı vardır.")
    steps = [
        ("Kaynağı doğrula", "JSON bağlantıları"),
        ("Belgeyi hazırla", "indir • parçala • indeksle"),
        ("Depoyu al", "açık klonlama onayı"),
        ("Tahmin sun", "tüm kurulu modeller"),
        ("Taramayı çalıştır", "model ve kapsam onayı"),
        ("Rapor üret", "JSON • MD • HTML"),
        ("İlk ikiyi seç", "önem ve güven sırası"),
        ("Düzelt / test et", "ayrı onay kapıları"),
        ("PR oluştur", "son onay • GitHub"),
    ]
    for index, (title, detail) in enumerate(steps):
        row, col = divmod(index, 3)
        _step(slide, 0.78 + col * 4.02, 1.95 + row * 1.62, 3.75, index + 1, title, detail, [TEAL, CYAN, GOLD][col])
    _footer(slide, 6)


def _architecture_slides(presentation):
    slide = _new_slide(presentation)
    _header(slide, "06  •  Mimari", "Sorumlulukları ayrılmış, yerel çalışan bileşenler", "Terminal arayüzü kullanıcıyı yönlendirir; araçlar belirli girdilerle sınırlı işler yapar.")
    _card(slide, 0.75, 2.0, 3.7, 1.65, "Sohbet arayüzü", ["Türkçe doğal dil etkileşimi", "Proje promptu ve onay istemleri"], TEAL)
    _card(slide, 4.82, 2.0, 3.7, 1.65, "LangChain akışı", ["Tahmin → onay → tarama", "Rapor → düzeltme planı"], CYAN)
    _card(slide, 8.89, 2.0, 3.7, 1.65, "Yerel servisler", ["Ollama • BM25", "Git • test araçları • gh"], GOLD)
    _card(slide, 0.75, 4.05, 3.7, 1.65, "Girdi", ["PDF'ler ve JSON bağlantıları", "Kullanıcının seçtiği depo"], CYAN, BLUE_PALE)
    _card(slide, 4.82, 4.05, 3.7, 1.65, "Kayıtlar", ["Yerel indeks ve tarama JSON'u", "Markdown/HTML raporları"], TEAL, GREEN_PALE)
    _card(slide, 8.89, 4.05, 3.7, 1.65, "Düzeltme alanı", ["İzole Git worktree", "Commit / push yalnız PR onayıyla"], GOLD, GOLD_PALE)
    _footer(slide, 7)

    slide = _new_slide(presentation)
    _header(slide, "07  •  Tarama doğruluğu", "Model çıktısı doğrudan bulgu sayılmaz", "Tarama kapsamı Git tarafından izlenen kaynak dosyalarıyla sınırlıdır.")
    _card(slide, 0.75, 2.02, 3.75, 2.5, "Bağlam seçimi", ["Kod dosyası için ilgili BM25 parçaları aranır", "İlgili mevzuat bulunmazsa dosya modele gönderilmez"], TEAL)
    _card(slide, 4.8, 2.02, 3.75, 2.5, "Kanıt kontrolü", ["Kod satırı dosyadaki içerikle karşılaştırılır", "Mevzuat sayfa atfı sunulan kaynakla eşleştirilir"], CYAN)
    _card(slide, 8.85, 2.02, 3.75, 2.5, "Raporlama", ["Geçersiz kanıtlı bulgular elenir", "Kısmi tarama ve sınırlamalar rapora yazılır"], GOLD)
    _box(slide, 0.75, 4.95, 11.85, 0.9, GOLD_PALE)
    _text(slide, "Doğrulama, hukuki doğruluk garantisi değildir.", 1.05, 5.16, 10.9, 0.4, size=17, color=NAVY, bold=True, align=PP_ALIGN.CENTER)
    _footer(slide, 8)

    slide = _new_slide(presentation)
    _header(slide, "08  •  Raporlar", "İncelenebilir bulgular ve açık sınırlamalar", "Her tarama için makinece okunabilir JSON ile paylaşılabilir Markdown ve HTML çıktısı üretilir.")
    _box(slide, 0.82, 1.95, 7.65, 4.1, WHITE)
    _text(slide, "MEVZUAT UYUMLULUK TARAMA RAPORU", 1.15, 2.18, 6.95, 0.34, size=13, color=NAVY, bold=True)
    _text(slide, "Depo  •  dal/commit  •  model  •  tarama kapsamı", 1.15, 2.65, 6.9, 0.28, size=10, color=MUTED)
    _box(slide, 1.15, 3.15, 6.9, 0.76, GOLD_PALE)
    _text(slide, "HIGH   |   Kaynak atıflı örnek bulgu", 1.38, 3.34, 6.4, 0.3, size=13, color=NAVY, bold=True)
    _text(slide, "Dosya/satır • güven puanı • mevzuat sayfası • kod kanıtı • öneri", 1.25, 4.12, 6.7, 0.4, size=11, color=INK)
    _text(slide, "Kapsam ve sınırlar", 1.25, 4.85, 2.2, 0.32, size=12, color=TEAL, bold=True)
    _text(slide, "Kısmi tarama, atlanan dosyalar ve model hataları ayrıca gösterilir.", 1.25, 5.22, 6.7, 0.48, size=11, color=MUTED)
    _card(slide, 8.8, 2.05, 3.8, 1.15, "Markdown", ["Kod inceleme ve sürüm kontrolü için"], TEAL)
    _card(slide, 8.8, 3.45, 3.8, 1.15, "HTML", ["Stilli, tarayıcıda açılabilir rapor"], CYAN)
    _card(slide, 8.8, 4.85, 3.8, 1.15, "Güven ilkesi", ["Bulgu yoksa bu, uygunluk kanıtı değildir"], GOLD)
    _footer(slide, 9)


def _remediation_slides(presentation):
    slide = _new_slide(presentation)
    _header(slide, "09  •  Gereksinim 8", "İlk iki bulgu için kontrollü remediation", "Uygulama, model önerisini otomatik olarak kod tabanına yazmaz.")
    stages = [
        ("Sırala", "Önem seviyesi ve güven puanıyla ilk iki bulguyu seç."),
        ("Öner", "Yerel Ollama modelinden değişiklik önerisi al."),
        ("Doğrula", "Dosya yolu ve kanıt satırını bulguyla eşleştir."),
        ("İncele", "Markdown/HTML diff raporunu kullanıcıya göster."),
        ("Onayla", "Açık onaydan sonra izole worktree'de uygula."),
    ]
    for index, (title, body) in enumerate(stages):
        _step(slide, 0.78 + index * 2.42, 2.4, 2.18, index + 1, title, body, [TEAL, CYAN, GOLD, TEAL, RED][index])
    _box(slide, 0.8, 4.52, 11.75, 1.03, BLUE_PALE)
    _text(slide, "Kaynak depo korunur", 1.08, 4.7, 2.3, 0.3, size=14, color=NAVY, bold=True)
    _text(slide, "Değişiklikler ayrı Git worktree/dalında tutulur; kaynak kopyaya otomatik yazılmaz.", 3.4, 4.66, 8.7, 0.4, size=13, color=INK)
    _text(slide, "Önerinin doğruluğu garanti edilmez; insan diff'i inceleyip ayrıca onaylar.", 1.08, 5.85, 11.0, 0.34, size=12, color=MUTED)
    _footer(slide, 10)

    slide = _new_slide(presentation)
    _header(slide, "10  •  Gereksinim 9", "Test ve GitHub PR için ayrı onay kapıları", "Tarama izni; kod çalıştırma, commit veya GitHub'a gönderme izni değildir.")
    _card(slide, 0.78, 2.05, 3.75, 2.35, "1. Test onayı", ["Sabit ve desteklenen araç seçilir", "Zaman aşımı uygulanır", "Çıktı MD/HTML raporlanır"], TEAL)
    _card(slide, 4.79, 2.05, 3.75, 2.35, "2. Son kontrol", ["Test başarılı olmalı", "Yalnız beklenen dosyalar değişmeli", "Diff ve dal kullanıcıca incelenmeli"], CYAN)
    _card(slide, 8.8, 2.05, 3.75, 2.35, "3. PR onayı", ["gh kimlik doğrulaması gerekir", "Commit ve push gerçekleşir", "GitHub PR bağlantısı raporlanır"], GOLD)
    _box(slide, 0.78, 4.8, 11.77, 0.88, GOLD_PALE)
    _text(slide, "Gerçek GitHub PR bu proje doğrulamasında açılmadı; PR akışı yerel sahte remote ile test edildi.", 1.02, 5.02, 11.25, 0.38, size=13, color=NAVY, bold=True, align=PP_ALIGN.CENTER)
    _footer(slide, 11)


def _installation_slides(presentation):
    slide = _new_slide(presentation)
    _header(slide, "11  •  Kurulum ve kullanım", "macOS'ta anlaşılır, tekrar çalıştırılabilir kurulum", "Kurulum; çevreyi hazırlar, isteğe bağlı ağ/model işlemlerini kullanıcıya bırakır.")
    steps = [
        ("Başlat", "Kurulum.command veya ./install.sh"),
        ("Kontrol et", "macOS • Git • Python 3.10+"),
        ("Hazırla", ".venv ve proje paketleri"),
        ("Doğrula", "JSON ve çalışma klasörleri"),
        ("Seçim sun", "Ollama • belge • depo"),
        ("Sohbeti başlat", "mevzuat-agent • yerel Ollama"),
    ]
    for index, (title, detail) in enumerate(steps):
        row, col = divmod(index, 3)
        _step(slide, 0.82 + col * 4.0, 2.05 + row * 1.75, 3.72, index + 1, title, detail, [TEAL, CYAN, GOLD][col])
    _box(slide, 0.82, 5.75, 11.72, 0.58, GREEN_PALE)
    _text(slide, "Varsayılan davranış: depoları klonlama, model indirme veya mevzuat indirme otomatik onaysız yapılmaz.", 1.0, 5.84, 11.35, 0.33, size=11, color=NAVY, bold=True, align=PP_ALIGN.CENTER)
    _footer(slide, 12)

    slide = _new_slide(presentation)
    _header(slide, "12  •  Onay modeli", "Bir onay, sonraki işlemlere taşınmaz", "Etkisi dış sisteme veya kod çalıştırmaya uzanan işlemler kendi onaylarını ister.")
    names = [
        ("Klonla", "repo_link.json\ndepoları indir", TEAL),
        ("Tara", "Tahmini gör\nmodeli ve kapsamı seç", CYAN),
        ("Değiştir", "Diff'i incele\nizole dala uygula", GOLD),
        ("Test et", "Seçilen testleri\nçalıştır", TEAL),
        ("PR aç", "Commit • push\nGitHub PR", RED),
    ]
    for index, (title, detail, color) in enumerate(names):
        x = 0.72 + index * 2.48
        _box(slide, x, 2.4, 2.16, 2.2, WHITE)
        _box(slide, x + 0.72, 2.72, 0.7, 0.7, color)
        _text(slide, str(index + 1), x + 0.72, 2.75, 0.7, 0.62, size=19, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
        _text(slide, title, x + 0.2, 3.58, 1.76, 0.35, size=15, color=NAVY, bold=True, align=PP_ALIGN.CENTER)
        _text(slide, detail, x + 0.15, 4.0, 1.86, 0.5, size=10, color=MUTED, align=PP_ALIGN.CENTER)
        if index < 4:
            _text(slide, "›", x + 2.15, 3.28, 0.28, 0.4, size=24, color=TEAL, bold=True, align=PP_ALIGN.CENTER)
    _box(slide, 1.0, 5.23, 11.3, 0.82, BLUE_PALE)
    _text(slide, "Kullanıcı her kritik adımda kapsamı ve olası yan etkiyi yeniden görür.", 1.28, 5.42, 10.75, 0.34, size=15, color=NAVY, bold=True, align=PP_ALIGN.CENTER)
    _footer(slide, 13)


def _testing_slides(presentation):
    slide = _new_slide(presentation)
    _header(slide, "13  •  Doğrulama", "Otomatik testler akış sınırlarını doğrular", "Testler kodun mevzuata uygunluğunu değil, yazılım davranışını ve onay kapılarını denetler.")
    _box(slide, 0.8, 2.0, 3.35, 2.55, NAVY)
    _text(slide, "56", 1.02, 2.25, 2.9, 0.9, size=44, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
    _text(slide, "geçen otomatik test", 1.05, 3.25, 2.85, 0.38, size=15, color=CYAN, bold=True, align=PP_ALIGN.CENTER)
    _text(slide, "13 uyarı: bağımlılık deprecation uyarıları", 1.02, 3.83, 2.9, 0.36, size=9, color=RGBColor(213, 225, 238), align=PP_ALIGN.CENTER)
    _card(slide, 4.5, 2.0, 3.78, 2.55, "Kapsanan alanlar", ["JSON ve RAG hazırlama", "Model tahmini/onay akışı", "Kanıt ve rapor üretimi", "Remediation, test ve PR"], TEAL)
    _card(slide, 8.62, 2.0, 3.78, 2.55, "Test yaklaşımı", ["Onaysız adımların reddi", "İzole geçici Git depoları", "Sahte GitHub yanıtları", "Sabit test araçları ve timeout"], CYAN)
    _text(slide, "56 otomatik test yazılım davranışını doğrular; gerçek model çıktısı hukuki doğruluğu kanıtlamaz.", 0.95, 5.0, 11.2, 0.42, size=11, color=MUTED, align=PP_ALIGN.CENTER)
    _footer(slide, 14)

    slide = _new_slide(presentation)
    _header(slide, "14  •  Test verisi", "İki demo, toplam on sentetik bulgu", "Demo depoları uygulama akışını güvenli biçimde denemek için hazırlanmıştır.")
    _card(slide, 0.82, 2.05, 3.72, 2.25, "demo1", ["5 sentetik bulgu", "Örnek iş kuralı kodu", "Tarama ve düzeltme raporları"], TEAL)
    _card(slide, 4.8, 2.05, 3.72, 2.25, "demo2", ["5 sentetik bulgu", "İkinci örnek senaryo", "Tarama ve düzeltme raporları"], CYAN)
    _box(slide, 8.78, 2.05, 3.72, 2.25, GOLD_PALE)
    _text(slide, "YALNIZCA TEST", 9.03, 2.35, 3.22, 0.5, size=19, color=NAVY, bold=True, align=PP_ALIGN.CENTER)
    _text(slide, "Gerçek mevzuat ihlali değildir.\nTEST_FIXTURE_NOT_LAW", 9.03, 3.05, 3.22, 0.62, size=13, color=INK, align=PP_ALIGN.CENTER)
    _box(slide, 0.82, 4.72, 11.68, 0.92, BLUE_PALE)
    _text(slide, "Fixture yerel ve deterministiktir; sentetik kodu üretim sistemlerinde kullanmayın.", 1.08, 4.94, 11.1, 0.4, size=14, color=NAVY, bold=True, align=PP_ALIGN.CENTER)
    _footer(slide, 15)

    slide = _new_slide(presentation)
    _header(slide, "15  •  Gerçek uçtan uca deneme", "Model hatası ve deterministik demo ayrı raporlandı", "Gerçek model kalitesi ile akışın yazılım testleri birbirinden ayrılır.")
    _card(
        slide,
        0.78,
        2.02,
        3.72,
        2.58,
        "Mevzuat hazırlığı",
        [
            "2 mevzuat PDF'i indirildi",
            "146 RAG parçası üretildi",
            "Yerel BM25 indeksi",
            "Demo fixture deposu hazır",
        ],
        TEAL,
    )
    _card(
        slide,
        4.8,
        2.02,
        3.72,
        2.58,
        "Gerçek model denemesi",
        [
            "llama3.2:1b yanıtı geçersiz JSON",
            "Model taraması: 0 doğrulanmış dosya",
            "Gerçek remediation durduruldu",
            "Hata raporda açıkça gösterildi",
        ],
        CYAN,
    )
    _card(
        slide,
        8.82,
        2.02,
        3.72,
        2.58,
        "Deterministik E2E",
        [
            "Fixture üzerinden 2 sentetik bulgu",
            "Remediation izole worktree'de",
            "pytest: 2 geçti",
            "PR yanıtı yerel mock ile doğrulandı",
        ],
        GOLD,
    )
    _box(slide, 0.78, 4.92, 11.76, 0.98, GOLD_PALE)
    _text(slide, "Canlı model taraması başarısız olduğunda sentetik rapor yalnızca demo/test amacıyla ayrı üretilir; gerçek tarama veya PR girdisi olmaz.", 1.03, 5.1, 11.23, 0.58, size=12, color=NAVY, bold=True, align=PP_ALIGN.CENTER)
    _footer(slide, 16)

    slide = _new_slide(presentation)
    _header(slide, "16  •  Remediation kabul denemesi", "İlk iki sentetik bulgu, izole dalda test edildi", "Model taramasının bulguları tutarsız olduğundan düzeltme hattı önceden etiketlenmiş sentetik fixture bulgularıyla ayrıca sınandı.")
    _step(slide, 0.82, 2.05, 3.72, "1", "Önce başarısız", "Yeni kabul testleri iki bilinen hatayı yakaladı.", RED)
    _step(slide, 4.82, 2.05, 3.72, "2", "Öneri ve diff", "Model maskenin yanlış tarafını önerdi; incelemede düzeltildi ve worktree'ye uygulandı.", CYAN)
    _step(slide, 8.82, 2.05, 3.72, "3", "Test ve PR provası", "2 kabul testi geçti; push yerel bare remote'a, gh yanıtı taklitçiye yöneldi.", TEAL)
    _box(slide, 0.82, 4.02, 11.72, 1.18, BLUE_PALE)
    _text(slide, "Dış GitHub etkisi yok", 1.12, 4.24, 2.5, 0.34, size=15, color=NAVY, bold=True)
    _text(slide, "Gerçek PR açılmadı. Akışın commit/push/PR bağlantısı adımları gerçek fixture Git geçmişi ve yerel sahte GitHub CLI ile sınandı.", 3.72, 4.17, 8.35, 0.58, size=13, color=INK)
    _text(slide, "Test verisi `TEST_FIXTURE_NOT_LAW` olarak işaretlidir; düzeltmeler hukuki uyumluluk kanıtı değildir.", 1.12, 5.54, 11.0, 0.38, size=12, color=MUTED, align=PP_ALIGN.CENTER)
    _footer(slide, 17)


def _scope_and_conclusion(presentation):
    slide = _new_slide(presentation)
    _header(slide, "20  •  Güvenlik ve mahremiyet", "Güvenli varsayılanlar ve açık sınırlar", "Kod ve mevzuat bağlamı yerel Ollama'ya gider; tarama akışı bulguları uzman incelemesine sunar.")
    _card(slide, 0.78, 2.0, 5.7, 2.2, "Kontroller", ["Klonlama ve tarama kullanıcı onaylıdır", "Düzeltme ayrı worktree'de uygulanır", "Test ve PR ayrı onay ister", "PR için yalnız beklenen dosyalar seçilir"], TEAL)
    _card(slide, 6.75, 2.0, 5.7, 2.2, "Kullanım sorumluluğu", ["İndirilen kaynağın güncelliğini denetleyin", "Yalnız güvendiğiniz projelerde test çalıştırın", "Model bulgusunu hukuk uzmanına doğrulatın", "Gerçek depoda yedek ve temiz çalışma alanı kullanın"], GOLD)
    _box(slide, 0.78, 4.68, 11.67, 0.98, GOLD_PALE)
    _text(slide, "Otomasyon kanıtı düzenler; hukuki görüş, kesin uygunluk kararı veya güvenlik sertifikası vermez.", 1.02, 4.92, 11.15, 0.44, size=14, color=NAVY, bold=True, align=PP_ALIGN.CENTER)
    _footer(slide, 20)

    slide = _new_slide(presentation)
    _header(slide, "21  •  Gereksinim izleme", "Ödev maddeleri ve uygulamadaki karşılıkları", "Maddeler, konuşmada verilen dokuz gereksinim üzerinden eşleştirilmiştir.")
    rows = [
        ("1", "Python/PyCharm • sohbet • Ollama • LangChain", "Proje promptu, yerel sohbet ve Runnable zinciri"),
        ("2", "mevzuat_link.json'dan indirme", "download_mevzuat aracı"),
        ("3", "Orta boy RAG parçaları", "1.200 karakter • 200 örtüşme • BM25"),
        ("4", "Onaylı depo klonlama", "clone_repositories + sohbet/pipeline onayı"),
        ("5", "Model havuzu tahmini", "Kurulu modelleri ölç • hızlıyı öner"),
        ("6", "Tahmin sonrası onaylı tarama", "Seçilen model/kapsam onayı"),
        ("7", "MD ve HTML tarama raporu", "Bulgular, kanıt, dosya sonucu, sınır"),
        ("8", "İlk iki bulguyu iyileştir", "Öneri • diff raporu • izole worktree"),
        ("9", "Top iki bulgu için GitHub PR", "Test onayı • son PR onayı • gh"),
    ]
    table_shape = slide.shapes.add_table(10, 3, Inches(0.78), Inches(1.92), Inches(11.76), Inches(4.75))
    table = table_shape.table
    table.columns[0].width = Inches(0.65)
    table.columns[1].width = Inches(4.45)
    table.columns[2].width = Inches(6.66)
    for row_index, values in enumerate([("No", "Gereksinim", "Uygulamadaki karşılık"), *rows]):
        for column_index, value in enumerate(values):
            cell = table.cell(row_index, column_index)
            cell.text = value
            cell.margin_left = Inches(0.1)
            cell.margin_right = Inches(0.08)
            cell.margin_top = Inches(0.035)
            cell.margin_bottom = Inches(0.02)
            cell.fill.solid()
            cell.fill.fore_color.rgb = NAVY if row_index == 0 else (WHITE if row_index % 2 else BLUE_PALE)
            for paragraph in cell.text_frame.paragraphs:
                paragraph.font.name = "Aptos"
                paragraph.font.size = Pt(11 if row_index else 12)
                paragraph.font.bold = row_index == 0
                paragraph.font.color.rgb = WHITE if row_index == 0 else INK
    _footer(slide, 21)

    slide = _new_slide(presentation)
    _header(slide, "22  •  Bilinen sınırlamalar", "Tamamlanan iş ve sonraki geliştirme alanları", "Kapsamı dürüstçe ayırmak, model çıktısına gereğinden fazla güvenilmesini önler.")
    _card(slide, 0.78, 2.02, 5.72, 2.65, "Uygulanan", ["PDF indirme ve sayfa metnini parçalama", "BM25 ile yerel mevzuat araması", "Onaylı tarama ve MD/HTML rapor", "İzole düzeltme, test ve PR akışları"], TEAL)
    _card(slide, 6.72, 2.02, 5.72, 2.65, "Henüz yok / garanti edilmez", ["OCR, vektör arama ve belge sürüm takibi", "Hukuki doğruluğun otomatik kanıtlanması", "Web arayüzü ve devam ettirilebilir işler", "Gerçek GitHub PR ile uçtan uca canlı doğrulama"], GOLD)
    _box(slide, 0.78, 5.12, 11.66, 0.82, GOLD_PALE)
    _text(slide, "Sonraki adımlar: PDF rubriğini doğrula • gerçek mevzuat örnekleriyle uzman değerlendirmesi yap • gerçek PR akışını yetkili test deposunda dene.", 1.0, 5.29, 11.2, 0.45, size=11, color=NAVY, bold=True, align=PP_ALIGN.CENTER)
    _footer(slide, 22)

    slide = _new_slide(presentation)
    _header(slide, "23  •  Kısa demo", "Uygulamayı sunumda nasıl gösteririm?", "Sentetik test deposunda, dış sisteme yan etki oluşturmadan ana akışı sergileyin.")
    demo = [
        ("01", "Sohbeti başlat", "mevzuat-agent → yerel Ollama modeli"),
        ("02", "Kapsamı seç", "1 veya 2; * tüm mevzuatlar"),
        ("03", "Pipeline'ı sürdür", "devam → sıradaki önerilen adım"),
        ("04", "Sentetik demo", "demo1 → beş deterministik fixture bulgusu"),
        ("05", "Raporu incele", "JSON/Markdown/HTML ve sınırlar"),
        ("06", "Remediation / PR", "Diff ve test; PR için ayrı onay gerekir"),
    ]
    for index, (number, title, detail) in enumerate(demo):
        row, col = divmod(index, 2)
        x = 0.9 + col * 6.0
        y = 1.95 + row * 1.42
        _box(slide, x, y, 5.55, 1.08, WHITE)
        _text(slide, number, x + 0.17, y + 0.22, 0.54, 0.32, size=13, color=TEAL, bold=True)
        _text(slide, title, x + 0.85, y + 0.15, 4.4, 0.32, size=14, color=NAVY, bold=True)
        _text(slide, detail, x + 0.85, y + 0.56, 4.4, 0.3, size=10, color=MUTED)
    _footer(slide, 23)

    slide = _new_slide(presentation, NAVY)
    _text(slide, "ÖZET", 0.86, 0.82, 3.0, 0.32, size=11, color=CYAN, bold=True)
    _text(slide, "İzlenebilir analiz.\nAçık onay. İnsan kararı.", 0.86, 1.48, 10.8, 1.72, size=34, color=WHITE, bold=True)
    _text(slide, "MevzuatAgent; yerel LLM ve RAG'i kontrollü kod inceleme, raporlama ve düzeltme akışına bağlar.", 0.9, 3.62, 10.7, 0.72, size=17, color=RGBColor(215, 227, 240))
    _box(slide, 0.9, 4.76, 11.25, 1.1, NAVY_LIGHT)
    _text(slide, "Kaynak notu: Bu sunum konuşmada verilen dokuz gereksinime göre hazırlanmıştır. Ekli dosya yalnızca PDF simgesi olarak erişilebildi; PDF içeriği ve rubriği doğrulanamadı.", 1.15, 4.94, 10.75, 0.68, size=11, color=WHITE)
    _footer(slide, 24, dark=True)


def _end_to_end_evidence_slides(presentation):
    slide = _new_slide(presentation)
    _header(
        slide,
        "18  •  Sohbetten rapora uçtan uca akış",
        "Kullanıcı sohbeti yönlendirir; pipeline her adımda onay ister",
        "Sistem promptu proje kapsamını korur; Ollama yanıtı ve pipeline işlemleri birbirinden ayrıdır.",
    )
    flow = [
        ("Sohbet", "Soru sor\nveya devam yaz"),
        ("Kapsam", "Mevzuat seç\n1 • 2 • tümü"),
        ("Hazırlık", "PDF → RAG\nRepo → klon"),
        ("Tahmin", "Model hızı\nToken • süre"),
        ("Tarama", "Kapsam ve model\nkullanıcı onayı"),
        ("Rapor", "JSON • MD\nHTML • bulgu"),
    ]
    for index, (title, detail) in enumerate(flow):
        x = 0.72 + index * 2.08
        _box(slide, x, 2.15, 1.78, 1.68, WHITE)
        _text(slide, f"0{index + 1}", x + 0.15, 2.32, 0.4, 0.24, size=10, color=TEAL, bold=True)
        _text(slide, title, x + 0.15, 2.67, 1.48, 0.32, size=14, color=NAVY, bold=True)
        _text(slide, detail, x + 0.15, 3.1, 1.48, 0.5, size=10, color=MUTED)
        if index < len(flow) - 1:
            _text(slide, "→", x + 1.8, 2.78, 0.26, 0.32, size=17, color=TEAL, bold=True, align=PP_ALIGN.CENTER)
    _box(slide, 0.82, 4.28, 11.7, 1.15, BLUE_PALE)
    _text(slide, "Deterministik demo", 1.08, 4.5, 2.1, 0.3, size=14, color=NAVY, bold=True)
    _text(
        slide,
        "Model taraması JSON hatası veya bulgusuz sonuç verirse demo1/demo2 için ayrı sentetik rapor üretilebilir. Bu rapor gerçek mevzuat tespiti ve remediation girdisi değildir.",
        3.12,
        4.43,
        9.0,
        0.6,
        size=12,
        color=INK,
    )
    _text(slide, "İşlem adımları: sohbet komutu → pipeline önerisi → açık kullanıcı onayı → çıktı/rapor → sonraki adım.", 1.02, 5.82, 11.15, 0.35, size=12, color=MUTED, bold=True, align=PP_ALIGN.CENTER)
    _footer(slide, 18)

    slide = _new_slide(presentation)
    _header(
        slide,
        "19  •  Remediation, kod farkı ve PR",
        "İlk iki bulgu: diff → izole dal → test → PR",
        "Aşağıdaki değişiklik sentetik E2E fixture'ından alınmıştır; mevzuat düzeltmesi veya gerçek GitHub PR'ı değildir.",
    )
    _box(slide, 0.78, 1.95, 7.28, 3.85, NAVY)
    _text(slide, "ÖNCE  (payment_rules.py)", 1.05, 2.15, 6.7, 0.28, size=11, color=RED, bold=True, font="Aptos Mono")
    _text(
        slide,
        "def mask_reference(value, visible=4):\n    return value\n\ndef is_positive_amount(amount):\n    return amount >= 0",
        1.05,
        2.52,
        6.7,
        1.1,
        size=12,
        color=WHITE,
        font="Aptos Mono",
    )
    _text(slide, "SONRA  (yalnızca kullanıcı onayıyla)", 1.05, 3.82, 6.7, 0.28, size=11, color=TEAL, bold=True, font="Aptos Mono")
    _text(
        slide,
        "def mask_reference(value, visible=4):\n    return \"*\" * max(0, len(value)-visible) + value[-visible:]\n\ndef is_positive_amount(amount):\n    return amount > 0",
        1.05,
        4.18,
        6.7,
        1.32,
        size=10,
        color=WHITE,
        font="Aptos Mono",
    )
    _card(
        slide,
        8.38,
        1.98,
        4.15,
        1.02,
        "1 • İncele ve uygula",
        ["En yüksek iki bulgu", "Ayrı worktree / branch"],
        TEAL,
    )
    _card(
        slide,
        8.38,
        3.18,
        4.15,
        1.02,
        "2 • Testi onayla",
        ["Test raporu MD/HTML", "Başarısızsa PR durur"],
        CYAN,
    )
    _card(
        slide,
        8.38,
        4.38,
        4.15,
        1.02,
        "3 • PR için son onay",
        ["Commit + push + gh PR", "Her adım ayrı izin"],
        GOLD,
    )
    _box(slide, 0.82, 6.04, 11.7, 0.58, GOLD_PALE)
    _text(
        slide,
        "E2E kanıtı: test geçti; push yerel bare remote'a, PR yanıtı mock gh'ye yapıldı. Gerçek GitHub PR açılmadı.",
        1.0,
        6.15,
        11.2,
        0.32,
        size=11,
        color=NAVY,
        bold=True,
        align=PP_ALIGN.CENTER,
    )
    _footer(slide, 19)


def create_presentation():
    """Sunumu kaydeder."""
    presentation = Presentation()
    presentation.slide_width = Inches(WIDTH)
    presentation.slide_height = Inches(HEIGHT)
    presentation.core_properties.title = "MevzuatAgent - Ödev Sunumu"
    presentation.core_properties.subject = "Proje gereksinimleri, mimari, testler ve sınırlamalar"
    presentation.core_properties.author = "MevzuatAgent"

    _title_slide(presentation)
    _requirements_slides(presentation)
    _architecture_slides(presentation)
    _remediation_slides(presentation)
    _installation_slides(presentation)
    _testing_slides(presentation)
    _end_to_end_evidence_slides(presentation)
    _scope_and_conclusion(presentation)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    presentation.save(str(OUTPUT))
    print(f"Sunum oluşturuldu: {OUTPUT}")


if __name__ == "__main__":
    create_presentation()
