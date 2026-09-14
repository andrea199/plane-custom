"""Install additive routes/app in a copy of an existing Plane API image."""
from pathlib import Path

root = Path('/code/plane')
(root / 'settings/planning_test.py').write_text('from oniro_planning.test_settings import *\n')
(root / 'settings/planning_preview.py').write_text('from oniro_planning.preview_settings import *\n')
settings = root / 'settings/common.py'
urls = root / 'urls.py'
if not (root / 'db/migrations/0131_v137e_canonical_workflow_b.py').exists():
    raise SystemExit('Requires the verified ONIRO v1.37 runtime; do not rebuild from an older overlay.')
marker = '# ONIRO daily planning v1'
text = settings.read_text()
if marker not in text:
    settings.write_text(text + '\n' + marker + '\nINSTALLED_APPS.append("oniro_planning.apps.PlanningConfig")\n')
text = urls.read_text()
if marker not in text:
    urls.write_text(text + '\n' + marker + '\nurlpatterns = [\n'
                   '    path("api/workspaces/<str:slug>/planning/", include("oniro_planning.urls")),\n'
                   '    path("api/v1/workspaces/<str:slug>/planning/", include("oniro_planning.urls")),\n'
                   '] + urlpatterns\n')
