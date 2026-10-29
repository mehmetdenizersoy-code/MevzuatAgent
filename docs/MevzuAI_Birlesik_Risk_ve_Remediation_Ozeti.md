# MevzuAI — Birleşik Risk ve Remediation Özeti

> Kaynak: 24.10.2026 tarihli birleşik mevzuat uyum/risk raporu ve remediation tur 2 fark raporu. Bu belge, verilen raporların güvenli yönetici özetidir; bağımsız yeniden tarama değildir.

## Yönetici özeti

| Ölçüm | Kaynak rapordaki sonuç |
|---|---:|
| Taranan depo | 35 |
| Toplam bulgu | 82 |
| Bulgu dağılımı | 24 KRİTİK · 23 YÜKSEK · 21 ORTA · 9 DÜŞÜK · 5 BİLGİ |
| Depo bazında en yüksek risk | 17 kritik · 8 yüksek · 10 orta |
| Mevzuat uyum değerlendirmesi | %67 (61 değerlendirme) |
| Değerlendirme kırılımı | 41 uyumlu · 10 kısmi · 10 ihlal riski |
| Doğrulanmalı etiketi | 9 |
| Kaynak dayanağı | 13 RAG chunk · 9 DB-RAG atfı |

Kapsam raporda Kanun 5464 ve Yönetmelik 11180 olarak belirtilmiştir. Önceki raporlar girdi alınmadan taze tarama yapıldığı raporlanmıştır.

## Remediation tur 2

Kullanıcı onayıyla beş kritik bulgu seçilmiştir. Fark raporu toplam **5 depo, 9 dosya, +89/-10 satır** değişikliği bildirir.

| Bulgu | Alan | Özetlenen değişiklik |
|---|---|---|
| RISK-C05 | Safir.Abex · Kimlik bilgisi | Kod içindeki Basic-auth sabitini kaldırıp yapılandırma/secret store üzerinden okumak; mevcut credential rotasyonu ayrıca izlenmeli. |
| RISK-C08 | safir-online-sobe · Eşleşme ve log | ZERO_CVV merchant eşleşmesini tam eşleşmeye çevirmek; PIN/F55 benzeri hassas trace alanlarını maskelemek. |
| RISK-C09 | acqua-dcc-monex · DCC teklif akışı | İstek kimliğiyle idempotency sağlamak ve geçersiz kur değerlerini POS'a dönmeden önce reddetmek. |
| RISK-C10 | acqua-cassandra-data-archiver · Arşiv | S3 yüklemesini nesne metadata/boyut doğrulamasıyla teyit etmeden kaynak kayıtlarını silmemek. |
| RISK-C11 | acqua-rrn-generator · Sayaç | Cassandra LWT [applied] sonucunu denetlemek; başarısızlıkta sınırlı yeniden deneme ve açık hata üretmek. |

## Doğrulama ve açık işler

- Fark raporunda 3 konu **Doğrulanmalı** olarak işaretlenmiştir; iş kararı, ortam konfigürasyonu veya istemci davranışı ek doğrulama ister.
- C06 credential rotasyonu/vault işi; C12/C13 altyapı-konfigürasyon işi olarak bu turda kapsam dışı bırakılmıştır. C14/C15 sonraki tura ertelenmiştir.
- Kaynak fark raporu bir PR dalı adı verir; ancak bu özet, testlerin geçtiğini veya GitHub PR'ın açıldığını doğrulamamaktadır.
- Kaynak rapordaki credential/token örnekleri bu özet ve sunuma aktarılmamıştır. Credential rotasyonu ve Git geçmişi temizliği ayrı operasyonel işlerdir.

## Yorumlama sınırı

Rapor sayıları ve remediation açıklamaları verilen HTML belgelerinden aktarılmıştır; bu çalışma kaynak depoları yeniden taramadı, kod farklarını bağımsız test etmedi ve hukuki uygunluk görüşü sunmaz. Düzeltmeler merge edilmeden önce ilgili depo sahipleri, güvenlik ekibi ve mevzuat uzmanı tarafından doğrulanmalıdır.
