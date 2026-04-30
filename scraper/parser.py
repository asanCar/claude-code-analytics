import json

from bash_classifier import classify_bash

SKIP_TYPES = {"progress", "file-history-snapshot", "system", "last-prompt"}


def parse_line(raw_line):
    """Parse a single JSONL line. Returns a dict or None if the line should be skipped."""
    obj = json.loads(raw_line)
    line_type = obj.get("type")

    if line_type in SKIP_TYPES:
        return None

    if line_type not in ("user", "assistant"):
        return None

    msg = obj.get("message")
    if not msg:
        return None

    uuid = obj.get("uuid")
    if not uuid:
        return None

    session_meta = {
        "sessionId": obj.get("sessionId"),
        "version": obj.get("version"),
        "gitBranch": obj.get("gitBranch"),
        "cwd": obj.get("cwd"),
    }

    timestamp = obj.get("timestamp")
    role = msg.get("role", line_type)
    content = msg.get("content", "")

    if role == "user":
        prompt_type, prompt_text, tool_name = classify_user_content(content)
    else:
        prompt_type, prompt_text, tool_name = _classify_assistant_content(content)

    bash_subcategory = (
        classify_bash(prompt_text)
        if prompt_type == "tool_use" and tool_name == "Bash"
        else None
    )

    result = {
        "uuid": uuid,
        "timestamp": timestamp,
        "role": role,
        "prompt_type": prompt_type,
        "prompt_text": prompt_text,
        "tool_name": tool_name,
        "bash_subcategory": bash_subcategory,
        "session_meta": session_meta,
    }

    if role == "assistant":
        usage = msg.get("usage")
        if usage:
            result["usage"] = {
                "model": msg.get("model"),
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
                "cache_creation_tokens": usage.get("cache_creation_input_tokens", 0),
                "service_tier": usage.get("service_tier"),
            }
        result["model"] = msg.get("model")

    return result


def classify_user_content(content):
    """Classify user message content into (prompt_type, prompt_text, tool_name)."""
    if isinstance(content, str):
        return "human_input", content, None

    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_result":
                tool_name = _extract_tool_name_from_result(block)
                text = _extract_tool_result_text(block)
                return "tool_result", text[:200], tool_name

    return "human_input", str(content)[:200], None


def _extract_tool_name_from_result(block):
    """Extract tool name from a tool_result block."""
    inner = block.get("content", "")
    if isinstance(inner, list):
        for sub in inner:
            if isinstance(sub, dict) and sub.get("type") == "tool_reference":
                return sub.get("tool_name")
    return None


def _extract_tool_result_text(block):
    """Extract displayable text from a tool_result block."""
    inner = block.get("content", "")
    if isinstance(inner, str):
        return inner
    if isinstance(inner, list):
        texts = []
        for sub in inner:
            if isinstance(sub, dict):
                if sub.get("type") == "text":
                    texts.append(sub.get("text", ""))
                elif sub.get("type") == "tool_reference":
                    texts.append(f"[{sub.get('tool_name', 'unknown')}]")
        return " ".join(texts)
    return str(inner)


def _classify_assistant_content(content):
    """Classify assistant message content blocks."""
    if isinstance(content, str):
        return "assistant_text", content, None

    if not isinstance(content, list):
        return "assistant_text", str(content)[:200], None

    tool_uses = []
    texts = []

    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "tool_use":
            tool_uses.append(block)
        elif block_type == "text":
            texts.append(block.get("text", ""))

    if tool_uses:
        first = tool_uses[0]
        name = first.get("name", "unknown")
        summary = extract_tool_use_summary(name, first.get("input", {}))
        return "tool_use", summary, name

    if texts:
        return "assistant_text", "\n".join(texts), None

    return "assistant_text", "", None


def extract_tool_use_summary(tool_name, tool_input):
    """Extract a short summary from tool_use input, avoiding storing large file contents."""
    if tool_name in ("Read", "Write", "Edit"):
        return tool_input.get("file_path", str(tool_input)[:200])

    if tool_name == "Bash":
        return tool_input.get("command", str(tool_input)[:200])

    if tool_name in ("Grep", "Glob"):
        return tool_input.get("pattern", str(tool_input)[:200])

    return str(tool_input)[:200]
