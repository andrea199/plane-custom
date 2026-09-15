"""Server entry point; SMTP credentials stay inside the existing Plane container."""
import argparse
import base64
import datetime as dt
import fcntl
import html
import json
import os
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo

from digest import DigestError, Ledger, Plane, collect, due_now, render

HOME = Path('/home/plane/oniro-digest')


def plane_shell(source):
    try:
        result = subprocess.run(['docker', 'exec', '-i', 'plane-app-api-1', 'python', 'manage.py', 'shell'],
                                input=source, text=True, capture_output=True, timeout=90)
    except subprocess.TimeoutExpired:
        raise DigestError('SMTP: esito incerto (timeout); nessun reinvio automatico') from None
    # Never echo stderr: underlying libraries may include connection details.
    if result.returncode or 'DIGEST_OK' not in result.stdout:
        safe = next((line for line in result.stdout.splitlines() if line.startswith('DIGEST_ERROR:')), 'DIGEST_ERROR: operazione email non riuscita')
        raise DigestError(safe)


def mail_source(message=None):
    encoded = base64.b64encode(json.dumps(message).encode()).decode()
    return '''
import base64, json
from django.core.mail import EmailMultiAlternatives, get_connection
from plane.license.utils.instance_value import get_email_configuration
from plane.db.models import WorkspaceMember
try:
    host, username, password, port, tls, ssl, sender = get_email_configuration()
    assert host and sender == 'info@oniro.tech', 'Configurazione mittente inattesa'
    connection = get_connection(host=host, port=int(port), username=username, password=password,
        use_tls=tls == '1', use_ssl=ssl == '1', timeout=30)
    connection.open()
    message = json.loads(base64.b64decode(''' + repr(encoded) + '''))
    if message:
        assert message['to'] in ('luca.cervone@oniro.tech', 'riccardo.sicignano@oniro.tech', 'antonio.manzi@oniro.tech', 'andrea.detry@oniro.tech')
        assert WorkspaceMember.objects.filter(workspace__slug='oniro', member__email=message['to'], member__is_active=True).exists()
        mail = EmailMultiAlternatives(subject=message['subject'], body=message['text'], from_email=sender,
            to=[message['to']], connection=connection, headers={'Message-ID': message['message_id']})
        mail.attach_alternative(message['html'], 'text/html')
        assert mail.send() == 1, 'Invio non confermato'
    connection.close()
    print('DIGEST_OK')
except Exception as exc:
    print('DIGEST_ERROR:' + type(exc).__name__)
'''


def notify_failure(detail):
    """One service notice per day to the manager; never sends a partial task digest."""
    config = json.loads((HOME / 'config.json').read_text())
    manager = next(r for r in config['recipients'] if r['id'] == config['manager_id'])
    today = dt.datetime.now(ZoneInfo('Europe/Rome')).date().isoformat()
    ledger = Ledger(HOME / 'delivery.sqlite3')
    key = 'service-alert-' + today
    if not ledger.reserve(key, manager['email']):
        return
    text = ('Il riepilogo automatico ONIRO richiede un controllo.\n\n' + detail +
            '\n\nI riepiloghi basati su letture incomplete non vengono inviati. '
            'Le letture vengono ritentate fino alle 09:30; gli invii di esito incerto non vengono ripetuti automaticamente. '
            'Le attività rimangono consultabili in Plane.')
    message = {'to': manager['email'], 'subject': 'ONIRO — Verifica del promemoria automatico', 'text': text,
               'html': '<div style="white-space:pre-wrap">' + html.escape(text) + '</div>',
               'message_id': f'<oniro-digest.service-alert.{today}@oniro.tech>'}
    try:
        plane_shell(mail_source(message))
        ledger.finish(key, manager['email'], 'sent')
    except Exception:
        ledger.finish(key, manager['email'], 'uncertain')
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['preview', 'smtp-check', 'send-once', 'scheduled', 'test-manager', 'status'])
    args = parser.parse_args()
    os.umask(0o077)
    now = dt.datetime.now(ZoneInfo('Europe/Rome'))
    if args.mode == 'scheduled' and not due_now(now):
        return
    config = json.loads((HOME / 'config.json').read_text())
    if args.mode == 'smtp-check':
        plane_shell(mail_source())
        print('Connessione SMTP e autenticazione verificate; nessuna email inviata.')
        return
    lock = (HOME / 'run.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return
    ledger = Ledger(HOME / 'delivery.sqlite3')
    date_key = now.date().isoformat()
    if args.mode == 'test-manager':
        date_key = 'test-' + date_key
    if args.mode == 'status':
        print(json.dumps({'date': date_key, 'delivery': ledger.statuses(date_key),
                         'api_expires_at': config.get('api_expires_at')}, ensure_ascii=False))
        return
    target_emails = [r['email'] for r in config['recipients'] if args.mode != 'test-manager' or r['id'] == config['manager_id']]
    statuses = ledger.statuses(date_key)
    if args.mode != 'preview' and all(address in statuses for address in target_emails):
        if any(statuses[address] != 'sent' for address in target_emails):
            raise DigestError('Invio precedente incerto o fallito: controllo manuale necessario; duplicati evitati')
        return
    tasks, access, stats = collect(Plane(config), config)
    # Never send yesterday's result if an unusually long collection crosses midnight.
    if dt.datetime.now(ZoneInfo('Europe/Rome')).date() != now.date():
        raise DigestError('Data cambiata durante la lettura; riepilogo non inviato')
    messages = render(config, tasks, access, stats, now.date())
    preview_dir = HOME / 'previews' / now.date().isoformat()
    preview_dir.mkdir(parents=True, exist_ok=True)
    for message in messages:
        stem = message['to'].split('@')[0]
        (preview_dir / (stem + '.txt')).write_text(message['text'], encoding='utf-8')
        (preview_dir / (stem + '.html')).write_text(message['html'], encoding='utf-8')
    if args.mode == 'preview':
        print(json.dumps({'preview_directory': str(preview_dir), 'recipients': target_emails, 'tasks': len(tasks), **stats}, ensure_ascii=False))
        return
    failures = []
    for message in messages:
        if message['to'] not in target_emails or not ledger.reserve(date_key, message['to']):
            continue
        if args.mode == 'test-manager':
            message['subject'] = 'ANTEPRIMA — ' + message['subject']
        message['message_id'] = f"<oniro-digest.{date_key}.{message['to'].split('@')[0]}@oniro.tech>"
        try:
            plane_shell(mail_source(message))
            ledger.finish(date_key, message['to'], 'sent')
            print(f"{now.isoformat()} SMTP_ACCEPTED {message['to']}", flush=True)
        except DigestError as exc:
            ledger.finish(date_key, message['to'], 'uncertain')
            failures.append(message['to'])
            print(f"{now.isoformat()} DELIVERY_REQUIRES_REVIEW {message['to']}: {exc}", flush=True)
    if failures:
        raise DigestError('Uno o più invii richiedono verifica manuale')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Do not leak the API key, SMTP configuration or response bodies into cron logs.
        detail = str(exc) if isinstance(exc, DigestError) else type(exc).__name__
        print(dt.datetime.now(dt.timezone.utc).isoformat() + ' DIGEST_FAILED: ' + detail, file=sys.stderr)
        if len(sys.argv) > 1 and sys.argv[1] == 'scheduled':
            try:
                notify_failure(detail)
            except Exception:
                print('SERVICE_ALERT_FAILED: verificare il log locale', file=sys.stderr)
        sys.exit(1)
