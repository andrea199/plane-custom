set -euo pipefail
umask 077
cd /home/plane/plane-app
backup=/home/plane/backups/planning-20260914-before-install-v2
if [ -e "$backup" ]; then echo 'Backup already exists; do not overwrite'; exit 1; fi
mkdir -p "$backup"
cp -p docker-compose.yml docker-compose.override.yml "$backup/"
docker image tag "$(docker inspect -f '{{.Image}}' plane-app-api-1)" oniro-plane-api:before-planning-20260914
docker image tag "$(docker inspect -f '{{.Image}}' plane-app-web-1)" oniro-plane-web:before-planning-20260914
docker exec plane-app-plane-db-1 sh -c 'pg_dump -w -h /var/run/postgresql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$backup/database.dump"
test -s "$backup/database.dump"
docker exec -i plane-app-plane-db-1 pg_restore --list < "$backup/database.dump" > "$backup/database-contents.txt"
wc -c "$backup/database.dump"
grep -n -E '^[[:space:]]*(api|web|worker|beat-worker|image|build):' docker-compose.override.yml
docker compose -f docker-compose.yml -f docker-compose.override.yml -f /home/plane/staging/oniro-planning-20260914/compose.planning.yml run --rm --no-deps --entrypoint python api manage.py migrate oniro_planning --plan
