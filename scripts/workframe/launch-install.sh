#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
START="$ROOT/scripts/start-install.sh"
PAUSE='read -r -p "Press Enter to close..." _'

launch_in_terminal() {
  local cmd="cd $(printf '%q' "$ROOT") && exec $(printf '%q' "$START"); echo; $PAUSE"
  case "$(uname -s)" in
    Darwin)
      local root_esc
      root_esc=$(printf %s "$ROOT" | sed "s/'/'\\''/g")
      osascript <<APPLESCRIPT >/dev/null 2>&1
tell application "Terminal"
  activate
  do script "cd '${root_esc}' && exec './scripts/start-install.sh'"
end tell
APPLESCRIPT
      return 0
      ;;
    Linux)
      if command -v gnome-terminal >/dev/null 2>&1; then
        gnome-terminal -- bash -lc "$cmd"
        return 0
      fi
      if command -v konsole >/dev/null 2>&1; then
        konsole -e bash -lc "$cmd"
        return 0
      fi
      if command -v xfce4-terminal >/dev/null 2>&1; then
        xfce4-terminal -e bash -lc "$cmd"
        return 0
      fi
      if command -v xterm >/dev/null 2>&1; then
        xterm -e bash -lc "$cmd"
        return 0
      fi
      ;;
  esac
  return 1
}

if [ -z "${WORKFRAME_LAUNCH_IN_PLACE:-}" ]; then
  if launch_in_terminal; then
    echo "Opened Phase B installer in a new terminal."
    echo "Complete Hermes setup there — browser chat opens automatically at /chat when done."
    exit 0
  fi
fi

echo "Running Phase B installer in this terminal..."
exec "$START"
