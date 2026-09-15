"""Install a marked server cron entry, preserving any unrelated jobs."""
import os
from pathlib import Path
import subprocess

root = Path('/home/plane/oniro-digest')
os.umask(0o077)
result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
assert result.returncode == 0 or (result.returncode == 1 and 'no crontab' in result.stderr)
old = result.stdout if result.returncode == 0 else ''
marker = '# ONIRO daily digest (Europe/Rome, weekdays 08:30)'
assert marker not in old and '/home/plane/oniro-digest/source/runner.py' not in old, 'Already installed; do not duplicate'
(root / 'crontab.before.txt').write_text(old)
entry = '*/5 * * * * /usr/bin/python3 /home/plane/oniro-digest/source/runner.py scheduled >> /home/plane/oniro-digest/digest.log 2>&1'
new = old.rstrip() + ('\n' if old.strip() else '') + marker + '\n' + entry + '\n'
subprocess.run(['crontab', '-'], input=new, text=True, check=True)
print('Activated: weekdays 08:30 Europe/Rome; retry collection until 09:30; per-recipient duplicate protection.')
