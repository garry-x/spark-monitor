# Spark-Monitor Design

## Overview
Spark-Monitor is a monitoring system for DGXSpark that collects and exposes metrics from various subsystems for visualization in Grafana via Prometheus.

## Architecture
```
+------------------+    +------------------+    +------------------+
|  System Collector|    |  GPU Collector   |    |  vLLM Collector  |
+------------------+    +------------------+    +------------------+
         |                     |                     |
         v                     v                     v
+------------------+    +------------------+    +------------------+
|   System Exporter|    |   GPU Exporter   |    |  vLLM Exporter   |
+------------------+    +------------------+    +------------------+
         \                     |                     /
          \                    |                    /
           \                   |                   /
            \                  |                  /
             +-----------------+-----------------+
                             |
                         +-----------+
                         | Prometheus|
                         +-----------+
                             |
                             v
                      +-----------+
                      |  Grafana  |
                      +-----------+
                             |
                             v
                      +-----------+
                      | OpenCode  |
                      +-----------+
```
*Note: OpenCode service status is collected by a separate checker and exposed via its own exporter.*

## Components

### 1. System Collector
- Collects CPU usage (user, system, idle, etc.)
- Collects memory usage (total, used, free, buffers, cache)
- Collects I/O statistics (disk read/write, network in/out)
- Uses /proc filesystem or system commands (vmstat, iostat, etc.)

### 2. GPU Collector
- Collects GPU utilization, memory usage, temperature, power draw
- Uses nvidia-smi or NVIDIA Data Center GPU Manager (DCGM)

### 3. vLLM Collector
- Collects vLLM server metrics (if available via metrics endpoint)
- Alternatively, parses logs for inference metrics (latency, throughput, token counts)
- May require instrumenting vLLM or using its built-in Prometheus metrics

### 4. OpenCode Service Checker
- Performs health checks on OpenCode service endpoints
- Collects response times, error rates, status codes
- Exposes as Prometheus metrics

### 5. Exporters
Each collector has a corresponding Prometheus exporter that:
- Runs as a separate process
- Exposes metrics on a specific port in Prometheus format
- Is scraped by Prometheus server

### 6. Prometheus Server
- Scrapes metrics from all exporters at configured intervals
- Stores time-series data
- Provides querying interface (PromQL)

### 7. Grafana
- Visualizes metrics from Prometheus
- Provides pre-built dashboards for each subsystem
- Allows alerting based on metric thresholds

## Implementation Details

### Metrics Naming Convention
Use Prometheus conventions:
- Prefix: `spark_monitor_`
- Subsystem: `system`, `gpu`, `vllm`, `opencode`
- Metric name: descriptive, with units if applicable (e.g., `_seconds`, `_bytes`, `_total`)
- Labels: for differentiation (e.g., `instance`, `job`, `gpu_id`)

### Example Metrics
- `spark_monitor_system_cpu_utilization_percent`
- `spark_monitor_system_memory_used_bytes`
- `spark_monitor_gpu_utilization_percent{gpu_id="0"}`
- `spark_monitor_vllm_request_latency_seconds`
- `spark_monitor_opencode_service_up`

### Deployment
- Each exporter runs in its own container (or process)
- Prometheus and Grafana deployed as per their documentation
- Configuration via files or environment variables

## Security Considerations
- Exporters should only expose necessary metrics
- Use authentication if exposing to untrusted networks
- Run exporters with least privileges

## Scalability
- Horizontal scaling of exporters if needed
- Prometheus federation for large deployments
- Grafana can handle multiple users and dashboards
