"""Read-only smoke test of the installed stdio MCP; never prints credentials."""
import json
import os
from pathlib import Path
import subprocess
import tomllib
from datetime import date

config_path=Path.home()/'.codex/config.toml'
config=tomllib.loads(config_path.read_text(encoding='utf-8'))['mcp_servers']['oniro']
environment=os.environ.copy()
environment.update(config.get('env',{}))
messages=[
    {'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'planning-verification','version':'1'}}},
    {'jsonrpc':'2.0','id':2,'method':'tools/list'},
    {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'get_planning_context','arguments':{}}},
    {'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'list_daily_plan','arguments':{'from':date.today().isoformat(),'to':date.today().isoformat(),'limit':10}}},
]
result=subprocess.run([config['command'],*config['args']],input=''.join(json.dumps(x)+'\n' for x in messages),text=True,encoding='utf-8',capture_output=True,env=environment,timeout=60,check=True)
responses={r['id']:r for r in map(json.loads,result.stdout.splitlines())}
for response in responses.values():
    if 'error' in response or response.get('result',{}).get('isError'):
        raise SystemExit('MCP verification failed: '+json.dumps(response))
context=json.loads(responses[3]['result']['content'][0]['text'])
plan=json.loads(responses[4]['result']['content'][0]['text'])
print(json.dumps({'version':responses[1]['result']['serverInfo']['version'],'tools':len(responses[2]['result']['tools']),'members':len(context['members']),'projects':len(context['projects']),'commitments_today':plan['total'],'read_only_verification':'passed'}))
