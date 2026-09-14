# Pianificazione ONIRO — v1

Agenda giornaliera e settimanale collegata alle task di Plane. Il lavoro si programma per persona, giorno, minuti, ordine e risultato atteso. I commenti sono quelli della task originale. Nessuna chiamata AI è necessaria per usare la schermata.

## Uso

Aprire `/<workspace>/planning/` oppure **Pianificazione** nel menu laterale. Un amministratore sceglie **Progetti nell’agenda**; i progetti partono esclusi per evitare che le bozze entrino nel piano. Quindi **Pianifica attività**, selezionando una task, una persona del progetto, giorno, durata e risultato atteso.

**Team**, **La mia giornata** e **Settimana** mostrano gli stessi impegni. **Disponibilità** è esplicita: nessun valore significa sconosciuta, zero significa indisponibile. Il superamento delle ore disponibili è evidenziato. **Ripianifica** conserva l’impegno precedente nello storico. **Fatto oggi** conclude l’impegno giornaliero; non chiude la task. La scadenza della task rimane separata dalla data del lavoro.

Un membro può modificare la propria giornata; un amministratore quella del team. L’accesso rimane limitato ai progetti di cui l’utente è membro attivo. I conflitti di versione impediscono a due chat o persone di sovrascrivere silenziosamente lo stesso impegno. Dopo un errore di connessione verificare sempre il risultato prima di ripetere una scrittura, soprattutto un commento.

## Compatibilità e installazione

Questo repository contiene patch più vecchie della versione attiva sul server. Il modulo utilizza come base le immagini ONIRO v1.37 già verificate, senza ricompilare Plane da un upstream più recente. Non usare `build.bat` per installare questo modulo sulla versione attuale.

Le immagini `oniro-plane-api:planning-v1` e `oniro-plane-web:planning-v1` aggiungono un’app Django e risorse statiche. La migrazione `oniro_planning.0001_initial` dipende da `db.0131_v137e_canonical_workflow_b` e crea solo quattro tabelle e i relativi vincoli. Non generare nuove migrazioni per l’app `db`: il runtime presenta differenze preesistenti fra modelli e migrazioni, estranee a questo intervento.

`Dockerfile.api` aggiunge le route `/api/workspaces/<slug>/planning/` e `/api/v1/workspaces/<slug>/planning/`. Le sessioni verificano il token CSRF; le API accettano le chiavi Plane esistenti e applicano il limite di richieste.

`Dockerfile.web` conserva le risorse compilate esistenti e aggiunge un collegamento al menu tramite `navigation.js`. Questo collegamento dipende dalla struttura del menu (`#main-sidebar`, voce persone): dopo un futuro aggiornamento di Plane verificarlo. Il collegamento diretto alla schermata rimane indipendente dal menu. La schermata usa la sessione Plane e non contiene chiavi API.

Prima dell’aggiornamento: backup privato sul server, conservazione delle immagini correnti, controllo del piano di migrazione, test isolati e prova nel browser. Aggiornare anche l’immagine del servizio `migrator` per gli avvii futuri. Non avviare il database dimostrativo con credenziali o volumi di produzione.

## Ambiente dimostrativo

`stage-test.sh` crea una rete e un database dedicati. `stage-preview.sh` crea un’istanza con quattro persone e attività fittizie; `refresh-preview.sh` aggiorna solo i container dimostrativi. La porta dell’anteprima è vincolata a `127.0.0.1` sul server. Dal PC:

```text
tailscale ssh plane@plane-aziendaa -N -o ExitOnForwardFailure=yes -L 127.0.0.1:18080:127.0.0.1:18080
```

Aprire `http://localhost:18080/preview/start/`. La sessione dimostrativa ha un cookie distinto e il banner **Dati di esempio**. L’ingresso automatico è presente soltanto nella configurazione isolata `plane.settings.planning_preview`, che rifiuta altri host database. Non usare questa configurazione in produzione.

## MCP e più chat

`mcp/oniro_planning.py` aggiunge nove strumenti al connettore ONIRO già installato. L’installer `mcp/install.py <directory>` salva prima una copia del connettore e non legge le credenziali. I nuovi processi MCP vedranno gli strumenti dopo il riavvio/ricaricamento del connettore.

Per programmare il lavoro usare `get_planning_context`, `list_daily_plan` e `list_planning_work_items`. Le risposte sono filtrate e paginate sul server. Per modificare leggere prima la versione corrente. Per creare inviare un UUID nuovo; una verifica dopo un errore può riutilizzare lo stesso UUID con gli stessi dati. Le date giornaliere non cambiano le scadenze. I commenti continuano a usare lo strumento esistente `add_work_item_comment`.

## Verifiche

Test Django nel database isolato: permessi, sessione/CSRF, chiave API, duplicati, versione, ripianificazione con rollback atomico, disponibilità nulla/zero, esclusione progetti/task e commenti sulla task originale. Test MCP senza rete: validazione, paginazione, trasmissione della versione, nessun tentativo automatico e rimozione del token CSRF dalle risposte.

## Ripristino

Ripristinare il file Compose salvato e riavviare solo API, worker, beat-worker e web con le immagini precedenti. Le quattro tabelle aggiunte possono rimanere inutilizzate: non occorre cancellarle né ripristinare il database per tornare alla vecchia interfaccia. Conservare il dump per emergenze; un ripristino del database può perdere le modifiche avvenute dopo il backup e richiede una decisione esplicita.
