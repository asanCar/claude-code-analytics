#!/usr/bin/env bash
set -euo pipefail

# Installs and loads the optional launchd agent that runs scripts/up.sh at login.
# Run once per machine. Pairs with scripts/uninstall-autostart.sh.

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMPL="$ROOT/scripts/com.claude-code-analytics.up.plist.tmpl"
PLIST_DST="$HOME/Library/LaunchAgents/com.claude-code-analytics.up.plist"
LABEL="com.claude-code-analytics.up"

DOCKER_BIN="$(command -v docker || true)"
if [[ -z "$DOCKER_BIN" ]]; then
    echo "install-autostart: docker not found in PATH" >&2
    exit 1
fi
DOCKER_DIR="$(dirname "$DOCKER_BIN")"
PATH_VALUE="$DOCKER_DIR:/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

mkdir -p "$(dirname "$PLIST_DST")"
sed \
    -e "s|__ROOT__|$ROOT|g" \
    -e "s|__DOCKER__|$DOCKER_BIN|g" \
    -e "s|__PATH__|$PATH_VALUE|g" \
    "$TMPL" > "$PLIST_DST"

if launchctl list | grep -q "$LABEL"; then
    launchctl unload "$PLIST_DST"
fi
launchctl load "$PLIST_DST"

echo "install-autostart: installed and loaded"
echo "  plist: $PLIST_DST"
echo "  log:   /tmp/claude-code-analytics-up.log"
