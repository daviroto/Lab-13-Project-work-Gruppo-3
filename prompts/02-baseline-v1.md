# Prompt 2 — Baseline ripetibile e tracciata v1 (S2)

Prosegui il progetto esistente completando soltanto la fase S2 del Lab 13: training ripetibile, valutazione e conservazione della baseline v1. Prima di modificare file, leggi il README e riusa il contratto, il lettore, la configurazione e l'ordine delle feature stabiliti nella fase 1. Non riscrivere ciò che funziona e non iniziare API, v2 o attivazione.

## Contesto e vincoli

- Dataset: `dataset (1).csv` nella radice del progetto.
- Il train assegnato è di 800 righe; la validation di 200 righe. Usa la colonna `split` distribuita, senza creare nuovi split.
- Le feature sono le 30 colonne canoniche della fase 1. Escludi sempre `record_id`, `split` e `target` da `X`.
- Fit di ogni trasformazione esclusivamente sul train. La validation è solo per valutazione didattica, non è un test indipendente.
- Il CSV `richieste_monitoraggio.csv` non entra nel training.

## Procedura

1. Controlla che il lettore e il contratto della fase 1 siano riutilizzati da tutti gli script; evita liste di feature duplicate.
2. Implementa uno script/comando di training con configurazione esplicita e comportamento ripetibile. Usa come baseline una pipeline scikit-learn composta da `StandardScaler` e `LogisticRegression` (con parametri e seed registrati). Salva la pipeline completa così il serving applicherà la stessa trasformazione.
3. Allena solo sulle righe `train`. Calcola sulla validation accuracy, precision e recall per la classe 1, più matrice di confusione con ordine classi dichiarato. Conserva anche le predizioni e gli ID di validation che permettono di ricostruire il report.
4. Traccia con MLflow parametri, metriche, configurazione, fingerprint SHA-256 del CSV e riferimenti agli artefatti. Seleziona un tracking URI locale configurabile; non rendere necessaria una connessione esterna.
5. Salva la versione in una cartella distinta e non sovrascrivibile, per esempio `models/v1/`, contenente almeno pipeline serializzata e `model_metadata.json`. I metadati devono riportare versione, MLflow run ID, fingerprint dei dati, hash SHA-256 dell'artefatto, lista ordinata delle feature, ID di validation, parametri e versioni software disponibili.
6. Implementa un caricatore che controlli versione, schema/ordine feature, fingerprint previsto e hash dell'artefatto prima di restituire il modello. Se i controlli falliscono, interrompi il caricamento con un messaggio che identifica il controllo non superato.
7. Fai in modo che una seconda esecuzione non cancelli né sovrascriva v1: richiedi un percorso/versione nuova o termina con un errore esplicito.
8. Scrivi un report leggibile che colleghi metriche, run ID, file dati, split e artefatto. Registra i risultati effettivamente ottenuti; non inventare metriche e non dichiarare che v1 è pronta al deployment senza le fasi successive.

## Risultato atteso

Devono esistere un comando ripetibile per creare v1, una pipeline completa conservata, metadati verificabili e un report di valutazione. Non usare i dati di validation per fit, tuning o scelta dei parametri. Non creare v2 in questa fase.

Al termine, riepiloga file e comandi aggiunti, contenuto dei metadati e percorso degli artefatti. Se non puoi eseguire il training per dipendenze o dati mancanti, lascia il flusso implementato e indica il blocco senza fabbricare output.
