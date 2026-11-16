# Deploy su Docker - livello container

## Stato

Il livello **container** del progetto è implementato ed eseguito localmente con
Docker Engine 29.6.1 e Docker Compose v5.2.0 su Linux/amd64. Il container serve
la versione **v1**, la stessa della consegna S5-S6, e lascia disabilitato
`POST /admin/version`.

Questo è un **deploy Docker locale**: non è un deployment cloud, non usa un
registry esterno, non introduce TLS o autenticazione e non sostituisce le
misure del gate S4. Il livello HTTP locale era già coperto dal probe e dal
drill; qui viene verificato che lo stesso servizio funzioni dentro un'immagine
immutabile.

| Livello | Stato | Nota |
| --- | --- | --- |
| In-process | ✅ eseguito | training, test, probe `pipeline.predict` |
| HTTP locale | ✅ eseguito | probe HTTP v2 e drill v1 → v2 → v1 |
| Container Docker locale | ✅ eseguito | immagine, Compose, healthcheck e smoke test |
| Deployment esterno / registry / cloud | ❌ non eseguito | nessuna infrastruttura esterna |

## File aggiunti

| File | Contenuto |
| --- | --- |
| `Dockerfile` | Immagine `python:3.11.9-slim`, utente non privilegiato, healthcheck, serving su porta 8000 |
| `.dockerignore` | Contesto di build minimo: esclude `.git`, `mlruns`, `reports`, `tests`, cache |
| `docker-compose.yml` | Servizio `api`, volume log, root read-only, `cap_drop: ALL`, `no-new-privileges`, healthcheck |
| `requirements-serving.txt` | Dipendenze di serving pinnate, senza MLflow |
| `scripts/docker_smoke_test.py` | Build, avvio, richieste HTTP e verifica black-box; scrive le evidenze |
| `tests/test_docker_assets.py` | 14 test statici su Dockerfile, Compose, dipendenze e script |
| `reports/docker_deploy.json` | Esito strutturato della verifica container |
| `reports/docker_deploy.md` | Esito leggibile della verifica container |
| `reports/docker/` | Log richieste, log container e `docker inspect` |

## Immagine

| Elemento | Scelta |
| --- | --- |
| Base | `python:3.11.9-slim`, la stessa versione Python degli artefatti |
| Dipendenze | `numpy 2.4.6`, `scipy 1.17.1`, `scikit-learn 1.8.0`, `joblib 1.5.3`, `fastapi 0.115.6`, `pydantic 2.14.3`, `uvicorn 0.34.0` |
| MLflow | Escluso: serve per training/tracciamento, non per il serving |
| Utente | `lab13`, uid/gid `10001` |
| Filesystem | Root read-only nel Compose; scrivibile solo il volume `/app/logs` |
| Capabilities | Tutte rimosse (`cap_drop: ALL`) e `no-new-privileges` |
| Healthcheck | `GET /health` ogni 30 s, con `start_period` 20 s e 3 retry |
| Contenuto | `src/`, `config/`, `models/`, `dataset (1).csv`, `richieste_monitoraggio.csv` |
| Rete | Porta pubblicata solo su `127.0.0.1:8000` |
| Versione servita | v1 da `config/active_version.json`; cambio versione disabilitato |

Il dataset è copiato nell'immagine perché il servizio verifica il fingerprint
canonico all'avvio e `load_version` rifiuta un artefatto che non corrisponde.
L'immagine non dipende dal filesystem dell'host per servire.

## Comandi

### Build e avvio con Compose

```powershell
docker compose build
docker compose up -d
docker compose ps
Invoke-RestMethod http://127.0.0.1:8000/health
```

Per usare un'altra porta senza modificare il file:

```powershell
$env:LAB13_DOCKER_PORT = "8001"
docker compose up -d
Remove-Item Env:LAB13_DOCKER_PORT
```

### Build e avvio senza Compose

```powershell
docker build -t lab13-progetto3-api:local .
docker run --rm -d --name lab13-progetto3-api `
  -p 127.0.0.1:8000:8000 `
  --read-only --tmpfs /tmp `
  --cap-drop ALL --security-opt no-new-privileges `
  -v lab13-progetto3-logs:/app/logs `
  lab13-progetto3-api:local
```

### Smoke test automatico

```powershell
python scripts/docker_smoke_test.py
```

Lo script:

1. verifica che Docker Engine sia raggiungibile;
2. rimuove lo stack precedente e ricrea un volume log pulito;
3. esegue `docker compose build`, salvo `--no-build`;
4. avvia lo stack e attende `/health` e lo stato Docker `healthy`;
5. confronta versione, run ID, hash dell'artefatto e fingerprint canonico con
   `models/v1/model_metadata.json`;
6. invia le quattro richieste di `richieste_monitoraggio.csv` con i request ID
   del file;
7. verifica status, predizioni, versione servita, echo del request ID,
   correlazione con il log e assenza di payload nei log;
8. verifica `/metrics`, l'utente `10001`, il root read-only, `cap_drop: ALL` e
   `no-new-privileges`;
9. scrive i report e rimuove lo stack, salvo `--keep-running`.

Opzioni utili:

```powershell
python scripts/docker_smoke_test.py --port 8001
python scripts/docker_smoke_test.py --no-build
python scripts/docker_smoke_test.py --keep-running
```

Con `--keep-running`, lo stack resta attivo per una prova manuale. Si ferma con:

```powershell
docker compose down -v
```

## Esito misurato (2026-11-16)

| Elemento | Valore |
| --- | --- |
| Esito complessivo | **SUPERATO** (22 controlli su 22) |
| Immagine | `lab13-progetto3-api:local` |
| Image ID | `sha256:f96becea9ac1621b72d3817db604bed27f5a4790c26fa3b00f77c1acdaff0684` |
| Dimensione immagine | 581 MB su disco (`docker image ls`); 129,1 MiB compressa (`inspect .Size`) |
| Container | `lab13-progetto3-api` |
| Stato | `running`, health `healthy` |
| Utente / UID | `lab13` / `10001` |
| Root filesystem | read-only |
| Porta | `127.0.0.1:8000` |
| Versione servita | `v1` |
| Run ID | `64079619c2c947bd83699d0d552b9d78` |
| Hash artefatto | `f8aea6264329d4c53d1f87e270c10ef7a3567c739c59c5796ccf116ccb7e1bd7` |
| Fingerprint canonico dataset | `5c999d24a24126e81a033ae5ecf9b9b1049925f8abe59367883bcd171476c72f` |

Richieste:

| # | Request ID | Versione richiesta dal CSV | Status atteso | Status reale | Predizione | Versione servita | Log correlato |
| ---: | --- | --- | ---: | ---: | ---: | --- | --- |
| 1 | `req_01` | v1 | 200 | 200 | 0 | v1 | sì |
| 2 | `req_02` | v2 | 200 | 200 | 1 | v1 | sì |
| 3 | `req_03` | v1 | 200 | 200 | 1 | v1 | sì |
| 4 | `req_04` | v1 incompleta (29 feature) | 422 | 422 | - | - | sì |

Metriche della finestra:

- richieste `POST /predict`: 4;
- errori HTTP ≥ 400: 1 (il 422 atteso di `req_04`);
- error rate: 0,25;
- p95: 2,92 ms;
- finestra: 900 s.

`req_02` indica `v2` nel CSV perché lo stesso file serve al drill S5-S6. Il
deployment resta su v1 e non cambia versione. Il drill `v1 → v2 → v1` resta
documentato in `reports/drill_s5_s6.md`; il suo error rate 0,25 e il p95 dello
smoke test **non** sostituiscono il gate S4 (0/30, p95 HTTP 28,3657 ms).

## Versioni nel container

| Componente | Versione |
| --- | --- |
| Python | `3.11.9` |
| `numpy` | `2.4.6` |
| `scikit-learn` | `1.8.0` |
| `joblib` | `1.5.3` |
| `fastapi` | `0.115.6` |
| `uvicorn` | `0.34.0` |
| `pydantic` | `2.14.3` |

Le versioni di NumPy, scikit-learn e joblib coincidono con quelle registrate
nei metadati degli artefatti; il caricamento nel container non emette il
warning di versione diversa osservato nell'ambiente Python 3.12 del drill.

## Evidenze

| Evidenza | Percorso |
| --- | --- |
| Esito strutturato | `reports/docker_deploy.json` |
| Esito leggibile | `reports/docker_deploy.md` |
| Log richieste del container (senza payload) | `reports/docker/requests.jsonl` |
| Log stdout/stderr del container | `reports/docker/container.log` |
| `docker inspect` del container | `reports/docker/container_inspect.json` |
| `docker image inspect` | `reports/docker/image_inspect.json` |
| Asset Docker e test | `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `requirements-serving.txt`, `tests/test_docker_assets.py` |

## Riproducibilità

- L'immagine è costruita da `python:3.11.9-slim` e da dipendenze pinnate; il
  modello dentro l'immagine è lo stesso file versionato in `models/v1`.
- Il controllo forte non è l'ID dell'immagine, che cambia a ogni build per
  timestamp e provenance: è l'hash SHA-256 dell'artefatto e il fingerprint
  canonico del dataset, verificati da `load_version` all'avvio e da `/health`.
- Una nuova build con lo stesso codice e gli stessi pin produce lo stesso
  comportamento; per una nuova versione del modello si costruisce una nuova
  immagine con il tag corrispondente, senza sovrascrivere `models/v1`.
- La verifica è stata eseguita su Linux/amd64 (Docker Desktop). Su un'altra
  architettura l'immagine va ricostruita e lo smoke test rieseguito.

## Test automatici

Nel container di serving non sono installati `pytest`, `httpx` o MLflow: il
servizio non ne ha bisogno. La suite completa è stata eseguita in un ambiente
virtuale pulito con lo stesso stack pinnato di `requirements-serving.txt`, più
`httpx` per `TestClient`:

```text
Ran 114 tests in 2.972s
OK
```

Sono inclusi i 14 test statici del livello Docker. L'ambiente Python globale
della macchina di lavoro ha un conflitto preesistente tra FastAPI 0.115.6 e
Starlette 1.9.0 (`pip check` lo segnala); per questo la verifica è stata fatta
in un ambiente isolato, come indicato nel setup del README. L'immagine Docker
risolve invece Starlette 0.41.3, compatibile con FastAPI 0.115.6.

## Cleanup

```powershell
# Ferma e rimuove container, rete e volume dei log
docker compose down -v

# Rimuove l'immagine locale (facoltativo)
docker image rm lab13-progetto3-api:local
```

`scripts/docker_smoke_test.py` esegue già `docker compose down -v` al termine,
salvo `--keep-running`.

## Limiti

- Docker locale single-node: non è un deployment cloud, Kubernetes o con
  registry esterno.
- Nessun TLS, autenticazione o rate limiting: la porta è pubblicata solo su
  `127.0.0.1`.
- Lo smoke test non è un test di carico: il p95 su quattro richieste non
  sostituisce il p95 del gate S4.
- I dati sono sintetici e didattici: le metriche non misurano spedizioni reali.
- Il deployment serve la v1 e lascia `/admin/version` disabilitato; il drill
  `v1 → v2 → v1` resta un'operazione locale S5-S6.
- La validation assegnata non è un test indipendente e non simula una
  validazione temporale.
