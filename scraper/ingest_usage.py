#!/usr/bin/env python3
"""Poll Anthropic OAuth usage API and store utilization snapshots."""
from datetime import datetime, timezone

import requests

from db import get_connection, insert_usage_snapshot

USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
API_USER_AGENT = "claude-code/2.0.32"
API_BETA = "oauth-2025-04-20"
TOKEN_FILE = "/run/secrets/claude_token"

WINDOWS = ["five_hour", "seven_day", "seven_day_opus", "seven_day_sonnet"]


def read_token():
    """Read OAuth access token from the mounted secret file."""
    try:
        with open(TOKEN_FILE) as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


def fetch_usage(token):
    """Fetch usage data from Anthropic OAuth API. Returns dict or None on failure."""
    if not token:
        print(f"[ingest_usage] No token at {TOKEN_FILE}, skipping")
        return None
    try:
        resp = requests.get(
            USAGE_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": API_USER_AGENT,
                "anthropic-beta": API_BETA,
                "Content-Type": "application/json",
            },
            timeout=8,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[ingest_usage] API call failed: {e}")
        return None


def parse_plan(data):
    """Detect plan from API response fields."""
    tier = data.get("rateLimitTier", "")
    sub = data.get("subscriptionType", "")
    if "max_20x" in tier:
        return "MAX20"
    if "max_5x" in tier:
        return "MAX5"
    if sub == "max":
        return "MAX"
    return "PRO"


def ingest_snapshots(conn, api_data, plan):
    """Insert one usage_snapshot row per window."""
    now = datetime.now(timezone.utc).isoformat()
    for window in WINDOWS:
        window_data = api_data.get(window) or {}
        utilization = window_data.get("utilization", 0)
        resets_at = window_data.get("resets_at")
        insert_usage_snapshot(conn, {
            "timestamp": now,
            "window_name": window,
            "utilization_pct": utilization,
            "resets_at": resets_at,
            "plan": plan,
        })


def main():
    print(f"[ingest_usage] {datetime.now(timezone.utc).isoformat()}")
    token = read_token()
    data = fetch_usage(token)
    if data is None:
        return

    plan = parse_plan(data)
    print(f"[ingest_usage] Plan: {plan}")

    conn = get_connection()
    conn.autocommit = True
    ingest_snapshots(conn, data, plan)
    conn.close()

    fh = (data.get("five_hour") or {}).get("utilization", 0)
    sd = (data.get("seven_day") or {}).get("utilization", 0)
    print(f"[ingest_usage] Stored: 5h={fh:.1f}% 7d={sd:.1f}% plan={plan}")


if __name__ == "__main__":
    main()
