#!/usr/bin/env bash
# Push the app to a Hugging Face Space (Docker SDK).
# Usage: bash scripts/deploy_hf.sh <hf-username>/<space-name>
# Builds a clean snapshot (code only: no FITS, no recon images, which the Hub would
# reject as un-LFS'd binaries) and force-pushes it. Git asks for your HF username and an
# access token with "write" permission the first time.
set -euo pipefail
SPACE="${1:?usage: deploy_hf.sh <user>/<space>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT

cp -r "$ROOT/server" "$ROOT/web" "$ROOT/scripts" "$ROOT/Dockerfile" "$ROOT/requirements.txt" "$ROOT/.dockerignore" "$OUT/"
find "$OUT" -name __pycache__ -type d -prune -exec rm -rf {} +

{
  cat <<'EOF'
---
title: SPHEREx Time Explorer
emoji: 🔭
colorFrom: indigo
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
short_description: Flip through every SPHEREx image of a sky patch
---

EOF
  cat "$ROOT/README.md"
} > "$OUT/README.md"

cd "$OUT"
git init -q -b main
git add -A
git commit -q -m "Deploy SPHEREx Time Explorer ($(git -C "$ROOT" rev-parse --short HEAD))"
git push --force "https://huggingface.co/spaces/$SPACE" main
echo "Pushed. Build log: https://huggingface.co/spaces/$SPACE?logs=build"
