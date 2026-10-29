# Mevzuat Uyumluluk Tarama Raporu

- **Depo:** `sentetik-test/demo1`
- **Dal / commit:** `main@7296b02`
- **Model:** `synthetic-fixture (LLM taraması yapılmadı)`
- **Kapsam:** Sentetik test: önceden tanımlı örnek bulgular
- **Tarih:** 2026-10-29T14:44:23.148051+00:00
- **İncelenen dosya:** 1 / 1
- **Doğrulanmış bulgu:** 5

> Bu rapor otomatik araç tarafından oluşturulmuştur. Bulguları uygulamadan önce kod ve mevzuat kaynağını uzmanla doğrulayın.

## Bulgular

### 1. [HIGH] Ödeme başvurusu gizlenmiyor

- **Konum:** `payment_rules.py:6`
- **Güven:** 10 / 10
- **Mevzuat kaynağı:** `TEST_FIXTURE_NOT_LAW`, sayfa 1
- **Açıklama:** Maskeleme işlevi girdiyi olduğu gibi döndürüyor.
- **Öneri:** Son dört karakteri koruyup önceki karakterleri maskeleyin.

**Kod kanıtı:**

> `    return value`

### 2. [MEDIUM] Sıfır tutar geçerli sayılıyor

- **Konum:** `payment_rules.py:11`
- **Güven:** 10 / 10
- **Mevzuat kaynağı:** `TEST_FIXTURE_NOT_LAW`, sayfa 1
- **Açıklama:** İşlev sıfır tutara da olumlu yanıt veriyor.
- **Öneri:** Pozitif tutar için sıfırdan büyük olma koşulunu kullanın.

**Kod kanıtı:**

> `    return amount >= 0`

### 3. [MEDIUM] Son kullanma ayı dikkate alınmıyor

- **Konum:** `payment_rules.py:21`
- **Güven:** 9 / 10
- **Mevzuat kaynağı:** `TEST_FIXTURE_NOT_LAW`, sayfa 1
- **Açıklama:** Aynı yıldaki ay karşılaştırması yapılmıyor.
- **Öneri:** Yıl eşitse son kullanma ayını da mevcut ayla karşılaştırın.

**Kod kanıtı:**

> `    return expiry_year < current_year`

### 4. [LOW] Taksit tutarı hesaplanmıyor

- **Konum:** `payment_rules.py:26`
- **Güven:** 10 / 10
- **Mevzuat kaynağı:** `TEST_FIXTURE_NOT_LAW`, sayfa 1
- **Açıklama:** Taksit tutarı toplam tutardan ve taksit sayısından hesaplanmıyor.
- **Öneri:** Geçerli taksit sayısı için toplamı taksit sayısına bölün.

**Kod kanıtı:**

> `    return total`

### 5. [LOW] İsim alanındaki boşluklar temizlenmiyor

- **Konum:** `payment_rules.py:31`
- **Güven:** 10 / 10
- **Mevzuat kaynağı:** `TEST_FIXTURE_NOT_LAW`, sayfa 1
- **Açıklama:** İşlev baştaki ve sondaki boşlukları kaldırmıyor.
- **Öneri:** İsim metninin başındaki ve sonundaki boşlukları temizleyin.

**Kod kanıtı:**

> `    return name`

## Dosya sonuçları

- `payment_rules.py` — **synthetic_fixture**

## Sınırlamalar

- Sentetik test bulgularıdır; gerçek mevzuat taraması veya hukukî tespit değildir.
