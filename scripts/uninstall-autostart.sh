#!/usr/bin/env bash
set -euo pipefail

PLIST_DST="$HOME/Library/LaunchAgents/com.claude-code-analytics.up.plist"
LABEL="com.claude-code-analytics.up"

if launchctl list | grep -q "$LABEL"; then
    launchctl unload "$PLIST_DST"
fi
rm -f "$PLIST_DST"
echo "uninstall-autostart: removed"
