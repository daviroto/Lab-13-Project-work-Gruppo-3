# Decisione gate S4

- Decisione: **SUPERATO**
- Policy: `lab13-gate-v1` (congelata: sì)
- Accuracy baseline selezionata: 0.735; v2: 0.735; soglia: v2 ≥ baseline
- p95 HTTP v2: 28.36569999999483 ms; soglia ≤ 120 ms
- Error rate HTTP: 0.0; soglia ≤ 0.01
- Dataset e ID validation comparabili: sì

Baseline di confronto: `comparison_baseline\models\v1` (originale v1: no; riaddestrata sul CSV incluso).
Hash CSV incluso: `5c999d24a24126e81a033ae5ecf9b9b1049925f8abe59367883bcd171476c72f`; hash dichiarato dagli artefatti v1 originali: `afee41161484c561feb59576f464321f3f0453c00acb9752a9173a7755e97c79`.
La versione attiva non è stata modificata. v2 non è stata attivata e il drill S5-S6 non è stato eseguito al momento della decisione.

> **Nota successiva (S5-S6):** è stato eseguito un drill locale `v1 -> v2 -> v1`
> con rollback verificato. v2 non è rimasta attiva: lo stato finale è v1. La
> decisione e le soglie di questo report non sono state modificate. Evidenze:
> `reports/drill_s5_s6.md` e `reports/drill/transitions.jsonl`.
