#!/bin/sh
# Hermes sets HERMES_WRITE_SAFE_ROOT=/opt/data — user artifacts must resolve under it.
# Bind host Files at /opt/data/workspace; keep /workspace as a symlink for agents and API.
mkdir -p /opt/data/workspace
if [ -L /workspace ] || [ ! -e /workspace ]; then
  rm -rf /workspace 2>/dev/null || true
  ln -sfn /opt/data/workspace /workspace
fi
