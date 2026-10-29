# Mevzuat Uyumluluk Tarama Raporu

- **Depo:** `synthetic/e2e-fixture`
- **Dal / commit:** `main@5d55d59`
- **Model:** `e2e-fast:1b`
- **Kapsam:** first 1 tracked source files (limit 1)
- **Tarih:** 2026-10-29T13:46:42.238669+00:00
- **İncelenen dosya:** 1 / 3
- **Doğrulanmış bulgu:** 2

> Bu rapor otomatik araç tarafından oluşturulmuştur. Bulguları uygulamadan önce kod ve mevzuat kaynağını uzmanla doğrulayın.

## Bulgular

### 1. [HIGH] [E2E TEST ONLY] Payment reference is not masked

- **Konum:** `demo1/payment_rules.py:6`
- **Güven:** 10 / 10
- **Mevzuat kaynağı:** `TEST_FIXTURE_NOT_LAW`, sayfa 1
- **Açıklama:** Synthetic test finding; not a legal assessment.
- **Öneri:** Mask all but the last four characters.

**Kod kanıtı:**

> `return value`

### 2. [MEDIUM] [E2E TEST ONLY] Zero amount is accepted

- **Konum:** `demo1/payment_rules.py:11`
- **Güven:** 10 / 10
- **Mevzuat kaynağı:** `TEST_FIXTURE_NOT_LAW`, sayfa 1
- **Açıklama:** Synthetic test finding; not a legal assessment.
- **Öneri:** Require an amount greater than zero.

**Kod kanıtı:**

> `return amount >= 0`

## Dosya sonuçları

- `demo1/payment_rules.py` — **Tarandı**

## Sınırlamalar

- Kısmi tarama: 3 kaynak dosyasından 1 tanesi incelendi.
