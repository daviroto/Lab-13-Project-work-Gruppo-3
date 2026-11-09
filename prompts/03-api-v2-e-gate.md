# Prompt 3 — Servizio osservabile, candidata v2 e gate (S3–S4)

Prosegui il progetto esistente implementando in sequenza S3 e S4 del Lab 13: servizio di inferenza osservabile, candidata v2 e decisione basata sul gate. Leggi il README e riusa il contratto dati, il caricatore e gli artefatti v1 delle fasi precedenti. Non attivare v2 e non eseguire il drill di cambio/ripristino: quelli appartengono alla fase 4.

## A. Servizio e telemetria

1. Implementa un'app FastAPI con contratto di inferenza `{"features": [30 numeri]}` nell'ordine canonico. Rifiuta quantità errata, valori non numerici o non finiti con HTTP 422 prima di invocare il modello.
2. Carica il modello selezionato tramite lo stato/configurazione della versione attiva: la versione dichiarata dalla risposta deve corrispondere all'artefatto realmente caricato, non a una stringa cosmetica.
3. `GET /health` deve esporre almeno versione attiva e run ID. La risposta di predict deve contenere predizione, versione, run ID e request ID.
4. Accetta un request ID fornito dal client (per esempio header `X-Request-ID`) oppure generane uno; restituiscilo anche nei casi di errore di validazione e usalo nei log.
5. Registra timestamp, request ID, versione, stato HTTP e durata per richieste valide e respinte, includendo le 422. Non registrare payload grezzi. Mantieni `health` e lettura metriche fuori dal conteggio delle predizioni.
6. Espone una finestra di metriche operativa con numero di richieste, errori HTTP ≥400, error rate e p95 in millisecondi. Specifica la semantica della finestra e gestisci il caso di zero richieste senza divisioni per zero.
7. Mantieni distinto ciò che l'app prova in-process da avvio HTTP/container: non presentare un livello come verificato se non lo è.

## B. Candidata v2 e gate

8. Definisci un'ipotesi motivata per la candidata, scegliendo una modifica a modello o configurazione. Allena v2 sullo stesso train di v1, senza modificare i dati, l'ordine feature o lo split; non fare fit sulla validation.
9. Valuta la vera v1 salvata e v2 sugli stessi ID di validation. Registra per entrambe accuracy, precision, recall della classe 1 e matrice di confusione. Conserva v2 separatamente in `models/v2/`, con run MLflow e metadati/fingerprint coerenti con quelli di v1.
10. Implementa una probe locale ripetibile per la candidata usando un payload valido tratto da `richieste_monitoraggio.csv`: 3 warm-up seguiti da 30 misure. La probe deve riportare p95, error rate, ambiente e fingerprint dell'artefatto realmente caricato. Distingui chiaramente chiamata in-process e chiamata HTTP.
11. Crea un report/tabella di gate con requisito, valore misurato, soglia, esito e motivazione: (a) accuracy v2 ≥ accuracy v1, (b) p95 locale ≤120 ms, (c) error rate ≤0,01 sulle richieste valide. Non cambiare soglie dopo aver visto i risultati. Se una misura manca, è attribuita a un artefatto diverso o usa una prova non comparabile, il gate deve risultare bloccato.
12. Il gate registra una decisione; non deve modificare lo stato attivo. Anche una v2 migliore in accuracy non supera automaticamente un eventuale vincolo operativo violato.

## Vincoli e risultato atteso

Le quattro righe del CSV monitoraggio sono input operativi, non training: `req_01` (v1, attesa 200), `req_02` (v2, attesa 200), `req_03` (v1, attesa 200), `req_04` (v1 incompleta, attesa 422). Il payload JSON contiene la chiave `features`; l'ultima richiesta ne contiene 29.

Al termine devono esistere servizio, telemetria, comando per produrre e valutare v2, probe e report di gate. Riepiloga i file e la decisione risultante senza attivare v2; se non puoi produrre misure, dichiara il gate bloccato e il motivo.
