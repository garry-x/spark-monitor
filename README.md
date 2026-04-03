# Spark-Monitor

A monitoring system for DGXSpark that tracks:
1. CPU, memory, I/O usage
2. GPU utilization
3. vLLM system status and inference metrics
4. OpenCode service status

Based on open-source platforms like Prometheus and Grafana for web-based visualization.

## Deployment

### Prerequisites
- Docker and Docker Compose
- NVIDIA GPU with drivers (for GPU monitoring)
- vLLM service running with metrics endpoint enabled

### Quick Start

1. Clone the repository
2. Start the monitoring stack:
    ```bash
    make up
    ```
    OR
    ```bash
    ./spark-monitor start
    ```
3. Access the services:
    - Prometheus: http://localhost:9090
    - Grafana: http://localhost:3000 (admin/admin)
4. Verify all services are healthy:
    ```bash
    ./scripts/health_check.sh
    ```
    OR
    ```bash
    ./spark-monitor health
    ```

### Services

- **node_exporter**: System metrics (CPU, memory, I/O) on port 9100
- **gpu_exporter**: GPU metrics placeholder on port 9400 (to be replaced with actual implementation)
- **prometheus**: Metric collection and storage on port 9090
- **grafana**: Visualization on port 3000
- **opencode-exporter**: OpenCode service health checks on port 9105

### Configuration

- Prometheus scrape configuration: `prometheus.yml`
- Grafana dashboards: `grafana/dashboards/`
- Grafana provisioning: `grafana/provisioning/`

### Custom Exporters

The OpenCode service health checker exporter is located in:
- `exporters/opencode_exporter.py`
- Built with: `Dockerfile.opencode_exporter`

### Stopping and Cleaning Up

```bash
make down        # Stop all containers
make clean       # Stop containers and remove volumes/cache
```

## Components

1. **System Metrics Collector**: Uses node_exporter for CPU, memory, I/O metrics
2. **GPU Metrics Collector**: Uses NVIDIA DCGM Exporter for GPU utilization, memory, temperature, power
3. **vLLM Metrics Collector**: Uses vLLM's built-in Prometheus metrics endpoint
4. **OpenCode Service Health Checker**: Custom Python exporter for service availability and latency
5. **Prometheus Server**: Scrapes and stores metrics from all exporters
6. **Grafana**: Visualizes metrics with pre-built dashboards

## Metrics

Standard metrics from exporters are available with their native names. Custom metrics use the `spark_monitor_` prefix.

## License

MIT
