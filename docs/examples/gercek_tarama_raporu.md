# Mevzuat Uyumluluk Tarama Raporu

- **Depo:** `data/repositories/demo1`
- **Dal / commit:** `master@203506d`
- **Model:** `qwen3:4b`
- **Kapsam:** first 2 tracked source files (limit 2)
- **Tarih:** 2026-10-29T16:09:02.020466+00:00
- **İncelenen dosya:** 2 / 59
- **Doğrulanmış bulgu:** 1

> Bu rapor otomatik araç tarafından oluşturulmuştur. Bulguları uygulamadan önce kod ve mevzuat kaynağını uzmanla doğrulayın.

## Bulgular

### 1. [CRITICAL] Üye işyerlerinden komisyon tutarları ile ilgili bilgi saklama ve açıklama yetkisi

- **Konum:** `samples/ThreeDPayment.Sample/Controllers/HomeController.cs:1`
- **Güven:** 1 / 10
- **Mevzuat kaynağı:** `002_GeneratePdf`, sayfa 7
- **Açıklama:** Kodda 1. satır '/*' ile başlayan yorum satırı, mevzuatın 'MADDE 25' ve 'MADDE 31' hükümlerine uyumsuz olarak üyen işyerlerin komisyon tutarları ve sırların saklanması konusunda yetki ve sorumluluk belirlemektedir. Mevzuatta, üye işyerlerin kart hamilinin yazılı rızasını almadan başkasına açıklayamaması ve sırların saklanması gerektiği belirtilmiştir. Ancak kodda yorum satırı, bu konuda yetki ve sorumlulukların doğru şekilde uygulanmasını desteklemek için gerekli olan bilgileri saklamamaktadır.
- **Öneri:** Üye işyerlerin komisyon tutarları ve kart hamilleri ile ilgili bilgilerin saklanması ve açıklanması konusunda mevzuat hükümlerine uygun olarak yetki ve sorumlulukları belirlemelidir. Yorum satırlarının yerine, mevzuat hükümlerini uygulamak için gerekli olan bilgileri kodda açıkça ifade etmelidir.

**Kod kanıtı:**

> `/*`

**Mevzuat metni:**

> f) Üye işyerlerinden sağlanan komisyon tutarları kart kuruluşlarınca aylık olarak Kuruma iletilir. Üye işyerleri MADDE 25 –  (1) Üye işyerleri, kartın kullanımı sonucunda kart ve kart hamili ile ilgili edindikleri bilgileri, kanunla yetkili kılınan kişi, kurum ve kuruluşlar hariç olmak üzere kart hamilinin yazılı rızasını almadan başkasına açıklayamaz, tahsilât amacıyla saklanan harcamaya ait bilgi ve belgeler ile kart hamilince verilen yazılı onay çerçevesinde, dönemsel ödemelerin tahsili amacıyla muhafaza edilen bilgi ve belgeler hariç olmak üzere saklayamaz

## Dosya sonuçları

- `samples/ThreeDPayment.Sample/Controllers/HomeController.cs` — **Tarandı**
- `samples/ThreeDPayment.Sample/Controllers/PaymentController.cs` — **Reddedilen bulgular var**
  - 0 numaralı bulgu reddedildi: finding 0 mevzuat evidence does not match the cited excerpt

## Sınırlamalar

- Kısmi tarama: 59 kaynak dosyasından 2 tanesi incelendi.
- samples/ThreeDPayment.Sample/Controllers/PaymentController.cs: dosyanın ilk 4000 karakteri incelendi.
- Kanıt doğrulamasından geçmeyen model bulguları rapora alınmadı.
