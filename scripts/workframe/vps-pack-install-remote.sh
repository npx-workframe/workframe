#!/usr/bin/env bash
# DEPRECATED wrapper — VPS sign-off = reset-vps-runtime.sh with pack tarball.
# Usage: bash vps-pack-install-remote.sh /tmp/create-workframe.tgz [MyBusiness] [/opt/workframe] [2]
set -euo pipefail
TGZ="${1:?pack tarball required}"
PROJECT="${2:-MyBusiness}"
export WORKFRAME_INSTALL_ROOT="${3:-/opt/workframe}"
export WORKFRAME_PROJECT_NAME="$PROJECT"
export WORKFRAME_SLOT="${4:-2}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec bash "$SCRIPT_DIR/reset-vps-runtime.sh" "$TGZ"
