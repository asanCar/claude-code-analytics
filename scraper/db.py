import os
import psycopg2


def get_connection():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def upsert_session(conn, data):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO sessions (session_id, project, git_branch, model, started_at, ended_at, version, is_subagent, parent_session_id)
            VALUES (%(session_id)s, %(project)s, %(git_branch)s, %(model)s, %(started_at)s, %(ended_at)s, %(version)s, %(is_subagent)s, %(parent_session_id)s)
            ON CONFLICT (session_id) DO UPDATE SET
                ended_at = GREATEST(sessions.ended_at, EXCLUDED.ended_at),
                model = COALESCE(EXCLUDED.model, sessions.model),
                git_branch = COALESCE(EXCLUDED.git_branch, sessions.git_branch),
                version = COALESCE(EXCLUDED.version, sessions.version)
        """, data)


def insert_message(conn, data):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO messages (message_uuid, session_id, timestamp, role, prompt_type, prompt_text, tool_name)
            VALUES (%(message_uuid)s, %(session_id)s, %(timestamp)s, %(role)s, %(prompt_type)s, %(prompt_text)s, %(tool_name)s)
            ON CONFLICT (message_uuid) DO NOTHING
        """, data)


def insert_token_usage(conn, data):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO token_usage (message_uuid, model, input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens, service_tier)
            VALUES (%(message_uuid)s, %(model)s, %(input_tokens)s, %(output_tokens)s, %(cache_read_tokens)s, %(cache_creation_tokens)s, %(service_tier)s)
            ON CONFLICT (message_uuid) DO NOTHING
        """, data)


def insert_usage_snapshot(conn, data):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO usage_snapshots (timestamp, window_name, utilization_pct, resets_at, plan)
            VALUES (%(timestamp)s, %(window_name)s, %(utilization_pct)s, %(resets_at)s, %(plan)s)
        """, data)


def update_scraper_state(conn, file_path, last_offset, last_modified):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO scraper_state (file_path, last_offset, last_modified)
            VALUES (%s, %s, %s)
            ON CONFLICT (file_path) DO UPDATE SET
                last_offset = EXCLUDED.last_offset,
                last_modified = EXCLUDED.last_modified
        """, (file_path, last_offset, last_modified))


def get_scraper_state(conn, file_path):
    with conn.cursor() as cur:
        cur.execute("SELECT last_offset, last_modified FROM scraper_state WHERE file_path = %s", (file_path,))
        row = cur.fetchone()
        if row:
            return {"last_offset": row[0], "last_modified": row[1]}
        return {"last_offset": 0, "last_modified": None}
