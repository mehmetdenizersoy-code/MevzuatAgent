# Sentetik Fixture Tarama Raporu — Demo 2

> **YALNIZCA TEST GÖSTERİMİDİR.** Bu rapor `mevzuatagent-test-fixtures`
> deposundaki önceden tanımlı sentetik `scan_result.json` verisinden hazırlanmıştır.
> Ollama çalıştırılmamış, gerçek bir kod taraması yapılmamış ve mevzuata aykırılık
> tespiti üretilmemiştir.

- **Depo örneği:** `demo2`
- **Model:** `synthetic-fixture (LLM çağrısı yok)`
- **Kaynak dosyası:** `payment_rules.py`
- **Sentetik örnek bulgu sayısı:** 5
- **Mevzuat alanı:** `TEST_FIXTURE_NOT_LAW`

## Örnek bulgular

### 1. [HIGH] Desteklenmeyen para birimleri kabul ediliyor

- **Konum:** `payment_rules.py:9`
- **Kod örneği:** `return True`
- **Fixture açıklaması:** İşlev izin verilen para birimi listesini kullanmıyor.
- **Fixture önerisi:** Para biriminin desteklenenler kümesinde olup olmadığını denetleyin.

### 2. [MEDIUM] Yeniden deneme sınırı bir fazla kabul ediliyor

- **Konum:** `payment_rules.py:14`
- **Kod örneği:** `return attempt <= limit`
- **Fixture açıklaması:** Deneme sayısı sınıra eşit olduğunda yeni denemeye izin veriliyor.
- **Fixture önerisi:** Yeni deneme için mevcut deneme sayısının sınırdan küçük olmasını şart koşun.

### 3. [HIGH] İade tutarı işlem tutarını aşabiliyor

- **Konum:** `payment_rules.py:19`
- **Kod örneği:** `return requested_amount > 0`
- **Fixture açıklaması:** İşlev iade tutarını ilk işlem tutarıyla karşılaştırmıyor.
- **Fixture önerisi:** İade tutarını ilk işlem tutarıyla karşılaştırın.

### 4. [MEDIUM] Başvuru numarası gizlenmiyor

- **Konum:** `payment_rules.py:24`
- **Kod örneği:** `return reference`
- **Fixture açıklaması:** Gösterim işlevi başvuru numarasını değiştirmeden döndürüyor.
- **Fixture önerisi:** Yalnızca son karakterleri gösterip önceki karakterleri maskeleyin.

### 5. [LOW] İşlem ücreti hesaplanmıyor

- **Konum:** `payment_rules.py:29`
- **Kod örneği:** `return amount`
- **Fixture açıklaması:** Ücret oranı hesaplamada kullanılmıyor.
- **Fixture önerisi:** Tutarı ücret oranıyla çarparak işlem ücretini hesaplayın.

## Sınırlamalar

Bu örnekler hukukî değerlendirme, gerçek sistem bulgusu veya mevzuata uygunluk
sonucu değildir. Gerçek tarama çıktısı olarak kullanılamaz.
