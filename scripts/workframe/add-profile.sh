#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

INPUT="${1:-}"
if [ -z "$INPUT" ]; then
  echo "Usage: $0 <profile>" >&2
  echo "Specialists: architect designer dev docs research visionary" >&2
  exit 1
fi
if [ "$INPUT" = "workframe-agent" ]; then
  echo "Use bootstrap-native for workframe-agent." >&2
  exit 1
fi
PROFILE=""
case "$INPUT" in
  "architect") PROFILE="architect" ;;
  "designer") PROFILE="designer" ;;
  "dev") PROFILE="dev" ;;
  "docs") PROFILE="docs" ;;
  "research") PROFILE="research" ;;
  "visionary") PROFILE="visionary" ;;
  *)
    echo "Unknown profile: $INPUT" >&2
    echo "Available: architect designer dev docs research visionary" >&2
    exit 1
    ;;
esac

if [ ! -d "$ROOT/Agents" ]; then
  echo "Agents/ missing. Run Hermes setup first." >&2
  exit 1
fi

DESC=""
case "$PROFILE" in
  "architect") DESC="Defines system design, technical boundaries, implementation plans, and code-review standards." ;;
  "designer") DESC="Handles UI direction, design docs, visual assets, image prompts, brand direction, and layout feedback." ;;
  "dev") DESC="Builds and modifies project files, scripts, tests, and implementation artifacts." ;;
  "docs") DESC="Maintains AGENTS.md, .hermes.md, docs indexes, source-of-truth maps, and change summaries." ;;
  "research") DESC="Performs technical research, market research, references, competitive analysis, and R&D notes." ;;
  "visionary") DESC="Clarifies product purpose, positioning, strategy, user value, and long-term alignment." ;;
esac

set +e
create_out=$(docker run --rm --name "workframe-add-$PROFILE" --entrypoint hermes \
  -v "$ROOT/Agents:/opt/data" \
  -v "$ROOT/Files:/workspace" \
  nousresearch/hermes-agent:latest profile create "$PROFILE" --clone --description "$DESC" 2>&1)
create_code=$?
set -e
if [ "$create_code" -ne 0 ]; then
  if docker run --rm --name "workframe-add-$PROFILE-show" --entrypoint hermes \
    -v "$ROOT/Agents:/opt/data" \
    -v "$ROOT/Files:/workspace" \
    nousresearch/hermes-agent:latest profile show "$PROFILE" >/dev/null 2>&1; then
    echo "Profile $PROFILE already exists, continuing."
  else
    echo "$create_out" >&2
    echo "ERROR: failed to create profile $PROFILE" >&2
    exit 1
  fi
fi

if [ -f "$ROOT/scripts/seed/profiles/$PROFILE/SOUL.md" ]; then
  mkdir -p "$ROOT/Agents/profiles/$PROFILE"
  cp "$ROOT/scripts/seed/profiles/$PROFILE/SOUL.md" "$ROOT/Agents/profiles/$PROFILE/SOUL.md"
fi

cat > "$ROOT/Agents/profiles/$PROFILE/profile.yaml" <<EOF
description: "$DESC"
description_auto: false
soul:
  file: /opt/data/profiles/$PROFILE/SOUL.md
EOF

echo "Profile $PROFILE ready."
