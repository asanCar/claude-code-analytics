#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_SRC="$ROOT/scripts/com.claude-code-analytics.token-sync.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.claude-code-analytics.token-sync.plist"
LABEL="com.claude-code-analytics.token-sync"

"$ROOT/scripts/sync-token.sh"

mkdir -p "$(dirname "$PLIST_DST")"
cp "$PLIST_SRC" "$PLIST_DST"

if launchctl list | grep -q "$LABEL"; then
    launchctl unload "$PLIST_DST"
fi
launchctl load "$PLIST_DST"

docker compose -f "$ROOT/docker-compose.yml" up -d --build
