set -euo pipefail
umask 077
cd /home/plane/plane-app
backup=/home/plane/backups/remove-planning-20260915
test ! -e "$backup"
docker image inspect oniro-plane-api:before-planning-20260914 >/dev/null
docker image inspect oniro-plane-web:before-planning-20260914 >/dev/null
mkdir -p "$backup"
cp -p docker-compose.yml docker-compose.override.yml "$backup/"
docker exec plane-app-plane-db-1 sh -c 'pg_dump -w -h /var/run/postgresql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$backup/database.dump"
test -s "$backup/database.dump"
docker exec -i plane-app-plane-db-1 pg_restore --list < "$backup/database.dump" > "$backup/database-contents.txt"
docker exec -i plane-app-api-1 python manage.py shell <<'PY'
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from oniro_planning.models import Capacity, PlanEvent, PlanSlot, ProjectPlanning
assert all(not model.objects.exists() for model in [Capacity, PlanEvent, PlanSlot, ProjectPlanning]), 'Planning contains data: stop before removing schema'
executor = MigrationExecutor(connection)
plan = executor.migration_plan([('oniro_planning', None)])
assert len(plan) == 1 and all(m.app_label == 'oniro_planning' and backwards for m, backwards in plan)
executor.migrate([('oniro_planning', None)])
print('Removed the four empty planning tables; original Plane data unchanged.')
PY
python3 - <<'PY'
from pathlib import Path
p = Path('docker-compose.override.yml')
text = p.read_text()
assert text.count('image: oniro-plane-api:planning-v1') == 4
assert text.count('image: oniro-plane-web:planning-v1') == 1
text = text.replace('image: oniro-plane-api:planning-v1', 'image: oniro-plane-api:before-planning-20260914')
text = text.replace('image: oniro-plane-web:planning-v1', 'image: oniro-plane-web:before-planning-20260914')
p.write_text(text)
PY
docker compose up -d --no-deps --pull never api worker beat-worker web
ready=false
for attempt in $(seq 1 30); do
  code=$(curl --max-time 3 -s -o /dev/null -w '%{http_code}' http://127.0.0.1/api/instances/ || true)
  if [ "$code" = 200 ]; then ready=true; break; fi
  sleep 2
done
test "$ready" = true
docker exec plane-app-web-1 sh -c '! grep -q oniro-planning /usr/share/nginx/html/index.html && ! test -d /usr/share/nginx/html/oniro-planning'
docker exec plane-app-api-1 sh -c '! test -d /code/oniro_planning'
for container in planning-preview-web planning-preview-api planning-test-db planning-test-redis; do
  if docker container inspect "$container" >/dev/null 2>&1; then docker stop "$container" >/dev/null; fi
done
echo "Planner removed; original application images restored. Fresh backup: $backup"
