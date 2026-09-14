"""Fail closed if installation would apply any existing Plane migrations."""
from django.conf import settings
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
assert not getattr(settings,'ONIRO_PLANNING_PREVIEW',False)
assert connection.settings_dict['HOST'] != 'planning-test-db'
plan=MigrationExecutor(connection).migration_plan([('oniro_planning','0001_initial')])
assert all(m.app_label=='oniro_planning' and not backwards for m,backwards in plan), 'Unexpected dependencies; installation stopped'
print('Applying only the additive ONIRO planning migration')
call_command('migrate','oniro_planning',interactive=False)
