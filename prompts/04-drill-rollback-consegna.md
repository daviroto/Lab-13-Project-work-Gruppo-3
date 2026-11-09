# Prompt 4 — Drill di versione, rollback e consegna (S5–S6)

Completa la fase finale del progetto esistente: transizioni di versione, drill locale, prova del ripristino e materiali di consegna. Prima di agire, leggi README, report v1, report v2/gate, configurazione del serving e log disponibili. Riusa i componenti esistenti e non rigenerare dati, modelli o split.

## Procedura

1. Implementa comandi/operazioni espliciti per selezionare una versione servita e ripristinare la precedente. Conserva lo stato attivo e registra ogni transizione con timestamp, azione, stato prima/dopo, run ID e fingerprint dell'artefatto. Aggiorna lo stato in modo atomico, così il servizio non può indicare una versione diversa dal modello caricato.
2. Rispetta il risultato del gate: se v2 è accettata, documenta l'attivazione locale; se è bloccata, lascia la decisione invariata e consenti il cambio soltanto in modalità drill locale esplicitamente etichettata. Il drill non deve presentare una candidata bloccata come deployment approvato.
3. Implementa uno script per leggere `richieste_monitoraggio.csv` dalla radice del progetto, decodificare `payload_json` e inviare le richieste usando i request ID forniti. Rispetta l'ordine previsto: v1 valida, v2 valida, v1 valida, v1 incompleta.
4. Registra per ogni richiesta versione realmente servita, request ID, status HTTP, predizione quando disponibile e correlazione al log. Le attese sono 200, 200, 200 e 422. Il 422 deve risultare dal normale contratto di validazione, non da una risposta simulata.
5. Dopo la richiesta v2, ripristina v1 e dimostra tramite health, metadati/fingerprint e una richiesta valida che il modello servito è tornato effettivamente alla baseline. Lascia lo stato finale su v1.
6. Riporta separatamente la probe della fase 3 e il drill: nel drill ci sono 3 risposte valide e 1 errore (stato ≥400), quindi error rate 0,25 su quattro richieste; questo valore non sostituisce la misura del gate sulle richieste valide.
7. Completa il README del progetto: scopo e classi, provenienza sintetica e limiti, schema/ordine feature, ambiente e versioni, setup, comandi per audit/training/serving/probe/drill, percorsi dei report e artefatti, stato finale, cleanup. Indica esplicitamente quali livelli sono stati realmente eseguiti (in-process, HTTP, container) e scrivi “non eseguito” dove manca evidenza.
8. Organizza le evidenze essenziali: report v1/v2, configurazioni e run ID, tabella gate, risultato della probe, risposte e log del drill, registro transizioni e prova dello stato finale. Non inserire payload grezzi nei log o nei report se non sono necessari.
9. Prepara una traccia di presentazione ordinata: problema → dati → baseline → servizio → candidata → gate → drill/rollback → limiti e contributi dei componenti. Non inventare risultati o dichiarare generalizzazione a dati reali.
10. Documenta il cleanup dei processi/container. Conserva sorgenti, dipendenze, input assegnati, artefatti versionati con metadati e prove essenziali.

## Criterio di completamento

Un compagno deve poter ricostruire una predizione fino a versione, run e dataset e seguire la sequenza v1 → v2 → v1, compresa la richiesta incompleta. Lo stato effettivamente servito alla fine deve essere v1. Se un passaggio non può essere eseguito per mancanza di dipendenze o ambiente, lascia il relativo comando/documentazione e marca l'evidenza come non eseguita, senza inventarla.

Al termine, riepiloga file ed evidenze prodotti, stato finale della versione attiva, limitazioni residue e istruzioni per ripetere la consegna.
