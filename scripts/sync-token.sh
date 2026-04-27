#!/usr/bin/env bash
set -euo pipefail

# Reads the current Claude Code OAuth access token from the macOS Keychain
# and writes it to scraper/.token so the Dockerised scraper can mount it.
# Intended to be run periodically by launchd; safe to run by hand too.

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/scraper/.token"

TOKEN=$(security find-generic-password -s "Claude Code-credentials" -w \
  | /usr/bin/python3 -c "import sys, json; print(json.load(sys.stdin)['claudeAiOauth']['accessToken'])")

if [[ -z "$TOKEN" ]]; then
  echo "sync-token: empty token from Keychain" >&2
  exit 1
fi

umask 077
TMP="$(mktemp "$OUT.XXXXXX")"
printf '%s' "$TOKEN" > "$TMP"
mv "$TMP" "$OUT"
echo "sync-token: wrote $OUT"
