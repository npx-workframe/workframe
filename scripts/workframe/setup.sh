#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

mkdir -p Agents Files

echo "Pulling Hermes image..."
docker pull nousresearch/hermes-agent:latest

cat <<'EOF'

Workframe Phase B — use ONE of these:

  FULL (recommended — credentials → native agent → browser chat):
    ./scripts/start-install.sh

  Open full installer in new terminal (TTY-friendly):
    ./scripts/launch-install.sh

  Already ran Hermes setup? Finish boot:
    ./scripts/install.sh

  Credentials / dashboard only:
    ./scripts/open-setup.sh

Phase C — chat with Workframe Agent:
  ./scripts/chat.sh

WARNING: docker run ... hermes-agent:latest WITHOUT -p workframe-agent
         starts generic default Hermes (OWL) — not Workframe Agent.
EOF
