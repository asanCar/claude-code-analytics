#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_DST="$HOME/Library/LaunchAgents/com.claude-code-analytics.token-sync.plist"
LABEL="com.claude-code-analytics.token-sync"

docker compose -f "$ROOT/docker-compose.yml" down

if launchctl list | grep -q "$LABEL"; then
    launchctl unload "$PLIST_DST"
fi
