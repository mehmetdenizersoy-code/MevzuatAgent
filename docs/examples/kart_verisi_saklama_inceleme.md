# Kart verisi saklama bulgu adayı

> Bu, gerçek `demo1` kaynak kodu ile yerel `1.5.5464` mevzuat indeksinin
> elle çapraz kontrol edilmiş bir bulgu adayıdır; hukukî görüş veya kesin
> mevzuat ihlali tespiti değildir. Yazılı rızanın başka bir sistemde alınıp
> alınmadığı ve saklamanın hukuki kapsamı uzman tarafından doğrulanmalıdır.

**Depo:** `mehmetdenizersoy-code/demo1`
**Dal / commit:** `master@203506d`
**Mevzuat:** 5464 sayılı Banka Kartları ve Kredi Kartları Kanunu, Madde 23,
indeks kaynağı `001_1.5.5464.pdf`, sayfa 8.

## Kod kanıtı

`PaymentController.cs:57-72`, `PaymentGatewayRequest` nesnesini kart sahibi,
kart numarası ve CVV dahil form alanlarıyla oluşturuyor. Aynı denetleyicide:

```csharp
BankRequest = JsonConvert.SerializeObject(gatewayRequest)
```

ile nesneyi `PaymentTransaction.BankRequest` alanına yazıyor
(`PaymentController.cs:83-100`, `PaymentTransaction.cs:27`). Bu kayıt
`_paymentService.Insert(payment)` çağrısıyla kaydediliyor. İncelenen
`PaymentViewModel` içinde veya denetleyicide yazılı rıza alanı/doğrulaması
görülmedi.

## Mevzuat kanıtı

> “Üye işyerleri, kartın kullanımı sonucunda kart ve kart hamili ile ilgili
> edindikleri bilgileri, kanunla yetkili kılınan kişi, kurum ve kuruluşlar hariç
> olmak üzere kart hamilinin yazılı rızasını almadan başkasına açıklayamaz,
> saklayamaz ve kopyalayamaz.”

## Değerlendirme ve öneri

Kod akışı, hassas kart verisinin ödeme isteği içinde oluşturulup işlem kaydına
serileştirildiğini gösteriyor. Bu nedenle gereksiz kart verisinin kalıcı
saklanması ve yazılı rıza/istisna koşullarının bu akışta doğrulanmaması
incelenmelidir. Tam kart numarası ve CVV'yi işlem kaydında tutmayın; sadece
ödeme sağlayıcısının gerektirdiği, saklanmasına izin verilen asgari alanları
koruyun. Uygulama davranışını ve hukuki uygulanabilirliği ürün/ödeme ve hukuk
uzmanlarıyla doğrulayın.
