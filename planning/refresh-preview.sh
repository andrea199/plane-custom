set -euo pipefail
cd /home/plane/staging/oniro-planning-20260914
docker build -f Dockerfile.api -t oniro-plane-api:planning-v1 .
docker build -f Dockerfile.web -t oniro-plane-web:planning-v1 .
docker stop -t 2 planning-preview-api planning-preview-web
docker rm planning-preview-api planning-preview-web
docker run -d --name planning-preview-api --network oniro-planning-test -e DATABASE_URL=postgres://postgres:isolated-test-only@planning-test-db:5432/planner --entrypoint python oniro-plane-api:planning-v1 manage.py runserver 0.0.0.0:8000 --noreload --settings=plane.settings.planning_preview
docker run -d --name planning-preview-web --network oniro-planning-test -p 127.0.0.1:18080:3000 -v "$PWD/preview-nginx.conf:/etc/nginx/nginx.conf:ro" oniro-plane-web:planning-v1
