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

# Metrics (Gauge used since values are read from files, not incremented)
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
            model_str = str(model)
            tokens_int = int(tokens)

            # Cumulative
            if model_str not in cumulative:
                cumulative[model_str] = 0
            cumulative[model_str] += tokens_int

            # Daily
            if entry_date not in daily:
                daily[entry_date] = {}
            daily[entry_date][model_str] = daily[entry_date].get(model_str, 0) + tokens_int

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

    conn = None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Cumulative: sum tokens_used per model
        cursor.execute("""
            SELECT model, SUM(tokens_used) as total
            FROM threads
            WHERE archived=0 AND tokens_used > 0
            GROUP BY model
        """)
        for row in cursor.fetchall():
            model = row['model'] or 'unknown'
            cumulative[model] = cumulative.get(model, 0) + (row['total'] or 0)

        # Daily: sum tokens_used per model per day (last 7 days)
        seven_days_ago = (date.today() - timedelta(days=7)).isoformat()
        cursor.execute("""
            SELECT model,
                   DATE(datetime(created_at, 'unixepoch')) as day,
                   SUM(tokens_used) as total
            FROM threads
            WHERE archived=0 AND tokens_used > 0
              AND DATE(datetime(created_at, 'unixepoch')) >= ?
            GROUP BY model, day
            ORDER BY day DESC
        """, (seven_days_ago,))
        for row in cursor.fetchall():
            model = row['model'] or 'unknown'
            day = row['day']
            if day not in daily:
                daily[day] = {}
            daily[day][model] = daily[day].get(model, 0) + (row['total'] or 0)

    except Exception as e:
        logger.warning(f"Failed to read Codex state DB: {e}")
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass

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
