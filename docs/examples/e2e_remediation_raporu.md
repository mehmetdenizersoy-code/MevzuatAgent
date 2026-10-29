# Düzeltme Diff Raporu

> **YALNIZCA TEST İÇİNDİR.** Sentetik bulgular gerçek mevzuat tespiti veya hukukî görüş değildir.

- **Kaynak depo:** `synthetic/e2e-fixture`
- **İzole çalışma alanı:** `synthetic/e2e-remediation-worktree-d49786ac56`
- **Dal:** `mevzuatagent/remediation-d49786ac56`
- **Durum:** Değişiklikler ayrı worktree'de uygulanmıştır; otomatik olarak commit edilmemiş veya PR açılmamıştır.

## Kod farkı

```diff
diff --git a/demo1/payment_rules.py b/demo1/payment_rules.py
index 73d3e64..9cee0c3 100644
--- a/demo1/payment_rules.py
+++ b/demo1/payment_rules.py
@@ -3,12 +3,12 @@

 def mask_reference(value: str, visible: int = 4) -> str:
     """Ödeme başvurusunu kısaltır."""
-    return value
+    return "*" * max(0, len(value) - visible) + value[-visible:]


 def is_positive_amount(amount: float) -> bool:
     """Tutarın pozitif olup olmadığını döndürür."""
-    return amount >= 0
+    return amount > 0


 def is_expired(
```
