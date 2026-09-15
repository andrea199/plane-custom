"""Remove only the planning extension installed in the existing ONIRO connector."""
from datetime import datetime
from pathlib import Path
import shutil

root = Path(r'C:\Users\andre\Documents\Codex\Integrations\oniro').resolve()
target = root / 'oniro_mcp.py'
text = target.read_text(encoding='utf-8')
invoke = '        if name in PLANNING_NAMES:\n            return invoke_planning(self,name,a)\n'
extension = ('from oniro_planning import PLANNING_NAMES, build_planning_tools, invoke_planning\n'
             'TOOLS.extend(build_planning_tools())\n'
             'INSTRUCTIONS += " For daily work use get_planning_context and list_daily_plan. Read a fresh version before updating commitments; dates of execution are separate from deadlines."\n')
assert text.count(invoke) == 1 and text.count(extension) == 1
text = text.replace(invoke, '').replace(extension, '').replace('VERSION = "1.2.0"', 'VERSION = "1.1.1"')
compile(text, str(target), 'exec')
backup = root / ('backup-remove-planning-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
backup.mkdir()
shutil.copy2(target, backup / target.name)
target.write_text(text, encoding='utf-8')
module = root / 'oniro_planning.py'
if module.exists():
    assert module.resolve().parent == root
    shutil.move(str(module), str(backup / module.name))
print('Removed planning tools; original ONIRO connector preserved. Backup:', backup)
