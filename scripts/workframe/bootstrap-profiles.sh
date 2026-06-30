#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -d "$ROOT/Agents" ]; then
  echo "Agents/ missing. Run Hermes setup first."
  exit 1
fi

mkdir -p "$ROOT/Agents/profiles"
echo "Creating profile: workframe-agent"
profile_config="$ROOT/Agents/profiles/workframe-agent/config.yaml"
clean_profile_orphan_workframe-agent() {
  docker run --rm --name "workframe-bootstrap-workframe-agent-clean" --entrypoint hermes \
    -v "$ROOT/Agents:/opt/data" \
    -v "$ROOT/Files:/workspace" \
    nousresearch/hermes-agent:latest profile delete -y workframe-agent >/dev/null 2>&1 || true
  rm -rf "$ROOT/Agents/profiles/workframe-agent"
}
if docker run --rm --name "workframe-bootstrap-workframe-agent-show-precheck" --entrypoint hermes \
  -v "$ROOT/Agents:/opt/data" \
  -v "$ROOT/Files:/workspace" \
  nousresearch/hermes-agent:latest profile show workframe-agent >/dev/null 2>&1 && [ -f "$profile_config" ]; then
  echo "Profile workframe-agent already exists, continuing."
else
  clean_profile_orphan_workframe-agent
  set +e
  create_out=$(docker run --rm --name "workframe-bootstrap-workframe-agent" --entrypoint hermes \
    -v "$ROOT/Agents:/opt/data" \
    -v "$ROOT/Files:/workspace" \
    nousresearch/hermes-agent:latest profile create workframe-agent --clone --description "Workframe Agent: Workframe Manager, orchestrator, and Workframe admin." 2>&1)
  create_code=$?
  set -e
  if [ "$create_code" -ne 0 ]; then
    if docker run --rm --name "workframe-bootstrap-workframe-agent-show" --entrypoint hermes \
      -v "$ROOT/Agents:/opt/data" \
      -v "$ROOT/Files:/workspace" \
      nousresearch/hermes-agent:latest profile show workframe-agent >/dev/null 2>&1 && [ -f "$profile_config" ]; then
      echo "Profile workframe-agent already exists, continuing."
    else
      echo "Retrying profile create after cleaning incomplete registration: workframe-agent"
      clean_profile_orphan_workframe-agent
      docker run --rm --name "workframe-bootstrap-workframe-agent-retry" --entrypoint hermes \
        -v "$ROOT/Agents:/opt/data" \
        -v "$ROOT/Files:/workspace" \
        nousresearch/hermes-agent:latest profile create workframe-agent --clone --description "Workframe Agent: Workframe Manager, orchestrator, and Workframe admin." || {
        echo "$create_out" >&2
        echo "ERROR: failed to create profile workframe-agent" >&2
        exit 1
      }
    fi
  fi
fi

if [ -f "$ROOT/scripts/seed/profiles/workframe-agent/SOUL.md" ]; then
  mkdir -p "$ROOT/Agents/profiles/workframe-agent"
  cp "$ROOT/scripts/seed/profiles/workframe-agent/SOUL.md" "$ROOT/Agents/profiles/workframe-agent/SOUL.md"
fi
if [ -f "$ROOT/scripts/seed/profiles/workframe-agent/SETUP.md" ]; then
  cp "$ROOT/scripts/seed/profiles/workframe-agent/SETUP.md" "$ROOT/Agents/profiles/workframe-agent/SETUP.md"
fi


mkdir -p "$ROOT/Agents/profiles"
echo "Creating profile: visionary"
profile_config="$ROOT/Agents/profiles/visionary/config.yaml"
clean_profile_orphan_visionary() {
  docker run --rm --name "workframe-bootstrap-visionary-clean" --entrypoint hermes \
    -v "$ROOT/Agents:/opt/data" \
    -v "$ROOT/Files:/workspace" \
    nousresearch/hermes-agent:latest profile delete -y visionary >/dev/null 2>&1 || true
  rm -rf "$ROOT/Agents/profiles/visionary"
}
if docker run --rm --name "workframe-bootstrap-visionary-show-precheck" --entrypoint hermes \
  -v "$ROOT/Agents:/opt/data" \
  -v "$ROOT/Files:/workspace" \
  nousresearch/hermes-agent:latest profile show visionary >/dev/null 2>&1 && [ -f "$profile_config" ]; then
  echo "Profile visionary already exists, continuing."
else
  clean_profile_orphan_visionary
  set +e
  create_out=$(docker run --rm --name "workframe-bootstrap-visionary" --entrypoint hermes \
    -v "$ROOT/Agents:/opt/data" \
    -v "$ROOT/Files:/workspace" \
    nousresearch/hermes-agent:latest profile create visionary --clone --description "Clarifies product purpose, positioning, strategy, user value, and long-term alignment." 2>&1)
  create_code=$?
  set -e
  if [ "$create_code" -ne 0 ]; then
    if docker run --rm --name "workframe-bootstrap-visionary-show" --entrypoint hermes \
      -v "$ROOT/Agents:/opt/data" \
      -v "$ROOT/Files:/workspace" \
      nousresearch/hermes-agent:latest profile show visionary >/dev/null 2>&1 && [ -f "$profile_config" ]; then
      echo "Profile visionary already exists, continuing."
    else
      echo "Retrying profile create after cleaning incomplete registration: visionary"
      clean_profile_orphan_visionary
      docker run --rm --name "workframe-bootstrap-visionary-retry" --entrypoint hermes \
        -v "$ROOT/Agents:/opt/data" \
        -v "$ROOT/Files:/workspace" \
        nousresearch/hermes-agent:latest profile create visionary --clone --description "Clarifies product purpose, positioning, strategy, user value, and long-term alignment." || {
        echo "$create_out" >&2
        echo "ERROR: failed to create profile visionary" >&2
        exit 1
      }
    fi
  fi
fi

if [ -f "$ROOT/scripts/seed/profiles/visionary/SOUL.md" ]; then
  mkdir -p "$ROOT/Agents/profiles/visionary"
  cp "$ROOT/scripts/seed/profiles/visionary/SOUL.md" "$ROOT/Agents/profiles/visionary/SOUL.md"
fi


mkdir -p "$ROOT/Agents/profiles"
echo "Creating profile: architect"
profile_config="$ROOT/Agents/profiles/architect/config.yaml"
clean_profile_orphan_architect() {
  docker run --rm --name "workframe-bootstrap-architect-clean" --entrypoint hermes \
    -v "$ROOT/Agents:/opt/data" \
    -v "$ROOT/Files:/workspace" \
    nousresearch/hermes-agent:latest profile delete -y architect >/dev/null 2>&1 || true
  rm -rf "$ROOT/Agents/profiles/architect"
}
if docker run --rm --name "workframe-bootstrap-architect-show-precheck" --entrypoint hermes \
  -v "$ROOT/Agents:/opt/data" \
  -v "$ROOT/Files:/workspace" \
  nousresearch/hermes-agent:latest profile show architect >/dev/null 2>&1 && [ -f "$profile_config" ]; then
  echo "Profile architect already exists, continuing."
else
  clean_profile_orphan_architect
  set +e
  create_out=$(docker run --rm --name "workframe-bootstrap-architect" --entrypoint hermes \
    -v "$ROOT/Agents:/opt/data" \
    -v "$ROOT/Files:/workspace" \
    nousresearch/hermes-agent:latest profile create architect --clone --description "Defines system design, technical boundaries, implementation plans, and code-review standards." 2>&1)
  create_code=$?
  set -e
  if [ "$create_code" -ne 0 ]; then
    if docker run --rm --name "workframe-bootstrap-architect-show" --entrypoint hermes \
      -v "$ROOT/Agents:/opt/data" \
      -v "$ROOT/Files:/workspace" \
      nousresearch/hermes-agent:latest profile show architect >/dev/null 2>&1 && [ -f "$profile_config" ]; then
      echo "Profile architect already exists, continuing."
    else
      echo "Retrying profile create after cleaning incomplete registration: architect"
      clean_profile_orphan_architect
      docker run --rm --name "workframe-bootstrap-architect-retry" --entrypoint hermes \
        -v "$ROOT/Agents:/opt/data" \
        -v "$ROOT/Files:/workspace" \
        nousresearch/hermes-agent:latest profile create architect --clone --description "Defines system design, technical boundaries, implementation plans, and code-review standards." || {
        echo "$create_out" >&2
        echo "ERROR: failed to create profile architect" >&2
        exit 1
      }
    fi
  fi
fi

if [ -f "$ROOT/scripts/seed/profiles/architect/SOUL.md" ]; then
  mkdir -p "$ROOT/Agents/profiles/architect"
  cp "$ROOT/scripts/seed/profiles/architect/SOUL.md" "$ROOT/Agents/profiles/architect/SOUL.md"
fi


mkdir -p "$ROOT/Agents/profiles"
echo "Creating profile: docs"
profile_config="$ROOT/Agents/profiles/docs/config.yaml"
clean_profile_orphan_docs() {
  docker run --rm --name "workframe-bootstrap-docs-clean" --entrypoint hermes \
    -v "$ROOT/Agents:/opt/data" \
    -v "$ROOT/Files:/workspace" \
    nousresearch/hermes-agent:latest profile delete -y docs >/dev/null 2>&1 || true
  rm -rf "$ROOT/Agents/profiles/docs"
}
if docker run --rm --name "workframe-bootstrap-docs-show-precheck" --entrypoint hermes \
  -v "$ROOT/Agents:/opt/data" \
  -v "$ROOT/Files:/workspace" \
  nousresearch/hermes-agent:latest profile show docs >/dev/null 2>&1 && [ -f "$profile_config" ]; then
  echo "Profile docs already exists, continuing."
else
  clean_profile_orphan_docs
  set +e
  create_out=$(docker run --rm --name "workframe-bootstrap-docs" --entrypoint hermes \
    -v "$ROOT/Agents:/opt/data" \
    -v "$ROOT/Files:/workspace" \
    nousresearch/hermes-agent:latest profile create docs --clone --description "Maintains AGENTS.md, .hermes.md, docs indexes, source-of-truth maps, and change summaries." 2>&1)
  create_code=$?
  set -e
  if [ "$create_code" -ne 0 ]; then
    if docker run --rm --name "workframe-bootstrap-docs-show" --entrypoint hermes \
      -v "$ROOT/Agents:/opt/data" \
      -v "$ROOT/Files:/workspace" \
      nousresearch/hermes-agent:latest profile show docs >/dev/null 2>&1 && [ -f "$profile_config" ]; then
      echo "Profile docs already exists, continuing."
    else
      echo "Retrying profile create after cleaning incomplete registration: docs"
      clean_profile_orphan_docs
      docker run --rm --name "workframe-bootstrap-docs-retry" --entrypoint hermes \
        -v "$ROOT/Agents:/opt/data" \
        -v "$ROOT/Files:/workspace" \
        nousresearch/hermes-agent:latest profile create docs --clone --description "Maintains AGENTS.md, .hermes.md, docs indexes, source-of-truth maps, and change summaries." || {
        echo "$create_out" >&2
        echo "ERROR: failed to create profile docs" >&2
        exit 1
      }
    fi
  fi
fi

if [ -f "$ROOT/scripts/seed/profiles/docs/SOUL.md" ]; then
  mkdir -p "$ROOT/Agents/profiles/docs"
  cp "$ROOT/scripts/seed/profiles/docs/SOUL.md" "$ROOT/Agents/profiles/docs/SOUL.md"
fi


mkdir -p "$ROOT/Agents/profiles"
echo "Creating profile: dev"
profile_config="$ROOT/Agents/profiles/dev/config.yaml"
clean_profile_orphan_dev() {
  docker run --rm --name "workframe-bootstrap-dev-clean" --entrypoint hermes \
    -v "$ROOT/Agents:/opt/data" \
    -v "$ROOT/Files:/workspace" \
    nousresearch/hermes-agent:latest profile delete -y dev >/dev/null 2>&1 || true
  rm -rf "$ROOT/Agents/profiles/dev"
}
if docker run --rm --name "workframe-bootstrap-dev-show-precheck" --entrypoint hermes \
  -v "$ROOT/Agents:/opt/data" \
  -v "$ROOT/Files:/workspace" \
  nousresearch/hermes-agent:latest profile show dev >/dev/null 2>&1 && [ -f "$profile_config" ]; then
  echo "Profile dev already exists, continuing."
else
  clean_profile_orphan_dev
  set +e
  create_out=$(docker run --rm --name "workframe-bootstrap-dev" --entrypoint hermes \
    -v "$ROOT/Agents:/opt/data" \
    -v "$ROOT/Files:/workspace" \
    nousresearch/hermes-agent:latest profile create dev --clone --description "Builds and modifies project files, scripts, tests, and implementation artifacts." 2>&1)
  create_code=$?
  set -e
  if [ "$create_code" -ne 0 ]; then
    if docker run --rm --name "workframe-bootstrap-dev-show" --entrypoint hermes \
      -v "$ROOT/Agents:/opt/data" \
      -v "$ROOT/Files:/workspace" \
      nousresearch/hermes-agent:latest profile show dev >/dev/null 2>&1 && [ -f "$profile_config" ]; then
      echo "Profile dev already exists, continuing."
    else
      echo "Retrying profile create after cleaning incomplete registration: dev"
      clean_profile_orphan_dev
      docker run --rm --name "workframe-bootstrap-dev-retry" --entrypoint hermes \
        -v "$ROOT/Agents:/opt/data" \
        -v "$ROOT/Files:/workspace" \
        nousresearch/hermes-agent:latest profile create dev --clone --description "Builds and modifies project files, scripts, tests, and implementation artifacts." || {
        echo "$create_out" >&2
        echo "ERROR: failed to create profile dev" >&2
        exit 1
      }
    fi
  fi
fi

if [ -f "$ROOT/scripts/seed/profiles/dev/SOUL.md" ]; then
  mkdir -p "$ROOT/Agents/profiles/dev"
  cp "$ROOT/scripts/seed/profiles/dev/SOUL.md" "$ROOT/Agents/profiles/dev/SOUL.md"
fi


mkdir -p "$ROOT/Agents/profiles"
echo "Creating profile: research"
profile_config="$ROOT/Agents/profiles/research/config.yaml"
clean_profile_orphan_research() {
  docker run --rm --name "workframe-bootstrap-research-clean" --entrypoint hermes \
    -v "$ROOT/Agents:/opt/data" \
    -v "$ROOT/Files:/workspace" \
    nousresearch/hermes-agent:latest profile delete -y research >/dev/null 2>&1 || true
  rm -rf "$ROOT/Agents/profiles/research"
}
if docker run --rm --name "workframe-bootstrap-research-show-precheck" --entrypoint hermes \
  -v "$ROOT/Agents:/opt/data" \
  -v "$ROOT/Files:/workspace" \
  nousresearch/hermes-agent:latest profile show research >/dev/null 2>&1 && [ -f "$profile_config" ]; then
  echo "Profile research already exists, continuing."
else
  clean_profile_orphan_research
  set +e
  create_out=$(docker run --rm --name "workframe-bootstrap-research" --entrypoint hermes \
    -v "$ROOT/Agents:/opt/data" \
    -v "$ROOT/Files:/workspace" \
    nousresearch/hermes-agent:latest profile create research --clone --description "Performs technical research, market research, references, competitive analysis, and R&D notes." 2>&1)
  create_code=$?
  set -e
  if [ "$create_code" -ne 0 ]; then
    if docker run --rm --name "workframe-bootstrap-research-show" --entrypoint hermes \
      -v "$ROOT/Agents:/opt/data" \
      -v "$ROOT/Files:/workspace" \
      nousresearch/hermes-agent:latest profile show research >/dev/null 2>&1 && [ -f "$profile_config" ]; then
      echo "Profile research already exists, continuing."
    else
      echo "Retrying profile create after cleaning incomplete registration: research"
      clean_profile_orphan_research
      docker run --rm --name "workframe-bootstrap-research-retry" --entrypoint hermes \
        -v "$ROOT/Agents:/opt/data" \
        -v "$ROOT/Files:/workspace" \
        nousresearch/hermes-agent:latest profile create research --clone --description "Performs technical research, market research, references, competitive analysis, and R&D notes." || {
        echo "$create_out" >&2
        echo "ERROR: failed to create profile research" >&2
        exit 1
      }
    fi
  fi
fi

if [ -f "$ROOT/scripts/seed/profiles/research/SOUL.md" ]; then
  mkdir -p "$ROOT/Agents/profiles/research"
  cp "$ROOT/scripts/seed/profiles/research/SOUL.md" "$ROOT/Agents/profiles/research/SOUL.md"
fi


mkdir -p "$ROOT/Agents/profiles"
echo "Creating profile: designer"
profile_config="$ROOT/Agents/profiles/designer/config.yaml"
clean_profile_orphan_designer() {
  docker run --rm --name "workframe-bootstrap-designer-clean" --entrypoint hermes \
    -v "$ROOT/Agents:/opt/data" \
    -v "$ROOT/Files:/workspace" \
    nousresearch/hermes-agent:latest profile delete -y designer >/dev/null 2>&1 || true
  rm -rf "$ROOT/Agents/profiles/designer"
}
if docker run --rm --name "workframe-bootstrap-designer-show-precheck" --entrypoint hermes \
  -v "$ROOT/Agents:/opt/data" \
  -v "$ROOT/Files:/workspace" \
  nousresearch/hermes-agent:latest profile show designer >/dev/null 2>&1 && [ -f "$profile_config" ]; then
  echo "Profile designer already exists, continuing."
else
  clean_profile_orphan_designer
  set +e
  create_out=$(docker run --rm --name "workframe-bootstrap-designer" --entrypoint hermes \
    -v "$ROOT/Agents:/opt/data" \
    -v "$ROOT/Files:/workspace" \
    nousresearch/hermes-agent:latest profile create designer --clone --description "Handles UI direction, design docs, visual assets, image prompts, brand direction, and layout feedback." 2>&1)
  create_code=$?
  set -e
  if [ "$create_code" -ne 0 ]; then
    if docker run --rm --name "workframe-bootstrap-designer-show" --entrypoint hermes \
      -v "$ROOT/Agents:/opt/data" \
      -v "$ROOT/Files:/workspace" \
      nousresearch/hermes-agent:latest profile show designer >/dev/null 2>&1 && [ -f "$profile_config" ]; then
      echo "Profile designer already exists, continuing."
    else
      echo "Retrying profile create after cleaning incomplete registration: designer"
      clean_profile_orphan_designer
      docker run --rm --name "workframe-bootstrap-designer-retry" --entrypoint hermes \
        -v "$ROOT/Agents:/opt/data" \
        -v "$ROOT/Files:/workspace" \
        nousresearch/hermes-agent:latest profile create designer --clone --description "Handles UI direction, design docs, visual assets, image prompts, brand direction, and layout feedback." || {
        echo "$create_out" >&2
        echo "ERROR: failed to create profile designer" >&2
        exit 1
      }
    fi
  fi
fi

if [ -f "$ROOT/scripts/seed/profiles/designer/SOUL.md" ]; then
  mkdir -p "$ROOT/Agents/profiles/designer"
  cp "$ROOT/scripts/seed/profiles/designer/SOUL.md" "$ROOT/Agents/profiles/designer/SOUL.md"
fi


echo "Setting default profile to workframe-agent..."
docker run --rm --name "workframe-bootstrap-use" --entrypoint hermes \
  -v "$ROOT/Agents:/opt/data" \
  -v "$ROOT/Files:/workspace" \
  nousresearch/hermes-agent:latest profile use workframe-agent

echo "Full pack bootstrap complete. Start chat with: ./scripts/chat.sh"
docker run --rm --name "workframe-bootstrap-list" --entrypoint hermes \
  -v "$ROOT/Agents:/opt/data" \
  -v "$ROOT/Files:/workspace" \
  nousresearch/hermes-agent:latest profile list
