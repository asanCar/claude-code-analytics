import json
import pytest
from parser import (
    parse_line,
    classify_user_content,
    extract_tool_use_summary,
)


def make_line(type_, uuid="test-uuid", message=None, **kwargs):
    obj = {"type": type_, "uuid": uuid, "timestamp": "2024-01-01T00:00:00Z"}
    if message is not None:
        obj["message"] = message
    obj.update(kwargs)
    return json.dumps(obj)


# --- Skip tests ---

def test_skip_progress_line():
    line = make_line("progress")
    assert parse_line(line) is None


def test_skip_file_history_snapshot():
    line = make_line("file-history-snapshot")
    assert parse_line(line) is None


def test_skip_system_line():
    line = make_line("system")
    assert parse_line(line) is None


def test_skip_last_prompt():
    line = make_line("last-prompt")
    assert parse_line(line) is None


# --- User message tests ---

def test_user_human_input():
    msg = {"role": "user", "content": "Hello, Claude!"}
    line = make_line("user", message=msg)
    result = parse_line(line)
    assert result is not None
    assert result["role"] == "user"
    assert result["prompt_type"] == "human_input"
    assert result["prompt_text"] == "Hello, Claude!"
    assert result["tool_name"] is None


def test_user_tool_result():
    long_text = "x" * 300
    content = [{"type": "tool_result", "content": long_text}]
    msg = {"role": "user", "content": content}
    line = make_line("user", message=msg)
    result = parse_line(line)
    assert result is not None
    assert result["prompt_type"] == "tool_result"
    assert len(result["prompt_text"]) == 200


def test_user_tool_result_with_tool_reference():
    content = [
        {
            "type": "tool_result",
            "content": [
                {"type": "tool_reference", "tool_name": "Read"},
                {"type": "text", "text": "file contents here"},
            ],
        }
    ]
    msg = {"role": "user", "content": content}
    line = make_line("user", message=msg)
    result = parse_line(line)
    assert result is not None
    assert result["prompt_type"] == "tool_result"
    assert result["tool_name"] == "Read"


# --- Assistant message tests ---

def test_assistant_text():
    content = [
        {"type": "thinking", "thinking": "let me think..."},
        {"type": "text", "text": "Here is my answer."},
    ]
    usage = {"input_tokens": 100, "output_tokens": 50, "cache_read_input_tokens": 10, "cache_creation_input_tokens": 5}
    msg = {"role": "assistant", "content": content, "usage": usage, "model": "claude-3-5-sonnet-20241022"}
    line = make_line("assistant", message=msg)
    result = parse_line(line)
    assert result is not None
    assert result["role"] == "assistant"
    assert result["prompt_type"] == "assistant_text"
    assert result["prompt_text"] == "Here is my answer."
    assert result["tool_name"] is None
    assert "usage" in result
    assert result["usage"]["input_tokens"] == 100
    assert result["usage"]["output_tokens"] == 50
    assert result["usage"]["cache_read_tokens"] == 10
    assert result["usage"]["cache_creation_tokens"] == 5
    assert result["model"] == "claude-3-5-sonnet-20241022"


def test_assistant_tool_use():
    file_content = "A" * 5000
    content = [
        {
            "type": "tool_use",
            "name": "Write",
            "input": {"file_path": "/some/path/file.py", "content": file_content},
        }
    ]
    msg = {"role": "assistant", "content": content}
    line = make_line("assistant", message=msg)
    result = parse_line(line)
    assert result is not None
    assert result["prompt_type"] == "tool_use"
    assert result["tool_name"] == "Write"
    assert result["prompt_text"] == "/some/path/file.py"
    assert file_content not in result["prompt_text"]


# --- extract_tool_use_summary tests ---

def test_extract_tool_use_summary_bash():
    summary = extract_tool_use_summary("Bash", {"command": "ls -la"})
    assert summary == "ls -la"


def test_extract_tool_use_summary_read():
    summary = extract_tool_use_summary("Read", {"file_path": "/path/to/file.py"})
    assert summary == "/path/to/file.py"


def test_extract_tool_use_summary_edit():
    summary = extract_tool_use_summary("Edit", {"file_path": "/path/to/edit.py", "old_string": "foo", "new_string": "bar"})
    assert summary == "/path/to/edit.py"


def test_extract_tool_use_summary_grep():
    summary = extract_tool_use_summary("Grep", {"pattern": "def parse_line"})
    assert summary == "def parse_line"


def test_extract_tool_use_summary_glob():
    summary = extract_tool_use_summary("Glob", {"pattern": "**/*.py"})
    assert summary == "**/*.py"


def test_extract_tool_use_summary_unknown():
    big_input = {"data": "z" * 500}
    summary = extract_tool_use_summary("UnknownTool", big_input)
    assert len(summary) <= 200


# --- classify_user_content tests ---

def test_classify_user_content_string():
    prompt_type, prompt_text, tool_name = classify_user_content("Just a plain string")
    assert prompt_type == "human_input"
    assert prompt_text == "Just a plain string"
    assert tool_name is None


def test_classify_user_content_tool_result_string():
    content = [{"type": "tool_result", "content": "some output from a tool"}]
    prompt_type, prompt_text, tool_name = classify_user_content(content)
    assert prompt_type == "tool_result"
    assert prompt_text == "some output from a tool"
