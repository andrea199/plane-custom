#!/usr/bin/env bash
set -euo pipefail
cd /home/plane/staging/oniro-planning-20260914
docker image inspect plane-api-custom:latest --format '{{.Id}}' | grep -qx 'sha256:39a68c2a0b97f4f7e7c8c12fcd2fcaec463e68110c4462a2a86719f7eb9c27fe'
docker build -f Dockerfile.api -t oniro-plane-api:planning-v1 .
docker network inspect oniro-planning-test >/dev/null 2>&1 || docker network create oniro-planning-test
if ! docker container inspect planning-test-redis >/dev/null 2>&1; then
  docker run -d --network oniro-planning-test --name planning-test-redis valkey/valkey:7.2.11-alpine
fi
if ! docker container inspect planning-test-db >/dev/null 2>&1; then
  docker run -d --network oniro-planning-test --name planning-test-db -e POSTGRES_PASSWORD=isolated-test-only -e POSTGRES_DB=planner postgres:15.7-alpine
fi
for attempt in $(seq 1 30); do
  if docker exec planning-test-db pg_isready -U postgres >/dev/null; then break; fi
  sleep 1
done
docker run --rm --network oniro-planning-test -e DATABASE_URL=postgres://postgres:isolated-test-only@planning-test-db:5432/planner -v "$PWD/oniro_planning:/code/oniro_planning" --entrypoint python oniro-plane-api:planning-v1 manage.py test oniro_planning --noinput --settings=plane.settings.planning_test --verbosity 1
