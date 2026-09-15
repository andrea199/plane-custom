# Promemoria email ONIRO

Servizio Python sul server Plane, senza LLM, servizi AI o consumo di crediti per le esecuzioni. Legge le API ufficiali e invia email tramite la configurazione SMTP già presente in Plane. Non aggiorna progetti, task, date, assegnatari o commenti.

## Destinatari e orario

- Luca Cervone: `luca.cervone@oniro.tech`
- Riccardo Emanuele Sicignano: `riccardo.sicignano@oniro.tech`
- Antonio Manzi: `antonio.manzi@oniro.tech`
- Andrea Detry: `andrea.detry@oniro.tech`, con quadro aggiuntivo del team.

Mittente verificato: `info@oniro.tech`. Esecuzione dal lunedì al venerdì alle **08:30 Europe/Rome**, seguendo automaticamente ora legale e solare. Il lavoro di lettura richiede alcuni minuti: limita le richieste per rispettare la quota API di Plane. Sabato e domenica esclusi; festività e assenze non sono ancora un calendario separato.

Il cron verifica la finestra ogni cinque minuti. In caso di errore di lettura riprova fino alle 09:30. Non recupera automaticamente giorni precedenti o un’intera mattina in cui il server era spento. Il server deve restare acceso; il PC di Andrea e Codex possono essere chiusi.

## Regole visibili nei messaggi

1. Legge tutte le pagine dei progetti e delle task accessibili alla chiave; esclude progetti nascosti/archiviati e task chiuse, annullate, archiviate, eliminate o bozze.
2. Ogni destinatario riceve solo le proprie task dei progetti in cui è membro. Nessun dato viene inviato al quinto membro del workspace, che non fa parte dei destinatari richiesti.
3. Propone fino a tre priorità: scadenze superate di recente, scadenze di oggi, attività in corso, date di inizio raggiunte; usa priorità, data e identificativo per ordinare. Una priorità alta/urgente senza data può comparire come proposta. Una data di inizio futura esclude la proposta per oggi.
4. Scadenze superate da **oltre 30 giorni** rimangono in una sezione da riconfermare, non occupano le priorità suggerite. Non vengono corrette automaticamente.
5. Le task con dipendenze `blocked_by` ancora aperte o con stato esplicitamente bloccato sono mostrate nei blocchi. Dipendenze non leggibili rimangono da verificare. Le dipendenze chiuse/annullate non bloccano. Il testo libero dei commenti non viene interpretato.
6. Mostra scadenze dei prossimi sette giorni, conteggi e link alle task. Il messaggio di Andrea include i quattro riepiloghi e il numero di attività senza assegnatario.

Le proposte non sono impegni giornalieri assegnati né una stima della capacità oraria. Per renderle utili è necessario tenere aggiornati stati, priorità e date dentro Plane.

## Percorsi e gestione

Host: `/home/plane/oniro-digest/`

- `source/`: codice di questa cartella.
- `config.json`: URL, destinatari, chiave API già esistente; modalità 0600. Mai includerlo in Git o nei log.
- `previews/YYYY-MM-DD/`: copie locali dei messaggi testuali e HTML, modalità privata.
- `delivery.sqlite3`: registro invii per data e destinatario.
- `digest.log`: esito delle esecuzioni pianificate, senza credenziali.
- `crontab.before.txt`: crontab precedente.

Comandi sul server:

```bash
cd /home/plane/oniro-digest/source
python3 runner.py preview       # solo letture, nessuna email
python3 runner.py smtp-check    # connessione/autenticazione, nessuna email
python3 runner.py test-manager  # un’anteprima ad Andrea al massimo una volta al giorno
python3 runner.py status        # registro degli invii di oggi
python3 runner.py scheduled     # rispetta finestra e giorni
```

`send-once` invia i quattro messaggi fuori orario solo se richiesto esplicitamente, usando lo stesso registro giornaliero. Non usarlo come semplice test. Prima di SMTP viene registrato il tentativo: un timeout o arresto non provoca reinvii automatici. In caso di esito incerto verificare il provider prima di intervenire sul registro. Un errore dell’automazione produce al massimo un avviso giornaliero ad Andrea, se SMTP funziona; se anche SMTP è indisponibile rimane il log locale.

Per sospendere: `crontab -e`, rimuovere solo le due righe marcate `ONIRO daily digest` e il comando `runner.py scheduled`, conservando eventuali altri lavori.

## Credenziali e manutenzione

La chiave riutilizzata è **Codex ONIRO**, già appartenente ad Andrea: non sono state create chiavi o ampliati permessi. Alla configurazione iniziale scade il **14 ottobre 2026**. Nei 14 giorni precedenti il riepilogo di Andrea segnala il rinnovo necessario. La configurazione contiene una copia della chiave: dopo la rotazione aggiornare in modo riservato `api_key` e `api_expires_at` in `config.json`, quindi eseguire `preview`. Il servizio non rinnova credenziali da solo.

Le credenziali SMTP restano nel sistema di configurazione originale di Plane. L’invio riusa `get_email_configuration()` dentro il container `plane-app-api-1`; non esporta password email. Una futura variazione del nome del container o del mittente richiede l’aggiornamento verificato del servizio.

## Rimozione della vecchia agenda

Il 15 settembre 2026 sono stati ripristinati `oniro-plane-api:before-planning-20260914` e `oniro-plane-web:before-planning-20260914` per i servizi API/web/worker/beat e configurazione migrator. Le quattro tabelle `oniro_planning_*`, verificate vuote, sono state rimosse con la sola migrazione inversa del modulo. La pagina `/oniro/planning/` mostra il 404 nativo e il menu non contiene più il collegamento.

Backup aggiornato precedente alla rimozione: `/home/plane/backups/remove-planning-20260915/`, dump PostgreSQL verificato tramite `pg_restore --list`. Il database corrente non è stato ripristinato da backup. Le task e i progetti sono preservati. I quattro container dell’anteprima sono stati fermati. Le immagini storiche e i backup restano disponibili per recupero.

Dal connettore globale sono stati rimossi solo i nove strumenti dell’agenda; i 14 strumenti originali restano disponibili. Backup locale: `C:\Users\andre\Documents\Codex\Integrations\oniro\backup-remove-planning-20260915-094300`. Le nuove connessioni al connettore caricano la versione 1.1.1.

## Verifica

```bash
python3 -m unittest -v test_digest
```

I test coprono selezione, blocchi, riservatezza dei destinatari, paginazione, scadenze vecchie, HTML, idempotenza e fuso orario. La conferma SMTP significa accettazione da parte del server email, non prova della lettura né dell’arrivo in posta in entrata anziché spam.

Verifica di rilascio del 15 settembre 2026: **22 test sul server** (`test_digest test_runner`) e **17 test del connettore originale** superati. Anteprima inviata soltanto ad Andrea, accettata dal server SMTP e registrata come `sent`. Quattro destinatari aziendali verificati nel database Plane; 13 progetti attivi letti e 87 task aperte assegnate ai destinatari nella verifica. Cron attivo; prima esecuzione ordinaria prevista il 16 settembre 2026 dalle 08:30.
