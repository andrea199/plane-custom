set -euo pipefail
cd /home/plane/staging/oniro-planning-20260914
docker build -f Dockerfile.web -t oniro-plane-web:planning-v1 .
cd /home/plane/plane-app
docker compose up -d --no-deps --pull never web
