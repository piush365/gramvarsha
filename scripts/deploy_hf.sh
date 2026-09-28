#!/usr/bin/env bash
# Push the API to a Hugging Face Space (Docker SDK, free CPU).
#
#   HF_TOKEN=hf_xxx ./scripts/deploy_hf.sh <user>/<space-name>
#
# A Space needs its Dockerfile and README (with YAML front matter) at the root, so
# this script stages exactly the files the image needs and uploads that folder.
set -euo pipefail

SPACE="${1:?usage: deploy_hf.sh <user>/<space-name>}"
: "${HF_TOKEN:?set HF_TOKEN (a write token from huggingface.co/settings/tokens)}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

cd "$ROOT"
mkdir -p "$STAGE"/{ml,data,frontend/public}
cp backend/Dockerfile "$STAGE/Dockerfile"
cp deploy/hf-space/README.md "$STAGE/README.md"
cp .dockerignore "$STAGE/"
rsync -a --exclude cache --exclude __pycache__ backend "$STAGE/"
cp ml/__init__.py ml/features.py ml/kriging.py ml/model.py ml/physics.py ml/explain.py ml/metrics.json "$STAGE/ml/"
cp -r ml/models "$STAGE/ml/"
cp data/manifest.json data/panchayats.csv data/terrain.csv data/village_names.csv data/*.geojson "$STAGE/data/"
cp frontend/public/snapshot.json "$STAGE/frontend/public/"

# The Space Dockerfile builds from the Space root, which mirrors the repo layout.
# Python API rather than the `hf` CLI: its command names change between releases.
python -m pip install --quiet "huggingface_hub>=0.34"
SPACE="$SPACE" STAGE="$STAGE" REV="$(git rev-parse --short HEAD)" python - <<'PY'
import os
from huggingface_hub import HfApi

api = HfApi(token=os.environ["HF_TOKEN"])
space = os.environ["SPACE"]
api.create_repo(space, repo_type="space", space_sdk="docker", exist_ok=True)
api.upload_folder(repo_id=space, repo_type="space", folder_path=os.environ["STAGE"],
                  commit_message=f"Deploy {os.environ['REV']}", delete_patterns=["*"])
PY
echo "Deployed. API: https://${SPACE/\//-}.hf.space/api/health"
