set -euo pipefail
cd /home/plane/plane-app
backup=/home/plane/backups/planning-20260914-before-install-v2
staging=/home/plane/staging/oniro-planning-20260914
test -s "$backup/database.dump"
test -s "$backup/database-contents.txt"
cmp docker-compose.override.yml "$backup/docker-compose.override.yml"
docker image inspect oniro-plane-api:before-planning-20260914 >/dev/null
docker image inspect oniro-plane-web:before-planning-20260914 >/dev/null
docker compose -f docker-compose.yml -f docker-compose.override.yml -f "$staging/compose.planning.yml" run -T --rm --no-deps --entrypoint python api manage.py shell < "$staging/migrate_planning.py"
python3 - <<'PY'
from pathlib import Path
p=Path('docker-compose.override.yml')
text=p.read_text()
assert text.count('image: plane-api-custom:latest')==4
assert text.count('image: plane-web-custom:latest')==1
text=text.replace('image: plane-api-custom:latest','image: oniro-plane-api:planning-v1')
text=text.replace('image: plane-web-custom:latest','image: oniro-plane-web:planning-v1')
p.write_text(text)
PY
rollback() {
  echo 'Startup check failed; restoring previous application images'
  cp -p "$backup/docker-compose.override.yml" docker-compose.override.yml
  docker compose up -d --no-deps --pull never api worker beat-worker web
}
trap rollback ERR
docker compose up -d --no-deps --pull never api worker beat-worker web
ready=false
for attempt in $(seq 1 60); do
  code=$(curl --max-time 3 -s -o /dev/null -w '%{http_code}' http://127.0.0.1/api/workspaces/oniro/planning/bootstrap/ || true)
  if [ "$code" = 403 ] || [ "$code" = 401 ]; then ready=true; break; fi
  sleep 2
done
test "$ready" = true
curl --fail --max-time 10 -s http://127.0.0.1/oniro/planning/ | grep -q 'Il lavoro, giorno per giorno'
curl --fail --max-time 10 -s http://127.0.0.1/oniro-planning/navigation.js | grep -q 'Pianificazione'
trap - ERR
echo 'Planning installed; authenticated smoke test still required.'
