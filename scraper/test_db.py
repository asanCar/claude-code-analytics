import os
import uuid
from datetime import datetime, timezone

import psycopg2
import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://claude:changeme@localhost:5432/claude_analytics")

import db

TEST_SESSION_ID = "test-session-" + str(uuid.uuid4())
TEST_MESSAGE_UUID = "test-msg-" + str(uuid.uuid4())
TEST_FILE_PATH = "/tmp/test-scraper-state-" + str(uuid.uuid4())

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 1, 1, 13, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def conn():
    c = db.get_connection()
    yield c
    # Cleanup in reverse FK order
    with c.cursor() as cur:
        cur.execute("DELETE FROM token_usage WHERE message_uuid LIKE 'test-msg-%'")
        cur.execute("DELETE FROM messages WHERE message_uuid LIKE 'test-msg-%'")
        cur.execute("DELETE FROM sessions WHERE session_id LIKE 'test-session-%'")
        cur.execute("DELETE FROM scraper_state WHERE file_path LIKE '/tmp/test-scraper-state-%'")
        cur.execute("DELETE FROM usage_snapshots WHERE window_name = 'test_window'")
    c.commit()
    c.close()


def base_session(session_id=None):
    return {
        "session_id": session_id or TEST_SESSION_ID,
        "project": "test-project",
        "git_branch": "main",
        "model": "claude-3",
        "started_at": NOW,
        "ended_at": NOW,
        "version": "1.0",
        "is_subagent": False,
        "parent_session_id": None,
    }


def base_message(message_uuid=None, session_id=None):
    return {
        "message_uuid": message_uuid or TEST_MESSAGE_UUID,
        "session_id": session_id or TEST_SESSION_ID,
        "timestamp": NOW,
        "role": "assistant",
        "prompt_type": "text",
        "prompt_text": "hello",
        "tool_name": None,
    }


def test_upsert_session_creates_new(conn):
    sid = "test-session-new-" + str(uuid.uuid4())
    data = base_session(session_id=sid)
    db.upsert_session(conn, data)
    conn.commit()
    with conn.cursor() as cur:
        cur.execute("SELECT project, model FROM sessions WHERE session_id = %s", (sid,))
        row = cur.fetchone()
    assert row is not None
    assert row[0] == "test-project"
    assert row[1] == "claude-3"


def test_upsert_session_updates_ended_at(conn):
    sid = "test-session-upd-" + str(uuid.uuid4())
    data = base_session(session_id=sid)
    db.upsert_session(conn, data)
    conn.commit()

    updated = base_session(session_id=sid)
    updated["ended_at"] = LATER
    updated["model"] = None  # should keep existing model via COALESCE
    db.upsert_session(conn, updated)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute("SELECT ended_at, model FROM sessions WHERE session_id = %s", (sid,))
        row = cur.fetchone()
    assert row[0].replace(tzinfo=timezone.utc) == LATER
    assert row[1] == "claude-3"


def test_insert_message_deduplicates(conn):
    sid = "test-session-msg-" + str(uuid.uuid4())
    db.upsert_session(conn, base_session(session_id=sid))
    conn.commit()

    mid = "test-msg-dup-" + str(uuid.uuid4())
    db.insert_message(conn, base_message(message_uuid=mid, session_id=sid))
    db.insert_message(conn, base_message(message_uuid=mid, session_id=sid))
    conn.commit()

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM messages WHERE message_uuid = %s", (mid,))
        count = cur.fetchone()[0]
    assert count == 1


def test_insert_token_usage(conn):
    sid = "test-session-tok-" + str(uuid.uuid4())
    db.upsert_session(conn, base_session(session_id=sid))
    conn.commit()

    mid = "test-msg-tok-" + str(uuid.uuid4())
    db.insert_message(conn, base_message(message_uuid=mid, session_id=sid))
    conn.commit()

    usage = {
        "message_uuid": mid,
        "model": "claude-3",
        "input_tokens": 100,
        "output_tokens": 50,
        "cache_read_tokens": 10,
        "cache_creation_tokens": 5,
        "service_tier": "default",
    }
    db.insert_token_usage(conn, usage)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute("SELECT input_tokens, output_tokens FROM token_usage WHERE message_uuid = %s", (mid,))
        row = cur.fetchone()
    assert row[0] == 100
    assert row[1] == 50


def test_scraper_state_roundtrip(conn):
    path = "/tmp/test-scraper-state-" + str(uuid.uuid4())
    db.update_scraper_state(conn, path, 100, NOW)
    conn.commit()

    state = db.get_scraper_state(conn, path)
    assert state["last_offset"] == 100

    db.update_scraper_state(conn, path, 200, LATER)
    conn.commit()

    state = db.get_scraper_state(conn, path)
    assert state["last_offset"] == 200
