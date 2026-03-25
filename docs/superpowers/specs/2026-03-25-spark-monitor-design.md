# Spark-Monitor System Design Specification

## Overview
Spark-Monitor is a comprehensive monitoring system for DGXSpark that leverages existing open-source exporters where possible to collect and expose metrics from various subsystems for visualization in Grafana via Prometheus.

## Design Decisions Summary
Based on user preferences, the system will use:
1. node_exporter for system metrics (CPU, memory, I/O)
2. NVIDIA DCGM Exporter for GPU metrics
3. vLLM built-in metrics endpoint for vLLM system metrics
4. Custom exporter for OpenCode service health checks (if needed)
5. Prometheus for metric collection and storage
6. Grafana for visualization

## Architecture

```
+------------------+    +------------------+    +------------------+
|  node_exporter   |    |  DCGM Exporter   |    |  vLLM Metrics    |
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

*Note: Additional exporters may be added for OpenCode service health checks if needed.*

## Components

### 1. System Metrics Collection
- **Tool**: node_exporter (https://github.com/prometheus/node_exporter)
- **Metrics Collected**:
  - CPU usage (user, system, idle, etc.)
  - Memory usage (total, used, free, buffers, cache)
  - I/O statistics (disk read/write, network in/out)
  - Filesystem usage
  - Load averages
- **Port**: 9100 (default)
- **Configuration**: Minimal, primarily enabled collectors

### 2. GPU Metrics Collection
- **Tool**: NVIDIA DCGM Exporter (https://github.com/NVIDIA/dcgm-exporter)
- **Metrics Collected**:
  - GPU utilization (%)
  - GPU memory usage (total, used, free)
  - GPU temperature
  - Power draw
  - Clock speeds
  - ECC errors
  - PCIe throughput
- **Port**: 9400 (default)
- **Configuration**: DCGM group configuration for targeted metrics

### 3. vLLM Metrics Collection
- **Tool**: vLLM built-in Prometheus metrics endpoint
- **Metrics Collected** (subject to vLLM version):
  - Request latency
  - Throughput (tokens/second)
  - Active requests
  - Queue length
  - Cache hit rates
  - Token counts (input/output)
- **Port**: Typically 8000-8001 (configurable in vLLM)
- **Configuration**: Enable metrics in vLLM startup arguments

### 4. OpenCode Service Health Checker
- **Tool**: Custom Python exporter (if needed)
- **Metrics Collected**:
  - Service availability (up/down)
  - Response latency
  - Error rates
  - Status codes
- **Port**: 9105 (suggested)
- **Configuration**: Target endpoints and check intervals

### 5. Prometheus Server
- **Function**: Scrapes metrics from all exporters
- **Storage**: Time-series database
- **Querying**: PromQL interface
- **Configuration**:
  - Scrape intervals (typically 15s-1m)
  - Retention policies
  - Alerting rules
  - Service discovery (static config for now)

### 6. Grafana
- **Function**: Visualizes metrics from Prometheus
- **Features**:
  - Pre-built dashboards for each subsystem
  - Customizable panels
  - Alerting notifications
  - User authentication/authorization
- **Dashboards**:
  - System overview (CPU, memory, I/O)
  - GPU utilization and health
  - vLLM performance metrics
  - OpenCode service status
  - Combined system view

## Metrics Naming Convention
Following Prometheus conventions:
- **Prefix**: `spark_monitor_` (for custom metrics)
- **Standard exporters**: Use their native metric names
- **Subsystem identification**: Via labels when needed
- **Descriptive names**: With units where applicable (e.g., `_seconds`, `_bytes`, `_total`)
- **Labels**: For differentiation (e.g., `instance`, `job`, `gpu_id`)

## Example Metrics
- From node_exporter: `node_cpu_seconds_total`, `node_memory_Used_bytes`
- From DCGM Exporter: `DCGM_FI_DEV_GPU_UTIL`, `DCGM_FI_DEV_FB_USED`
- From vLLM: `vllm:request_latency_seconds`, `vllm:token_counter_total`
- Custom: `spark_monitor_opencode_service_up`, `spark_monitor_opencode_response_latency_seconds`

## Deployment
1. Deploy node_exporter on target hosts
2. Deploy DCGM Exporter on GPU-enabled hosts
3. Ensure vLLM is started with metrics endpoint enabled
4. Deploy OpenCode health checker exporter (if needed)
5. Deploy Prometheus server with scrape configuration
6. Deploy Grafana and import dashboards
7. Configure alerting rules as needed

## Security Considerations
- Exporters should bind to internal interfaces only if not publicly needed
- Use authentication for Grafana access
- Run exporters with least privileges
- Secure Prometheus endpoint if exposing externally
- Consider TLS for inter-service communication if needed

## Scalability
- Horizontal scaling of exporters as needed
- Prometheus federation for large multi-cluster deployments
- Grafana can handle multiple users and concurrent dashboard views
- Consider Cortex or Thanos for long-term storage and global query view

## Implementation Plan
1. Set up development environment with Docker/docker-compose
2. Create docker-compose.yml for all services
3. Configure Prometheus to scrape all exporters
4. Create initial Grafana dashboards
5. Test with sample metrics
6. Document deployment procedures
7. Create monitoring alerts for critical metrics

## Future Enhancements
- Automated service discovery
- Advanced alerting with anomaly detection
- Log integration with Loki
- Distributed tracing with Tempo
- Multi-tenancy support
- Export to other monitoring systems (e.g., Elasticsearch, InfluxDB)