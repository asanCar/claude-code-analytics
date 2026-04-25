#!/bin/sh
set -e

echo "[scraper] Running initial ingestion..."
python /app/ingest_sessions.py || true
python /app/ingest_usage.py || true

echo "[scraper] Starting cron (every 5 min)..."
exec supercronic /app/crontab
