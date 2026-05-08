# Claude Code Analytics

Local monitoring stack for Claude Code token usage. Ingests session JSONL files into PostgreSQL and provides Grafana dashboards.

**Live site:** <https://asancar.github.io/claude-code-analytics/>

## Quick Start

1. Copy `.env.example` to `.env` and fill in values
2. Bring up the stack: `./scripts/up.sh` (installs the token-sync launchd agent and starts containers)
3. Open Grafana at http://localhost:3808 (default: admin/admin)
4. Tear everything down with `./scripts/down.sh`

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `POSTGRES_PASSWORD` | Yes | PostgreSQL password |
| `CLAUDE_DIR` | No | Override `~/.claude` path |
| `GRAFANA_PASSWORD` | No | Grafana admin password (default: admin) |

## OAuth token sync (macOS) — automatic

> Installed and loaded by `./scripts/up.sh`; unloaded by `./scripts/down.sh`. No
> manual steps required.

`ingest_usage.py` reads the Claude Code OAuth access token from `scraper/.token`,
which is mounted into the scraper container. The token rotates every few hours,
so a launchd agent keeps `scraper/.token` in sync with the live token in your
macOS Keychain.

The agent runs `scripts/sync-token.sh` at load and every 60 seconds. Logs go to
`/tmp/claude-code-analytics-token-sync.log`.

## Auto-start at login (macOS) — optional, manual

> Not installed by `up.sh`. Set this up yourself only if you want the stack to
> come up automatically on every login.

A launchd agent runs `scripts/up.sh` at login, waiting up to 5 minutes for
Docker to become available before bringing the stack up. The install script
renders `scripts/com.claude-code-analytics.up.plist.tmpl` with your project
path and the absolute path to `docker` from your `PATH`, copies the result
to `~/Library/LaunchAgents/`, and loads it. Logs go to
`/tmp/claude-code-analytics-up.log`.

**Install:**

```bash
./scripts/install-autostart.sh
```

**Remove:**

```bash
./scripts/uninstall-autostart.sh
```
