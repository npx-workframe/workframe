#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ ! -f "$ROOT/Agents/profiles/workframe-agent/SOUL.md" ]; then
  echo "ERROR: Workframe not bootstrapped." >&2
  echo "Run: ./scripts/bootstrap-native.sh" >&2
  echo "Full pack fallback: ./scripts/bootstrap-profiles.sh" >&2
  echo "Bare Hermes default profile is NOT a Workframe install." >&2
  exit 1
fi
if [ ! -f "$ROOT/Agents/SOUL.md" ] || ! grep -q 'Workframe concierge' "$ROOT/Agents/SOUL.md"; then
  echo "ERROR: Agents/SOUL.md missing Workframe native identity." >&2
  echo "Re-run: ./scripts/bootstrap-native.sh" >&2
  exit 1
fi
cfg="$ROOT/Agents/profiles/workframe-agent/config.yaml"
if [ -f "$cfg" ] && grep -q '^  cwd: \.$' "$cfg"; then
  echo "ERROR: profile terminal.cwd must be /workspace (Files/), not ." >&2
  echo "Re-run: ./scripts/bootstrap-native.sh" >&2
  exit 1
fi
