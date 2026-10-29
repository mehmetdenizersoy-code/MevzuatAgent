# Düzeltme Diff Raporu

> **YALNIZCA TEST İÇİNDİR.** Sentetik bulgular gerçek mevzuat tespiti veya hukukî görüş değildir.

- **Kaynak depo:** `synthetic-card-payment-demo`
- **İzole çalışma alanı:** `synthetic-card-payment-demo-remediation-example`
- **Dal:** `mevzuatagent/remediation-example`
- **Durum:** Değişiklikler ayrı worktree'de uygulanmıştır; otomatik olarak commit edilmemiş veya PR açılmamıştır.

## Kod farkı

```diff
diff --git a/payment_flow.py b/payment_flow.py
index ccbaff1..4689516 100644
--- a/payment_flow.py
+++ b/payment_flow.py
@@ -3,9 +3,9 @@
 def mask_reference(value: str, visible: int = 4) -> str:
     """Mask a payment reference."""

-    return value
+    return "*" * max(0, len(value) - visible) + value[-visible:]

 def is_positive_amount(amount: float) -> bool:
     """Check that amount is positive."""

-    return amount >= 0
+    return amount > 0
```
