# Mevzuat Uyumluluk Tarama Raporu

- **Depo:** `synthetic-card-payment-demo`
- **Dal / commit:** `main@fixture`
- **Model:** `synthetic-fixture`
- **Kapsam:** Sentetik kartlı ödeme akışı; yalnızca örnek rapor
- **Tarih:** 2026-10-29T00:00:00+00:00
- **İncelenen dosya:** 1 / 1
- **Doğrulanmış bulgu:** 2

> Bu rapor otomatik araç tarafından oluşturulmuştur. Bulguları uygulamadan önce kod ve mevzuat kaynağını uzmanla doğrulayın.

## Bulgular

### 1. [HIGH] Ödeme referansı maskelenmiyor

- **Konum:** `payment_flow.py:6`
- **Güven:** 10 / 10
- **Mevzuat kaynağı:** `TEST_FIXTURE_NOT_LAW`, sayfa 1
- **Açıklama:** Örnek maskeleme işlevi değeri olduğu gibi döndürüyor.
- **Öneri:** Gerekli olmayan karakterleri maskeleyin; hassas veriyi loglamayın.

**Kod kanıtı:**

> `    return value`

### 2. [MEDIUM] Sıfır tutar geçerli sayılıyor

- **Konum:** `payment_flow.py:11`
- **Güven:** 10 / 10
- **Mevzuat kaynağı:** `TEST_FIXTURE_NOT_LAW`, sayfa 1
- **Açıklama:** Örnek doğrulama sıfır tutarı da kabul ediyor.
- **Öneri:** İş kuralı ve mevzuat kaynağıyla doğrulanmış tutar sınırını uygulayın.

**Kod kanıtı:**

> `    return amount >= 0`

## Dosya sonuçları

- `payment_flow.py` — **Tarandı**

## Sınırlamalar

- Sentetik örnek; gerçek ödeme verisi, mevzuat tespiti veya hukukî görüş değildir.
