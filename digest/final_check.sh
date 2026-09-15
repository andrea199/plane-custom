set -euo pipefail
cd /home/plane/oniro-digest/source
python3 -m unittest -v test_digest test_runner
python3 runner.py scheduled
python3 runner.py status
python3 - <<'PY'
import sqlite3
from pathlib import Path
from zoneinfo import ZoneInfo
import datetime as dt
root = Path('/home/plane/oniro-digest')
now = dt.datetime.now(ZoneInfo('Europe/Rome'))
with sqlite3.connect(root / 'delivery.sqlite3') as db:
    print('Preview delivery:', list(db.execute('SELECT day,recipient,status FROM delivery WHERE day=?', ('test-' + now.date().isoformat(),))))
print('Config mode:', oct((root / 'config.json').stat().st_mode & 0o777))
for address in ['luca.cervone', 'riccardo.sicignano', 'antonio.manzi', 'andrea.detry']:
    text = (root / 'previews' / now.date().isoformat() / (address + '.txt')).read_text()
    start = text.index('DA CUI INIZIARE')
    end = text.index('SCADUTE O IN SCADENZA OGGI')
    print(address + ':\n' + text[start:end])
PY
systemctl is-active cron
crontab -l
docker ps --format '{{.Names}} {{.Image}}' | grep -E 'plane-app-(api|web|worker|beat)|planning-'
