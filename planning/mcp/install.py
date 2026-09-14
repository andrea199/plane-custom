"""Back up and extend an existing ONIRO MCP installation; no credentials are read."""
from pathlib import Path
from datetime import datetime
import argparse
import shutil

parser=argparse.ArgumentParser()
parser.add_argument('directory',type=Path)
args=parser.parse_args()
target=args.directory/'oniro_mcp.py'
text=target.read_text(encoding='utf-8')
if 'from oniro_planning import PLANNING_NAMES' not in text:
    anchor='        if name in EXTENDED_NAMES:'
    if text.count(anchor)!=1 or 'TOOLS.extend(build_tools())' not in text:
        raise SystemExit('Unexpected connector version; inspect before updating.')
    text=text.replace(anchor,'        if name in PLANNING_NAMES:\n            return invoke_planning(self,name,a)\n'+anchor,1)
    text=text.replace('TOOLS.extend(build_tools())','TOOLS.extend(build_tools())\nfrom oniro_planning import PLANNING_NAMES, build_planning_tools, invoke_planning\nTOOLS.extend(build_planning_tools())\nINSTRUCTIONS += " For daily work use get_planning_context and list_daily_plan. Read a fresh version before updating commitments; dates of execution are separate from deadlines."',1)
    text=text.replace('VERSION = "1.1.0"','VERSION = "1.2.0"',1)
    text=text.replace('messages={401:', 'messages={409:"The plan changed. Read its current version before retrying.",401:',1)
    compile(text,str(target),'exec')
    backup=args.directory/('backup-planning-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    backup.mkdir()
    shutil.copy2(target,backup/target.name)
    extension=args.directory/'oniro_planning.py'
    if extension.exists():shutil.copy2(extension,backup/extension.name)
    shutil.copy2(Path(__file__).with_name('oniro_planning.py'),extension)
    target.write_text(text,encoding='utf-8')
    print('Updated ONIRO MCP to 1.2.0; backup:',backup)
else:
    raise SystemExit('Planning extension already installed; inspect before replacing.')
