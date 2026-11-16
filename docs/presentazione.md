# Traccia di presentazione - Progetto 3

## 1. Problema e uso della previsione

- Domanda: quali spedizioni rischiano di arrivare dopo la scadenza promessa?
- Momento della previsione: partenza della spedizione; solo storia precedente.
- `target = 1`: consegna dopo la scadenza; `target = 0`: entro la scadenza.
- Uso operativo: prioritizzare le spedizioni a rischio e avvisare il cliente.
- Costi:
  - falso positivo: notifica preventiva inutile, costo di gestione e possibile
    perdita di fiducia;
  - falso negativo: ritardo non gestito, reclamo e costo maggiore.
- Per questo contano sia il **recall** dei ritardi (non perderli) sia la
  **precision** delle notifiche (non allarmare troppo).

## 2. Dati

- Due CSV: `dataset (1).csv` (1000 righe, 30 feature) e
  `richieste_monitoraggio.csv` (4 richieste operative).
- Split distribuito: 800 train, 200 validation; non rigenerato.
- 30 feature numeriche in ordine canonico; `record_id`, `split` e `target`
  esclusi da `X`.
- Dati interamente sintetici, seed 1303: non rappresentano spedizioni reali.
- Fingerprint: raw `afee…` (CRLF) e canonico `5c99…` (LF) sono lo stesso
  contenuto; dettagli in `reports/fingerprint_coerenza.md`.

## 3. Baseline v1

- Pipeline: `StandardScaler` + `LogisticRegression(C=1.0, solver=liblinear,
  max_iter=1000, seed=1303)`.
- Fit solo su 800 righe train; validation solo per la valutazione.
- Risultati su 200 righe:

| Metrica | Valore |
| --- | ---: |
| Accuracy | 0.7350 |
| Precision classe 1 | 0.6742 |
| Recall classe 1 | 0.7143 |

| | Predetto 0 | Predetto 1 |
| --- | ---: | ---: |
| Reale 0 | 87 (TN) | 29 (FP) |
| Reale 1 | 24 (FN) | 60 (TP) |

- Artefatto versionato in `models/v1`, run MLflow
  `64079619c2c947bd83699d0d552b9d78`.

## 4. Servizio

- FastAPI, contratto `{"features": [30 numeri finiti]}` in ordine canonico.
- Invalidità (quantità errata, non numerici, `NaN`, infiniti) → HTTP 422 prima
  del predict.
- `POST /predict`: predizione, versione, run ID, request ID.
- `GET /health`: versione, run ID, hash artefatto, fingerprint dataset.
- `GET /metrics`: finestra mobile 15 minuti su `POST /predict`, errori ≥400,
  error rate, p95; a zero richieste p95 è `null`.
- Telemetria JSONL in `logs/requests.jsonl`, senza payload.

## 5. Candidata v2

- Ipotesi: più regolarizzazione (`C=0.5` invece di `1.0`) per ridurre la
  sensibilità al rumore delle feature sintetiche.
- Stessi dati, split, feature e seed; nessun tuning sulla validation.
- Risultati: accuracy 0.7350, precision 0.6742, recall 0.7143; matrice di
  confusione identica alla v1 (TN=87, FP=29, FN=24, TP=60).
- Artefatto in `models/v2`, run MLflow
  `5258ffae2cec4803b81e47220dd2137e`.

## 6. Gate

- Policy congelata `lab13-gate-v1` in `config/gate.json`; soglie non cambiate
  dopo i risultati.

| Requisito | Misura | Soglia | Esito |
| --- | ---: | ---: | --- |
| Accuracy v2 ≥ v1 | 0.735 = 0.735 | v2 ≥ v1 | superato |
| p95 HTTP | 28,3657 ms | ≤ 120 ms | superato |
| Error rate HTTP | 0/30 = 0.0 | ≤ 0,01 | superato |

- Decisione: **SUPERATO** rispetto alla baseline isolata
  `comparison_baseline/models/v1`.
- v2 non è attivata automaticamente: il gate registra una decisione, non cambia
  lo stato del serving.

## 7. Drill e rollback

- Sequenza eseguita: `req_01` v1 → `req_02` v2 → rollback → `req_03` v1 →
  `req_04` v1 incompleta.
- Esiti: `200, 200, 200, 422`; `req_04` è respinta dal contratto reale.
- Error rate drill: 1/4 = 0,25 (3 valide + 1 errore atteso); non sostituisce il
  0/30 del gate.
- Stato finale: v1, run ID `64079619c2c947bd83699d0d552b9d78`, hash
  `f8aea6264329d4c53d1f87e270c10ef7a3567c739c59c5796ccf116ccb7e1bd7`.
- Evidenze: `reports/drill_s5_s6.*`, `reports/drill/transitions.jsonl`,
  `reports/drill/requests.jsonl`.
- Dimostrazione: `python scripts/drill_rollback.py`, poi
  `python scripts/switch_version.py status`.

## 7-bis. Deploy Docker

- Immagine `lab13-progetto3-api:local` da `python:3.11.9-slim`, dipendenze
  pinnate in `requirements-serving.txt` (senza MLflow).
- Container non-root (`lab13`, uid 10001), root read-only, `cap_drop: ALL`,
  `no-new-privileges`, healthcheck su `/health`, porta solo su `127.0.0.1`.
- Dataset, config e modelli sono dentro l'immagine: il fingerprint canonico e
  l'hash dell'artefatto sono verificati all'avvio.
- Smoke test: `python scripts/docker_smoke_test.py`; richieste
  `200, 200, 200, 422`, v1 servita, 22 controlli su 22, p95 2,92 ms.
- `req_02` resta v1 nel deployment; il cambio a v2 appartiene solo al drill
  locale S5-S6. Il p95 dello smoke test non sostituisce il gate S4.
- Evidenze: `reports/docker_deploy.json`, `reports/docker_deploy.md`,
  `reports/docker/`; istruzioni in `docs/deploy_docker.md`.

## 8. Limiti

- Dati sintetici: nessuna generalizzazione a spedizioni reali.
- Validation non indipendente e non temporale.
- Baseline lineare, parametri fissati a priori, nessuna ricerca di
  iperparametri.
- Gate misurato con baseline isolata; decisione non riscritta.
- Drill locale, non deployment di produzione; container Docker verificato
  localmente, non su cloud o registry esterno.
- Smoke test Docker senza TLS/autenticazione e senza prova di carico.
- Warning di versione scikit-learn nel caricamento degli artefatti locali, con
  predizioni riprodotte identiche; nel container le versioni coincidono.

## 9. Contributi dei componenti

Compilare con i nomi effettivi del gruppo:

| Componente | Contributo |
| --- | --- |
| `[Gillone stefano]` | Dati, contratto, audit, documentazione |
| `[Rotondo Davide]` | Training baseline, valutazione, MLflow |
| `[Pellegrino Patrick]` | Servizio FastAPI, telemetria, probe |
| `[Destefanis Marco]` | Candidata v2, gate, drill e rollback |

## 10. Chiusura

- Ripetere: audit → test → training (solo se necessario) → probe → gate →
  drill → verifica stato v1 → build Docker → smoke test container.
- Stato finale: v1 attiva; v2 candidata approvata dal gate, attivata solo nel
  drill locale; deployment Docker locale su v1.
- Materiali di supporto: `docs/consegna_finale.md`,
  `docs/consegna_s4_s5.md`, `docs/deploy_docker.md`,
  `reports/drill_s5_s6.md`, `reports/docker_deploy.md`.
