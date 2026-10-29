# Uçtan Uca Doğrulama Özeti

> Deterministik E2E testidir: tarama bulguları sentetik; Ollama yanıtı yerel mock sunucudan; push geçici yerel bare remote'a; GitHub PR çağrısı mock. Hukuki görüş/gerçek mevzuat tespiti değildir.

| Aşama | Gerçekleşen sonuç |
|---|---|
| PDF → RAG | 2 PDF, 146 chunk; hata yok |
| Tahmin | 1 dosya; 1 test chunk; 956 tahmini token |
| Model havuzu | 2 mock model; onaylanan öneri `e2e-fast:1b` |
| Tarama | 1 dosya; 2 sentetik, kanıtı doğrulanmış bulgu |
| Canlı model | `llama3.2:1b`: geçersiz JSON yanıtı; 0 dosya tarandı |
| Rapor | Markdown ve HTML tarama raporları üretildi |
| Remediation | En yüksek öncelikli 2 bulgu izole worktree'de düzeltildi; MD/HTML diff üretildi |
| Test | `pytest`: passed; 2 passed, 13 dependency deprecation warnings |
| PR provası | Yerel bare remote push doğrulandı; mock PR yanıtı alındı, gerçek GitHub isteği yok |

> Canlı model denemesinde dosya taraması tamamlanmadı. Aşağı akış remediation, test ve PR provası deterministik mock yanıtla ayrıca çalıştırıldı; bu, gerçek Ollama kalitesini doğrulamaz.
