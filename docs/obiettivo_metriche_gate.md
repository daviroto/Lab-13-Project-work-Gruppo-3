# Obiettivo, classi, metriche e gate

## Problema e momento della previsione

**Domanda:** quali spedizioni rischiano di essere consegnate dopo la scadenza
promessa?

La previsione avviene **alla partenza della spedizione**, usando solo
informazioni disponibili in quel momento. Non sono input dello scenario dati
osservati durante il viaggio o dopo la consegna. I dati sono sintetici e
didattici: i risultati non hanno validità dimostrata su spedizioni reali.

## Significato delle classi

| Valore | Significato |
| ---: | --- |
| `target = 1` | La spedizione viene consegnata **dopo** la scadenza promessa. |
| `target = 0` | La spedizione viene consegnata **entro** la scadenza promessa. |

La classe positiva per precision e recall è `target = 1`, cioè il ritardo.

## Uso operativo previsto

La previsione serve a supportare decisioni umane: priorità di monitoraggio,
contatto preventivo con il cliente e allocazione di capacità. Non è una
decisione automatica di rimborso, cancellazione o modifica contrattuale. Questa
è una descrizione dello scopo, non un servizio già implementato in S1.

## Costi plausibili degli errori

I costi seguenti sono qualitativi: il dataset non contiene informazioni
economiche e non è possibile stimare importi dai dati assegnati.

### Falso positivo (`target = 0` previsto come `1`)

Una spedizione puntuale viene segnalata come a rischio. Conseguenze plausibili:

- notifica o priorità non necessaria, con costo operativo;
- possibile contatto con il cliente e aspettativa creata senza necessità;
- uso improprio di capacità di intervento;
- perdita di fiducia nelle notifiche se i falsi allarmi sono frequenti.

Il falso positivo riduce la **precision** delle notifiche preventive. Una
precision bassa rende costoso gestire l'alerting e può portare a ignorare
segnali utili.

### Falso negativo (`target = 1` previsto come `0`)

Una spedizione che arriverà in ritardo non viene segnalata. Conseguenze
plausibili:

- nessun intervento preventivo o contatto con il cliente;
- ritardo scoperto tardi, con costi di recupero e possibili penali;
- danno alla relazione con il cliente;
- minore capacità di riallocare mezzi e personale.

Il falso negativo riduce la **recall** della classe ritardo. In questo dominio
è particolarmente critico, ma la scelta di un punto di lavoro deve comunque
bilanciare il costo degli allarmi inutili.

## Metriche richieste

Sulla validation si riportano sempre, con ordine delle classi dichiarato
`[0, 1]`:

- **accuracy**: proporzione di classificazioni corrette;
- **precision della classe 1**: `TP / (TP + FP)`;
- **recall della classe 1**: `TP / (TP + FN)`;
- **matrice di confusione**: righe = classe reale, colonne = classe predetta.

Matrice con ordine `[0, 1]`:

| | Predetto 0 | Predetto 1 |
| --- | ---: | ---: |
| **Reale 0** | TN | FP |
| **Reale 1** | FN | TP |

L'accuracy da sola non descrive il tipo di errore: una baseline può avere
accuracy simile e una diversa distribuzione di falsi positivi e falsi
negativi. Per questo il report deve includere precision, recall e matrice di
confusione. La validation assegnata contiene 116 esempi di classe 0 e 84 di
classe 1; non è un test indipendente e non va usata per il fit.

## Gate comune congelato

Le soglie sono fissate **prima** di osservare i risultati del modello. Non
vanno modificate dopo la misura. Il file di riferimento è
`config/gate.json` (`policy_id: lab13-gate-v1`, congelato il 2026-11-09).

| Requisito | Regola | Misura richiesta |
| --- | --- | --- |
| Accuratezza | `accuracy(v2) >= accuracy(v1)` | Stessi `record_id` di validation, stessa definizione di metrica |
| Latenza | `p95 <= 120 ms` | Probe locale ripetibile, stesso artefatto caricato |
| Error rate | `error_rate <= 0.01` | Risposte HTTP con stato ≥ 400 / richieste valide |

Precisazioni:

- l'accuracy della candidata non può essere confrontata con una misura della
  baseline calcolata su righe diverse;
- il p95 è espresso in millisecondi ed è una misura locale, non una garanzia
  di latenza in produzione;
- l'error rate del gate riguarda le richieste valide; il drill con una richiesta
  incompleta è una prova separata e non sostituisce questa misura;
- se una misura manca, riguarda un artefatto diverso o non è comparabile, il
  gate è bloccato;
- il superamento dell'accuracy non annulla la violazione di un requisito
  operativo;
- il gate registra una decisione e non attiva automaticamente una versione.

## Stato in S1

In questa fase non esistono ancora modello addestrato, metriche di validation,
servizio HTTP o probe di latenza. Non vengono quindi dichiarati risultati o
superamenti del gate. Le metriche saranno misurate e riportate nelle fasi
successive, senza cambiare le soglie qui fissate.
