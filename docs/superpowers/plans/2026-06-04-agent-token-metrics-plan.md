# Agent Token Usage Metrics - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collect token usage from local AI agents (Claude Code, Codex) and expose as Prometheus metrics for Grafana and CLI monitor display.

**Architecture:** New `agent_exporter.py` reads `~/.claude/stats-cache.json` (JSON) and `~/.codex/state_5.sqlite` (SQLite read-only), exposes cumulative counter and daily gauge metrics on port 9107. Docker service with host volume mounts. CLI monitor gains `agent` category. Grafana dashboard gains agent token panels.

**Tech Stack:** Python 3.10, prometheus-client, sqlite3 (stdlib), bash (CLI)

---

### Task 1: Create the Agent Exporter

**Files:**
- Create: `exporters/agent_exporter.py`

- [ ] **Step 1: Write the agent_exporter.py**

```python
#!/usr/bin/env python3
"""
Agent Token Usage Exporter
Exposes token usage metrics from local AI coding agents (Claude Code, Codex)
for Prometheus scraping.
"""

import time
import json
import os
import sqlite3
import logging
from datetime import date, timedelta
from prometheus_client import start_http_server, Gauge

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Metrics (Gauge used for both since values are read from files, not incremented)
AGENT_TOKENS_TOTAL = Gauge(
    'spark_monitor_agent_tokens_total',
    'Total tokens used by local AI agents (cumulative, read from source files)',
    ['tool', 'model']
)
AGENT_TOKENS_DAILY = Gauge(
    'spark_monitor_agent_tokens_daily',
    'Tokens used per day by local AI agents (last 7 days retained)',
    ['tool', 'model', 'date']
)
AGENT_UP = Gauge(
    'spark_monitor_agent_exporter_up',
    'Agent exporter availability (1=up, 0=down)'
)


def collect_claude_tokens(stats_path):
    """
    Read Claude Code stats-cache.json and return:
    - cumulative: dict of {model_name: total_tokens}
    - daily: dict of {date_str: {model_name: tokens}}
    """
    cumulative = {}
    daily = {}

    if not os.path.exists(stats_path):
        logger.debug(f"Claude stats file not found: {stats_path}")
        return cumulative, daily

    try:
        with open(stats_path, 'r') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Failed to read Claude stats: {e}")
        return cumulative, daily

    daily_model_tokens = data.get('dailyModelTokens', [])
    if not daily_model_tokens:
        return cumulative, daily

    for entry in daily_model_tokens:
        entry_date = entry.get('date', '')
        tokens_by_model = entry.get('tokensByModel', {})

        for model, tokens in tokens_by_model.items():
            model = str(model)
            tokens = int(tokens)

            # Cumulative
            if model not in cumulative:
                cumulative[model] = 0
            cumulative[model] += tokens

            # Daily
            if entry_date not in daily:
                daily[entry_date] = {}
            daily[entry_date][model] = daily[entry_date].get(model, 0) + tokens

    return cumulative, daily


def collect_codex_tokens(db_path):
    """
    Read Codex state_5.sqlite and return:
    - cumulative: dict of {model_name: total_tokens}
    - daily: dict of {date_str: {model_name: tokens}}
    """
    cumulative = {}
    daily = {}

    if not os.path.exists(db_path):
        logger.debug(f"Codex state DB not found: {db_path}")
        return cumulative, daily

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Cumulative: sum tokens_used per model
        cursor.execute("""
            SELECT model, SUM(tokens_used) as total
            FROM threads
            WHERE tokens_used > 0
            GROUP BY model
        """)
        for row in cursor.fetchall():
            model = row['model'] or 'unknown'
            cumulative[model] = cumulative.get(model, 0) + (row['total'] or 0)

        # Daily: sum tokens_used per model per day (last 30 days)
        seven_days_ago = (date.today() - timedelta(days=30)).isoformat()
        cursor.execute("""
            SELECT model,
                   DATE(datetime(created_at, 'unixepoch')) as day,
                   SUM(tokens_used) as total
            FROM threads
            WHERE tokens_used > 0
              AND day >= ?
            GROUP BY model, day
            ORDER BY day DESC
        """, (seven_days_ago,))
        for row in cursor.fetchall():
            model = row['model'] or 'unknown'
            day = row['day']
            if day not in daily:
                daily[day] = {}
            daily[day][model] = daily[day].get(model, 0) + (row['total'] or 0)

        conn.close()
    except Exception as e:
        logger.warning(f"Failed to read Codex state DB: {e}")

    return cumulative, daily


def update_metrics(stats_path, db_path):
    """Collect from all sources and update Prometheus metrics."""
    try:
        AGENT_UP.set(1)

        # Collect from Claude Code
        claude_cum, claude_daily = collect_claude_tokens(stats_path)
        for model, tokens in claude_cum.items():
            AGENT_TOKENS_TOTAL.labels(tool='claude-code', model=model).set(tokens)
        for day, models in claude_daily.items():
            for model, tokens in models.items():
                AGENT_TOKENS_DAILY.labels(tool='claude-code', model=model, date=day).set(tokens)

        # Collect from Codex
        codex_cum, codex_daily = collect_codex_tokens(db_path)
        for model, tokens in codex_cum.items():
            AGENT_TOKENS_TOTAL.labels(tool='codex', model=model).set(tokens)
        for day, models in codex_daily.items():
            for model, tokens in models.items():
                AGENT_TOKENS_DAILY.labels(tool='codex', model=model, date=day).set(tokens)

        # Log summary
        total_claude = sum(claude_cum.values())
        total_codex = sum(codex_cum.values())
        logger.debug(f"Agent tokens: Claude={total_claude}, Codex={total_codex}")

    except Exception as e:
        AGENT_UP.set(0)
        logger.error(f"Error updating agent metrics: {e}")


def main():
    import argparse

    default_claude_stats = os.path.expanduser('~/.claude/stats-cache.json')
    default_codex_db = os.path.expanduser('~/.codex/state_5.sqlite')

    parser = argparse.ArgumentParser(description='Agent Token Usage Exporter')
    parser.add_argument('--port', type=int,
                        default=int(os.getenv('EXPORTER_PORT', 9107)),
                        help='Port to expose metrics on (default: 9107)')
    parser.add_argument('--interval', type=int,
                        default=int(os.getenv('SCRAPE_INTERVAL', 60)),
                        help='Collection interval in seconds (default: 60)')
    parser.add_argument('--claude-stats',
                        default=os.getenv('CLAUDE_STATS_PATH', default_claude_stats),
                        help='Path to Claude Code stats-cache.json')
    parser.add_argument('--codex-db',
                        default=os.getenv('CODEX_DB_PATH', default_codex_db),
                        help='Path to Codex state_5.sqlite')

    args = parser.parse_args()

    start_http_server(args.port)
    logger.info(f"Agent exporter started on port {args.port}")
    logger.info(f"Claude stats: {args.claude_stats}")
    logger.info(f"Codex DB: {args.codex_db}")

    while True:
        update_metrics(args.claude_stats, args.codex_db)
        time.sleep(args.interval)


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Verify syntax and imports**

```bash
cd /data/code/spark-monitor && python3 -c "import ast; ast.parse(open('exporters/agent_exporter.py').read()); print('Syntax OK')"
```

Expected: `Syntax OK`

- [ ] **Step 3: Test with local data (dry run)**

```bash
cd /data/code/spark-monitor && python3 -c "
from exporters.agent_exporter import collect_claude_tokens, collect_codex_tokens
import os

# Test Claude
stats = os.path.expanduser('~/.claude/stats-cache.json')
cum, daily = collect_claude_tokens(stats)
print(f'Claude cumulative: {cum}')
print(f'Claude daily dates: {list(daily.keys())[:5]}')

# Test Codex
db = os.path.expanduser('~/.codex/state_5.sqlite')
cum2, daily2 = collect_codex_tokens(db)
print(f'Codex cumulative: {cum2}')
print(f'Codex daily dates: {list(daily2.keys())[:5]}')
"
```

- [ ] **Step 4: Commit**

```bash
git add exporters/agent_exporter.py
git commit -m "feat: add agent token usage exporter

Reads Claude Code stats-cache.json and Codex state_5.sqlite to expose
cumulative and daily token usage metrics via Prometheus on port 9107."
```

---

### Task 2: Create Dockerfile for Agent Exporter

**Files:**
- Create: `Dockerfile.agent_exporter`

- [ ] **Step 1: Write Dockerfile**

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY exporters/agent_exporter.py exporters/agent_exporter.py
RUN pip install --no-cache-dir prometheus-client
```

- [ ] **Step 2: Verify Dockerfile syntax**

```bash
cd /data/code/spark-monitor && docker build -f Dockerfile.agent_exporter --dry-run . 2>&1 || echo "(dry-run not supported, syntax-only check)"
```

- [ ] **Step 3: Commit**

```bash
git add Dockerfile.agent_exporter
git commit -m "feat: add Dockerfile for agent exporter"
```

---

### Task 3: Update Docker Compose and Prometheus Config

**Files:**
- Modify: `docker-compose.yml`
- Modify: `prometheus.yml`

- [ ] **Step 1: Add agent_exporter service to docker-compose.yml**

Insert after the `system_exporter` service block (before `prometheus` service):

```yaml
  # Agent token usage exporter (Claude Code + Codex)
  agent_exporter:
    build:
      context: .
      dockerfile: Dockerfile.agent_exporter
    container_name: agent_exporter
    ports:
      - "9107:9107"
    volumes:
      - ${HOME}/.claude/stats-cache.json:/root/.claude/stats-cache.json:ro
      - ${HOME}/.codex/state_5.sqlite:/root/.codex/state_5.sqlite:ro
    environment:
      - EXPORTER_PORT=9107
      - SCRAPE_INTERVAL=60
      - CLAUDE_STATS_PATH=/root/.claude/stats-cache.json
      - CODEX_DB_PATH=/root/.codex/state_5.sqlite
    command: python exporters/agent_exporter.py
    restart: unless-stopped
```

- [ ] **Step 2: Add agent_exporter job to prometheus.yml**

Insert after `system_exporter` job:

```yaml
  - job_name: 'agent_exporter'
    static_configs:
      - targets: ['agent_exporter:9107']
```

- [ ] **Step 3: Verify YAML syntax**

```bash
cd /data/code/spark-monitor && python3 -c "import yaml; yaml.safe_load(open('docker-compose.yml')); print('docker-compose.yml OK')"
cd /data/code/spark-monitor && python3 -c "import yaml; yaml.safe_load(open('prometheus.yml')); print('prometheus.yml OK')"
```

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml prometheus.yml
git commit -m "feat: add agent_exporter service to compose and prometheus config"
```

---

### Task 4: Update CLI — monitor command (agent category)

**Files:**
- Modify: `spark-monitor`

- [ ] **Step 1: Add `agent` to valid categories in cmd_monitor**

In `cmd_monitor()`, update the category validation (around line 1023):

```bash
    case "$category" in
        system|gpu|vllm|agent|all)
            ;;
        *)
            print_error "Invalid category: $category"
            echo "Valid categories: system, gpu, vllm, agent, all"
            return 1
            ;;
    esac
```

- [ ] **Step 2: Add `agent` monitor section**

Insert before the `sleep "$interval"` line (before line 1520), add:

```bash
        case "$category" in
            agent|all)
                echo -e "${BLUE}┌─────────────────────────────────────┐${NC}"
                echo -e "${BLUE}│ AGENT TOKEN USAGE                   │${NC}"
                echo -e "${BLUE}└─────────────────────────────────────┘${NC}"

                local agent_total_result agent_daily_result
                agent_total_result=$(query_prometheus 'spark_monitor_agent_tokens_total')
                agent_daily_result=$(query_prometheus 'spark_monitor_agent_tokens_daily')

                # Show cumulative totals by tool
                local current_tool=""
                if [ -n "$agent_total_result" ]; then
                    echo "$agent_total_result" | jq -r '
                        .data.result
                        | sort_by(.metric.tool + .metric.model)
                        | .[]
                        | "\(.metric.tool)\t\(.metric.model)\t\(.value[1])"
                    ' 2>/dev/null | while IFS=$'\t' read -r tool model tokens; do
                        if [[ "$tool" != "$current_tool" ]]; then
                            current_tool="$tool"
                            printf "  ├─ Tool: ${GREEN}%s${NC}\n" "$tool"
                        fi
                        local tokens_fmt
                        tokens_fmt=$(format_number "${tokens%.*}")
                        printf "  │   ├─ %-24s %s tokens\n" "$model" "$tokens_fmt"
                    done
                else
                    echo "  ├─ No agent token data available"
                fi

                # Show today's usage
                if [ -n "$agent_daily_result" ]; then
                    local today
                    today=$(date +%Y-%m-%d)
                    local today_tokens
                    today_tokens=$(echo "$agent_daily_result" | jq -r --arg d "$today" '
                        [.data.result[] | select(.metric.date == $d) | .value[1] | tonumber] | add // 0
                    ' 2>/dev/null)
                    if [[ "$today_tokens" != "0" ]] && [[ "$today_tokens" != "" ]]; then
                        local today_fmt
                        today_fmt=$(format_number "${today_tokens%.*}")
                        printf "  └─ Today (%s): %s tokens\n" "$today" "$today_fmt"
                    fi
                fi
                echo
                ;;
        esac
```

- [ ] **Step 3: Update help text for monitor command**

In `cmd_help()`, update the monitor section (around line 323):

```bash
    echo "  monitor   Show real-time metrics (system|gpu|vllm|agent|all) [-i interval]"
```

And in the examples section (around line 345):

```bash
    echo "  spark-monitor monitor agent    # Agent token metrics only"
    echo "  spark-monitor monitor -i 30    # 30s refresh"
```

- [ ] **Step 4: Verify bash syntax**

```bash
bash -n /data/code/spark-monitor/spark-monitor && echo "Syntax OK"
```

- [ ] **Step 5: Commit**

```bash
git add spark-monitor
git commit -m "feat: add agent category to CLI monitor command

Adds agent token usage display showing cumulative tokens per tool/model
and today's token usage from the agent_exporter metrics."
```

---

### Task 5: Update CLI — install and upgrade commands

**Files:**
- Modify: `spark-monitor` (cmd_install and cmd_upgrade)

- [ ] **Step 1: Add Dockerfile.agent_exporter copy to cmd_install**

In `cmd_install()`, after the existing Dockerfile copies (around line 666), add:

```bash
    # Copy Dockerfile for agent_exporter build
    if [[ -f "$source_dir/Dockerfile.agent_exporter" ]]; then
        cp "$source_dir/Dockerfile.agent_exporter" "$config_dir/"
    fi
```

- [ ] **Step 2: Add Dockerfile.agent_exporter copy to cmd_upgrade**

In `cmd_upgrade()`, after the existing Dockerfile copies (around line 956), add:

```bash
    # Copy Dockerfile for agent_exporter build
    if [[ -f "$source_dir/Dockerfile.agent_exporter" ]]; then
        cp "$source_dir/Dockerfile.agent_exporter" "$DEFAULT_CONFIG_DIR/" 2>/dev/null || true
    fi
```

- [ ] **Step 3: Verify bash syntax**

```bash
bash -n /data/code/spark-monitor/spark-monitor && echo "Syntax OK"
```

- [ ] **Step 4: Commit**

```bash
git add spark-monitor
git commit -m "feat: include Dockerfile.agent_exporter in install/upgrade"
```

---

### Task 6: Update Grafana Dashboard

**Files:**
- Modify: `grafana/dashboards/dgxspark-overview.json`

- [ ] **Step 1: Add agent token panels**

Add two new panels before the closing `]` of the `"panels"` array. The last existing panel is at y=58. New panels go at y=66.

**Panel 1: Agent Token Usage (Total)** — insert at panels array:

```json
    {
      "type": "graph",
      "title": "Agent Token Usage (Total)",
      "gridPos": {
        "x": 0,
        "y": 66,
        "w": 12,
        "h": 8
      },
      "targets": [
        {
          "expr": "spark_monitor_agent_tokens_total",
          "legendFormat": "{{tool}} / {{model}}",
          "refId": "A"
        }
      ],
      "lines": true,
      "linewidth": 2,
      "fill": 1,
      "description": "Cumulative token usage by local AI agents (Claude Code, Codex)",
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "decimals": 0
        }
      }
    },
    {
      "type": "graph",
      "title": "Agent Daily Token Usage",
      "gridPos": {
        "x": 12,
        "y": 66,
        "w": 12,
        "h": 8
      },
      "targets": [
        {
          "expr": "spark_monitor_agent_tokens_daily",
          "legendFormat": "{{tool}} / {{model}} / {{date}}",
          "refId": "A"
        }
      ],
      "lines": true,
      "linewidth": 2,
      "fill": 1,
      "description": "Daily token usage by local AI agents (last 7 days)",
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "decimals": 0
        }
      }
    }
```

- [ ] **Step 2: Verify JSON syntax**

```bash
cd /data/code/spark-monitor && python3 -c "import json; json.load(open('grafana/dashboards/dgxspark-overview.json')); print('JSON OK')"
```

- [ ] **Step 3: Commit**

```bash
git add grafana/dashboards/dgxspark-overview.json
git commit -m "feat: add agent token usage panels to Grafana dashboard"
```

---

### Task 7: Integration Verification

**Files:**
- No new files — verification only

- [ ] **Step 1: Build agent_exporter Docker image**

```bash
cd /data/code/spark-monitor && docker build -f Dockerfile.agent_exporter -t spark-monitor-agent-exporter .
```

Expected: Image builds successfully.

- [ ] **Step 2: Run agent_exporter locally and test metrics endpoint**

```bash
cd /data/code/spark-monitor && timeout 10 python3 exporters/agent_exporter.py --port 19107 &
sleep 3
curl -s http://localhost:19107/metrics | grep spark_monitor_agent
kill %1 2>/dev/null || true
```

Expected: Output shows `spark_monitor_agent_tokens_total` and `spark_monitor_agent_tokens_daily` metrics with `tool` and `model` labels.

- [ ] **Step 3: Verify all changes with bash syntax check**

```bash
bash -n /data/code/spark-monitor/spark-monitor && echo "CLI syntax OK"
```

- [ ] **Step 4: Run agent_exporter help text**

```bash
cd /data/code/spark-monitor && python3 exporters/agent_exporter.py --help
```

Expected: Shows usage with --port, --interval, --claude-stats, --codex-db options.

- [ ] **Step 5: Commit (if any fixes applied)**

Only if fixes were needed:
```bash
git add -A && git commit -m "chore: integration verification fixes"
```
