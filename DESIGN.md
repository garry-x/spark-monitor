# Spark-Monitor Design

## Overview
Spark-Monitor is a monitoring system for DGXSpark that collects and exposes metrics from various subsystems for visualization in Grafana via Prometheus.

All services run in a single Docker container managed by supervisord.

## Architecture
```
+------------------------------------------------------------------+
|                       spark-monitor container                     |
|                                                                   |
|  +----------------+  +----------------+  +-------------------+   |
|  | node_exporter  |  | gpu_exporter   |  | vllm_exporter     |   |
|  | (prom/node)    |  | (nvidia/dcgm)  |  | (custom Python)   |   |
|  +----------------+  +----------------+  +-------------------+   |
|                                                                   |
|  +----------------+  +----------------+  +-------------------+   |
|  |system_exporter |  | agent_exporter |  |    Prometheus     |   |
|  |(custom Python) |  |(custom Python) |  |                   |   |
|  +----------------+  +----------------+  +-------------------+   |
|                                                                   |
|  +----------------------------------------------------------------+  |
|  |                         Grafana                               |  |
|  +----------------------------------------------------------------+  |
|                                                                   |
|  Process supervisor: supervisord                                  |
+------------------------------------------------------------------+
                                  |
                                  v
                           +-----------+
                           |  vLLM     |  (host service, scraped directly)
                           +-----------+
```

*All components run inside a single container. vLLM is an external service scraped from the host.*

## Components

### 1. node_exporter (upstream binary)
- Collects host CPU, memory, disk, network metrics
- Reads from /proc and /sys (mounted from host)
- Port: 9100

### 2. gpu_exporter (NVIDIA DCGM)
- Collects GPU utilization, memory, temperature, power, NVLink, ECC metrics
- Uses NVIDIA DCGM libraries
- Port: 9400

### 3. vLLM Exporter (custom Python)
- Scrapes vLLM metrics endpoint and provides persistent counter state
- Handles vLLM restart counter resets
- Port: 8001

### 4. System Exporter (custom Python)
- Collects per-process GPU memory usage via nvidia-smi and NVML
- Tracks peak memory per PID
- Requires pid:host and GPU access
- Port: 9106

### 5. Agent Exporter (custom Python)
- Reads token usage from Claude Code, Codex, and OpenCode local files
- Exposes cumulative and daily token metrics
- Port: 9107

### 6. Prometheus
- Scrapes metrics from all exporters
- Stores time-series data
- Evaluates alert rules
- Port: 9090

### 7. Grafana
- Visualizes metrics from Prometheus
- Pre-loaded with DGXSpark Overview dashboard
- Port: 3000

## Process Management
Supervisord manages all 7 processes inside the container with automatic restart on failure. Startup order:
1. Priority 100: Prometheus
2. Priority 200: Grafana, node_exporter, gpu_exporter
3. Priority 300: vllm_exporter, system_exporter, agent_exporter

## Metrics Naming Convention
- Prefix: `spark_monitor_` (custom exporters)
- DCGM metrics: `DCGM_FI_DEV_*`
- Node metrics: `node_*`
- vLLM metrics: `vllm:*`

## Deployment
- Single Dockerfile with multi-stage build
- docker-compose.yml defines one service
- CLI tool (`spark-monitor`) for start/stop/status/logs/health
- `spark-monitor supervisor status` to inspect internal processes

## Security Considerations
- Container runs with elevated privileges (pid:host, GPU access) — required for system metrics
- Host agent stats files mounted read-only
- Default Grafana credentials: admin/admin (change in production)

## Management
- CLI tool (`spark-monitor`) for easy management
- Provides start/stop/restart/status/logs/health/supervisor commands
- Supervisor process-level control via `spark-monitor supervisor`
