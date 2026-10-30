# MevzuatAgent

<p><img src="docs/assets/branding/softtech-logo-light-background.svg" alt="Softtech logosu" width="160"></p>

MevzuatAgent, kartlı ödeme sistemleri geliştiren yazılım depolarını kullanıcının
seçtiği mevzuat belgeleri ışığında incelemek için geliştirilen Python tabanlı
bir projedir. Ödeme başlatma/yetkilendirme, tutar ve para birimi kontrolleri,
tekrar deneme/idempotency, kart verisi maskeleme, iade ve mutabakat gibi alanlar
inceleme bağlamını oluşturur. Proje ödeme işlemi gerçekleştirmez ve canlı ödeme
altyapısına bağlanmaz; yalnızca onaylanan kod ve belge kapsamını analiz eder.
İndirme, mevzuat arama, tarama tahmini, bulgu raporlama ve kontrollü düzeltme
adımları ayrı ve kullanıcı onayına bağlıdır.


## İçindekiler

- [Proje durumu](#proje-durumu)
- [İş akışı](#iş-akışı)
- [Bileşenler](#bileşenler)
- [Kullanılan teknikler](#kullanılan-teknikler)
- [Sistem gereksinimleri](#sistem-gereksinimleri)
- [Kurulum](#kurulum)
- [Hızlı yerel test](#hızlı-yerel-test)
- [İlk çalıştırma](#ilk-çalıştırma)
- [Ödev rubriğiyle eşleşme](#ödev-rubriğiyle-eşleşme)
- [Yapılandırma dosyaları](#yapılandırma-dosyaları)
- [Belgeleri indirme ve RAG indeksi oluşturma](#belgeleri-indirme-ve-rag-indeksi-oluşturma)
- [Depo klonlama](#depo-klonlama)
- [Model havuzu ve tarama tahmini](#model-havuzu-ve-tarama-tahmini)
- [Onaylı tarama iş akışını çalıştırma](#onaylı-tarama-iş-akışını-çalıştırma)
- [Raporlar](#raporlar)
- [Remediation ve raporlar](#remediation-ve-raporlar)
- [Testleri çalıştırma](#testleri-çalıştırma)
- [Dizin yapısı](#dizin-yapısı)
- [Güvenlik ve gizlilik](#güvenlik-ve-gizlilik)
- [Bilinen sınırlamalar ve sonraki geliştirmeler](#bilinen-sınırlamalar-ve-sonraki-geliştirmeler)
- [Sorun giderme](#sorun-giderme)

## Proje durumu

Bu depo, Türkçe terminal menüsüyle çalışan Python araçlarını ve LangChain
tabanlı tarama zincirini içerir. Kurulumdan sonra `mevzuat-agent` komutu
mevzuat hazırlama, depo seçme, tahmin/onaylı tarama ve kontrollü remediation
adımlarını başlatır. Masaüstü/web arayüzü veya kalıcı sohbet ajanı değildir.

| İşlev | Durum |
|---|---|
| JSON yapılandırmalarını doğrulama | Uygulandı |
| Mevzuat PDF'lerini indirme | Uygulandı |
| PDF metnini orta boyutlu, örtüşen parçalara ayırma | Uygulandı |
| Yerel mevzuat araması | BM25 anahtar kelime ve isteğe bağlı sentence-transformers embedding aramasını RRF ile birleştirir |
| Kullanıcı onayından sonra depo klonlama | Araçta uygulandı |
| Kurulu Ollama modellerinin hızını ölçme ve süre tahmini | Uygulandı |
| Tahmin, tarama onayı, sınırlı tarama ve raporlamayı LangChain ile bağlama | Uygulandı; Python API |
| Markdown ve HTML tarama raporu | Uygulandı |
| En önemli iki bulgu için düzeltme planı | Uygulandı |
| Açık onayla izole worktree'de verilen düzeltmeyi uygulama | Araçta uygulandı |
| Türkçe terminal menüsüyle temel adımları çalıştırma | Uygulandı |
| En önemli iki bulgu için yerel Ollama düzeltme önerisi | Uygulandı; öneri kullanıcıya gösterilir |
| Onaylı remediation değişikliğini ayrı worktree'de uygulama | Uygulandı |
| Markdown ve HTML diff raporu oluşturma | Uygulandı; `MEVZUAT_AGENT_REPORTS_DIR` ile özelleştirilebilen kullanıcı rapor dizinine kaydedilir |
| Düzeltmenin hukuki doğruluğunu otomatik kanıtlama | Uygulanmadı; uzman incelemesi gerekir |

Menü, kod değişikliği için açık kullanıcı onayı ister. Onaydan sonra diff
raporları üretilir ve etkileşimli remediation akışı burada tamamlanır.

## İş akışı

1. Uygulama kendini tanıtır; kayıtlı mevzuat ve Git depo bağlantılarını listeler.
   Kullanıcı isterse yeni HTTP(S) mevzuat bağlantısı veya HTTPS/SSH depo
   bağlantısı ekleyebilir; bağlantılar ilgili JSON dosyasına kaydedilir.
2. `mevzuat_link.json` ve `repo_link.json` bağlantı dosyaları doğrulanır.
3. Mevzuat PDF'leri indirilir. Her sayfanın metni yaklaşık 1.200 karakterlik,
   200 karakter örtüşmeli parçalara ayrılır; kaynak dosya, sayfa ve parça
   konumu korunur.
4. RAG verisi yerel `chunks.jsonl` dosyasına yazılır; BM25 ve isteğe bağlı
   çok dilli sentence-transformers embedding araması reciprocal-rank fusion
   (RRF) ile birleştirilir. Tarama sırasında model ayrıca en fazla dört araç
   turunda `mevzuat_ara` ve yalnızca taranan dosyayı okuyabilen `dosya_oku`
   araçlarını seçer; araçlar kod çalıştıramaz veya dosya değiştiremez.
5. Depolar ancak açık kullanıcı onayından sonra yerel çalışma alanına klonlanır.
6. Seçilen depo ve dosya kapsamı için kurulu Ollama modelleri ölçülür; model
   başına tahmini token miktarı ve süre listelenir. En hızlı model önerilir.
   Yerel kullanım için fiyat bilgisi verilmediğinden parasal maliyet üretilmez.
7. Kullanıcı tahmin edilen modeller arasından birini seçip onaylamadan tarama
   başlamaz. İş akışı tarama öncesi branch ve commit değerlerinin tahminle
   aynı olduğunu kontrol eder.
8. Kod, ilgili mevzuat parçalarıyla birlikte Ollama'ya gönderilir. Kaynak satır
   kanıtı ve mevzuat sayfa/kaynak atfı doğrulanmayan bulgular elenir.
9. Tarama JSON'u, Markdown ve HTML raporları üretilir. Bulgu varsa en yüksek
   öncelikli iki bulgu için öneri planı oluşturulur.
10. Kullanıcı onaylı düzeltme ayrı worktree'de uygulanır; Markdown ve HTML
   diff raporları kullanıcı rapor dizinine kaydedilir ve akış sona erer.

## Bileşenler

| Dosya | Görevi |
|---|---|
| `src/mevzuat_agent/tools/validate_config.py` | Bağlantı JSON dosyalarını doğrular. |
| `src/mevzuat_agent/tools/mevzuat_config.py` | Mevzuat bağlantılarını okur ve kaydeder. |
| `src/mevzuat_agent/tools/download_mevzuat.py` | Mevzuat belgelerini indirir. |
| `src/mevzuat_agent/tools/build_mevzuat_rag.py` | PDF metnini parçalar, BM25 ve varsa çok dilli embedding indekslerini kurar. |
| `src/mevzuat_agent/tools/clone_repositories.py` | Açık onayla depoları klonlar; depo kodunu çalıştırmaz. |
| `src/mevzuat_agent/tools/estimate_scan_cost.py` | Kurulu modelleri ölçer ve tarama süresini tahmin eder. |
| `src/mevzuat_agent/tools/scan_repository.py` | Sınırlı dosya taraması yapar, kanıtı doğrulanmış bulguları kaydeder. |
| `src/mevzuat_agent/tools/generate_scan_report.py` | JSON sonuçtan Markdown ve HTML rapor üretir. |
| `src/mevzuat_agent/tools/prepare_remediation_plan.py` | En fazla iki bulgu için onay öncesi plan hazırlar. |
| `src/mevzuat_agent/tools/propose_remediation.py` | İlgili dosyalar için Ollama'dan sınırlı değişiklik önerisi alır. |
| `src/mevzuat_agent/tools/apply_remediation.py` | Onaylı içerikleri izole Git worktree ve dalına uygular, diff raporlar. |
| `src/mevzuat_agent/workflows/scan.py` | Tahmin, onay, tarama ve raporlamayı LangChain `Runnable` zincirinde bağlar. |
| `src/mevzuat_agent/console.py` | Türkçe etkileşimli menüyle belge, klonlama, tarama ve remediation adımlarını sunar. |
| `src/mevzuat_agent/prompts/system_prompt_tr.md` | Ajanın Türkçe kapsam ve onay kurallarını saklar. |

## Kullanılan teknikler

| Teknoloji / yaklaşım | Projedeki kullanımı |
|---|---|
| Python 3.10+ | Uygulama, araçlar, raporlama ve testler. |
| LangChain `Runnable` | Tahmin, kullanıcı onayı, tarama ve raporlamayı sıralı bir iş akışında orkestre eder. |
| Ollama | Yerel dil modeli çıkarımı; tarama sırasında `mevzuat_ara` ve `dosya_oku` araç çağrıları, remediation sırasında sınırlı kod önerileri. |
| RAG | Mevzuat PDF'lerini `pypdf` ile çıkarır, `RecursiveCharacterTextSplitter` ile kaynak/sayfa bilgisini koruyarak parçalara ayırır. |
| BM25 | Mevzuat parçaları üzerinde anahtar kelime tabanlı geri getirme. |
| Sentence Transformers | İsteğe bağlı çok dilli embedding modeliyle anlamsal geri getirme (`.[embeddings]` ekstra bağımlılığı). |
| Reciprocal Rank Fusion (RRF) | BM25 ve embedding sonuç sıralamalarını hibrit aramada birleştirir. |
| Kanıt doğrulama | Modelin kod satırı, mevzuat alıntısı, kaynak ve sayfa atıflarını rapora almadan önce doğrular. |
| Git worktree | Onaylanan değişiklikleri kaynak çalışma ağacından ayrı tutar; Markdown/HTML diff raporu üretir. |
| pytest | Birim ve entegrasyon testleri. |

## Sistem gereksinimleri

- macOS (kurulum dosyası macOS içindir; diğer sistemlerde Python adımları
  elle uygulanabilir).
- Python 3.10 veya üzeri. Python 3.12 önerilir; kurulum dosyası makinedeki
  uyumlu `python3` sürümünü kullanır.
- Git.
- Ollama ve tarama için en az bir yerel model. Başlangıç modeli
  `llama3.2:1b`'dir.
- Mevzuat belgelerini ilk kez indirirken internet bağlantısı.
- Modellerin indirilmesi ve çalıştırılması için yeterli disk alanı ve bellek.

PyCharm bir Python yorumlayıcısı sağlar/kurar, fakat Ollama'nın yerini almaz.
Ollama'yı [ollama.com/download](https://ollama.com/download) adresinden kurun
veya Homebrew kullanıyorsanız `brew install ollama` çalıştırın. Ollama yerel
servisi varsayılan olarak `http://localhost:11434` adresinde beklenir.

## Kurulum

### Kolay kurulum — macOS

Proje klasöründeki **`Kurulum.command`** dosyasına çift tıklayın. macOS
güvenlik uyarısı verirse dosyanın proje kaynağından geldiğini doğrulayıp
Terminal'den çalıştırın:

```bash
cd "/proje/klasorunuz/Final-Proje_MevzuatAgent"
chmod +x Kurulum.command
./Kurulum.command
```

Komut dosyası `install.sh` kurulum aracını başlatır. Kurulum:

1. macOS, Python ve Git gereksinimlerini kontrol eder.
2. Proje içinde `.venv` sanal ortamını oluşturur.
3. Python paketlerini `pyproject.toml` manifestinden yükler.
4. Gerekli çalışma klasörlerini oluşturur ve JSON yapılandırmalarını doğrular.
5. Ollama/LLM, mevzuat indirme ve repo klonlama adımlarını ayrı ayrı sorar.
   Depolar ancak bu kurulumda açıkça onaylanırsa klonlanır.

Kurulum adımları tekrar çalıştırılabilir. Mevcut `.venv` korunur; indirilen
belgelerin veya depoların üzerine yazılmaz. Kurulum dosyası Ollama'yı
onaysız kurmaz, model indirmez veya repo klonlamaz.

### Terminal'den kurulum

```bash
git clone https://github.com/mehmetdenizersoy-code/MevzuatAgent.git
cd MevzuatAgent
./install.sh
```

### Windows kurulumu

PowerShell'de Python 3.10+ ve Git'i kurup proje dizininde şu komutları çalıştırın:

```powershell
git clone https://github.com/mehmetdenizersoy-code/MevzuatAgent.git
cd MevzuatAgent
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest -q
python -m mevzuat_agent
```

PowerShell sanal ortam etkinleştirmesini engellerse, kullanıcı kapsamı için
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` komutunu çalıştırıp
etkinleştirmeyi tekrarlayın. Kod taraması için Ollama'yı Windows'a kurun,
Ollama uygulamasını başlatın ve `ollama pull gemma3:4b` ile yerel model indirin.
Ardından uygulamadan mevzuat PDF'lerini indirip RAG indeksini hazırlayın.

### Hibrit mevzuat aramasını etkinleştirme

Sentence-transformers embedding desteği isteğe bağlıdır. Model paketini kurup
RAG indeksini yeniden oluşturun:

```bash
.venv/bin/python -m pip install -e '.[embeddings]'
```

```powershell
python -m pip install -e ".[embeddings]"
```

İlk indeks oluşturma sırasında çok dilli embedding modeli indirilir ve yerelde
çalıştırılır. Bu ekstra kurulmazsa BM25 araması çalışmaya devam eder.

Kurulum dosyasının seçenekleri:

```bash
./install.sh --help
./install.sh --skip-model       # Ollama model indirme sorusunu atla
./install.sh --skip-ollama      # Ollama kurulum ve model indirme sorularını atla
./install.sh --skip-data        # Mevzuat indirme/RAG hazırlama sorusunu atla
./install.sh --skip-clone       # repo klonlama sorusunu atla
```

Kurulum sırasında seçilen adımlar dışında işlem yapılmaz. Ollama mevcut değilse
Python paketi kurulumu tamamlanır; Ollama kurulumu için resmi indirme adresi
gösterilir. Bu durumda kod taraması kullanılamaz.

### PyCharm ile açma

1. PyCharm'da **Open** ile proje klasörünü açın.
2. **Settings → Project → Python Interpreter** menüsünden proje içindeki
   `.venv/bin/python` yorumlayıcısını seçin.
3. Kurulum dosyasını çalıştırmadıysanız PyCharm Terminal'inde `./install.sh`
   çalıştırın.
4. Ollama'nın çalıştığını Terminal'de `ollama list` komutuyla kontrol edin.
5. Testleri PyCharm test penceresinden veya `.venv/bin/python -m pytest -q`
   komutuyla çalıştırın.

### Hızlı yerel test

İlk kez kuruyorsanız önce depoyu klonlayın:

```bash
git clone https://github.com/mehmetdenizersoy-code/MevzuatAgent.git ~/PycharmProjects/Final-Proje_MevzuatAgent
```

Gerçek bir Git deposu kullanın; üretim ödeme verisi veya sır içeren depolarda
çalıştırmayın. macOS Terminal veya PyCharm Terminal'de:

```bash
cd ~/PycharmProjects/Final-Proje_MevzuatAgent
git pull origin main
./install.sh --skip-model --skip-data --skip-clone
ollama pull gemma3:4b
ollama list
ollama run gemma3:4b "Sadece {} döndür."
.venv/bin/python -m pytest -q
.venv/bin/mevzuat-agent
```

Mevcut klonda yeniden çalıştırırken ilk `git clone` komutunu atlayın. Proje
klasörünüz farklı konumdaysa `cd` ve klonlama hedef yolunu değiştirin. Ollama
yüklü değilse [resmi kurulumdan](https://ollama.com/download) yükleyip
uygulamasını başlatın.

Modelin kısa deneme yanıtı vermesi, tarama çıktısının geçerli veya hukuken
doğru olacağını garanti etmez. Tarama yalnızca kanıtı doğrulanmış bulguları
sonraki adıma taşır; model hatası varsa remediation'a geçmeyin.

Uygulama basit bir sohbet olarak açılır. Mevzuat kapsamını listedeki numara,
dosya adı veya `*` (tümü) ile sohbette seçin; ör. `1` ya da `1,2`. Ardından
proje hakkında doğal dille soru sorabilir veya `devam` yazarak pipeline'ın
önerdiği adımı başlatabilirsiniz. `yardım` komutları, `çıkış` uygulamayı
kapatır. Sohbet yanıtları sistem promptuna ve güncel pipeline durumuna göre
yerel Ollama modeliyle üretilir.

Başlangıçta uygulama `mevzuat_link.json` içindeki mevzuat bağlantılarını ve
`repo_link.json` içindeki depo bağlantılarını listeler. Her iki liste için de
istenirse yeni bağlantı eklenebilir; girilen bağlantılar biçim kontrolünden
geçtikten sonra ilgili JSON dosyasına kaydedilir.

Pipeline aşamasını doğrudan sohbet isteğiyle de başlatabilirsiniz: `RAG
hazırla`, `depoları klonla`, `tarama yap`, `bulguları düzelt`. İndirme,
klonlama, tarama ve dosya değiştirme adımları ayrıca kullanıcı onayı ister.

Gerçek taramada tahmin ekranında taramayı onaylayın ve model listesinden uygun
bir yerel modeli seçin. Model hatası veya sıfır doğrulanmış bulgu varsa
remediation başlamaz. Önerilen diff'i inceleyip yalnızca onayladığınız
değişikliği uygulayın. Markdown ve HTML diff raporları, proje kökünde varsayılan
olarak `data/reports/remediation/` olan kullanıcı rapor dizinine kaydedilir;
akış raporlar oluşturulduktan sonra tamamlanır. Otomatik test, commit, push
adımı yoktur.

Uygulama son tarama raporundaki depo kökünü ve tarama JSON yolunu otomatik
bulur; bu yolları elle yazmanız gerekmez. Son taramadaki bulgular için geçerli
bir depo yolu bulunamazsa depoyu yeniden klonlayıp tarayın.

Tarama raporları `data/reports/scans/`, remediation raporları ise
`MEVZUAT_AGENT_REPORTS_DIR` ile belirtilen dizinde (varsayılan:
`data/reports/remediation/`) oluşur.

## İlk çalıştırma

Sanal ortamı etkinleştirin:

```bash
source .venv/bin/activate
```

Türkçe sohbet arayüzünü başlatma:

```bash
mevzuat-agent
# eşdeğeri:
python -m mevzuat_agent
```

Sohbette mevzuat kapsamını seçtikten sonra doğal dille proje hakkında
konuşabilir ve `devam` yazarak önerilen pipeline aşamasını çalıştırabilirsiniz.
Tarama sonunda doğrulanmış bulgu varsa uygulama aynı depo ve tarama raporuyla
remediation'a geçmek için ayrıca onay ister. Bulgu yoksa remediation başlatılmaz.

Remediation seçeneği, tarama JSON dosyasından en öncelikli iki bulguyu seçer;
Ollama önerisinin diff'ini gösterir. Yalnızca kod değişikliği için onay ister.
Değişiklik ayrı worktree'de uygulanır, Markdown ve HTML raporları kullanıcı
rapor dizinine kaydedilir ve etkileşimli akış burada biter.

## Ödev rubriğiyle eşleşme

Bootcamp kapanış projesi beş eşit ağırlıklı ölçütle değerlendirilir. Aşağıdaki
eşleme, uygulamanın gösterdiği kanıtları ve sınırlarını birlikte açıklar.

| Ölçüt (%20) | Projedeki karşılığı ve kanıt |
|---|---|
| Problem tanımı ve gerçek dünya uygunluğu | Kartlı ödeme yazılımlarında maskeleme, tutar ve idempotency gibi gerçekçi kontroller için mevzuat destekli ön inceleme. Çıktı uzman kararı veya uygunluk sertifikası değildir. |
| Agentic mimari ve eğitim yaklaşımları | Yerel Ollama'nın sınırlı araç döngüsünde `mevzuat_ara` ve `dosya_oku` araçlarını seçmesi, hibrit BM25/embedding mevzuat RAG'i ve çok adımlı LangChain `Runnable` akışı. Kalıcı hafıza, otonom planlayıcı ve çoklu agent yoktur. |
| İşlevsellik ve çıktı kalitesi | Depo taraması, kod kanıtı doğrulama ve Markdown/HTML raporlama akışları ile 61 otomatik test. Gerçek model çıktıları uzman incelemesi olmadan hukukî sonuç sayılmaz. |
| Kod kalitesi ve teknik uygulama | Modüler Python araçları, ayrı iş akışı ve testler; yerel Ollama kullanımı bulut LLM API anahtarı gerektirmez. |
| Dokümantasyon ve teslim | README'de proje amacı, teknoloji, kurulum ve çalıştırma adımları açıklanır. Gerçek depo çalıştırmasından alınacak terminal ve HTML rapor ekran görüntüleri sonradan eklenecektir. |

## Yapılandırma dosyaları

Proje kökündeki yapılandırmalar:

### `mevzuat_link.json`

İndirilecek belgelerin HTTP(S) bağlantılarını içerir:

```json
{
  "links": [
    "https://www.mevzuat.gov.tr/MevzuatMetin/1.5.5464.pdf"
  ]
}
```

### `repo_link.json`

Kullanıcı onayıyla klonlanabilecek HTTPS/SSH Git depo bağlantılarını içerir:

```json
{
  "repos": [
    "https://github.com/ornek/uygulama.git"
  ]
}
```

Bağlantıları doğrulayın:

```bash
.venv/bin/python - <<'PY'
from mevzuat_agent.tools.validate_config import validate_config

result = validate_config(".")
for error in result.errors:
    print(error)
if result.is_valid:
    print("Yapılandırma geçerli.")
PY
```

## Belgeleri indirme ve RAG indeksi oluşturma

Bu adımı kurulumda seçebilir veya elle başlatabilirsiniz:

```bash
.venv/bin/python - <<'PY'
from mevzuat_agent.tools.download_mevzuat import download_mevzuat
from mevzuat_agent.tools.build_mevzuat_rag import build_mevzuat_rag

download = download_mevzuat("data/legislation/downloads")
for document in download.documents:
    print(f"İndirildi: {document.path} ({document.size_bytes} bayt)")
for error in download.errors:
    print(f"İndirme hatası: {error}")
if download.errors and not download.documents:
    raise SystemExit("Mevzuat belgeleri indirilemedi.")

rag = build_mevzuat_rag(
    "data/legislation/downloads",
    "data/legislation/rag",
    chunk_size=1200,
    chunk_overlap=200,
)
print(f"Parça sayısı: {len(rag.chunks)}")
print(f"İndeks: {rag.index_path}")
for error in rag.errors:
    print(f"RAG uyarısı: {error}")
if not rag.chunks:
    raise SystemExit("Aranabilir mevzuat metni oluşturulamadı.")
PY
```

Üretilen önemli dosyalar:

- İndirilen kaynaklar: `data/legislation/downloads/`
- BM25 parçaları: `data/legislation/rag/chunks.jsonl`
- İndeks özeti: `data/legislation/rag/manifest.json`

Bu RAG çözümü yerel metin eşleşmesi yapar; vektör embedding veya semantik
vektör veritabanı değildir. PDF taranmış görüntülerden oluşuyorsa metin
çıkarımı boş kalabilir; OCR şu anda uygulanmamıştır. Mevzuat PDF'lerini
yeniden indirmek için var olan hedef dosyaları elle silmeden önce yedek alın;
indirme aracı mevcut dosyanın üzerine yazmaz.

## Depo klonlama

Kurulum dosyası `repo_link.json` içindeki depoları klonlamak için ayrıca onay
ister. Elle kullanmak için:

```bash
.venv/bin/python - <<'PY'
from mevzuat_agent.tools.clone_repositories import clone_repositories

result = clone_repositories(
    "data/repositories",
    config_path="repo_link.json",
    user_approved=True,  # Bu değeri yalnızca depoları klonlamayı onayladıysanız verin.
)
for checkout in result.checkouts:
    print(f"Klonlandı: {checkout.path}")
for error in result.errors:
    print(f"Klonlama hatası: {error}")
PY
```

`user_approved=True` açık onay anlamına gelir. Araç repo kodunu çalıştırmaz.
Daha önce aynı adla yerel depo varsa üzerine yazmaz; hata olarak bildirir.

## Model havuzu ve tarama tahmini

Ollama yerel servisinin çalıştığını ve model bulunduğunu kontrol edin:

```bash
ollama list
ollama pull llama3.2:1b
```

`ollama pull` yalnızca model indirmeyi siz istediğinizde çalıştırın. Model
havuzu tahmin aracı kurulu Ollama modellerini kısa isteklerle ölçer; tüm
modeller ve en hızlı öneri için:

```python
from mevzuat_agent.tools.estimate_scan_cost import estimate_scan_cost_for_model_pool

estimate = estimate_scan_cost_for_model_pool(
    ["data/repositories/your-repository"],
    rag_index_path="data/legislation/rag/chunks.jsonl",
    max_files=5,
)
for model in estimate.models:
    print(
        f"{model.model}: {model.tokens_per_second:.2f} token/sn, "
        f"tahmini {model.estimated_seconds} sn"
    )
print("Önerilen model:", estimate.recommended_model)
```

Tahmini süre benchmark ve yaklaşık token sayımına dayanır; donanım, modelin
ilk yüklenme süresi, bağlam uzunluğu ve Ollama ayarlarına göre değişir. Yerel
LLM kullanımı için parasal birim fiyat verilmediğinden parasal bedel
hesaplanmaz. `max_files` ile belirlenen tahmin kapsamı, tarama kapsamıyla aynı
olmalıdır.

## Onaylı tarama iş akışını çalıştırma

Tarama zinciri model tahminini ve kullanıcı onayını zorunlu kılar. Callback
model listesini kullanıcıya gösterir; `None` döndürmek taramayı reddeder,
ölçülen modellerden birinin adını döndürmek onay verir:

```python
from mevzuat_agent.workflows.scan import run_scan_workflow

def tarama_onayi(istek):
    print("Dosya sınırı:", istek.max_files)
    for model in istek.estimate.models:
        print(
            f"{model.model}: {model.tokens_per_second:.2f} token/sn; "
            f"yaklaşık {model.estimated_seconds} sn"
        )
    print("Önerilen:", istek.recommended_model)
    secim = input("Model adını yazarak taramayı onaylayın; vazgeçmek için Enter: ")
    return secim.strip() or None

sonuc = run_scan_workflow(
    ["data/repositories/your-repository"],
    max_files=5,
    rag_index_path="data/legislation/rag/chunks.jsonl",
    output_dir="data/reports/scans",
    approval_callback=tarama_onayi,
)
print("Durum:", sonuc.status)
for depo in sonuc.repositories:
    print("Tarama JSON:", depo.scan.output_path)
    print("Markdown:", depo.markdown_report)
    print("HTML:", depo.html_report)
    if depo.remediation_plan:
        print("Düzeltme planı:", depo.remediation_plan)
```

Örneği `ornek_tarama.py` gibi bir Python dosyasına kaydedip proje sanal
ortamında çalıştırabilirsiniz. Callback yalnızca model seçimini ve tarama
onayını temsil eder; kod değişikliği onayı vermez. İş akışı mevcut, yerel Git depolarını ve önceden hazırlanmış
RAG indeksini bekler.

## Raporlar

Tarama JSON çıktısı her depo için `data/reports/scans/` altında saklanır.
Yanında aynı temel ada sahip Markdown ve HTML dosyaları oluşturulur. Bulgu
bulunursa ayrıca `_remediation_plan.md` üretilir.

Raporlarda depo/commit, model, kapsam, tarih, incelenen dosya sayısı, bulgular,
kod kanıtı, mevzuat kaynağı ve sınırlamalar yer alır. Bulgu çıkmaması
uyumluluğun kanıtlandığı anlamına gelmez. HTML raporu kullanıcı/kod kaynaklı
değerleri HTML olarak kaçışlayarak yazar.

Gerçek depo çalıştırmasından alınan terminal ekran görüntüleri ve raporların
HTML görselleri, canlı tarama tamamlandıktan sonra bu bölüme eklenecektir.
Ödeme alanındaki bir kod örneği tek başına mevzuat bulgusu sayılmaz; ilgili
mevzuat metni ve kod kanıtı uzman tarafından doğrulanmalıdır.

## Remediation ve raporlar

`prepare_remediation_plan` yalnızca plan oluşturur; kendi başına kod
değiştirmez. `apply_remediation` ayrı, açık `user_approved=True` onayı ister.
Yalnızca en öncelikli iki bulguyla eşleşen dosyaları değiştirir. Kaynak
deponun Git çalışma ağacının temiz olmasını, bulgu kanıtının kaynak satırda
bulunmasını ve verilen metin değişikliklerinin bu dosyalarla sınırlı olmasını
kontrol eder. Değişikliği ayrı bir `mevzuatagent/remediation-*` dalı ve
worktree içinde uygular; kaynak dalı değiştirmez ve otomatik commit oluşturmaz.

Onaylı değişiklik için Markdown ve HTML diff raporları, varsayılan olarak
`data/reports/remediation/` dizinine yazılır; etkileşimli akış raporlar
oluşturulduktan sonra tamamlanır. Başka bir kullanıcı rapor dizini seçmek için
`MEVZUAT_AGENT_REPORTS_DIR` ortam değişkenini mutlak veya göreli bir yola
ayarlayın. macOS/Linux örneği:

```bash
export MEVZUAT_AGENT_REPORTS_DIR="$HOME/Documents/MevzuatAgent-Raporlar"
```

PowerShell örneği:

```powershell
$env:MEVZUAT_AGENT_REPORTS_DIR = "$HOME\Documents\MevzuatAgent-Raporlar"
```

Kaynak depo değiştirilmez; etkileşimli akış raporlar oluşturulduktan sonra
tamamlanır ve ek bir otomatik adım çalıştırmaz.

## Testleri çalıştırma

```bash
.venv/bin/python -m pytest -q
```

Testler için Ollama servisi veya gerçek GitHub bağlantısı gerekmez. Testler
depo içindeki yerel fixture'ları kullanır; bunlar canlı tarama raporu değildir.

## Dizin yapısı

```text
.
├── Kurulum.command                 # macOS çift tıklama başlatıcısı
├── install.sh                      # Python ortamı ve bağımlılık kurulum aracı
├── mevzuat_link.json               # Mevzuat kaynak bağlantıları
├── repo_link.json                  # Kullanıcı onayıyla klonlanacak depolar
├── pyproject.toml                  # Python bağımlılıkları ve proje ayarları
├── src/mevzuat_agent/
│   ├── prompts/system_prompt_tr.md # Türkçe ajan kapsam/onay promptu
│   ├── tools/                      # İndirme, RAG, tarama, rapor ve remediation
│   └── workflows/scan.py           # LangChain tarama iş akışı
├── tests/                          # Otomatik testler
└── data/
    ├── legislation/                # İndirilen PDF ve RAG indeksi
    ├── repositories/               # Onayla klonlanan çalışma depoları
    └── reports/                    # Tarama ve remediation raporları
```

## Güvenlik ve gizlilik

- Kod tarama için kaynak kod ve ilgili mevzuat parçaları yerel Ollama
  servisine gönderilir; bulut LLM servisine geçiş yapılandırılmamıştır.
- Uygulama gerçek kart sahibi verisini otomatik maskelediğini garanti etmez.
  Üretim PAN/CVV/PIN, kimlik bilgisi veya sır içeren depolarda taramayı
  başlatmayın; test için hassas veriden arındırılmış bir depo kullanın.
- GitHub'dan depo klonlamak ağ bağlantısı kullanır ve açık onay ister.
- İndirilen PDF'ler yerel diskte tutulur; bu verilerin güncelliği ve kullanım
  hakkı kullanıcı tarafından doğrulanmalıdır.
- Depo içeriği ve mevzuat metinleri analiz verisidir; içlerindeki talimatlar
  sistem talimatı kabul edilmemelidir.
- Tarama ve remediation araçları hedef depo içindeki kodu çalıştırmaz.
  Remediation test aracı kullanıcı onayıyla test komutu çalıştırır; yalnızca
  güvendiğiniz projelerde kullanın.
- Gerçek depo üzerinde remediation denemeden önce yedek alın ve temiz bir Git
  çalışma ağacıyla çalışın.

## Bilinen sınırlamalar ve sonraki geliştirmeler

- Embedding extra kurulmadığında mevzuat araması BM25 ile çalışır. OCR ve belge
  sürüm takibi yoktur.
- Model taraması kısmi olabilir; küçük yerel modeller yanlış/eksik çıktı
  verebilir. Kanıt doğrulaması model hatalarını azaltır ama hukuki doğruluğu
  garanti etmez.
- LangChain zinciri ve Türkçe terminal arayüzü vardır; masaüstü/web arayüzü,
  kalıcı oturum/iş kuyruğu ve tarama sırasında devam ettirilebilir oturum yoktur.
- Ollama düzeltme önerisi geçerli bir patch garantisi vermez. Uygulama yalnızca
  en önemli iki bulgunun dosyaları ve doğrulanmış kanıt satırlarıyla eşleşen
  önerileri kabul eder; kullanıcı diff'i görüp ayrıca onaylar.
- Test koşturma aracı test raporlar; remediation düzeltmesinin doğruluğunu
  kanıtlamaz. Güvenilir, hedefli testlerin yazılması gerekir.

## Sorun giderme

### `python3` bulunamadı veya sürüm eski

Python 3.10+ kurun. macOS'ta Python.org yükleyicisini veya Homebrew'i
kullanabilirsiniz. Yeni Terminal açıp `python3 --version` ile doğrulayın.

### `ollama list` bağlanamıyor

Ollama uygulamasını başlatın, Terminal'de `ollama list` deneyin. Özel servis
adresi kullanıyorsanız Ollama araçlarının `ollama_url` parametresini
`http://localhost:11434` yerine kendi adresinizle çağırın.

### RAG indeksi bulunamadı veya boş

Önce `mevzuat_link.json` bağlantılarının erişilebilir olduğunu kontrol edin;
belgeleri indirin ve `build_mevzuat_rag` çalıştırın. `manifest.json` içindeki
hataları inceleyin. İndeks oluşturulurken kullanılabilir metin parçası
çıkmamışsa tarama başlamaz.

### Depo taraması bulunamadı

Tarama yalnızca Git tarafından izlenen kaynak dosyaları inceler. Yeni dosyaları
önce commit edin veya taramayı commit edilmiş bir test deposunda deneyin.
İncelenecek dosya sayısını `max_files` ile sınırlayın.

### Kurulum bağımlılıkları yüklenemedi

Proje kökünde `./install.sh` komutunu yeniden çalıştırın. Ağ/paket yöneticisi
hatasını çözmeden sanal ortamı silmeyin; hata mesajında belirtilen paketi ve
Python sürümünü kontrol edin.
