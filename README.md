# Claude Code Analytics

Local monitoring stack for Claude Code token usage. Ingests session JSONL files into PostgreSQL and provides Grafana dashboards.

## Quick Start

1. Copy `.env.example` to `.env` and fill in values
2. Run `docker compose up -d`
3. Open Grafana at http://localhost:3000 (default: admin/admin)

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `POSTGRES_PASSWORD` | Yes | PostgreSQL password |
| `CLAUDE_OAUTH_TOKEN` | No | Enables usage % tracking |
| `CLAUDE_DIR` | No | Override `~/.claude` path |
| `GRAFANA_PASSWORD` | No | Grafana admin password (default: admin) |
