# Prompt 1 — Dati, obiettivo e contratti (S1)

Agisci sul progetto aperto nella cartella di lavoro corrente. Implementa la prima fase del Lab 13: lettura e controllo dei dati, contratti condivisi e struttura minima del progetto. Non svolgere ancora training, API, candidata, attivazione o rollback.

## Contesto

- Soggetto: Progetto 3, previsione dei ritardi nelle consegne logistiche.
- Momento della previsione: partenza della spedizione.
- `target=1`: consegna dopo la scadenza promessa; `target=0`: consegna entro la scadenza.
- I dati sono sintetici e didattici: non attribuire ai risultati validità su spedizioni reali.
- README del soggetto: `README.md` nella radice del progetto.
- Dataset assegnato: `dataset (1).csv` nella radice del progetto.
- Richieste assegnate: `richieste_monitoraggio.csv` nella radice del progetto.
- Il file richieste serve esclusivamente alle prove API e non deve mai essere usato per training o valutazione.

## Procedura

1. Leggi le istruzioni locali (`AGENTS.md`, se presenti), il README e l'intestazione dei CSV. Mantieni eventuali convenzioni del progetto già esistente.
2. Crea una struttura di progetto semplice per sorgenti, configurazione, modelli, report, log e script. Mantieni i due percorsi CSV configurabili; usa quelli indicati sopra come valori predefiniti. Non copiare né modificare i CSV di input.
3. Definisci una sola lista canonica, ordinata, di 30 feature API:

   `distanza_pianificata_km`, `numero_fermate_pianificate`, `indice_congestione_prevista`, `quota_percorso_urbano_pct`, `deviazione_prevista_km`, `tempo_viaggio_stimato_ore`, `pacchi_in_coda_hub`, `occupazione_hub_pct`, `attesa_carico_prevista_min`, `addetti_disponibili_pct`, `mezzi_disponibili_pct`, `variazione_volumi_hub_pct`, `ritardi_vettore_90g_pct`, `ritardi_rotta_90g_pct`, `ritardo_medio_rotta_90g_min`, `tentativi_falliti_zona_90g_pct`, `puntualita_vettore_90g_pct`, `esperienza_autista_rotta_mesi`, `pioggia_prevista_mm`, `vento_previsto_km_h`, `rischio_neve_previsto_pct`, `cantieri_noti_sul_percorso`, `tratti_con_limitazioni`, `indice_criticita_meteo_prevista`, `margine_piano_rispetto_scadenza_ore`, `flessibilita_finestra_consegna_ore`, `peso_totale_carico_kg`, `saturazione_mezzo_pct`, `colli_fragili_pct`, `documenti_da_completare`.

4. Implementa un lettore configurabile che separi feature, `record_id`, `split` e `target`. Solo le 30 feature sono input; `record_id`, `split` e `target` non devono arrivare al modello.
5. Aggiungi controlli espliciti per file vuoto/assente, intestazioni o colonne duplicate, colonne mancanti/inattese, ID mancanti o ripetuti, split inattesi, target diversi da 0/1, feature non numeriche o non finite. Mantieni l'ordine delle feature canonico e segnala chiaramente gli errori.
6. Calcola e restituisci conteggi per split e classe, ID delle righe di validation e fingerprint SHA-256 dei byte del CSV. Il dataset atteso contiene 1.000 righe: train 800 (463 target 0, 337 target 1), validation 200 (116 target 0, 84 target 1). Non rigenerare lo split.
7. Definisci un contratto unico per i payload di inferenza: oggetto JSON `{ "features": [30 valori numerici nell'ordine canonico] }`. Le richieste incomplete devono poter essere riconosciute e respinte; non riempire valori mancanti.
8. Documenta lo scopo, il significato delle classi, il momento della previsione, i costi plausibili di falsi positivi/falsi negativi e le metriche richieste: accuracy, precision, recall e matrice di confusione. Fissa sin d'ora il gate comune: accuracy candidata almeno pari a v1, p95 locale ≤ 120 ms ed error rate ≤ 0,01 sulle richieste valide. Non modificarlo dopo aver osservato i risultati.
9. Prepara il manifest delle dipendenze Python previste dal laboratorio (NumPy, scikit-learn, MLflow, FastAPI, Pydantic, HTTPX e Uvicorn; Docker facoltativo) senza installarle. Registra nel progetto che le versioni reali andranno annotate quando l'ambiente sarà predisposto.

## Risultato atteso

Lascia sorgenti riutilizzabili per il lettore, configurazione, documentazione del contratto e struttura pronta per la fase 2. Il README deve indicare come individuare i file assegnati e ricordare che il CSV richieste non è un dataset di training. Non inventare righe o etichette e non modificare i dati originali.

Al termine, riepiloga i file creati/modificati, il contratto adottato, le verifiche di schema implementate e gli eventuali blocchi dovuti ai file mancanti. Non anticipare le fasi successive.
