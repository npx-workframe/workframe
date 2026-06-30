#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
"$ROOT/scripts/verify-bootstrap.sh"
if docker ps -aq -f "name=^workframe-chat$" | grep -q .; then
  docker rm -f "workframe-chat"
fi
exec docker run --rm -it --name "workframe-chat" --entrypoint hermes \
  -v "$ROOT/Agents:/opt/data" \
  -v "$ROOT/Files:/workspace" \
  nousresearch/hermes-agent:latest -p workframe-agent chat "$@"
