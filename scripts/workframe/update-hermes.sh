#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "Pulling latest Hermes image..."
docker compose pull gateway dashboard
echo "Recreating Hermes containers (in-container hermes update is unsupported in Docker)..."
docker compose up -d --force-recreate gateway dashboard
echo "Done. Workframe API and Workframe UI remain in place unless you recreate the full stack."
