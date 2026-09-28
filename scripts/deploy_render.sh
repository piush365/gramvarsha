#!/usr/bin/env bash
# Build the API image, push it to Docker Hub, and (optionally) tell Render to redeploy.
#
#   ./scripts/deploy_render.sh <dockerhub-user>/gramvarsha-api
#   RENDER_DEPLOY_HOOK=https://api.render.com/deploy/srv-...  ./scripts/deploy_render.sh <user>/gramvarsha-api
#
# Needs `docker login` done once. Render's free web service pulls this image
# ("New > Web Service > Existing image"); the deploy hook URL is under the
# service's Settings > Deploy Hook.
set -euo pipefail

IMAGE="${1:?usage: deploy_render.sh <dockerhub-user>/gramvarsha-api}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TAG="$(git -C "$ROOT" rev-parse --short HEAD)"

docker build -f "$ROOT/backend/Dockerfile" -t "$IMAGE:latest" -t "$IMAGE:$TAG" "$ROOT"
docker push "$IMAGE:$TAG"
docker push "$IMAGE:latest"

if [[ -n "${RENDER_DEPLOY_HOOK:-}" ]]; then
  curl -fsS -X POST "$RENDER_DEPLOY_HOOK" >/dev/null && echo "Render redeploy triggered."
else
  echo "Pushed $IMAGE:latest. Set RENDER_DEPLOY_HOOK to trigger Render automatically."
fi
