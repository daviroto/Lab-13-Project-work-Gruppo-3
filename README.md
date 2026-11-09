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
documentazione di obiettivo/metriche/gate. **Non** sono ancora presenti
training, modello, servizio API, candidata v2, attivazione o rollback. Il gate è
fissato ma non ancora misurato.

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
  config.py                 # risoluzione percorsi e impostazioni
  contracts.py              # unica lista canonica + validatore payload
  data.py                   # lettore, controlli e fingerprint SHA-256
scripts/
  audit_data.py             # audit S1 e generazione dei report
tests/                      # test stdlib: contratti, dati, configurazione, gate
models/                     # predisposta per gli artefatti delle fasi successive
reports/                    # report di audit generati
logs/                       # predisposta per i log delle fasi successive
requirements.txt            # manifest delle dipendenze previste, senza versioni
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
Python. Il manifest è volutamente **senza versioni** e non è stato installato in
S1; le versioni reali andranno annotate quando l'ambiente del laboratorio sarà
predisposto.

## Limiti

- I dati sono sintetici e didattici: i risultati non misurano prestazioni su
  spedizioni reali.
- I CSV inclusi nel progetto sono copie degli input assegnati; l'audit ne
  registra il fingerprint. Se si usano file assegnati diversi, impostare i
  percorsi e rieseguire l'audit.
- La validation non è un test indipendente e lo split non simula una
  validazione temporale.
- Le fasi successive (training, API, candidata, gate misurato, attivazione e
  rollback) non sono implementate in questa fase.
