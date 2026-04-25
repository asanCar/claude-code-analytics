"""Tests for ingest_usage.py"""
import os
from unittest.mock import MagicMock, patch

import psycopg2
import pytest

import ingest_usage
from db import get_connection, insert_usage_snapshot

DB_URL = "postgresql://claude:changeme@localhost:5432/claude_analytics"


# --- parse_plan tests ---

def test_parse_plan_default():
    assert ingest_usage.parse_plan({}) == "PRO"


def test_parse_plan_max_5x():
    assert ingest_usage.parse_plan({"rateLimitTier": "max_5x_something"}) == "MAX5"


def test_parse_plan_max_20x():
    assert ingest_usage.parse_plan({"rateLimitTier": "max_20x_something"}) == "MAX20"


def test_parse_plan_subscription_max():
    assert ingest_usage.parse_plan({"subscriptionType": "max"}) == "MAX"


# --- fetch_usage tests ---

def test_fetch_usage_success():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"five_hour": {"utilization": 42.0}}
    with patch("ingest_usage.requests.get", return_value=mock_resp) as mock_get:
        result = ingest_usage.fetch_usage("sometoken")
    mock_get.assert_called_once()
    assert result == {"five_hour": {"utilization": 42.0}}


def test_fetch_usage_failure():
    with patch("ingest_usage.requests.get", side_effect=Exception("timeout")):
        result = ingest_usage.fetch_usage("sometoken")
    assert result is None


def test_fetch_usage_no_token():
    result = ingest_usage.fetch_usage("")
    assert result is None


# --- ingest_snapshots DB test ---

@pytest.fixture
def db_conn():
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DELETE FROM usage_snapshots")
    yield conn
    with conn.cursor() as cur:
        cur.execute("DELETE FROM usage_snapshots")
    conn.close()


def test_ingest_snapshots(db_conn):
    api_data = {
        "five_hour": {"utilization": 10.0, "resets_at": None},
        "seven_day": {"utilization": 20.0, "resets_at": None},
        "seven_day_opus": {"utilization": 30.0, "resets_at": None},
        "seven_day_sonnet": {"utilization": 40.0, "resets_at": None},
    }
    ingest_usage.ingest_snapshots(db_conn, api_data, "PRO")

    with db_conn.cursor() as cur:
        cur.execute("SELECT window_name, plan FROM usage_snapshots ORDER BY window_name")
        rows = cur.fetchall()

    assert len(rows) == 4
    window_names = {r[0] for r in rows}
    assert window_names == {"five_hour", "seven_day", "seven_day_opus", "seven_day_sonnet"}
    for _, plan in rows:
        assert plan == "PRO"
