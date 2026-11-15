# Valutazione v1 - S2

Generato (UTC): `2026-11-15T15:10:00+00:00`
Stato: Baseline valutata sulla validation distribuita. Serving API, candidata v2, gate misurato, attivazione e rollback non sono implementati: v1 non è dichiarata pronta al deployment.

## Run MLflow

- Run ID: `c771dbca820f4af48dd58dd7655225cc` (`v1-baseline`)
- Experiment: `lab13-progetto3-ritardi-consegne` (id 774480253119925424)
- Tracking URI locale: `comparison_baseline/mlruns` (argomento CLI)
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
- Parametri: `{"pipeline_steps": ["scaler", "classifier"], "scaler": "StandardScaler", "classifier": "LogisticRegression", "C": 1.0, "solver": "liblinear", "max_iter": 1000, "random_state": 1303}`
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

- Cartella versione: `comparison_baseline/models/v1`
- Pipeline serializzata: `comparison_baseline/models/v1/pipeline.joblib` (2317 byte)
- SHA-256 artefatto: `e9d20eff6374f0b69df6e4a5f6594b301731696d69c9adaeac72b84fdbfda9cb`
- Metadati: `comparison_baseline/models/v1/model_metadata.json`
- Predizioni e ID validation: `comparison_baseline/models/v1/validation_predictions.json`
- Report JSON: `comparison_baseline/reports/v1_valutazione.json`

## Ripetere l'esecuzione

```powershell
python scripts/train_baseline.py --dataset ".\dataset (1).csv" --version v1
```
Una seconda esecuzione sulla stessa versione termina con errore esplicito e non tocca la cartella già salvata. Per una prova senza toccare v1 usare `--version v2` (fase 3) o `--models-dir` e `--report-dir` di prova.

## Limiti

- Dati interamente sintetici: le metriche non misurano spedizioni reali.
- La validation assegnata non è un test indipendente.
- Il gate (config/gate.json) non è misurato in S2: mancano servizio, candidata, p95 ed error rate.
- v1 non è attivata: S3-S6 non sono implementate.
