# Consegna S4 → S5-S6 - Transizioni, drill e rollback

Questo documento raccoglie le aggiunte e le modifiche della fase finale del
progetto (S5-S6) rispetto allo stato consegnato in S3-S4. Il nome del file è
quello richiesto (`consegna_s4_s5.md`); per comodità qui la fase è indicata come
S5-S6, cioè transizioni di versione, drill locale e consegna.

## Esito sintetico

La fase finale è completa. Il drill locale ha eseguito la sequenza
`v1 → v2 → v1` con le quattro richieste assegnate, ha ottenuto
`200, 200, 200, 422`, ha ripristinato la baseline ed è terminato con lo stato
attivo su **v1**.

| Elemento | Esito |
| --- | --- |
| Stato attivo e registro transizioni | implementati, scrittura atomica |
| Cambio versione offline | `scripts/switch_version.py` (`status`, `activate`, `rollback`) |
| Cambio versione a caldo locale | `POST /admin/version`, solo con `LAB13_ALLOW_VERSION_SWITCH=1` |
| Sequenza drill | `req_01` v1, `req_02` v2, `req_03` v1, `req_04` v1 incompleta |
| Status HTTP | `200, 200, 200, 422` |
| Error rate drill | `1/4 = 0,25` (3 valide + 1 errore atteso) |
| Error rate sole richieste valide | `0/3 = 0,0` |
| Error rate gate S4 | `0/30 = 0,0` (misura separata, invariata) |
| Stato finale | `v1`, run `64079619c2c947bd83699d0d552b9d78` |
| Test automatici | 100 test superati |
| Container / deployment esterno | non eseguito, dichiarato esplicitamente |

## Checklist dei punti della consegna

| # | Punto del prompt | Realizzazione | Evidenza |
| ---: | --- | --- | --- |
| 1 | Comandi per selezionare/ripristinare la versione; stato, transizioni, atomicità | `version_state.py`, `switch_version.py`, `POST /admin/version`; stato scritto con file temporaneo + `os.replace`; journal JSONL con timestamp, azione, prima/dopo, run ID e hash artefatto | `src/lab13/version_state.py`, `config/active_version.json`, `reports/drill/transitions.jsonl` |
| 2 | Rispettare il gate; v2 solo in drill locale etichettato | Gate S4 `SUPERATO`; v2 attivata solo nel drill e poi ripristinata a v1; nessun deployment dichiarato | `reports/gate_s4.md`, `reports/drill_s5_s6.md`, `docs/consegna_finale.md` |
| 3 | Script che legge `richieste_monitoraggio.csv`, decodifica `payload_json`, usa i request ID e rispetta l'ordine | `scripts/drill_rollback.py`; ordine verificato e rifiutato se diverso | `scripts/drill_rollback.py`, `tests/test_drill.py` |
| 4 | Registrare versione servita, request ID, status, predizione e correlazione log; 422 reale | Report per richiesta con `served_version`, `request_id`, `actual_status`, `prediction`, `log_correlated`; `req_04` passa dal validatore e restituisce 422 | `reports/drill_s5_s6.json`, `reports/drill/requests.jsonl`, `reports/drill/request_log_extract.jsonl` |
| 5 | Dopo v2 ripristinare v1 e provarlo | Rollback registrato; `/health` con v1, run ID e hash; `req_03` valida su v1 dopo il ripristino | `reports/drill_s5_s6.md`, `config/active_version.json` |
| 6 | Riportare separatamente probe/gate e drill | Tabelle distinte; drill `0,25`, gate `0/30`, richieste valide del drill `0/3` | `docs/consegna_finale.md`, `README.md`, `reports/drill_s5_s6.md` |
| 7 | README completo | Scopo/classi, dati sintetici/limiti, schema e ordine delle 30 feature, ambiente/versioni, setup, comandi audit/training/serving/probe/drill, percorsi report/artefatti, stato finale, cleanup, livelli eseguiti | `README.md`, `docs/consegna_finale.md` |
| 8 | Evidenze organizzate senza payload grezzi | Report v1/v2, run ID, tabella gate, probe, risposte/log drill, registro transizioni, prova finale; log senza payload | `docs/consegna_finale.md`, `reports/`, `reports/drill/` |
| 9 | Traccia di presentazione ordinata | Problema → dati → baseline → servizio → candidata → gate → drill/rollback → limiti → contributi | `docs/presentazione.md` |
| 10 | Cleanup e conservazione di sorgenti, dipendenze, input e artefatti | Cleanup di processi/variabili documentato; porta 8000 verificata libera; nessun container creato; sorgenti, `requirements.txt`, CSV assegnati e artefatti conservati | `README.md`, `docs/consegna_finale.md`, `requirements.txt` |

## File aggiunti

| File | Contenuto |
| --- | --- |
| `src/lab13/version_state.py` | Stato attivo atomico, validazione di versione/azione/modalità, journal delle transizioni |
| `scripts/switch_version.py` | CLI offline `status`, `activate`, `rollback` |
| `scripts/drill_rollback.py` | Drill HTTP completo con avvio/arresto di uvicorn e generazione delle evidenze |
| `tests/test_version_state.py` | Test di stato atomico, transizioni e validazione |
| `tests/test_drill.py` | Test di lettura richieste, ordine, payload incompleto e calcolo error rate |
| `reports/drill_s5_s6.json` | Report strutturato del drill |
| `reports/drill_s5_s6.md` | Report leggibile del drill |
| `reports/drill/transitions.jsonl` | Registro delle transizioni `activate v1 -> v2` e `rollback v2 -> v1` |
| `reports/drill/requests.jsonl` | Log delle richieste del drill, senza payload |
| `reports/drill/request_log_extract.jsonl` | Estratto correlato alle quattro richieste |
| `reports/drill/server.log` | Log del server locale avviato dal drill |
| `reports/fingerprint_coerenza.md` | Spiegazione e verifica della differenza CRLF/LF |
| `docs/consegna_finale.md` | Consegna finale, mappa evidenze e istruzioni di ripetizione |
| `docs/presentazione.md` | Traccia di presentazione |
| `docs/consegna_s4_s5.md` | Questo documento di riepilogo delle modifiche finali |

## File modificati

| File | Modifica |
| --- | --- |
| `src/lab13/data.py` | Aggiunto SHA-256 canonico (CRLF→LF) accanto allo SHA-256 raw |
| `src/lab13/model_io.py` | Caricamento verificato con fingerprint canonico |
| `src/lab13/service.py` | Caricamento canonico, hash in `/health`, endpoint locale `POST /admin/version`, lock di transizione |
| `scripts/audit_data.py` | Audit con hash canonico nell'output e nei report |
| `scripts/train_baseline.py` | Metadati/report con fingerprint canonico, senza riallenare |
| `scripts/probe_service.py` | Caricamento della candidata con fingerprint canonico |
| `models/v1/model_metadata.json` | Aggiunto `dataset.sha256_canonical` |
| `models/v2/model_metadata.json` | Aggiunto `dataset.sha256_canonical` |
| `comparison_baseline/models/v1/model_metadata.json` | Aggiunto `dataset.sha256_canonical` |
| `config/active_version.json` | Stato finale v1 dopo rollback, con azione, modalità, run ID e hash |
| `tests/test_data.py` | Test del fingerprint canonico |
| `tests/test_model_io.py` | Test del caricamento con fingerprint canonico |
| `tests/test_service.py` | Test di `/health`, endpoint disabilitato e validazione azione |
| `README.md` | Stato finale, setup, sezione S5-S6, comandi, evidenze, livelli e cleanup |
| `docs/consegna_finale.md` | Aggiunto il collegamento a questo documento |
| `docs/consegna_s3_s4.md` | Nota storica e chiarimento sulla riconciliazione CRLF/LF |
| `docs/contratto_inferenza.md` | Nota sull'implementazione del contratto e sul 422 reale |
| `docs/obiettivo_metriche_gate.md` | Nota sullo stato finale del gate e sulle soglie invariate |
| `docs/presentazione.md` | Collegamento ai materiali di consegna |
| `reports/data_audit.json`, `reports/data_audit.md` | Rigenerati con il fingerprint canonico |
| `reports/gate_s4.md` | Nota successiva sul drill, senza modificare decisione o soglie |
| `reports/v1_valutazione.md` | Nota storica: report S2, stato finale successivo |
| `reports/v2_valutazione.md` | Nota storica: v2 attivata solo nel drill locale |
| `comparison_baseline/reports/v1_valutazione.md` | Nota storica: baseline isolata usata dal gate |
| `requirements.txt` | Annotato l'ambiente del drill e l'assenza di nuove dipendenze |

## Risultato del drill

| # | Request ID | Versione attesa | Status atteso | Status reale | Predizione | Versione servita |
| ---: | --- | --- | ---: | ---: | ---: | --- |
| 1 | `req_01` | v1 | 200 | 200 | 0 | v1 |
| 2 | `req_02` | v2 | 200 | 200 | 1 | v2 |
| 3 | `req_03` | v1 | 200 | 200 | 1 | v1 |
| 4 | `req_04` | v1 incompleta (29 feature) | 422 | 422 | - | - |

- Il 422 di `req_04` è prodotto dal contratto di validazione
  (`wrong_feature_count`) prima del predict.
- Ogni richiesta ha request ID restituito nel body e nel log.
- Il log delle richieste non contiene payload grezzi.
- Il valore `0,25` è l'error rate del drill; non sostituisce lo `0/30` del gate.

## Prova dello stato finale

- `config/active_version.json`: `version = v1`, `action = rollback`,
  `mode = drill`, run ID `64079619c2c947bd83699d0d552b9d78`, artefatto
  `f8aea6264329d4c53d1f87e270c10ef7a3567c739c59c5796ccf116ccb7e1bd7`.
- `/health` finale: `active_version = v1`, stesso run ID e stesso hash.
- Metadati `models/v1`: stessi run ID, hash artefatto e fingerprint canonico
  `5c999d24a24126e81a033ae5ecf9b9b1049925f8abe59367883bcd171476c72f`.
- `req_03`, inviata dopo il rollback, è valida e servita da v1 con status 200.
- La suite completa esegue 100 test senza errori.

## Comandi di verifica

```powershell
python -m unittest discover -s tests -v
python scripts/switch_version.py status
python scripts/drill_rollback.py
```

Per un server già avviato:

```powershell
$env:LAB13_ALLOW_VERSION_SWITCH = "1"
uvicorn lab13.service:app --app-dir src --host 127.0.0.1 --port 8000
python scripts/drill_rollback.py --base-url http://127.0.0.1:8000
```

## Ambiente

- Misure S5-S6: Python 3.12.4, NumPy 2.4.5, scikit-learn 1.9.0, joblib 1.5.3.
- Artefatti v1/v2: creati con Python 3.11.9, NumPy 2.4.6 e scikit-learn
  1.8.0/1.9.1; il caricamento emette `InconsistentVersionWarning`, ma le
  predizioni riprodotte coincidono con quelle salvate.
- MLflow non è richiesto dal drill e non era installato nell'ambiente usato.
- Nessuna nuova dipendenza Python è stata introdotta: stato e transizioni usano
  solo la libreria standard.

## Limiti e livelli non eseguiti

- Dati sintetici e didattici: nessuna generalizzazione a spedizioni reali.
- Validation assegnata non indipendente e non temporale.
- Il gate conserva la decisione misurata in S4 con la baseline isolata; non è
  stato riscritto dopo il drill.
- Il cambio versione è locale e richiede `LAB13_ALLOW_VERSION_SWITCH=1`; non è
  un endpoint di produzione.
- **Container / deployment esterno: non eseguito.**
- La tabella dei contributi in `docs/presentazione.md` contiene ancora i
  segnaposto dei nomi: vanno compilati a cura del gruppo.

## Cleanup

- Il drill avviato senza `--base-url` arresta uvicorn al termine.
- Se il server è avviato manualmente, fermarlo con `Ctrl+C`; la porta 8000 è
  stata verificata libera dopo il drill.
- Rimuovere le variabili della sessione:
  `LAB13_ALLOW_VERSION_SWITCH`, `LAB13_ACTIVE_VERSION_PATH`,
  `LAB13_TRANSITIONS_PATH`, `LAB13_REQUEST_LOG`.
- Non eliminare `models/`, `reports/`, `reports/drill/` e
  `config/active_version.json`: sono artefatti ed evidenze.
- Nessun container è stato creato, quindi non c'è nulla da rimuovere a quel
  livello.

## Riferimenti

- Consegna completa: `docs/consegna_finale.md`
- Presentazione: `docs/presentazione.md`
- Drill: `reports/drill_s5_s6.md`
- Transizioni: `reports/drill/transitions.jsonl`
- Fingerprint: `reports/fingerprint_coerenza.md`
- Gate: `reports/gate_s4.md`
