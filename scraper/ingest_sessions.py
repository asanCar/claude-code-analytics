#!/usr/bin/env python3
"""Ingest Claude Code JSONL session files into PostgreSQL."""
import os
import re
import glob
from datetime import datetime, timezone

from db import get_connection, upsert_session, insert_message, insert_token_usage, update_scraper_state, get_scraper_state
from parser import parse_line

CLAUDE_DIR = os.environ.get("CLAUDE_DIR", "/data/claude")
PROJECTS_DIR = os.path.join(CLAUDE_DIR, "projects")


def discover_jsonl_files(projects_dir):
    """Find all .jsonl files under the projects directory."""
    return sorted(glob.glob(os.path.join(projects_dir, "**", "*.jsonl"), recursive=True))


def extract_project_name(filepath):
    """Extract project name from path like /data/claude/projects/-Users-alex-Workspace-myproject/...

    Claude encodes the cwd path by replacing '/' with '-'. The last dash-delimited
    segment of the directory name is used as the project identifier.
    """
    parts = filepath.split("/projects/")
    if len(parts) < 2:
        return "unknown"
    after_projects = parts[1]
    project_dir = after_projects.split("/")[0]
    segments = project_dir.split("-")
    return segments[-1] if segments else project_dir


def extract_session_info(filepath):
    """Determine if file is a top-level session or subagent, extract IDs."""
    if "/subagents/" in filepath:
        parent_match = re.search(r"/([0-9a-f-]{36})/subagents/", filepath)
        parent_id = parent_match.group(1) if parent_match else None
        filename = os.path.basename(filepath).replace(".jsonl", "")
        return {
            "is_subagent": True,
            "parent_session_id": parent_id,
            "file_session_id": filename,
        }

    filename = os.path.basename(filepath).replace(".jsonl", "")
    return {
        "is_subagent": False,
        "parent_session_id": None,
        "file_session_id": filename,
    }


def process_file(conn, filepath, project, is_subagent, parent_session_id):
    """Process a single JSONL file, reading incrementally from last offset."""
    state = get_scraper_state(conn, filepath)
    last_offset = state["last_offset"]

    file_size = os.path.getsize(filepath)
    if file_size <= last_offset:
        return

    session_id = None
    model = None
    version = None
    git_branch = None
    first_ts = None
    last_ts = None

    with open(filepath, "r") as f:
        f.seek(last_offset)
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                parsed = parse_line(line)
            except Exception:
                continue

            if parsed is None:
                continue

            meta = parsed.get("session_meta", {})
            if not session_id:
                session_id = meta.get("sessionId") or extract_session_info(filepath)["file_session_id"]
            if meta.get("version"):
                version = meta["version"]
            if meta.get("gitBranch"):
                git_branch = meta["gitBranch"]
            if parsed.get("model"):
                model = parsed["model"]

            ts = parsed["timestamp"]
            if not first_ts or ts < first_ts:
                first_ts = ts
            if not last_ts or ts > last_ts:
                last_ts = ts

            upsert_session(conn, {
                "session_id": session_id,
                "project": project,
                "git_branch": git_branch,
                "model": model,
                "started_at": first_ts,
                "ended_at": last_ts,
                "version": version,
                "is_subagent": is_subagent,
                "parent_session_id": parent_session_id,
            })

            insert_message(conn, {
                "message_uuid": parsed["uuid"],
                "session_id": session_id,
                "timestamp": ts,
                "role": parsed["role"],
                "prompt_type": parsed["prompt_type"],
                "prompt_text": parsed["prompt_text"],
                "tool_name": parsed["tool_name"],
            })

            if parsed.get("usage"):
                insert_token_usage(conn, {
                    "message_uuid": parsed["uuid"],
                    **parsed["usage"],
                })

        new_offset = f.tell()

    mtime = datetime.fromtimestamp(os.path.getmtime(filepath), tz=timezone.utc).isoformat()
    update_scraper_state(conn, filepath, new_offset, mtime)


def main():
    print(f"[ingest_sessions] {datetime.now(timezone.utc).isoformat()}")

    if not os.path.isdir(PROJECTS_DIR):
        print(f"[ingest_sessions] Projects dir not found: {PROJECTS_DIR}")
        return

    conn = get_connection()
    conn.autocommit = True

    files = discover_jsonl_files(PROJECTS_DIR)
    print(f"[ingest_sessions] Found {len(files)} JSONL files")

    for filepath in files:
        project = extract_project_name(filepath)
        info = extract_session_info(filepath)

        if info["is_subagent"] and info["parent_session_id"]:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM sessions WHERE session_id = %s", (info["parent_session_id"],))
                if not cur.fetchone():
                    continue

        try:
            process_file(conn, filepath, project, info["is_subagent"], info["parent_session_id"])
        except Exception as e:
            print(f"[ingest_sessions] Error processing {filepath}: {e}")

    conn.close()
    print("[ingest_sessions] Done")


if __name__ == "__main__":
    main()
