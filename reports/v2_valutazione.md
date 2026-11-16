# Valutazione v2 - S3-S4

Generato (UTC): `2026-11-15T14:56:12+00:00`
Stato al momento del report (S3-S4): Candidata v2 valutata in S3-S4; non ancora attivata.

> **Nota successiva (S5-S6):** questo report è la fotografia della fase S3-S4 e
> non è stato ricalcolato. v2 è stata attivata solo nel drill locale e poi
> ripristinata: lo stato finale è v1. Vedi `docs/consegna_s4_s5.md`,
> `docs/consegna_finale.md` e `reports/drill_s5_s6.md`.

## Run MLflow

- Run ID: `5258ffae2cec4803b81e47220dd2137e` (`v2-candidate`)
- Experiment: `lab13-progetto3-ritardi-consegne` (id 684684872782029071)
- Tracking URI locale: `mlruns` (store locale predefinito del progetto)
- Connessione esterna richiesta: no

## Dati e split

- File dataset: `dataset (1).csv` (copia assegnata nella cartella del progetto)
- SHA-256 CSV: `5c999d24a24126e81a033ae5ecf9b9b1049925f8abe59367883bcd171476c72f`
- Righe di fit: 800 (`train`)
- Righe di valutazione: 200 (`validation`)
- Split distribuito non rigenerato: sì
- Validation mai usata per fit, tuning o scelta dei parametri: sì
- `record_id`, `split`, `target` esclusi da `X`: sì
- File richieste: richieste_monitoraggio.csv è input operativo per le prove API: non è entrato nel fit né nella valutazione.

## Pipeline salvata

- Passi: scaler → classifier
- Parametri: `{"pipeline_steps": ["scaler", "classifier"], "scaler": "StandardScaler", "classifier": "LogisticRegression", "C": 0.5, "solver": "liblinear", "max_iter": 1000, "random_state": 1303}`
- Seed registrato: 1303

## Metriche sulla validation

| Metrica | Valore |
| --- | ---: |
| Accuracy | 0.7350 |
| Precision classe 1 | 0.6742 |
| Recall classe 1 | 0.7143 |

## Matrice di confusione (ordine classi [0, 1])

Righe = classe reale, colonne = classe predetta.

| | Predetto 0 | Predetto 1 |
| --- | ---: | ---: |
| Reale 0 | 87 (TN) | 29 (FP) |
| Reale 1 | 24 (FN) | 60 (TP) |

Conteggi: TN=87, FP=29, FN=24, TP=60 su 200 righe.

## Artefatti

- Cartella versione: `models/v2`
- Pipeline serializzata: `models/v2/pipeline.joblib` (2317 byte)
- SHA-256 artefatto: `5b9dc55028ac824b0602da7e9bf4a090a4f5eb30753bfb1d83b1037601856e63`
- Metadati: `models/v2/model_metadata.json`
- Predizioni e ID validation: `models/v2/validation_predictions.json`
- Report JSON: `reports/v2_valutazione.json`

## Ripetere l'esecuzione

```powershell
python scripts/train_baseline.py --dataset ".\dataset (1).csv" --version v2
```
Una seconda esecuzione sulla stessa versione termina con errore esplicito e non tocca la cartella già salvata. Per una prova senza toccare v1 usare `--version v2` (fase 3) o `--models-dir` e `--report-dir` di prova.

## Limiti

- Dati interamente sintetici: le metriche non misurano spedizioni reali.
- La validation assegnata non è un test indipendente.
- Il gate (config/gate.json) non è misurato in S2: mancano servizio, candidata, p95 ed error rate.
- Al momento del report v1 non era attivata e S3-S6 non erano implementate.
