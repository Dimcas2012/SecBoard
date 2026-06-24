#!/usr/bin/env bash
# Build a public release tarball of SecBoard Community Edition (no secrets, no venv).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NAME="SecBoard_base"
VERSION="${1:-$(date +%Y%m%d)}"
OUT="${ROOT}/dist/${NAME}-${VERSION}.tar.gz"

mkdir -p "${ROOT}/dist"

tar -czf "$OUT" \
  --exclude='.env' \
  --exclude='.secboard_*' \
  --exclude='venv' \
  --exclude='logs' \
  --exclude='*.log' \
  --exclude='staticfiles' \
  --exclude='media' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.git' \
  --exclude='dist' \
  --exclude='celerybeat-schedule*' \
  -C "$(dirname "$ROOT")" "$(basename "$ROOT")"

echo "Created: $OUT"
echo "SHA256: $(sha256sum "$OUT" | awk '{print $1}')"
