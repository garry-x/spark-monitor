# Agent Token Usage Metrics - Design Spec

**Date:** 2026-06-04
**Status:** Approved

## Overview

Collect token usage metrics from local AI coding agents (Claude Code and Codex) and expose them as Prometheus metrics for visualization in Grafana and the `spark-monitor monitor` CLI command.

## Data Sources

| Tool | Source Path | Format | Key Data |
|------|------------|--------|----------|
| Claude Code | `~/.claude/stats-cache.json` | JSON | `dailyModelTokens[]` — per-day, per-model token counts |
| Codex | `~/.codex/state_5.sqlite` → `threads` | SQLite (WAL) | `tokens_used`, `model`, `created_at` per thread |

### Access Pattern

- All reads are **read-only** — no writes to source files
- Claude Code: atomic `open()` + `json.load()`, catches `JSONDecodeError` for mid-write files
- Codex: SQLite `mode=ro` URI connection, WAL mode guarantees concurrency with live Codex process
- Scrape interval: 60s (configurable), each read < 10ms

### Safety

- Zero impact on running Codex or Claude Code processes
- SQLite WAL allows concurrent reads without blocking writes
- JSON read failures silently retry on next scrape cycle

## Metrics

### Cumulative Counter

```
# HELP spark_monitor_agent_tokens_total Total tokens used by local AI agents (cumulative)
# TYPE spark_monitor_agent_tokens_total counter
spark_monitor_agent_tokens_total{tool="claude-code", model="deepseek-v4-pro"} 122345678
spark_monitor_agent_tokens_total{tool="claude-code", model="deepseek-v4-flash"} 5432100
spark_monitor_agent_tokens_total{tool="codex", model="gpt-4o"} 8765432
```

### Daily Gauge

```
# HELP spark_monitor_agent_tokens_daily Tokens used per day (last 7 days retained)
# TYPE spark_monitor_agent_tokens_daily gauge
spark_monitor_agent_tokens_daily{tool="claude-code", model="deepseek-v4-pro", date="2026-06-04"} 156789
```

### Availability

```
# HELP spark_monitor_agent_exporter_up Agent exporter availability (1=up, 0=down)
# TYPE spark_monitor_agent_exporter_up gauge
spark_monitor_agent_exporter_up 1
```

## Architecture

```
~/.claude/stats-cache.json ──┐
                             ├──> agent_exporter (:9107) ──> Prometheus ──> Grafana
~/.codex/state_5.sqlite ────┘                            ──> CLI monitor "agent"
```

## File Changes

| Component | File | Action |
|-----------|------|--------|
| Exporter | `exporters/agent_exporter.py` | New — Python Prometheus exporter |
| Dockerfile | `Dockerfile.agent_exporter` | New — build image |
| Docker Compose | `docker-compose.yml` | Add agent_exporter service |
| Prometheus | `prometheus.yml` | Add agent_exporter scrape job |
| CLI | `spark-monitor` | Add `agent` category to `monitor` command |
| Grafana | `grafana/dashboards/dgxspark-overview.json` | Add agent token panels |
| Install | `spark-monitor` `cmd_install`/`cmd_upgrade` | Copy new files |

## Exporter Design

### Data Collection

**Claude Code** (`~/.claude/stats-cache.json`):
- Read `dailyModelTokens` array
- Sum all entries for cumulative counter
- Expose last 7 days as daily gauges
- Reset counters on tool restart via persistent state file (same pattern as vllm_exporter)

**Codex** (`~/.codex/state_5.sqlite`):
- `SELECT model, SUM(tokens_used) FROM threads WHERE archived=0 GROUP BY model` → cumulative
- `SELECT model, DATE(created_at) as date, SUM(tokens_used) FROM threads GROUP BY model, date` → daily
- Handle model column NULL values as "unknown"

### Exporter Options

```
--port           Exporter port (default: 9107)
--interval       Scrape interval in seconds (default: 60)
--claude-stats   Path to Claude stats-cache.json (default: ~/.claude/stats-cache.json)
--codex-db       Path to Codex state DB (default: ~/.codex/state_5.sqlite)
```

## CLI Monitor Integration

New `agent` category in `spark-monitor monitor`:

```
spark-monitor monitor agent        # Agent token metrics only
spark-monitor monitor agent -i 30  # 30s refresh
spark-monitor monitor all          # Includes agent section
```

Display:
- Per-tool token totals with model breakdown
- Daily token usage for current day
- Token rate (tokens/min) computed from delta between scrapes

## Grafana Integration

New panels in DGXSpark Overview dashboard:
1. **Agent Token Usage (Total)** — bar chart by tool/model — `spark_monitor_agent_tokens_total`
2. **Agent Daily Token Usage** — time series by tool/model — `spark_monitor_agent_tokens_daily`

## Self-Review

- [x] No placeholders/TODOs
- [x] Consistent with existing exporter patterns (vllm_exporter, system_exporter)
- [x] Scoped to single implementation plan
- [x] No ambiguous requirements
