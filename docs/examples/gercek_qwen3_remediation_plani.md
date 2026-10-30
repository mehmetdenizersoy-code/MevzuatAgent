# Düzeltme Planı

- **Depo:** `/Users/denizersoy/PycharmProjects/Final-Proje_MevzuatAgent/data/repositories/mevzuatagent-demo1-findings`
- **Dal / commit:** `main@7296b02`
- **Model:** `qwen3:4b`
- **Seçilen bulgu:** 1

> Bu dosya yalnızca öneri sunar. Kod değişikliği için kullanıcı onayı gerekir.

## 1. [CRITICAL] Ödeme planı taksit tutarını yanlış hesaplamak

- **Konum:** `payment_rules.py:24`
- **Güven:** 10 / 10
- **Mevzuat:** `001_1.5.5464.pdf`, sayfa 18
- **Bulgu:** Mevzuat 1.5.5464.pdf sayfa 18'de vadeli ödemeler için taksit tutarını hesaplama kuralları belirtilmiştir. Ancak kodda installment_amount fonksiyonu taksit sayısına göre hesaplamak yerine toplam tutarı döndürmektedir. Bu, mevzuatın aylık eşit taksitler şeklinde hesaplanmasını engelleyen bir uyumsuzluktur.
- **Önerilen düzeltme:** installment_amount fonksiyonunda toplam tutarı taksit sayısına göre hesaplamak için mevzuatın belirtilen oranlarla çarpma ve bölme işlemlerini uygulamalı. Örneğin, 12 aylık vade için (total * 1.08) / 12 şeklinde hesaplanmalıdır.
- **Kod kanıtı:** `def installment_amount(total: float, count: int) -> float:`

## Onay

Uygulamadan önce her değişiklik kullanıcıya gösterilmeli ve açık onay alınmalıdır.
Onaylanan değişiklikler ayrı bir dalda uygulanmalı, test edilmeli ve diff raporlanmalıdır.
