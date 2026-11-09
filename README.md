# Progetto 3 - Ritardi nelle consegne logistiche

## Domanda e momento della previsione

**Domanda:** Quali spedizioni potrebbero essere consegnate dopo la scadenza promessa?

**Momento di osservazione:** Momento della partenza; tempi e ritardi storici riguardano soltanto consegne precedenti.

- **target = 1:** Consegna successiva alla scadenza promessa.
- **target = 0:** Consegna entro la scadenza promessa.

Questi dati sono **interamente sintetici**, creati per il corso. Non rappresentano persone, aziende, macchine, edifici o prenotazioni reali. Le unità e gli intervalli descrivono la simulazione didattica. I risultati non misurano le prestazioni su un dominio reale.

## File da usare insieme

| File | Contenuto |
| --- | --- |
| [dataset (1).csv](<dataset (1).csv>) | 1000 righe, 30 feature numeriche, record_id univoco, split e target binario |
| [richieste_monitoraggio.csv](richieste_monitoraggio.csv) | Quattro richieste coerenti con queste feature: v1 valida, v2 valida, v1 valida e v1 con 29 feature → 422 |

Ricevi anche il [Lab 13](../../13_project_work_pipeline_serving_monitoring_e_aggiornamento.md). Segui le fasi del lab usando i due CSV di questa cartella. Conserva la stessa coppia, lo stesso schema e lo stesso ordine delle feature durante tutto il progetto.

## Split e classi

| Split | target 0 | target 1 | Totale |
| --- | ---: | ---: | ---: |
| train | 463 | 337 | 800 |
| validation | 116 | 84 | 200 |

Lo split stratificato è già distribuito. Usalo per v1 e v2; non rigenerarlo. Record_id, split e target non entrano nelle feature. Non usare la validation per allenare lo scaler o il modello. Il CSV di richieste contiene solo input operativi: non è un altro dataset di training.

## Dizionario delle 30 feature

Il nome indica la misura e, dove previsto, la finestra temporale; `pct` indica percentuali: le quote sono tra 0 e 100, mentre gli scostamenti e le variazioni possono essere negativi secondo gli intervalli della tabella. I punteggi sono indici sintetici nella scala riportata. Per righe con unità «conteggio» i valori sono interi. Tutte le feature sono disponibili al momento della previsione descritto sopra.

**L'ordine seguente è l'ordine della lista features nell'API.** I payload distribuiti rispettano questo ordine; non contengono target, record_id o split.

| Posizione API | Colonna | Unità / scala | Intervallo della simulazione |
| --- | --- | --- | --- |
| 1 | `distanza_pianificata_km` | km | 10–1300 |
| 2 | `numero_fermate_pianificate` | conteggio | 1–40 |
| 3 | `indice_congestione_prevista` | punteggio 0–100 | 0–100 |
| 4 | `quota_percorso_urbano_pct` | % | 0–100 |
| 5 | `deviazione_prevista_km` | km | 0–70 |
| 6 | `tempo_viaggio_stimato_ore` | ore | 0.5–20 |
| 7 | `pacchi_in_coda_hub` | conteggio | 10–1500 |
| 8 | `occupazione_hub_pct` | % | 10–100 |
| 9 | `attesa_carico_prevista_min` | minuti | 0–150 |
| 10 | `addetti_disponibili_pct` | % | 35–100 |
| 11 | `mezzi_disponibili_pct` | % | 25–100 |
| 12 | `variazione_volumi_hub_pct` | % | -40–80 |
| 13 | `ritardi_vettore_90g_pct` | % | 0–60 |
| 14 | `ritardi_rotta_90g_pct` | % | 0–70 |
| 15 | `ritardo_medio_rotta_90g_min` | minuti | 0–100 |
| 16 | `tentativi_falliti_zona_90g_pct` | % | 0–40 |
| 17 | `puntualita_vettore_90g_pct` | % | 20–100 |
| 18 | `esperienza_autista_rotta_mesi` | mesi | 1–60 |
| 19 | `pioggia_prevista_mm` | mm | 0–60 |
| 20 | `vento_previsto_km_h` | km/h | 0–90 |
| 21 | `rischio_neve_previsto_pct` | % | 0–100 |
| 22 | `cantieri_noti_sul_percorso` | conteggio | 0–15 |
| 23 | `tratti_con_limitazioni` | conteggio | 0–12 |
| 24 | `indice_criticita_meteo_prevista` | punteggio 0–100 | 0–100 |
| 25 | `margine_piano_rispetto_scadenza_ore` | ore | 0.2–16 |
| 26 | `flessibilita_finestra_consegna_ore` | ore | 0.5–12 |
| 27 | `peso_totale_carico_kg` | kg | 10–2000 |
| 28 | `saturazione_mezzo_pct` | % | 10–100 |
| 29 | `colli_fragili_pct` | % | 0–100 |
| 30 | `documenti_da_completare` | conteggio | 0–10 |

## Lavoro richiesto al gruppo

1. Descrivere l'uso della previsione e il costo di falsi positivi e falsi negativi. Discutere recall dei ritardi e precision delle notifiche preventive inviate ai clienti.
2. Seguire S1–S6 del Lab 13: baseline tracciata, API, telemetria, candidata, gate e drill.
3. Conservare la regola comune del laboratorio (accuracy v2 almeno pari a v1) e aggiungere nel report precision, recall e matrice di confusione. Non cambiare la soglia del gate dopo aver visto i risultati.
4. Presentare le misure effettive e i limiti: non sono garantiti né un'accuracy prefissata né il superamento del gate da parte di v2.

## Compatibilità e riproducibilità

Il contratto condiviso del laboratorio prevede 30 feature numeriche e target 0/1. Il gruppo costruisce il proprio lettore, training e servizio seguendo i checkpoint del lab. Cambiano i percorsi dei due CSV e il significato delle feature; modello, schema, ordine e metadati devono restare coerenti in tutte le fasi. Il training legge il file fornito e non deve generare nuovi dati.

Provenienza: generazione sintetica del docente, seed 1303. Ogni soggetto usa gruppi di variabili correlate, effetti non lineari e target probabilistico con rumore, con vincoli di coerenza su contatori, picchi e totali; nessuna feature contiene la label o l'esito futuro osservato. Il seed documenta la preparazione: gli input assegnati restano i CSV distribuiti. Lo split non simula una validazione temporale; una prova su dati futuri reali richiederebbe una valutazione distinta.

---

# Implementazione del progetto - fase S1

## Stato

La fase S1 è implementata: struttura del progetto, configurazione dei percorsi,
lettore e validatore del dataset, contratto dei payload, audit dei dati e
documentazione di obiettivo/metriche/gate. **Non** sono ancora presenti servizio
API, candidata v2, attivazione o rollback. Il gate è fissato ma non ancora
misurato. La fase S2 (training ripetibile, valutazione e baseline v1 tracciata)
è implementata e descritta nella sezione seguente.

## Come individuare i file assegnati

| Risorsa | File nel progetto | Uso |
| --- | --- | --- |
| README del soggetto | Questo README | Descrive il soggetto, i dati, le classi e i vincoli |
| Dataset | `dataset (1).csv` | Input per training e valutazione |
| Richieste di monitoraggio | `richieste_monitoraggio.csv` | Input operativo per le prove API |

I due CSV sono inclusi nella radice del progetto e sono i percorsi predefiniti.
Possono essere sostituiti tramite argomenti CLI o variabili d'ambiente; il
report registra il nome del file e la provenienza.

Ordine di risoluzione dei due CSV:

1. argomento CLI `--dataset` / `--requests`;
2. variabile d'ambiente `LAB13_DATASET_PATH` / `LAB13_REQUESTS_PATH`;
3. CSV inclusi nella radice del progetto.

Esempio PowerShell:

```powershell
$env:LAB13_DATASET_PATH = ".\dataset (1).csv"
$env:LAB13_REQUESTS_PATH = ".\richieste_monitoraggio.csv"
python scripts/audit_data.py
```

Per rimuovere gli override e usare i CSV inclusi nella cartella del progetto:

```powershell
Remove-Item Env:LAB13_DATASET_PATH
Remove-Item Env:LAB13_REQUESTS_PATH
```

> **Attenzione:** `richieste_monitoraggio.csv` contiene solo input operativi per
> le prove API. **Non è un dataset di training o di valutazione**, non contiene
> etichette e non va mai passato al lettore del dataset o usato per il fit.

## Struttura

```text
config/
  gate.json                 # gate congelato: accuracy, p95, error rate
  lab13.env.example         # riferimento per le variabili d'ambiente
docs/
  contratto_inferenza.md    # schema, ordine feature e payload
  obiettivo_metriche_gate.md
src/lab13/
  config.py                 # risoluzione percorsi, tracking URI e impostazioni
  contracts.py              # unica lista canonica + validatore payload + ordine classi
  data.py                   # lettore, controlli e fingerprint SHA-256
  training.py               # pipeline baseline, fit sul train, metriche di validation
  model_io.py               # versionamento artefatti + caricatore con controlli
  tracking.py               # run MLflow su store locale
scripts/
  audit_data.py             # audit S1 e generazione dei report
  train_baseline.py         # training S2, valutazione, MLflow e versionamento
  # S3-S6: nessun script di servizio, candidata, gate misurato, attivazione o drill
tests/                      # test stdlib: contratti, dati, config, gate, training, artefatti
models/                     # artefatti versionati: v1/ (S2)
reports/                    # report di audit S1 e report di valutazione v1
logs/                       # predisposta per i log delle fasi successive
mlruns/                     # store MLflow locale (escluso da .gitignore)
requirements.txt            # manifest delle dipendenze previste, senza pin
```

## Comandi della fase S1

```powershell
# Audit del dataset; risolve i percorsi e scrive reports/data_audit.json e .md
python scripts/audit_data.py

# Percorsi espliciti, senza modificare la configurazione
python scripts/audit_data.py --dataset ".\dataset (1).csv" --requests ".\richieste_monitoraggio.csv"

# Solo controlli, senza scrivere i report
python scripts/audit_data.py --no-write

# Test dei contratti, del lettore, della configurazione e del gate
python -m unittest discover -s tests -v
```

La fase S1 usa solo la libreria standard di Python e non richiede
l'installazione delle dipendenze del laboratorio.

## Audit del dataset

Il report generato contiene i conteggi, gli ID delle 200 righe di validation e
il fingerprint SHA-256 dei byte del CSV. Il dataset di lavoro ha:

| Split | target 0 | target 1 | Totale |
| --- | ---: | ---: | ---: |
| train | 463 | 337 | 800 |
| validation | 116 | 84 | 200 |

Controlli implementati dal lettore:

- file assente, percorso non-file, file vuoto o privo di intestazione;
- intestazioni duplicate, colonne mancanti o inattese;
- righe vuote o con un numero di campi diverso dall'intestazione;
- `record_id` mancante o duplicato;
- split diverso da `train`/`validation`;
- `target` diverso da `0`/`1` (sono rifiutati anche `1.0` e i valori testuali);
- feature non numeriche o non finite (`NaN`, infiniti, notazioni non CSV);
- conteggi totali e per split/classe diversi da quelli attesi;
- ordine delle feature riallineato alla lista canonica.

Il lettore non scrive mai il CSV: il fingerprint è calcolato sui byte letti e
l'ordine delle righe è preservato. Lo split distribuito non viene rigenerato.

- Dataset di lavoro: `.\dataset (1).csv`
- SHA-256: `afee41161484c561feb59576f464321f3f0453c00acb9752a9173a7755e97c79`
- Report: `reports\data_audit.md` e `reports\data_audit.json`

## Contratto di inferenza

Il contratto unico è un oggetto JSON con una sola chiave `features` e
**esattamente 30 numeri finiti nell'ordine canonico**:

```text
{"features": [30 numeri]}
```

- `record_id`, `split` e `target` non sono mai input del modello.
- Le richieste incomplete (per esempio 29 valori) vengono riconosciute e
  respinte; non viene inserito alcun valore mancante.
- Sono rifiutati valori non numerici, booleani, `null`, `NaN` e infiniti.
- Il servizio previsto nelle fasi successive dovrà restituire HTTP 422 per un
  payload non conforme; in S1 il contratto è validato da
  `src/lab13/contracts.py`.

La lista canonica e la documentazione completa sono in
`src/lab13/contracts.py` e `docs/contratto_inferenza.md`.

## Obiettivo, classi, metriche e gate

- `target = 1`: consegna dopo la scadenza promessa.
- `target = 0`: consegna entro la scadenza promessa.
- Momento della previsione: partenza della spedizione.
- Metriche richieste: accuracy, precision e recall della classe 1, matrice di
  confusione con ordine classi `[0, 1]`.
- Costi di falsi positivi e falsi negativi e definizioni: vedi
  `docs/obiettivo_metriche_gate.md`.

Gate congelato il 2026-11-09 in `config/gate.json`:

| Requisito | Soglia |
| --- | --- |
| Accuracy candidata | almeno pari alla v1 sugli stessi ID di validation |
| p95 locale | ≤ 120 ms |
| Error rate | ≤ 0,01 sulle richieste valide |

Le soglie non vanno cambiate dopo aver osservato i risultati. In S1 non
esistono ancora misure di modello, latenza o error rate: non viene dichiarato
alcun superamento del gate.

## Dipendenze

`requirements.txt` elenca i pacchetti previsti: NumPy, scikit-learn, MLflow,
FastAPI, Pydantic, HTTPX e Uvicorn. Docker è facoltativo e non è una dipendenza
Python. Il manifest resta **senza pin**: le versioni osservate nell'ambiente
del laboratorio sono annotate nei commenti del file e nei metadati degli
artefatti (`python 3.11.9`, `numpy 2.4.6`, `scikit-learn 1.8.0`, `mlflow 3.16.1`,
`joblib 1.5.3`). L'audit S1 usa solo la libreria standard; il training S2
richiede NumPy, scikit-learn, joblib e MLflow.

## Limiti

- I dati sono sintetici e didattici: i risultati non misurano prestazioni su
  spedizioni reali.
- I CSV inclusi nel progetto sono copie degli input assegnati; l'audit ne
  registra il fingerprint. Se si usano file assegnati diversi, impostare i
  percorsi e rieseguire l'audit.
- La validation non è un test indipendente e lo split non simula una
  validazione temporale.
- Le fasi successive (API, candidata, gate misurato, attivazione e rollback) non
  sono implementate in queste fasi.
---

# Implementazione del progetto - fase S2

## Stato

S2 è implementata: training ripetibile della baseline, valutazione sulla
validation distribuita, tracciamento MLflow su store locale, artefatti
versionati in `models/v1/` e report di valutazione. Non sono implementati: il
servizio API (S3), la candidata v2 e il gate misurato (S4), le transizioni di
versione e il drill (S5-S6). **v1 non è dichiarata pronta al deployment.**

## Comandi della fase S2

```powershell
# Baseline v1: fit sul train, valutazione, run MLflow, artefatti e report
python scripts/train_baseline.py

# Percorsi espliciti (stessa precedence della fase S1)
python scripts/train_baseline.py --dataset ".\dataset (1).csv" --tracking-uri ".\mlruns"

# Prova di ripetibilità senza toccare v1: cartelle e store separati
python scripts/train_baseline.py --version v1 --models-dir ".\prova\models" --report-dir ".\prova\reports" --tracking-uri ".\prova\mlruns"

# Una seconda esecuzione su v1 è bloccata (exit 4); v1 non viene toccata
python scripts/train_baseline.py

# Test: contratti, dati, configurazione, gate, training, artefatti e caricatore
python -m unittest discover -s tests -v
```

Parametri configurabili: `--version`, `--seed`, `--C`, `--solver`, `--max-iter`,
`--models-dir`, `--report-dir`, `--tracking-uri`, `--experiment`. La baseline è
`StandardScaler` + `LogisticRegression(C=1.0, solver="liblinear", max_iter=1000,
random_state=1303)`; il seed è registrato nei metadati e nel run MLflow.

## Cosa fa il training

- legge il CSV con il lettore di S1 (`load_dataset`); le feature restano
  nell'ordine canonico di `contracts.FEATURE_NAMES` (nessuna lista duplicata);
- fit di scaler e classificatore **solo** sulle 800 righe `train`; le 200 righe
  `validation` sono lette per la sola valutazione, mai per fit, tuning o scelta
  dei parametri;
- `record_id`, `split` e `target` esclusi da `X`; `richieste_monitoraggio.csv`
  non entra nel training;
- calcola accuracy, precision e recall della classe 1 e matrice di confusione
  con ordine dichiarato `[0, 1]` (righe = reale, colonne = predetto);
- conserva predizioni e ID di validation in
  `models/v1/validation_predictions.json` (200 righe `record_id`, `target`,
  `prediction`), sufficienti per ricostruire il report;
- serializza la **pipeline completa** (scaler + classificatore), così il serving
  applicherà la stessa trasformazione;
- apre il run MLflow **prima** del salvataggio: il run ID entra nei metadati e i
  file versionati sono loggati come artefatti del run.

## Risultati effettivamente misurati (v1, validation 200 righe)

| Metrica | Valore |
| --- | ---: |
| Accuracy | 0.7350 |
| Precision classe 1 | 0.6742 |
| Recall classe 1 | 0.7143 |

| | Predetto 0 | Predetto 1 |
| --- | ---: | ---: |
| **Reale 0** | 87 (TN) | 29 (FP) |
| **Reale 1** | 24 (FN) | 60 (TP) |

Run MLflow della v1 prodotta: `64079619c2c947bd83699d0d552b9d78`, esperimento
`lab13-progetto3-ritardi-consegne`, store locale `mlruns`.

| Risorsa | Riferimento |
| --- | --- |
| Dataset | `dataset (1).csv`, SHA-256 `afee41161484c561feb59576f464321f3f0453c00acb9752a9173a7755e97c79` |
| Artefatto | `models/v1/pipeline.joblib`, SHA-256 `f8aea6264329d4c53d1f87e270c10ef7a3567c739c59c5796ccf116ccb7e1bd7` |
| Metadati | `models/v1/model_metadata.json` |
| Predizioni validation | `models/v1/validation_predictions.json` |
| Report | `reports/v1_valutazione.md` e `reports/v1_valutazione.json` |

Rieseguendo il comando in cartelle nuove l'artefatto produce lo stesso SHA-256 e
le stesse predizioni: la pipeline è ripetibile a parità di dati e parametri. Il
run ID cambia perché è un run nuovo, non una ripetizione di v1.

## Contenuto dei metadati

`models/v1/model_metadata.json` riporta: versione e fase, timestamp UTC, stato
(baseline valutata, non attivata), parametri e seed della pipeline, lista
ordinata delle 30 feature con la fonte (`contracts.py`), ordine classi e
significato, fingerprint SHA-256 del CSV con provenienza, conteggi per split e
classe, politica di training (fit solo su train, validation solo valutazione,
richieste non usate), ID delle 200 righe di validation, metriche e matrice di
confusione, run ID / esperimento / tracking URI MLflow, SHA-256 e dimensione
dell'artefatto, nomi dei file versionati e versioni software disponibili
(`python 3.11.9`, `numpy 2.4.6`, `scikit-learn 1.8.0`, `mlflow 3.16.1`,
`joblib 1.5.3`).

## Caricatore con controlli

```python
from lab13.model_io import load_version

model = load_version(
    "models/v1",
    expected_version="v1",
    expected_dataset_sha256="afee41161484c561feb59576f464321f3f0453c00acb9752a9173a7755e97c79",
)
model.pipeline.predict([[...30 valori nell'ordine canonico...]])
```

Controlli eseguiti prima di restituire il modello, nell'ordine: metadati
presenti, leggibili e con le chiavi richieste; versione (metadati ↔ cartella ↔
versione attesa); schema e ordine delle 30 feature (metadati contro la lista
canonica e `n_features_in_` dell'artefatto); fingerprint del dataset; hash
SHA-256 dell'artefatto; contratto della pipeline (due passi `scaler`/`classifier`).
Ogni fallimento solleva `ModelLoadError` con un messaggio che nomina il controllo
non superato (per esempio `Controllo 'hash dell'artefatto' non superato`).

## Tracciamento MLflow locale

- tracking URI con la stessa precedence dei percorsi: `--tracking-uri` >
  `LAB13_MLFLOW_TRACKING_URI` > `mlruns` nella radice del progetto;
- nessuna connessione esterna: store su file locale. MLflow 3.x mette il store
  su file in *maintenance mode* e richiede l'opt-out
  `MLFLOW_ALLOW_FILE_STORE=true`, impostato dal progetto (sovrascrivibile
  dall'ambiente). In alternativa un store locale a database:
  `--tracking-uri sqlite:///mlflow.db`;
- loggate nel run: parametri della pipeline, metriche, tag (fingerprint del CSV,
  split usato, hash e percorso dell'artefatto, stato) e gli artefatti
  `pipeline.joblib`, `model_metadata.json`, `validation_predictions.json`,
  `v1_valutazione.json`;
- UI locale opzionale e non necessaria: `mlflow ui --tracking-uri ./mlruns`.

## Ripetibilità e non-sovrascrittura

- una seconda esecuzione su `v1` termina con errore esplicito (exit 4) senza
  cancellare o sovrascrivere `models/v1` né i report della versione; la prova si
  fa con `--models-dir`, `--report-dir` e `--tracking-uri` separati;
- la versione è rivendicata prima di aprire il run, così un blocco non produce
  un fit né un run MLflow vuoto;
- se il tracciamento o la scrittura dei report falliscono dopo il salvataggio,
  la versione scritta da quell'esecuzione viene rimossa: non resta una versione
  senza run coerente.

## Limiti di S2

- I dati sono sintetici e didattici: le metriche non misurano spedizioni reali.
- La validation assegnata non è un test indipendente e non simula una
  validazione temporale.
- La baseline è lineare e i parametri sono fissati a priori (seed e solver
  documentati): nessuna ricerca di iperparametri né ottimizzazione di soglia,
  per non usare la validation come selezione.
- La serializzazione dell'artefatto dipende dalle versioni di joblib,
  scikit-learn e NumPy: le versioni usate sono registrate nei metadati
  (`environment`); un ambiente con versioni diverse può produrre un hash
  dell'artefatto diverso. Il caricatore confronta l'hash dei metadati, quindi
  una rserializzazione in un ambiente diverso va rieseguita in una versione
  nuova invece di sostituire v1.
- Il gate di `config/gate.json` non è misurato: in S2 non esistono servizio,
  p95 ed error rate. Il gate resta congelato.
