"""Host-side setup. Reuses an existing API key without displaying its value."""
import json
import os
from pathlib import Path
import subprocess

root = Path('/home/plane/oniro-digest')
os.umask(0o077)
root.mkdir(exist_ok=True)
assert not (root / 'config.json').exists(), 'Configuration already exists; do not overwrite'
source = '''
import json
from django.utils import timezone
from plane.db.models import APIToken, WorkspaceMember
token = APIToken.objects.get(id='9d1a05be-9a5b-464e-a190-dab20b0b9618', user_id='0d84b5c4-4dc1-4ab9-a981-ed5891f1d967', is_active=True)
assert token.expired_at is None or token.expired_at > timezone.now()
addresses = ['luca.cervone@oniro.tech','riccardo.sicignano@oniro.tech','antonio.manzi@oniro.tech','andrea.detry@oniro.tech']
recipients = []
for address in addresses:
    member = WorkspaceMember.objects.select_related('member').get(workspace__slug='oniro', member__email=address, member__is_active=True)
    recipients.append({'id': str(member.member_id), 'name': (member.member.first_name + ' ' + member.member.last_name).strip(), 'email': address})
print('CONFIG_JSON:' + json.dumps({'base_url':'https://plane-aziendaa.tail490d68.ts.net', 'workspace':'oniro',
    'api_key':token.token, 'api_expires_at':str(token.expired_at) if token.expired_at else None,
    'manager_id':'0d84b5c4-4dc1-4ab9-a981-ed5891f1d967', 'recipients':recipients}))
'''
result = subprocess.run(['docker', 'exec', '-i', 'plane-app-api-1', 'python', 'manage.py', 'shell'], input=source, text=True, capture_output=True, timeout=60)
assert result.returncode == 0, 'Unable to resolve existing connector and recipients'
lines = [line for line in result.stdout.splitlines() if line.startswith('CONFIG_JSON:')]
assert len(lines) == 1, 'Unexpected configuration response'
config = json.loads(lines[0].removeprefix('CONFIG_JSON:'))
with (root / 'config.json').open('x', encoding='utf-8') as target:
    json.dump(config, target)
print('Private configuration written; existing token reused, no new access granted.')
