import json
import os
import tempfile
import uuid

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://claude:changeme@localhost:5432/claude_analytics")

import db
from ingest_sessions import (
    discover_jsonl_files,
    extract_project_name,
    extract_session_info,
    process_file,
)

USER_LINE = json.dumps({
    "type": "user",
    "uuid": "u1",
    "timestamp": "2026-04-25T10:00:00Z",
    "sessionId": "sess-proc-1",
    "version": "2.1.79",
    "gitBranch": "main",
    "cwd": "/Users/test/proj",
    "message": {"role": "user", "content": "hello"},
})

ASSISTANT_LINE = json.dumps({
    "type": "assistant",
    "uuid": "a1",
    "timestamp": "2026-04-25T10:00:01Z",
    "sessionId": "sess-proc-1",
    "version": "2.1.79",
    "gitBranch": "main",
    "cwd": "/Users/test/proj",
    "message": {
        "model": "claude-sonnet-4-6",
        "role": "assistant",
        "content": [{"type": "text", "text": "hi there"}],
        "usage": {
            "input_tokens": 10,
            "output_tokens": 5,
            "cache_read_input_tokens": 100,
            "cache_creation_input_tokens": 50,
            "service_tier": "standard",
        },
    },
})


@pytest.fixture(scope="module")
def conn():
    c = db.get_connection()
    c.autocommit = True
    yield c
    with c.cursor() as cur:
        cur.execute("DELETE FROM token_usage WHERE message_uuid IN ('u1', 'a1', 'u2', 'a2')")
        cur.execute("DELETE FROM messages WHERE message_uuid IN ('u1', 'a1', 'u2', 'a2')")
        cur.execute("DELETE FROM sessions WHERE session_id = 'sess-proc-1'")
        cur.execute("DELETE FROM scraper_state WHERE file_path LIKE '/tmp/test-ingest-%'")
    c.close()


def test_extract_project_name():
    # Claude encodes '/' as '-'; the last segment of the encoded dir is the project name.
    # 'my-project' encodes as 'my-project' (single '-' is ambiguous with path sep),
    # so the last dash-split segment is 'project'.
    path = "/data/claude/projects/-Users-alex-Workspace-myproject/abc123.jsonl"
    assert extract_project_name(path) == "myproject"


def test_extract_project_name_nested():
    # Subagent path still resolves to same project dir segment.
    path = "/data/claude/projects/-Users-alex-Workspace-myproject/abc123/subagents/def456.jsonl"
    assert extract_project_name(path) == "myproject"


def test_extract_session_info_top_level():
    sid = str(uuid.uuid4())
    path = f"/data/claude/projects/-Users-alex-proj/{sid}.jsonl"
    info = extract_session_info(path)
    assert info["is_subagent"] is False
    assert info["parent_session_id"] is None
    assert info["file_session_id"] == sid


def test_extract_session_info_subagent():
    parent_id = str(uuid.uuid4())
    child_id = str(uuid.uuid4())
    path = f"/data/claude/projects/-Users-alex-proj/{parent_id}/subagents/{child_id}.jsonl"
    info = extract_session_info(path)
    assert info["is_subagent"] is True
    assert info["parent_session_id"] == parent_id
    assert info["file_session_id"] == child_id


def test_discover_jsonl_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        subdir = os.path.join(tmpdir, "proj-a")
        os.makedirs(subdir)
        jsonl_file = os.path.join(subdir, "session1.jsonl")
        json_file = os.path.join(subdir, "session2.json")
        open(jsonl_file, "w").close()
        open(json_file, "w").close()

        found = discover_jsonl_files(tmpdir)
        assert jsonl_file in found
        assert json_file not in found


def test_process_file_creates_session_and_messages(conn):
    with tempfile.NamedTemporaryFile(
        prefix="test-ingest-", suffix=".jsonl", mode="w", delete=False
    ) as f:
        f.write(USER_LINE + "\n")
        f.write(ASSISTANT_LINE + "\n")
        filepath = f.name

    try:
        process_file(conn, filepath, "my-project", False, None)

        with conn.cursor() as cur:
            cur.execute("SELECT project, model, git_branch FROM sessions WHERE session_id = 'sess-proc-1'")
            row = cur.fetchone()
        assert row is not None
        assert row[0] == "my-project"
        assert row[1] == "claude-sonnet-4-6"
        assert row[2] == "main"

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM messages WHERE session_id = 'sess-proc-1'")
            count = cur.fetchone()[0]
        assert count == 2

        with conn.cursor() as cur:
            cur.execute("SELECT input_tokens, output_tokens, cache_read_tokens FROM token_usage WHERE message_uuid = 'a1'")
            row = cur.fetchone()
        assert row is not None
        assert row[0] == 10
        assert row[1] == 5
        assert row[2] == 100

        with conn.cursor() as cur:
            cur.execute("SELECT last_offset FROM scraper_state WHERE file_path = %s", (filepath,))
            row = cur.fetchone()
        assert row is not None
        assert row[0] > 0
    finally:
        os.unlink(filepath)


def test_process_file_incremental(conn):
    with tempfile.NamedTemporaryFile(
        prefix="test-ingest-", suffix=".jsonl", mode="w", delete=False
    ) as f:
        f.write(USER_LINE + "\n")
        filepath = f.name

    try:
        process_file(conn, filepath, "my-project", False, None)

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM messages WHERE session_id = 'sess-proc-1'")
            count_after_first = cur.fetchone()[0]

        line2_user = json.dumps({
            "type": "user",
            "uuid": "u2",
            "timestamp": "2026-04-25T10:01:00Z",
            "sessionId": "sess-proc-1",
            "version": "2.1.79",
            "gitBranch": "main",
            "cwd": "/Users/test/proj",
            "message": {"role": "user", "content": "follow up"},
        })
        line2_asst = json.dumps({
            "type": "assistant",
            "uuid": "a2",
            "timestamp": "2026-04-25T10:01:01Z",
            "sessionId": "sess-proc-1",
            "version": "2.1.79",
            "gitBranch": "main",
            "cwd": "/Users/test/proj",
            "message": {
                "model": "claude-sonnet-4-6",
                "role": "assistant",
                "content": [{"type": "text", "text": "sure"}],
                "usage": {
                    "input_tokens": 20,
                    "output_tokens": 3,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                    "service_tier": "standard",
                },
            },
        })

        with open(filepath, "a") as f:
            f.write(line2_user + "\n")
            f.write(line2_asst + "\n")

        process_file(conn, filepath, "my-project", False, None)

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM messages WHERE session_id = 'sess-proc-1'")
            count_after_second = cur.fetchone()[0]

        assert count_after_second == count_after_first + 2
    finally:
        os.unlink(filepath)
