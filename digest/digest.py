"""Read-only Plane daily digest. Standard library only; no model or paid API."""
import datetime as dt
import html
import json
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request

PRIORITY = {"urgent": 0, "high": 1, "medium": 2, "low": 3, "none": 4}
PRIORITY_IT = {"urgent": "Urgente", "high": "Alta", "medium": "Media", "low": "Bassa", "none": "Non definita"}
GROUPS = {"backlog", "unstarted", "started", "completed", "cancelled"}


class DigestError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise DigestError("Redirect API rifiutato; nessuna credenziale inoltrata")


class Plane:
    def __init__(self, config):
        base = urllib.parse.urlsplit(config["base_url"])
        if base.scheme != "https" or not base.netloc or base.username or base.password or base.query or base.fragment or base.path not in ("", "/"):
            raise DigestError("URL Plane non valido")
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", config["workspace"]):
            raise DigestError("Workspace non valido")
        self.root = config["base_url"].rstrip("/") + "/api/v1/workspaces/" + config["workspace"] + "/"
        self.key = config["api_key"]
        self.opener = urllib.request.build_opener(NoRedirect)
        self.last_request = 0.0

    def get(self, path, params=None):
        if path.startswith("/") or ".." in path or ":" in path:
            raise DigestError("Percorso API non valido")
        url = self.root + path
        if params:
            url += "?" + urllib.parse.urlencode({key: value for key, value in params.items() if value is not None and value != ""})
        request = urllib.request.Request(url, headers={"x-api-key": self.key, "Accept": "application/json"}, method="GET")
        for attempt in range(3):
            time.sleep(max(0, 1.15 - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            try:
                with self.opener.open(request, timeout=30) as response:
                    return json.load(response)
            except urllib.error.HTTPError as exc:
                if exc.code in (429, 502, 503, 504) and attempt < 2:
                    time.sleep(30 if exc.code == 429 else 5)
                    continue
                raise DigestError(f"Lettura Plane fallita (HTTP {exc.code}, {path}); nessun riepilogo parziale inviato") from None
            except (urllib.error.URLError, TimeoutError, OSError, ValueError):
                raise DigestError("Lettura Plane fallita; nessun riepilogo parziale inviato") from None

    def all(self, path, params=None):
        rows, cursor, seen = [], "", set()
        for _ in range(500):
            page = self.get(path, {**(params or {}), "per_page": 100, "cursor": cursor})
            if isinstance(page, list):
                return rows + page
            if not isinstance(page, dict) or not isinstance(page.get("results"), list):
                raise DigestError("Formato API inatteso")
            rows.extend(page["results"])
            if page.get("next_page_results") is False:
                return rows
            if page.get("next_page_results") is not True:
                raise DigestError("Paginazione ambigua")
            cursor = page.get("next_cursor")
            if not cursor or cursor in seen:
                raise DigestError("Paginazione incompleta")
            seen.add(cursor)
        raise DigestError("Limite paginazione raggiunto")


def day(value):
    try:
        return dt.date.fromisoformat(value[:10]) if value else None
    except (ValueError, TypeError):
        raise DigestError("Data task non valida") from None


def clean(value):
    return " ".join(str(value or "").split())


def normalize(row, project, config):
    state = row.get("state")
    if not isinstance(state, dict) or state.get("group") not in GROUPS:
        raise DigestError("Stato task non riconosciuto")
    identifier = f"{project['identifier']}-{row['sequence_id']}"
    assignees = [a["id"] if isinstance(a, dict) else a for a in row.get("assignees", [])]
    return {"id": row["id"], "identifier": identifier, "project_id": project["id"],
            "project": clean(project["name"]), "name": clean(row.get("name")),
            "group": state["group"], "state": clean(state.get("name")),
            "priority": row.get("priority") or "none", "assignees": assignees,
            "start": day(row.get("start_date")), "due": day(row.get("target_date")),
            "active": state["group"] not in ("completed", "cancelled") and not row.get("archived_at") and not row.get("is_draft") and not row.get("deleted_at"),
            "url": config["base_url"].rstrip("/") + "/" + config["workspace"] + "/browse/" + urllib.parse.quote(identifier, safe="") + "/",
            "blockers": []}


def validate_recipients(config, member_ids):
    ids, emails = set(), set()
    for recipient in config["recipients"]:
        address = recipient["email"]
        if not re.fullmatch(r"[a-z0-9]+(?:\.[a-z0-9]+)+@oniro\.tech", address):
            raise DigestError("Indirizzo destinatario non approvato")
        if recipient["id"] not in member_ids or recipient["id"] in ids or address in emails:
            raise DigestError("Destinatario mancante o duplicato nel workspace")
        ids.add(recipient["id"])
        emails.add(address)
    if config["manager_id"] not in ids:
        raise DigestError("Responsabile non presente tra i destinatari")


def collect(api, config):
    members = api.all("members/")
    validate_recipients(config, {m["id"] for m in members})
    projects = api.all("projects/")
    tasks, access, skipped = {}, {}, []
    for project in projects:
        if project.get("archived_at") or project.get("is_hidden"):
            skipped.append(project["id"])
            continue
        prefix = f"projects/{project['id']}/"
        access[project["id"]] = {m["id"] for m in api.all(prefix + "members/")}
        for row in api.all(prefix + "work-items/", {"expand": "state"}):
            task = normalize(row, project, config)
            tasks[task["id"]] = task
    recipient_ids = {r["id"] for r in config["recipients"]}
    relevant = [t for t in tasks.values() if t["active"] and recipient_ids.intersection(t["assignees"])]
    for task in relevant:
        relations = api.get(f"projects/{task['project_id']}/work-items/{task['id']}/relations/")
        if not isinstance(relations, dict) or not isinstance(relations.get("blocked_by"), list):
            raise DigestError("Dipendenze non verificabili")
        for relation in relations["blocked_by"]:
            other = tasks.get(relation["issue_id"])
            if other is None or other["group"] not in ("completed", "cancelled"):
                # Do not expose another project's title through a dependency.
                task["blockers"].append("Dipendenza aperta" if other else "Dipendenza da verificare (fuori dai progetti letti)")
        if re.search(r"\b(blocked|bloccato|bloccata|bloccati|bloccate)\b", task["state"], re.I):
            task["blockers"].append("Stato: " + task["state"])
    return relevant, access, {"projects": len(access), "skipped_projects": len(skipped),
                              "unassigned": sum(t["active"] and not t["assignees"] for t in tasks.values())}


def rank(task, today):
    due = task["due"]
    bucket = 0 if due and due < today else 1 if due == today else 2 if task["group"] == "started" else 3 if task["start"] and task["start"] <= today else 4
    return bucket, PRIORITY.get(task["priority"], 4), due or dt.date.max, task["identifier"]


def summarize(tasks, recipient_id, access, today):
    assigned = [t for t in tasks if recipient_id in t["assignees"] and recipient_id in access.get(t["project_id"], set())]
    assigned.sort(key=lambda t: rank(t, today))
    blocked = [t for t in assigned if t["blockers"]]
    stale = [t for t in assigned if t["due"] and t["due"] < today - dt.timedelta(days=30)]
    eligible = [t for t in assigned if not t["blockers"] and t not in stale and (not t["start"] or t["start"] <= today)]
    eligible = [t for t in eligible if t["group"] == "started" or (t["start"] and t["start"] <= today) or (t["due"] and t["due"] <= today) or t["priority"] in ("urgent", "high")]
    return {"focus": eligible[:3], "deadlines": [t for t in assigned if t["due"] and today - dt.timedelta(days=30) <= t["due"] <= today], "stale": stale,
            "blocked": blocked, "active": len(assigned), "missing_dates": sum(not t["start"] for t in assigned),
            "upcoming": [t for t in assigned if t["due"] and today < t["due"] <= today + dt.timedelta(days=7)]}


def task_line(task, today):
    reasons = [PRIORITY_IT.get(task["priority"], "Non definita"), task["state"]]
    if task["due"]:
        reasons.append(("Scaduta il " if task["due"] < today else "Scadenza ") + task["due"].strftime("%d/%m/%Y"))
    if task["start"]:
        reasons.append("Inizio " + task["start"].strftime("%d/%m/%Y"))
    if task["blockers"]:
        reasons.extend(task["blockers"])
    return f"{task['identifier']} — {task['name']}\n{task['project']} · " + " · ".join(reasons) + "\n" + task["url"]


def section(title, items, today, limit=8):
    lines = [title]
    if not items:
        lines.append("Nessuna attività in questa sezione.")
    else:
        lines.extend(f"{i}. {task_line(task, today)}" for i, task in enumerate(items[:limit], 1))
        if len(items) > limit:
            lines.append(f"Altre {len(items) - limit} attività: consulta Plane.")
    return "\n\n".join(lines)


def render(config, tasks, access, stats, today):
    summaries = {r["id"]: summarize(tasks, r["id"], access, today) for r in config["recipients"]}
    messages = []
    for recipient in config["recipients"]:
        summary = summaries[recipient["id"]]
        parts = [f"ONIRO · {today.strftime('%d/%m/%Y')}\nBuongiorno {recipient['name']},",
                 "Ecco il riepilogo delle tue attività in Plane. Le priorità suggerite sono una proposta basata su stati, priorità e date: non sono nuovi impegni assegnati.",
                 section("DA CUI INIZIARE — FINO A 3 PRIORITÀ SUGGERITE", summary["focus"], today),
                 section("SCADUTE O IN SCADENZA OGGI", summary["deadlines"], today),
                 section("BLOCCHI DA RISOLVERE", summary["blocked"], today),
                 section("SCADENZE NEI PROSSIMI 7 GIORNI", summary["upcoming"], today, 5),
                 section("SCADENZE VECCHIE DA RICONFERMARE (OLTRE 30 GIORNI)", summary["stale"], today, 5),
                 f"Attività aperte assegnate: {summary['active']}. Senza data di inizio: {summary['missing_dates']}."]
        if recipient["id"] == config["manager_id"]:
            parts.append("QUADRO DEL TEAM")
            for person in config["recipients"]:
                s = summaries[person["id"]]
                parts.append(f"{person['name']}: {s['active']} aperte · {len(s['deadlines'])} scadute recenti/in scadenza oggi · {len(s['stale'])} scadenze vecchie da riconfermare · {len(s['blocked'])} bloccate\n" +
                             ("\n".join(task_line(t, today) for t in s["focus"]) or "Nessuna priorità giornaliera ricavabile dai dati disponibili."))
            parts.append(f"Copertura: {stats['projects']} progetti attivi accessibili al collegamento API; {stats['skipped_projects']} archiviati/nascosti esclusi. {stats['unassigned']} attività aperte senza assegnatario.")
            expiry = day(config.get("api_expires_at"))
            if expiry and (expiry - today).days <= 14:
                parts.append(f"MANUTENZIONE: la chiave API scade il {expiry.strftime('%d/%m/%Y')}. Rinnovare il collegamento prima di questa data.")
        parts.extend(["Apri Plane per aggiornare stati, date e commenti. Le scadenze superate da oltre 30 giorni restano visibili tra le attività da riconfermare e non diventano automaticamente obiettivi per oggi. I blocchi derivano dalle dipendenze 'blocked by' e dagli stati esplicitamente bloccati; il testo libero dei commenti non viene interpretato.",
                      config["base_url"].rstrip("/") + "/" + config["workspace"] + "/workspace-views/all-issues/"])
        text = "\n\n".join(parts)
        escaped = html.escape(text)
        allowed_link_prefix = html.escape(config["base_url"].rstrip("/") + "/")
        escaped = re.sub(r"https://[^\s<]+", lambda match: ('<a href="' + match[0] + '">Apri in Plane</a>') if match[0].startswith(allowed_link_prefix) else match[0], escaped)
        markup = '<!doctype html><html lang="it"><meta charset="utf-8"><body style="font:15px/1.6 Arial,sans-serif;color:#253247;max-width:760px;margin:24px auto;padding:16px"><div style="white-space:pre-wrap">' + escaped + '</div></body></html>'
        messages.append({"to": recipient["email"], "subject": f"ONIRO — Priorità e attività del {today.strftime('%d/%m/%Y')}", "text": text, "html": markup})
    return messages


class Ledger:
    """Reserve before SMTP: never automatically repeat an ambiguous delivery."""
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS delivery (day TEXT, recipient TEXT, status TEXT, updated TEXT, PRIMARY KEY(day,recipient))")
        self.db.commit()

    def reserve(self, day_key, address):
        cursor = self.db.execute("INSERT OR IGNORE INTO delivery VALUES (?,?,?,?)", (day_key, address, "sending", dt.datetime.now(dt.timezone.utc).isoformat()))
        self.db.commit()
        return cursor.rowcount == 1

    def finish(self, day_key, address, status):
        self.db.execute("UPDATE delivery SET status=?,updated=? WHERE day=? AND recipient=?", (status, dt.datetime.now(dt.timezone.utc).isoformat(), day_key, address))
        self.db.commit()

    def statuses(self, day_key):
        return dict(self.db.execute("SELECT recipient,status FROM delivery WHERE day=?", (day_key,)))


def due_now(now):
    # Caller supplies Europe/Rome. Every 5 minutes cron retries collection until 09:30.
    return now.weekday() < 5 and dt.time(8, 30) <= now.time().replace(tzinfo=None) < dt.time(9, 30)
