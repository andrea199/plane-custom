# Installazione ONIRO — 14 settembre 2026

Modulo installato su `https://plane-aziendaa.tail490d68.ts.net/oniro/planning/` e collegato al menu laterale. Il backend e l’interfaccia usano le immagini `oniro-plane-api:planning-v1` e `oniro-plane-web:planning-v1`. La configurazione Compose corrente aggiorna anche worker, beat-worker e migrator. Il database ha ricevuto solo `oniro_planning.0001_initial`.

Backup verificato prima della migrazione: `/home/plane/backups/planning-20260914-before-install-v2/`. Il dump PostgreSQL è di 1.538.916 byte; l’indice del dump è stato verificato con `pg_restore --list`. Immagini precedenti conservate come `oniro-plane-api:before-planning-20260914` e `oniro-plane-web:before-planning-20260914`. Il precedente tentativo senza suffisso `v2` non contiene un dump valido e non va usato.

Verifiche concluse:

- 19 test Django sul database isolato, incluse API key e sessione con CSRF, conflitti, permessi, ripianificazione e commenti originali.
- 8 test del modulo MCP e 17 test preesistenti del connettore eseguiti sulla copia aggiornata.
- Compilazione Python, controllo sintassi JavaScript, configurazione Nginx valida.
- Nel browser dimostrativo: modifica dei minuti persistente dopo ricaricamento e invio/lettura di commenti sulla task fittizia.
- Nel browser reale: accesso con la sessione esistente, membri reali e collegamento nel menu verificato dopo ricaricamento.
- Connettore globale aggiornato a 1.2.0 con backup; 23 strumenti disponibili. Letture reali tramite stdio MCP riuscite: 5 membri, 13 progetti accessibili, nessun impegno ancora inserito.

Nessun progetto è stato abilitato automaticamente e nessuna task reale è stata pianificata, riassegnata o commentata per fare prove. Il primo utilizzo richiede di scegliere i progetti nell’agenda e inserire gli impegni. L’accesso automatico e i dati dimostrativi esistono esclusivamente nel database isolato dell’anteprima.

Il dominio principale aveva già un Tailscale Funnel configurato prima di questo intervento; la sua configurazione è rimasta invariata. Non è stato creato alcun nuovo endpoint Tailscale Serve. L’anteprima usa un tunnel SSH verso il servizio vincolato a localhost.
