#!/usr/bin/env bash
set -euo pipefail
cd /home/plane/staging/oniro-planning-20260914
docker build -f Dockerfile.api -t oniro-plane-api:planning-v1 .
docker build -f Dockerfile.web -t oniro-plane-web:planning-v1 .
docker run --rm --network oniro-planning-test -e DATABASE_URL=postgres://postgres:isolated-test-only@planning-test-db:5432/planner --entrypoint python oniro-plane-api:planning-v1 manage.py migrate --noinput --settings=plane.settings.planning_preview
docker run --rm -i --network oniro-planning-test -e DATABASE_URL=postgres://postgres:isolated-test-only@planning-test-db:5432/planner --entrypoint python oniro-plane-api:planning-v1 manage.py shell --settings=plane.settings.planning_preview < seed_preview.py
docker run -d --name planning-preview-api --network oniro-planning-test -e DATABASE_URL=postgres://postgres:isolated-test-only@planning-test-db:5432/planner --entrypoint python oniro-plane-api:planning-v1 manage.py runserver 0.0.0.0:8000 --noreload --settings=plane.settings.planning_preview
docker run -d --name planning-preview-web --network oniro-planning-test -p 127.0.0.1:18080:3000 -v "$PWD/preview-nginx.conf:/etc/nginx/nginx.conf:ro" oniro-plane-web:planning-v1
printf 'Preview via SSH tunnel: http://localhost:18080/preview/start/\n'
