set -euo pipefail
docker exec plane-app-api-1 sh -c 'sed -n "2335,2410p" plane/api/views/issue.py; sed -n "1,125p" plane/api/serializers/issue.py'
