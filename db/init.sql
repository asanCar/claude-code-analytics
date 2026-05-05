CREATE TABLE IF NOT EXISTS sessions (
    session_id        TEXT PRIMARY KEY,
    project           TEXT NOT NULL,
    project_path      TEXT,
    git_branch        TEXT,
    model             TEXT,
    started_at        TIMESTAMPTZ NOT NULL,
    ended_at          TIMESTAMPTZ,
    version           TEXT,
    is_subagent       BOOLEAN DEFAULT FALSE,
    parent_session_id TEXT REFERENCES sessions(session_id)
);

CREATE TABLE IF NOT EXISTS messages (
    message_uuid     TEXT PRIMARY KEY,
    session_id       TEXT NOT NULL REFERENCES sessions(session_id),
    timestamp        TIMESTAMPTZ NOT NULL,
    role             TEXT NOT NULL,
    prompt_type      TEXT NOT NULL,
    prompt_text      TEXT,
    tool_name        TEXT,
    bash_subcategory TEXT
);

-- Migration: add column to existing tables created before bash_subcategory was introduced.
ALTER TABLE messages ADD COLUMN IF NOT EXISTS bash_subcategory TEXT;

CREATE TABLE IF NOT EXISTS token_usage (
    message_uuid          TEXT PRIMARY KEY REFERENCES messages(message_uuid),
    model                 TEXT,
    input_tokens          INTEGER DEFAULT 0,
    output_tokens         INTEGER DEFAULT 0,
    cache_read_tokens     INTEGER DEFAULT 0,
    cache_creation_tokens INTEGER DEFAULT 0,
    service_tier          TEXT
);

CREATE TABLE IF NOT EXISTS usage_snapshots (
    id              SERIAL PRIMARY KEY,
    "timestamp"     TIMESTAMPTZ NOT NULL,
    window_name     TEXT NOT NULL,
    utilization_pct REAL NOT NULL,
    resets_at       TIMESTAMPTZ,
    plan            TEXT
);

CREATE TABLE IF NOT EXISTS scraper_state (
    file_path     TEXT PRIMARY KEY,
    last_offset   BIGINT DEFAULT 0,
    last_modified TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_token_usage_model ON token_usage(model);
CREATE INDEX IF NOT EXISTS idx_usage_snapshots_timestamp ON usage_snapshots(timestamp);
CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project);

-- ============================================================
-- Bash command classification (prototype; will move to scraper)
-- ============================================================

CREATE OR REPLACE FUNCTION classify_bash_part(cmd TEXT)
RETURNS TEXT AS $$
DECLARE
  c TEXT;
  inner_cmd TEXT;
BEGIN
  c := trim(cmd);
  IF c = '' OR c IS NULL THEN
    RETURN NULL;
  END IF;

  -- Strip leading comment lines (# ...\n, possibly several)
  c := regexp_replace(c, '^(\s*#[^\n]*(\n|$))+', '', '');
  c := trim(c);
  IF c = '' THEN
    RETURN NULL;
  END IF;

  -- Subshell assignment: VAR=$( ... ) -> classify the inner command
  IF c ~* '^[A-Za-z_][A-Za-z0-9_]*=\$\(' THEN
    inner_cmd := substring(c FROM '^[A-Za-z_][A-Za-z0-9_]*=\$\((.*)\)\s*$');
    IF inner_cmd IS NOT NULL THEN
      RETURN classify_bash_part(inner_cmd);
    END IF;
  END IF;

  -- Strip leading env-var prefixes: VAR=val [VAR2=val2 ...] cmd
  WHILE c ~ '^[A-Za-z_][A-Za-z0-9_]*=\S*\s+\S' LOOP
    c := regexp_replace(c, '^[A-Za-z_][A-Za-z0-9_]*=\S*\s+', '', '');
  END LOOP;

  -- No-op shell builtins: return NULL so the wrapper skips this part
  IF c ~* '^cd(\s|$)' THEN RETURN NULL; END IF;
  IF c ~* '^source\s' OR c ~ '^\.\s' THEN RETURN NULL; END IF;
  IF c ~* '^export\s' THEN RETURN NULL; END IF;

  -- 1. infra-write
  IF c ~* '^kubectl\s+(apply|delete|scale|rollout|exec|cp|drain|cordon|uncordon|edit|patch|replace|annotate|label|set)(\s|$)' THEN RETURN 'infra-write'; END IF;
  IF c ~* '^helm\s+(install|upgrade|rollback|uninstall|delete)(\s|$)' THEN RETURN 'infra-write'; END IF;
  IF c ~* '^terraform\s+(apply|destroy|import|state)(\s|$)' THEN RETURN 'infra-write'; END IF;
  IF c ~* '^docker\s+(push|run|stop|rm|kill|restart|exec|build|tag|create|cp)(\s|$)' THEN RETURN 'infra-write'; END IF;
  IF c ~* '^docker-compose\s+(up|down|stop|start|restart|build|exec)(\s|$)' THEN RETURN 'infra-write'; END IF;
  IF c ~* '^aws\s+\w+\s+(create|update|delete|put|run|start|stop|terminate)(\s|$)' THEN RETURN 'infra-write'; END IF;
  IF c ~* '^gcloud\s+\w+\s+(create|update|delete|deploy)(\s|$)' THEN RETURN 'infra-write'; END IF;
  IF c ~* '^systemctl\s+(start|stop|restart|reload|enable|disable)(\s|$)' THEN RETURN 'infra-write'; END IF;
  IF c ~* '^launchctl\s+(load|unload|kickstart|kill)(\s|$)' THEN RETURN 'infra-write'; END IF;

  -- 2. fileops
  IF c ~* '^(rm|mv|cp|touch|mkdir|rmdir|chmod|chown|chgrp|ln)(\s|$)' THEN RETURN 'fileops'; END IF;
  IF c ~* '^sed\s+-i(\s|$)' THEN RETURN 'fileops'; END IF;

  -- 3. deps
  IF c ~* '^(npm|yarn|pnpm|bun)\s+(install|add|i|remove|uninstall|upgrade|update)(\s|$)' THEN RETURN 'deps'; END IF;
  IF c ~* '^(pip|pip3|poetry|uv)\s+(install|add|sync|remove|uninstall|update|upgrade)(\s|$)' THEN RETURN 'deps'; END IF;
  IF c ~* '^cargo\s+(add|remove|update|install)(\s|$)' THEN RETURN 'deps'; END IF;
  IF c ~* '^(brew|apt|apt-get|yum|dnf)\s+(install|remove|upgrade|update)(\s|$)' THEN RETURN 'deps'; END IF;

  -- 4. git-write
  IF c ~* '^git\s+(commit|push|pull|fetch|merge|rebase|checkout|switch|cherry-pick|reset|stash|am|apply|revert|clean|init|clone|add|rm|mv|restore)(\s|$)' THEN RETURN 'git-write'; END IF;
  IF c ~* '^git\s+(branch|tag)\s+-(d|D|a)(\s|$)' THEN RETURN 'git-write'; END IF;
  IF c ~* '^gh\s+(pr|issue)\s+(create|merge|close|edit|comment|review|reopen)(\s|$)' THEN RETURN 'git-write'; END IF;
  IF c ~* '^gh\s+(repo|release|workflow)\s+(create|delete|edit)(\s|$)' THEN RETURN 'git-write'; END IF;

  -- 5. build (compilers, bundlers, formatters, linters)
  IF c ~* '^(make|cmake|tsc|webpack|vite|rollup|esbuild|swc|babel)(\s|$)' THEN RETURN 'build'; END IF;
  IF c ~* '^(npm|yarn|pnpm|bun)\s+(run\s+build|build|compile)(\s|$)' THEN RETURN 'build'; END IF;
  IF c ~* '^cargo\s+(build|check|clippy)(\s|$)' THEN RETURN 'build'; END IF;
  IF c ~* '^go\s+build(\s|$)' THEN RETURN 'build'; END IF;
  IF c ~* '^(prettier|eslint|ruff|black|gofmt|hclfmt|stylelint|biome)(\s|$)' THEN RETURN 'build'; END IF;
  IF c ~* '^terraform\s+fmt(\s|$)' THEN RETURN 'build'; END IF;

  -- 6. test
  IF c ~* '^(pytest|jest|vitest|mocha|rspec|phpunit|tox|nox)(\s|$)' THEN RETURN 'test'; END IF;
  IF c ~* '^(npm|yarn|pnpm|bun)\s+(test|run\s+test|t)(\s|$)' THEN RETURN 'test'; END IF;
  IF c ~* '^(go|cargo)\s+test(\s|$)' THEN RETURN 'test'; END IF;

  -- 7. exec
  IF c ~* '^(python|python3|node|deno|ruby|perl|java|php)(\s|$)' THEN RETURN 'exec'; END IF;
  IF c ~* '^(bun|go|cargo)\s+run(\s|$)' THEN RETURN 'exec'; END IF;
  IF c ~* '^\./[\w./-]+(\s|$)' THEN RETURN 'exec'; END IF;
  IF c ~* '^bash\s+[\w./-]+(\s|$)' THEN RETURN 'exec'; END IF;

  -- 8. db
  IF c ~* '^(psql|mysql|sqlite3?|redis-cli|mongosh|mongo|cqlsh)(\s|$)' THEN RETURN 'db'; END IF;

  -- 9. infra-read (catches read-only kubectl/docker/helm/etc.)
  IF c ~* '^(kubectl|kustomize|docker|docker-compose|helm|terraform|aws|gcloud|gsutil|systemctl|launchctl)(\s|$)' THEN RETURN 'infra-read'; END IF;

  -- 10. research (HTTP, API)
  IF c ~* '^(curl|wget|http|httpie)(\s|$)' THEN RETURN 'research'; END IF;
  IF c ~* '^gh\s+(api|pr\s+view|issue\s+view|repo\s+view|pr\s+list|issue\s+list|run\s+view|run\s+list)(\s|$)' THEN RETURN 'research'; END IF;

  -- 11. git-read
  IF c ~* '^git\s+(log|show|diff|status|blame|reflog|describe|cat-file|rev-parse|whatchanged|shortlog|grep)(\s|$)' THEN RETURN 'git-read'; END IF;
  IF c ~* '^git\s+(branch|tag|stash\s+list|stash\s+show|remote|config)(\s|$)' THEN RETURN 'git-read'; END IF;
  IF c ~* '^gh\s+(pr|issue)\s+(diff|status|checks)(\s|$)' THEN RETURN 'git-read'; END IF;

  -- 12. search
  IF c ~* '^(grep|rg|ack|ag|fgrep|egrep|zgrep)(\s|$)' THEN RETURN 'search'; END IF;
  IF c ~* '^sed\s+-n(\s|$)' THEN RETURN 'search'; END IF;
  IF c ~* '^awk(\s|$)' THEN RETURN 'search'; END IF;

  -- 13. read
  IF c ~* '^(cat|head|tail|less|more|bat|ls|find|tree|fd|stat|wc|file|du|df|which|whereis|type|echo)(\s|$)' THEN RETURN 'read'; END IF;

  -- Path-like exec fallback: first token contains a slash (e.g. tools/foo/bin/foo)
  IF c ~ '^[\w][\w./-]*/[\w./-]+(\s|$)' THEN RETURN 'exec'; END IF;

  RETURN 'bash-other';
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Splits a compound Bash command on &&, ||, ;, | and returns the
-- highest-priority subcategory among the parts (lower priority number wins).
CREATE OR REPLACE FUNCTION classify_bash(full_cmd TEXT)
RETURNS TEXT AS $$
DECLARE
  parts TEXT[];
  part TEXT;
  cat TEXT;
  best_priority INT := 999;
  best_cat TEXT := 'bash-other';
  cur_priority INT;
BEGIN
  IF full_cmd IS NULL OR trim(full_cmd) = '' THEN
    RETURN NULL;
  END IF;

  parts := regexp_split_to_array(full_cmd, '\s*(&&|\|\||;|\|)\s*');

  FOREACH part IN ARRAY parts LOOP
    IF trim(part) = '' THEN CONTINUE; END IF;
    cat := classify_bash_part(part);
    IF cat IS NULL THEN CONTINUE; END IF;
    cur_priority := CASE cat
      WHEN 'infra-write' THEN 1
      WHEN 'fileops'     THEN 2
      WHEN 'deps'        THEN 3
      WHEN 'git-write'   THEN 4
      WHEN 'build'       THEN 5
      WHEN 'test'        THEN 6
      WHEN 'exec'        THEN 7
      WHEN 'db'          THEN 8
      WHEN 'infra-read'  THEN 9
      WHEN 'research'    THEN 10
      WHEN 'git-read'    THEN 11
      WHEN 'search'      THEN 12
      WHEN 'read'        THEN 13
      ELSE 99
    END;

    IF cur_priority < best_priority THEN
      best_priority := cur_priority;
      best_cat := cat;
    END IF;
  END LOOP;

  RETURN best_cat;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- One-time backfill: classify any existing Bash messages that don't have a subcategory.
-- After this runs once, the scraper handles all new messages at insert time.
-- The classify_bash() function above is kept for ad-hoc / manual reclassification.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM messages WHERE tool_name = 'Bash' AND bash_subcategory IS NULL LIMIT 1) THEN
    UPDATE messages
       SET bash_subcategory = classify_bash(prompt_text)
     WHERE tool_name = 'Bash' AND bash_subcategory IS NULL;
  END IF;
END $$;

-- Drop the prototype materialized view (its job is now done by the column).
DROP VIEW IF EXISTS messages_classified;
DROP MATERIALIZED VIEW IF EXISTS bash_classifications;

-- View that rolls Bash subcategory + tool_name up into a top-level archetype.
--
-- Archetype catalogue (the value returned in the `archetype` column):
--   exploration        Reading / searching the codebase or repo state
--                      (Read, Grep, Glob; Bash: read, search, git-read).
--   active_coding      Modifying files (Edit, Write, MultiEdit).
--   shell_ops          Local shell side-effects: file ops, git writes,
--                      arbitrary exec (Bash: fileops, git-write, exec).
--   build_test         Compile / test / dependency operations
--                      (Bash: test, build, deps).
--   infra_ops          Infrastructure & database operations
--                      (Bash: infra-write, infra-read, db).
--   research           External information gathering
--                      (WebFetch, WebSearch, ToolSearch; Bash: research).
--   self_orchestration Claude organising its own work — spawning
--                      subagents (Task, Agent) AND managing its own
--                      todo list (TaskCreate / Update / Get / List /
--                      Output / Stop). Both are meta-cognition, not
--                      delegation in the human sense (TaskList has no
--                      recipient), hence "self".
--   mcp                Any MCP tool call (tool_name LIKE 'mcp__%').
--   other              Tool call that didn't match any rule above.
--   NULL               Non-tool messages (human_input, assistant_text,
--                      tool_result).
CREATE OR REPLACE VIEW messages_classified AS
SELECT
  m.*,
  CASE
    WHEN m.tool_name = 'Bash' THEN
      CASE m.bash_subcategory
        WHEN 'read'        THEN 'exploration'
        WHEN 'search'      THEN 'exploration'
        WHEN 'git-read'    THEN 'exploration'
        WHEN 'research'    THEN 'research'
        WHEN 'test'        THEN 'build_test'
        WHEN 'build'       THEN 'build_test'
        WHEN 'deps'        THEN 'build_test'
        WHEN 'infra-write' THEN 'infra_ops'
        WHEN 'infra-read'  THEN 'infra_ops'
        WHEN 'db'          THEN 'infra_ops'
        WHEN 'fileops'     THEN 'shell_ops'
        WHEN 'git-write'   THEN 'shell_ops'
        WHEN 'exec'        THEN 'shell_ops'
        ELSE 'shell_ops'
      END
    WHEN m.tool_name IN ('Read', 'Grep', 'Glob') THEN 'exploration'
    WHEN m.tool_name IN ('Edit', 'Write', 'MultiEdit') THEN 'active_coding'
    WHEN m.tool_name IN ('Task','TaskCreate','TaskUpdate','TaskGet','TaskList','TaskOutput','TaskStop','Agent') THEN 'self_orchestration'
    WHEN m.tool_name IN ('WebFetch','WebSearch','ToolSearch') THEN 'research'
    WHEN m.tool_name LIKE 'mcp__%' THEN 'mcp'
    WHEN m.tool_name IS NOT NULL THEN 'other'
    ELSE NULL
  END AS archetype
FROM messages m;
