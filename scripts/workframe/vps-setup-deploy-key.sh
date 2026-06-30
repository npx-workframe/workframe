#!/usr/bin/env bash
# Print deploy key for manual GitHub registration (read-only).
# Do not pipe this to APIs or commit the private key.
set -euo pipefail
KEY=~/.ssh/workframe_deploy
if [[ ! -f "$KEY" ]]; then
  ssh-keygen -t ed25519 -f "$KEY" -N "" -C "workframe-vps-deploy"
fi
chmod 700 ~/.ssh
chmod 600 "$KEY"
ssh-keyscan -t ed25519 github.com >> ~/.ssh/known_hosts 2>/dev/null || true
cat "${KEY}.pub"
