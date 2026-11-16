# Consegna finale - Progetto 3 (Lab 13)

## Stato

S1-S6 sono implementate. Il progetto ha dati e contratto, baseline v1 tracciata,
servizio FastAPI osservabile, candidata v2 con gate misurato, transizioni di
versione, drill v1 → v2 → v1 con rollback e ripristino della baseline. Lo stato
finale della versione attiva è **v1**. Il dettaglio delle aggiunte e modifiche
della fase finale è in `docs/consegna_s4_s5.md`. Il livello container è stato
aggiunto successivamente ed è documentato in `docs/deploy_docker.md`.

| Fase | Contenuto | Stato |
| --- | --- | --- |
| S1 | Lettore, controlli, contratto, audit, gate congelato | ✅ eseguito |
| S2 | Baseline v1, validation, MLflow, artefatti | ✅ eseguito |
| S3 | Servizio FastAPI, request ID, log, metriche | ✅ eseguito |
| S4 | Candidata v2, probe HTTP, gate | ✅ eseguito |
| S5 | Stato attivo atomico, attivazione/rollback, registro transizioni | ✅ eseguito |
| S6 | Drill HTTP, prova del ripristino, documentazione | ✅ eseguito |
| Container | Immagine Docker, Compose, healthcheck, smoke test v1 | ✅ eseguito localmente |
| Deployment esterno | Registry, cloud, orchestratore | ❌ non eseguito |

## Versioni, run e artefatti

| Versione | Ruolo | Run MLflow | SHA-256 artefatto |
| --- | --- | --- | --- |
| `models/v1` | Baseline servita | `64079619c2c947bd83699d0d552b9d78` | `f8aea6264329d4c53d1f87e270c10ef7a3567c739c59c5796ccf116ccb7e1bd7` |
| `models/v2` | Candidata approvata dal gate, non attiva | `5258ffae2cec4803b81e47220dd2137e` | `5b9dc55028ac824b0602da7e9bf4a090a4f5eb30753bfb1d83b1037601856e63` |
| `comparison_baseline/models/v1` | Baseline isolata per il gate S4 | `c771dbca820f4af48dd58dd7655225cc` | `e9d20eff6374f0b69df6e4a5f6594b301731696d69c9adaeac72b84fdbfda9cb` |

- Dataset: `dataset (1).csv`, 1000 righe, split distribuito non rigenerato.
- SHA-256 raw del checkout corrente (CRLF):
  `afee41161484c561feb59576f464321f3f0453c00acb9752a9173a7755e97c79`.
- SHA-256 canonico (CRLF/LF normalizzati):
  `5c999d24a24126e81a033ae5ecf9b9b1049925f8abe59367883bcd171476c72f`.
- Dettagli sulla coerenza CRLF/LF: `reports/fingerprint_coerenza.md`.

## Gate S4

| Requisito | Valore misurato | Soglia | Esito |
| --- | ---: | ---: | --- |
| Accuracy v2 ≥ accuracy v1 | 0.735 = 0.735 | v2 ≥ v1 | superato |
| p95 HTTP v2 | 28,3657 ms | ≤ 120 ms | superato |
| Error rate HTTP valido | 0/30 = 0.0 | ≤ 0,01 | superato |

Decisione registrata: **SUPERATO** rispetto alla baseline isolata. Soglie lette
da `config/gate.json` e non modificate dopo i risultati. Il report completo è in
`reports/gate_s4.json` e `reports/gate_s4.md`.

## Probe S3-S4 e drill S5-S6

| Misura | Ambito | Richieste | Errori ≥400 | Error rate |
| --- | --- | ---: | ---: | ---: |
| Probe in-process | `pipeline.predict`, 30 misure dopo 3 warm-up | 30 | 0 | 0.0 |
| Probe HTTP | `POST /predict` su v2 | 30 | 0 | 0.0 |
| Drill S5-S6 | 4 richieste operative, 3 valide + 1 incompleta | 4 | 1 | 0.25 |
| Drill, sole richieste valide | `req_01`, `req_02`, `req_03` | 3 | 0 | 0.0 |

Il drill ha risposto `200, 200, 200, 422` nell'ordine `v1, v2, v1, v1`. Il 422 di
`req_04` deriva dal contratto di validazione (29 feature), non da una risposta
simulata. Il valore 0,25 del drill non sostituisce l'error rate del gate.

## Deploy Docker

Il livello container è stato eseguito localmente con Docker Engine 29.6.1 e
Docker Compose v5.2.0. L'immagine `lab13-progetto3-api:local` usa
`python:3.11.9-slim`, dipendenze pinnate in `requirements-serving.txt`, utente
non-root `lab13` (uid 10001), root filesystem read-only, `cap_drop: ALL`,
`no-new-privileges` e healthcheck su `/health`. Il container serve la v1 e
lascia `/admin/version` disabilitato.

| Controllo | Esito |
| --- | --- |
| Build e avvio Compose | ✅ immagine 581 MB su disco (129,1 MiB compressa), container `running` |
| Healthcheck Docker | ✅ `healthy` |
| Identità servita | ✅ v1, run ID e hash artefatto di `models/v1` |
| Fingerprint canonico dataset | ✅ `5c999d24a24126e81a033ae5ecf9b9b1049925f8abe59367883bcd171476c72f` |
| Sequenza richieste | ✅ `200, 200, 200, 422`, predizioni 0, 1, 1 |
| Metriche | 4 richieste, 1 errore atteso, error rate 0,25, p95 2,92 ms |
| Log richieste | ✅ 4 correlazioni, nessun payload |
| Sicurezza | ✅ uid 10001, root read-only, capabilities rimosse |
| Controlli complessivi | ✅ 22 su 22 |

`req_02` indica v2 nel CSV perché lo stesso file serve al drill S5-S6: nel
deployment resta servita dalla v1. Il p95 e l'error rate dello smoke test non
sostituiscono il gate S4. Dettagli e comandi: `docs/deploy_docker.md`; evidenze:
`reports/docker_deploy.json`, `reports/docker_deploy.md`, `reports/docker/`.

## Stato finale e prova del ripristino

- `config/active_version.json`: versione `v1`, azione `rollback`, modalità
  `drill`, run ID `64079619c2c947bd83699d0d552b9d78`.
- `/health` finale: `active_version = v1`, stesso run ID e stesso hash
  `f8aea6264329d4c53d1f87e270c10ef7a3567c739c59c5796ccf116ccb7e1bd7`.
- `req_03` è una richiesta valida servita dopo il rollback: status 200,
  predizione 1, versione servita v1.
- Il registro transizioni contiene `activate v1 -> v2` e `rollback v2 -> v1`,
  con timestamp, run ID e fingerprint di entrambe le versioni.

## Tracciabilità di una predizione

Per ricostruire una singola risposta fino a versione, run e dataset:

1. `GET /health` restituisce `active_version`, `run_id`, `artifact_sha256`,
   `dataset_sha256` e `dataset_sha256_canonical`.
2. `POST /predict` restituisce `prediction`, `version`, `run_id` e
   `request_id`; il request ID può essere inviato con `X-Request-ID`.
3. Lo stesso `request_id` compare in `logs/requests.jsonl` (o nel log del drill)
   con versione, run ID, status HTTP e durata, senza payload.
4. `models/<version>/model_metadata.json` contiene lo stesso `run_id`,
   l'hash dell'artefatto e il fingerprint del dataset; il file
   `validation_predictions.json` conserva le predizioni salvate per il
   confronto.

## Evidenze

| Evidenza | Percorso |
| --- | --- |
| Audit S1 | `reports/data_audit.json`, `reports/data_audit.md` |
| Valutazione v1 | `reports/v1_valutazione.json`, `reports/v1_valutazione.md` |
| Valutazione v2 | `reports/v2_valutazione.json`, `reports/v2_valutazione.md` |
| Baseline isolata S4 | `comparison_baseline/reports/v1_valutazione.*` |
| Probe v2 | `reports/probe_v2.json` |
| Gate S4 | `reports/gate_s4.json`, `reports/gate_s4.md` |
| Drill S5-S6 | `reports/drill_s5_s6.json`, `reports/drill_s5_s6.md` |
| Registro transizioni | `reports/drill/transitions.jsonl` |
| Log richieste del drill | `reports/drill/requests.jsonl` |
| Estratto log correlato | `reports/drill/request_log_extract.jsonl` |
| Log server del drill | `reports/drill/server.log` |
| Stato attivo finale | `config/active_version.json` |
| Coerenza fingerprint | `reports/fingerprint_coerenza.md` |
| Deploy Docker | `reports/docker_deploy.json`, `reports/docker_deploy.md` |
| Log e inspect del container | `reports/docker/` |
| Istruzioni del livello container | `docs/deploy_docker.md` |
| Dettaglio modifiche S4 → S5-S6 | `docs/consegna_s4_s5.md` |
| Traccia presentazione | `docs/presentazione.md` |

I log non contengono i payload grezzi: solo timestamp, request ID, versione, run
ID, status e durata.

## Ripetere la consegna

Prerequisiti: Python con le dipendenze di `requirements.txt`. Per audit e test
basta la libreria standard; per servizio e drill servono FastAPI, Uvicorn,
scikit-learn, NumPy e joblib. MLflow serve solo per riallenare.

```powershell
# 0. Setup (solo la prima volta)
python -m pip install -r requirements.txt

# 1. Controlli dati e contratto
python scripts/audit_data.py --no-write
python -m unittest discover -s tests -v

# 2. Baseline e candidata (solo se si vuole ricreare un ambiente nuovo;
#    le versioni esistenti non vengono sovrascritte)
python scripts/train_baseline.py
python scripts/train_candidate.py

# 3. Probe della candidata (in-process; per HTTP avviare v2 e usare --base-url)
python scripts/probe_service.py

# 4. Gate con la baseline isolata registrata
python scripts/evaluate_gate.py --baseline-report .\comparison_baseline\reports\v1_valutazione.json --baseline-model-dir .\comparison_baseline\models\v1

# 5. Drill completo con server automatico
python scripts/drill_rollback.py

# 6. Verifica stato finale
python scripts/switch_version.py status

# 7. Deploy Docker e verifica black-box (richiede Docker con Compose)
docker compose build
python scripts/docker_smoke_test.py
```

Il drill automatico avvia uvicorn su `127.0.0.1:8000`, imposta
`LAB13_ALLOW_VERSION_SWITCH=1`, scrive il log in `reports/drill/requests.jsonl`
e arresta il server al termine. Se la porta è occupata, usare `--port`.
Lo smoke test Docker esegue build, avvio, quattro richieste, controlli di
identità/sicurezza/log e cleanup; con `--keep-running` lascia lo stack attivo.

## Livelli eseguiti e non eseguiti

| Livello | Stato |
| --- | --- |
| In-process (training, test, probe `predict`) | ✅ eseguito |
| HTTP locale (probe HTTP, drill, health, metrics) | ✅ eseguito |
| Container Docker locale (immagine, Compose, smoke test) | ✅ eseguito |
| Deployment esterno / registry / cloud | ❌ non eseguito |

## Cleanup

- Arrestare eventuali server uvicorn rimasti attivi (`Ctrl+C` o chiusura del
  processo) e verificare che la porta 8000 sia libera.
- Rimuovere le variabili d'ambiente della sessione:
  `LAB13_ALLOW_VERSION_SWITCH`, `LAB13_ACTIVE_VERSION_PATH`,
  `LAB13_TRANSITIONS_PATH`, `LAB13_REQUEST_LOG`.
- Non eliminare `models/`, `reports/`, `config/active_version.json`: sono
  artefatti ed evidenze della consegna.
- Container Docker: `docker compose down -v` rimuove container, rete e volume
  dei log; `docker image remove lab13-progetto3-api:local` rimuove l'immagine.
  Lo smoke test esegue già il primo comando, salvo `--keep-running`.

## Limiti

- Dati interamente sintetici e didattici: le metriche non misurano spedizioni
  reali.
- La validation assegnata non è un test indipendente e non simula una
  validazione temporale.
- Il gate è misurato su una baseline isolata; la v1 originale ha contenuto e
  accuracy equivalenti, ma il report S4 non è stato riscritto.
- Il drill è locale e abilitato da una variabile d'ambiente: non è un deployment
  di produzione.
- Il container è verificato localmente (Docker single-node), non su cloud,
  Kubernetes o registry esterno; non introduce TLS, autenticazione o rate
  limiting.
- Lo smoke test Docker non è un test di carico e il suo p95 su quattro richieste
  non sostituisce il gate S4.
- Gli artefatti sono stati serializzati con versioni di scikit-learn diverse da
  quelle del drill; il caricamento emette un warning, ma le predizioni
  riprodotte coincidono con quelle salvate. Nel container le versioni numeriche
  coincidono con i metadati e il warning non compare.
