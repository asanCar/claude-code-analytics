# Claude Code Analytics

Local monitoring stack for Claude Code token usage. Ingests session JSONL files into PostgreSQL and provides Grafana dashboards.

## Quick Start

1. Copy `.env.example` to `.env` and fill in values
2. Bring up the stack: `./scripts/up.sh` (installs the token-sync launchd agent and starts containers)
3. Open Grafana at http://localhost:3000 (default: admin/admin)
4. Tear everything down with `./scripts/down.sh`

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `POSTGRES_PASSWORD` | Yes | PostgreSQL password |
| `CLAUDE_DIR` | No | Override `~/.claude` path |
| `GRAFANA_PASSWORD` | No | Grafana admin password (default: admin) |

## OAuth token sync (macOS)

`ingest_usage.py` reads the Claude Code OAuth access token from `scraper/.token`,
which is mounted into the scraper container. The token rotates every few hours,
so a launchd agent keeps `scraper/.token` in sync with the live token in your
macOS Keychain.

`./scripts/up.sh` installs and loads the agent; `./scripts/down.sh` unloads it.
The agent runs `scripts/sync-token.sh` at load and every 30 minutes. Logs go to
`/tmp/claude-code-analytics-token-sync.log`.
