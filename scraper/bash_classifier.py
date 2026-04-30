"""Classify Bash commands by intent.

For compound commands (joined with &&, ||, ;, |) the highest-priority part wins:
state-mutating actions outrank read-only inspection.
"""
import re

BASH_PRIORITY = {
    "infra-write": 1,
    "fileops":     2,
    "deps":        3,
    "git-write":   4,
    "build":       5,
    "test":        6,
    "exec":        7,
    "db":          8,
    "infra-read":  9,
    "research":   10,
    "git-read":   11,
    "search":     12,
    "read":       13,
}

_PATTERNS = [
    # 1. infra-write
    (re.compile(r"^kubectl\s+(apply|delete|scale|rollout|exec|cp|drain|cordon|uncordon|edit|patch|replace|annotate|label|set)(\s|$)", re.I), "infra-write"),
    (re.compile(r"^helm\s+(install|upgrade|rollback|uninstall|delete)(\s|$)", re.I), "infra-write"),
    (re.compile(r"^terraform\s+(apply|destroy|import|state)(\s|$)", re.I), "infra-write"),
    (re.compile(r"^docker\s+(push|run|stop|rm|kill|restart|exec|build|tag|create|cp)(\s|$)", re.I), "infra-write"),
    (re.compile(r"^docker-compose\s+(up|down|stop|start|restart|build|exec)(\s|$)", re.I), "infra-write"),
    (re.compile(r"^aws\s+\w+\s+(create|update|delete|put|run|start|stop|terminate)(\s|$)", re.I), "infra-write"),
    (re.compile(r"^gcloud\s+\w+\s+(create|update|delete|deploy)(\s|$)", re.I), "infra-write"),
    (re.compile(r"^systemctl\s+(start|stop|restart|reload|enable|disable)(\s|$)", re.I), "infra-write"),
    (re.compile(r"^launchctl\s+(load|unload|kickstart|kill)(\s|$)", re.I), "infra-write"),

    # 2. fileops
    (re.compile(r"^(rm|mv|cp|touch|mkdir|rmdir|chmod|chown|chgrp|ln)(\s|$)", re.I), "fileops"),
    (re.compile(r"^sed\s+-i(\s|$)", re.I), "fileops"),

    # 3. deps
    (re.compile(r"^(npm|yarn|pnpm|bun)\s+(install|add|i|remove|uninstall|upgrade|update)(\s|$)", re.I), "deps"),
    (re.compile(r"^(pip|pip3|poetry|uv)\s+(install|add|sync|remove|uninstall|update|upgrade)(\s|$)", re.I), "deps"),
    (re.compile(r"^cargo\s+(add|remove|update|install)(\s|$)", re.I), "deps"),
    (re.compile(r"^(brew|apt|apt-get|yum|dnf)\s+(install|remove|upgrade|update)(\s|$)", re.I), "deps"),

    # 4. git-write
    (re.compile(r"^git\s+(commit|push|pull|fetch|merge|rebase|checkout|switch|cherry-pick|reset|stash|am|apply|revert|clean|init|clone|add|rm|mv|restore)(\s|$)", re.I), "git-write"),
    (re.compile(r"^git\s+(branch|tag)\s+-(d|D|a)(\s|$)", re.I), "git-write"),
    (re.compile(r"^gh\s+(pr|issue)\s+(create|merge|close|edit|comment|review|reopen)(\s|$)", re.I), "git-write"),
    (re.compile(r"^gh\s+(repo|release|workflow)\s+(create|delete|edit)(\s|$)", re.I), "git-write"),

    # 5. build
    (re.compile(r"^(make|cmake|tsc|webpack|vite|rollup|esbuild|swc|babel)(\s|$)", re.I), "build"),
    (re.compile(r"^(npm|yarn|pnpm|bun)\s+(run\s+build|build|compile)(\s|$)", re.I), "build"),
    (re.compile(r"^cargo\s+(build|check|clippy)(\s|$)", re.I), "build"),
    (re.compile(r"^go\s+build(\s|$)", re.I), "build"),
    (re.compile(r"^(prettier|eslint|ruff|black|gofmt|hclfmt|stylelint|biome)(\s|$)", re.I), "build"),
    (re.compile(r"^terraform\s+fmt(\s|$)", re.I), "build"),

    # 6. test
    (re.compile(r"^(pytest|jest|vitest|mocha|rspec|phpunit|tox|nox)(\s|$)", re.I), "test"),
    (re.compile(r"^(npm|yarn|pnpm|bun)\s+(test|run\s+test|t)(\s|$)", re.I), "test"),
    (re.compile(r"^(go|cargo)\s+test(\s|$)", re.I), "test"),

    # 7. exec
    (re.compile(r"^(python|python3|node|deno|ruby|perl|java|php)(\s|$)", re.I), "exec"),
    (re.compile(r"^(bun|go|cargo)\s+run(\s|$)", re.I), "exec"),
    (re.compile(r"^\./[\w./-]+(\s|$)"), "exec"),
    (re.compile(r"^bash\s+[\w./-]+(\s|$)", re.I), "exec"),

    # 8. db
    (re.compile(r"^(psql|mysql|sqlite3?|redis-cli|mongosh|mongo|cqlsh)(\s|$)", re.I), "db"),

    # 9. infra-read
    (re.compile(r"^(kubectl|kustomize|docker|docker-compose|helm|terraform|aws|gcloud|gsutil|systemctl|launchctl)(\s|$)", re.I), "infra-read"),

    # 10. research
    (re.compile(r"^(curl|wget|http|httpie)(\s|$)", re.I), "research"),
    (re.compile(r"^gh\s+(api|pr\s+view|issue\s+view|repo\s+view|pr\s+list|issue\s+list|run\s+view|run\s+list)(\s|$)", re.I), "research"),

    # 11. git-read
    (re.compile(r"^git\s+(log|show|diff|status|blame|reflog|describe|cat-file|rev-parse|whatchanged|shortlog|grep)(\s|$)", re.I), "git-read"),
    (re.compile(r"^git\s+(branch|tag|stash\s+list|stash\s+show|remote|config)(\s|$)", re.I), "git-read"),
    (re.compile(r"^gh\s+(pr|issue)\s+(diff|status|checks)(\s|$)", re.I), "git-read"),

    # 12. search
    (re.compile(r"^(grep|rg|ack|ag|fgrep|egrep|zgrep)(\s|$)", re.I), "search"),
    (re.compile(r"^sed\s+-n(\s|$)", re.I), "search"),
    (re.compile(r"^awk(\s|$)", re.I), "search"),

    # 13. read
    (re.compile(r"^(cat|head|tail|less|more|bat|ls|find|tree|fd|stat|wc|file|du|df|which|whereis|type|echo)(\s|$)", re.I), "read"),
]

_NOOP_PATTERNS = [
    re.compile(r"^cd(\s|$)", re.I),
    re.compile(r"^source\s", re.I),
    re.compile(r"^\.\s"),
    re.compile(r"^export\s", re.I),
]

_COMMENT_PREFIX = re.compile(r"^(\s*#[^\n]*(\n|$))+")
_ENV_PREFIX = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=\S*\s+(?=\S)")
_SUBSHELL_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=\$\((.*)\)\s*$", re.S)
_PATH_LIKE_EXEC = re.compile(r"^[\w][\w./-]*/[\w./-]+(\s|$)")
_SPLIT = re.compile(r"\s*(&&|\|\||;|\|)\s*")
_SEPARATORS = {"&&", "||", ";", "|"}


def classify_bash_part(cmd):
    """Classify a single Bash command segment. Returns subcategory or None."""
    if cmd is None:
        return None
    c = cmd.strip()
    if not c:
        return None

    c = _COMMENT_PREFIX.sub("", c).strip()
    if not c:
        return None

    m = _SUBSHELL_ASSIGN.match(c)
    if m:
        return classify_bash_part(m.group(1))

    while True:
        new_c = _ENV_PREFIX.sub("", c, count=1)
        if new_c == c:
            break
        c = new_c

    for p in _NOOP_PATTERNS:
        if p.match(c):
            return None

    for pattern, category in _PATTERNS:
        if pattern.match(c):
            return category

    if _PATH_LIKE_EXEC.match(c):
        return "exec"

    return "bash-other"


def classify_bash(full_cmd):
    """Classify a Bash command (possibly compound). Highest-priority subcategory wins."""
    if full_cmd is None or not full_cmd.strip():
        return None

    parts = [p for p in _SPLIT.split(full_cmd) if p and p not in _SEPARATORS]

    best_priority = float("inf")
    best_cat = "bash-other"

    for part in parts:
        if not part.strip():
            continue
        cat = classify_bash_part(part)
        if cat is None:
            continue
        pri = BASH_PRIORITY.get(cat, 99)
        if pri < best_priority:
            best_priority = pri
            best_cat = cat

    return best_cat
