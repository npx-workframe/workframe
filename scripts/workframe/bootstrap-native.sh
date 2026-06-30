#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [ -d "$ROOT/runtime/Agents" ]; then
  AGENTS_ROOT="$ROOT/runtime/Agents"
  FILES_ROOT="$ROOT/runtime/Files"
elif [ -d "$ROOT/Agents" ]; then
  AGENTS_ROOT="$ROOT/Agents"
  FILES_ROOT="$ROOT/Files"
else
  echo "Agents runtime missing (expected runtime/Agents or Agents/)." >&2
  exit 1
fi
mkdir -p "$AGENTS_ROOT/profiles" "$FILES_ROOT"
chmod -R a+rwX "$AGENTS_ROOT" "$FILES_ROOT" 2>/dev/null || true

echo "Creating profile: workframe-agent"
profile_config="$AGENTS_ROOT/profiles/workframe-agent/config.yaml"
clean_profile_orphan_native() {
  docker run --rm --name "workframe-bootstrap-native-clean" --entrypoint hermes \
    -v "$AGENTS_ROOT:/opt/data" \
    -v "$FILES_ROOT:/workspace" \
    nousresearch/hermes-agent:latest profile delete -y workframe-agent >/dev/null 2>&1 || true
  rm -rf "$AGENTS_ROOT/profiles/workframe-agent"
}
if docker run --rm --name "workframe-bootstrap-native-show-precheck" --entrypoint hermes \
  -v "$AGENTS_ROOT:/opt/data" \
  -v "$FILES_ROOT:/workspace" \
  nousresearch/hermes-agent:latest profile show workframe-agent >/dev/null 2>&1 && [ -f "$profile_config" ]; then
  echo "Profile workframe-agent already exists, continuing."
else
  clean_profile_orphan_native
  set +e
  create_out=$(docker run --rm --name "workframe-bootstrap-native" --entrypoint hermes \
    -v "$AGENTS_ROOT:/opt/data" \
    -v "$FILES_ROOT:/workspace" \
    nousresearch/hermes-agent:latest profile create workframe-agent --clone --description "Workframe Agent: Workframe Manager, orchestrator, and Workframe admin." 2>&1)
  create_code=$?
  set -e
  if [ "$create_code" -ne 0 ]; then
    if docker run --rm --name "workframe-bootstrap-native-show" --entrypoint hermes \
      -v "$AGENTS_ROOT:/opt/data" \
      -v "$FILES_ROOT:/workspace" \
      nousresearch/hermes-agent:latest profile show workframe-agent >/dev/null 2>&1 && [ -f "$profile_config" ]; then
      echo "Profile workframe-agent already exists, continuing."
    else
      echo "Retrying profile create after cleaning incomplete registration: workframe-agent"
      clean_profile_orphan_native
      docker run --rm --name "workframe-bootstrap-native-retry" --entrypoint hermes \
        -v "$AGENTS_ROOT:/opt/data" \
        -v "$FILES_ROOT:/workspace" \
        nousresearch/hermes-agent:latest profile create workframe-agent --clone --description "Workframe Agent: Workframe Manager, orchestrator, and Workframe admin." || {
        echo "$create_out" >&2
        echo "ERROR: failed to create profile workframe-agent" >&2
        exit 1
      }
    fi
  fi
fi

if [ -f "$ROOT/scripts/seed/profiles/workframe-agent/SOUL.md" ]; then
  mkdir -p "$AGENTS_ROOT/profiles/workframe-agent"
  cp "$ROOT/scripts/seed/profiles/workframe-agent/SOUL.md" "$AGENTS_ROOT/profiles/workframe-agent/SOUL.md"
  cp "$ROOT/scripts/seed/profiles/workframe-agent/SOUL.md" "$AGENTS_ROOT/SOUL.md"
fi
if [ -f "$ROOT/scripts/seed/profiles/workframe-agent/SETUP.md" ]; then
  cp "$ROOT/scripts/seed/profiles/workframe-agent/SETUP.md" "$AGENTS_ROOT/profiles/workframe-agent/SETUP.md"
fi

cat > "$AGENTS_ROOT/profiles/workframe-agent/profile.yaml" <<EOF
description: "Native Workframe agent: host, concierge, project manager, orchestrator, and Workframe admin."
description_auto: false
soul:
  file: /opt/data/profiles/workframe-agent/SOUL.md
EOF

mkdir -p "$AGENTS_ROOT/workframe"
cat > "$AGENTS_ROOT/workframe/routes.json" <<'EOF'
{
  "version": 1,
  "default_profile": "workframe-agent",
  "routes": [
    {
      "id": "workframe-agent",
      "surface": "ui",
      "channel_id": "ui://agent/workframe-agent",
      "profile": "workframe-agent",
      "display_name": "Workframe Agent",
      "role": "Workframe Agent: Workframe Manager, orchestrator, and Workframe admin.",
      "mode": "lane"
    }
  ]
}
EOF

cfg="$AGENTS_ROOT/profiles/workframe-agent/config.yaml"
if [ -f "$cfg" ] && grep -q '^  cwd: ' "$cfg"; then
  if sed --version >/dev/null 2>&1; then
    sed -i.bak 's|^  cwd: .*|  cwd: /workspace|' "$cfg" && rm -f "$cfg.bak"
  else
    sed -i '' 's|^  cwd: .*|  cwd: /workspace|' "$cfg"
  fi
fi

echo "Setting default profile to workframe-agent..."
docker run --rm --name "workframe-bootstrap-use" --entrypoint hermes \
  -v "$AGENTS_ROOT:/opt/data" \
  -v "$FILES_ROOT:/workspace" \
  nousresearch/hermes-agent:latest profile use workframe-agent

echo "Native bootstrap complete (workframe-agent). Create agents: node scripts/agent-lifecycle.mjs create --slug <name> --spawn"
docker run --rm --name "workframe-bootstrap-list" --entrypoint hermes \
  -v "$AGENTS_ROOT:/opt/data" \
  -v "$FILES_ROOT:/workspace" \
  nousresearch/hermes-agent:latest profile list
