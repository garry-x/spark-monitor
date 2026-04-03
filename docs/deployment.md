# Spark-Monitor Deployment Guide

## Architecture Overview

Spark-Monitor uses a layered architecture with specialized exporters for each subsystem:

```
+------------------+    +------------------+    +------------------+
|  node_exporter   |    |  gpu_exporter    |    |  vLLM Metrics    |
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

## Component Details

### System Metrics (node_exporter)
- **Image**: `prom/node-exporter:latest`
- **Port**: 9100
- **Metrics**: CPU, memory, disk, network, filesystem
- **Configuration**: Optimized for containerized environments

### GPU Metrics (NVIDIA DCGM Exporter)
- **Image**: `nvidia/dcgm-exporter:4.5.2-4.8.1-distroless`
- **Port**: 9400
- **Metrics**: GPU utilization, memory usage, temperature, power draw, and other DCGM metrics
- **Note**: Using official NVIDIA DCGM Exporter for comprehensive GPU monitoring

### vLLM Metrics
- **Source**: vLLM built-in Prometheus endpoint
- **Port**: Typically 8000-8001 (configure in vLLM startup)
- **Metrics**: Request latency, throughput, active requests, queue length, TTFT, token rates, cache usage, etc.
- **Requirement**: vLLM must be started with `--enable-metrics` flag

### OpenCode Service Health Checker
- **Language**: Python 3.9
- **Port**: 9105
- **Metrics**: Service availability, response latency, request counts, error rates
- **Configuration**: Defined in `SERVICES` dictionary in exporter

### Prometheus Server
- **Image**: `prom/prometheus:latest`
- **Port**: 9090
- **Storage**: Local volume (`prometheus_data`)
- **Configuration**: `prometheus.yml` with scrape intervals of 15s

### Grafana
- **Image**: `grafana/grafana:latest`
- **Port**: 3000
- **Storage**: Local volume (`grafana_data`)
- **Authentication**: Admin user/password (admin/admin)
- **Provisioning**: Dashboards and datasources auto-loaded on startup

## Deployment Steps

### 1. Environment Preparation
- Ensure Docker Engine and Docker Compose are installed
- Install NVIDIA drivers and container toolkit for GPU monitoring
- Start vLLM service with metrics endpoint enabled:
  ```bash
  python -m vllm.entrypoints.api_server \
    --model <model_path> \
    --enable-metrics \
    --port 8000
  ```

### 2. Start Monitoring Stack
```bash
# Clone repository (if not already done)
git clone <repository_url>
cd spark-monitor

# Start all services (choose one method):
  # Method 1: Using Makefile
  make up
  
  # Method 2: Using CLI tool (recommended)
  ./spark-monitor start

# Verify services started correctly
./scripts/health_check.sh
  # OR
  ./spark-monitor health
```

### 3. Access Dashboards
- Open Grafana at http://localhost:3000
- Login with admin/admin
- Navigate to Dashboards -> Manage to see available dashboards:
  - System Overview
  - GPU Overview  
  - vLLM Overview
  - OpenCode Service Status

### 4. Configure Alerting (Optional)
In Grafana:
1. Go to Alerting -> Contact points to set up notifications
2. Create alert rules on panels or manually
3. Set evaluation groups and notification policies

## Maintenance

### Logs
```bash
# View logs for all services
make logs

# View logs for specific service
docker-compose logs -f <service_name>
```

### Updates
```bash
# Pull latest images and recreate containers
make down
docker-compose pull
make up
```

### Backup
Backup the Prometheus and Grafana volumes:
```bash
# Stop services first
make down

# Backup volumes (example paths, adjust as needed)
cp -r prometheus_data /backup/prometheus_data_$(date +%Y%m%d)
cp -r grafana_data /backup/grafana_data_$(date +%Y%m%d)

# Restart services
make up
```

## Troubleshooting

### Service Not Starting
1. Check container logs: `docker-compose logs <service_name>`
2. Verify port availability: `netstat -tlnp | grep <port>`
3. Check resource constraints: `docker stats`

### Missing Metrics
1. Verify exporter is serving metrics: `curl http://localhost:<port>/metrics`
2. Check Prometheus targets: http://localhost:9090/targets
3. Validate scrape configuration in prometheus.yml

### GPU Metrics Missing
1. Ensure NVIDIA drivers are installed and accessible
2. Verify container has access to GPU devices
3. Check GPU exporter logs for initialization errors

### Grafana Login Issues
1. Default credentials: admin/admin
2. To reset password, access Grafana database or use reset functionality
3. Check Grafana logs for authentication errors

## Security Considerations

### Network Exposure
- By default, services bind to all interfaces (0.0.0.0)
- For production, consider:
  - Binding to specific interfaces
  - Using reverse proxy with authentication
  - Implementing network segmentation

### Data Protection
- Prometheus stores data locally - consider encryption at rest
- Grafana data includes dashboard definitions and users
- Regular backups recommended

### Service Accounts
- All containers run as non-root where possible
- Consider creating dedicated service accounts for production

## Performance Tuning

### Prometheus
- Increase scrape_interval for less frequent updates
- Adjust retention period based on storage capacity
- Enable remote storage for long-term retention

### Exporters
- Most exporters have minimal resource usage
- Adjust exporter frequency via environment variables
- node_exporter collectors can be enabled/disabled via command line flags

## Version Compatibility

- Docker Compose file version: 3.8
- Tested with:
  - Prometheus v2.45.0
  - Grafana v10.2.0
  - node_exporter v1.6.1
  - GPU exporter (placeholder)
  - Python 3.9

## Contact

For issues or questions, please refer to the project repository.