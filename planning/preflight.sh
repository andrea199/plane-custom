set -euo pipefail
docker inspect --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}' plane-app-api-1
docker inspect --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}' plane-app-api-1
docker inspect --format '{{json .Config.Entrypoint}} {{json .Config.Cmd}}' plane-app-api-1
docker exec plane-app-api-1 cat /code/bin/docker-entrypoint-api.sh
df -h /home/plane
