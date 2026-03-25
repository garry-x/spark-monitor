# Spark-Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a complete monitoring system for DGXSpark using existing open-source exporters where possible, including system metrics (node_exporter), GPU metrics (DCGM Exporter), vLLM metrics, and OpenCode service health checks, visualized through Prometheus and Grafana.

**Architecture:** Leverage existing open-source exporters for system and GPU metrics, use vLLM's built-in metrics endpoint, and create a custom exporter for OpenCode service health checks if needed. All metrics will be scraped by Prometheus and visualized in Grafana.

**Tech Stack:** 
- node_exporter for system metrics
- NVIDIA DCGM Exporter for GPU metrics
- vLLM built-in metrics endpoint
- Custom Python exporter for OpenCode health checks
- Prometheus for metric collection and storage
- Grafana for visualization
- Docker/docker-compose for deployment

---

### Task 1: Project Setup and Docker Configuration

**Files:**
- Create: `docker-compose.yml`
- Create: `Makefile`
- Create: `README.md` (update existing)

- [ ] **Step 1: Create docker-compose.yml with all services**

```yaml
version: '3.8'

services:
  # System metrics collector
  node_exporter:
    image: prom/node-exporter:latest
    container_name: node_exporter
    ports:
      - "9100:9100"
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - '--path.procfs=/host/proc'
      - '--path.sysfs=/host/sys'
      - '--collector.filesystem.ignored-mount-points=^/(dev|proc|sys|var/lib/docker/.+|var/lib/containers/.+)[:]'
      - '--collector.filesystem.ignored-fs-types=^(autofs|binfmt_misc|bpf|cgroup2?|configfs|debugfs|devpts|devtmpfs|fusectl|hugetlbfs|iso9660|mqueue|nsfs|overlay|proc|procfs|pstore|rpc_pipefs|securityfs|selinuxfs|squashfs|sysfs|tmpfs)'

  # GPU metrics collector
  dcgm_exporter:
    image: nvcr.io/nvidia/k8s/dcgm-exporter:3.1.1
    container_name: dcgm_exporter
    ports:
      - "9400:9400"
    environment:
      - DCGM_EXPORTER_LISTEN_ADDRESS=0.0.0.0:9400
      - DCGM_EXPORTER_UPDATE_FREQUENCY=1
      - DCGM_EXPORTER_EXPORT_DEFAULT_METRICS=true

  # Prometheus server
  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/usr/share/prometheus/console_libraries'
      - '--web.console.templates=/usr/share/prometheus/consoles'

  # Grafana
  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/dashboards:/var/lib/grafana/dashboards
      - ./grafana/provisioning:/etc/grafana/provisioning
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_USERS_ALLOW_SIGN_UP=false

volumes:
  prometheus_data:
  grafana_data:
```

- [ ] **Step 2: Run command to verify docker-compose syntax**

Run: `docker-compose config`
Expected: No errors, shows parsed configuration

- [ ] **Step 3: Create Makefile for common operations**

```makefile
.PHONY: up down logs clean

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

clean:
	docker-compose down -v
	docker system prune -f

init: up
	@echo "Services started. Access:"
	@echo "  Prometheus: http://localhost:9090"
	@echo "  Grafana: http://localhost:3000 (admin/admin)"
```

- [ ] **Step 4: Run make up to start services**

Run: `make up`
Expected: Services start successfully

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml Makefile README.md
git commit -m "feat: add docker-compose configuration for monitoring stack"
```

### Task 2: Configure Prometheus to Scrape Exporters

**Files:**
- Create: `prometheus.yml`
- Modify: `docker-compose.yml:28-35` (update prometheus service volume)

- [ ] **Step 1: Create prometheus.yml with scrape configurations**

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'node_exporter'
    static_configs:
      - targets: ['node_exporter:9100']

  - job_name: 'dcgm_exporter'
    static_configs:
      - targets: ['dcgm_exporter:9400']

  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  # vLLM metrics (to be configured when vLLM is running)
  - job_name: 'vllm'
    static_configs:
      - targets: ['vllm:8000']  # Default vLLM metrics port
    metrics_path: /metrics
    scheme: http

  # OpenCode service health checker (placeholder)
  - job_name: 'opencode'
    static_configs:
      - targets: ['opencode-exporter:9105']
```

- [ ] **Step 2: Update docker-compose.yml to mount prometheus.yml**

Modify the prometheus service volume to:
```yaml
volumes:
  - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
```

- [ ] **Step 3: Run command to verify prometheus configuration**

Run: `docker-compose run --rm prometheus prometheus --config.file=/etc/prometheus/prometheus.yml --dry`
Expected: No errors, shows "SUCCESS: 0 rule files loaded" or similar validation message

- [ ] **Step 4: Commit**

```bash
git add prometheus.yml docker-compose.yml
git commit -m "feat: add prometheus scrape configuration"
```

### Task 3: Configure Grafana Dashboards and Provisioning

**Files:**
- Create: `grafana/dashboards/system-overview.json`
- Create: `grafana/dashboards/gpu-overview.json`
- Create: `grafana/dashboards/vllm-overview.json`
- Create: `grafana/provisioning/dashboards/dashboards.yml`
- Create: `grafana/provisioning/datasources/datasource.yml`

- [ ] **Step 1: Create Grafana dashboard provisioning file**

```yaml
apiVersion: 1

providers:
  - name: 'default'
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards
```

- [ ] **Step 2: Create Grafana datasource provisioning file**

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    url: http://prometheus:9090
    access: proxy
    isDefault: true
    editable: false
```

- [ ] **Step 3: Create basic system overview dashboard**

```json
{
  "dashboard": {
    "id": null,
    "title": "System Overview",
    "tags": ["system"],
    "timezone": "browser",
    "schemaVersion": 16,
    "version": 0,
    "refresh": "10s",
    "panels": [
      {
        "type": "graph",
        "title": "CPU Usage",
        "gridPos": {"x": 0, "y": 0, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "100 - (avg by(instance) (irate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100)",
            "legendFormat": "{{instance}}",
            "refId": "A"
          }
        ]
      },
      {
        "type": "graph",
        "title": "Memory Usage",
        "gridPos": {"x": 12, "y": 0, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100",
            "legendFormat": "{{instance}}",
            "refId": "A"
          }
        ]
      },
      {
        "type": "graph",
        "title": "Disk I/O",
        "gridPos": {"x": 0, "y": 8, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "rate(node_disk_read_bytes_completed[5m])",
            "legendFormat": "{{instance}} - read",
            "refId": "A"
          },
          {
            "expr": "rate(node_disk_written_bytes_completed[5m])",
            "legendFormat": "{{instance}} - written",
            "refId": "B"
          }
        ]
      },
      {
        "type": "graph",
        "title": "Network I/O",
        "gridPos": {"x": 12, "y": 8, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "rate(node_network_receive_bytes_total[5m])",
            "legendFormat": "{{instance}} - received",
            "refId": "A"
          },
          {
            "expr": "rate(node_network_transmit_bytes_total[5m])",
            "legendFormat": "{{instance}} - transmitted",
            "refId": "B"
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 4: Create basic GPU overview dashboard**

```json
{
  "dashboard": {
    "id": null,
    "title": "GPU Overview",
    "tags": ["gpu"],
    "timezone": "browser",
    "schemaVersion": 16,
    "version": 0,
    "refresh": "10s",
    "panels": [
      {
        "type": "graph",
        "title": "GPU Utilization",
        "gridPos": {"x": 0, "y": 0, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "DCGM_FI_DEV_GPU_UTIL",
            "legendFormat": "GPU {{instance}}",
            "refId": "A"
          }
        ]
      },
      {
        "type": "graph",
        "title": "GPU Memory Usage",
        "gridPos": {"x": 12, "y": 0, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "DCGM_FI_DEV_FB_USED",
            "legendFormat": "GPU {{instance}}",
            "refId": "A"
          }
        ]
      },
      {
        "type": "graph",
        "title": "GPU Temperature",
        "gridPos": {"x": 0, "y": 8, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "DCGM_FI_DEV_GPU_TEMP",
            "legendFormat": "GPU {{instance}}",
            "refId": "A"
          }
        ]
      },
      {
        "type": "graph",
        "title": "GPU Power Draw",
        "gridPos": {"x": 12, "y": 8, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "DCGM_FI_DEV_POWER_USAGE",
            "legendFormat": "GPU {{instance}}",
            "refId": "A"
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 5: Create basic vLLM overview dashboard**

```json
{
  "dashboard": {
    "id": null,
    "title": "vLLM Overview",
    "tags": ["vllm"],
    "timezone": "browser",
    "schemaVersion": 16,
    "version": 0,
    "refresh": "10s",
    "panels": [
      {
        "type": "graph",
        "title": "Request Latency",
        "gridPos": {"x": 0, "y": 0, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "vllm:request_latency_seconds",
            "legendFormat": "{{instance}}",
            "refId": "A"
          }
        ]
      },
      {
        "type": "graph",
        "title": "Throughput (tokens/second)",
        "gridPos": {"x": 12, "y": 0, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "vllm:token_counter_total",
            "legendFormat": "{{instance}}",
            "refId": "A"
          }
        ]
      },
      {
        "type": "graph",
        "title": "Active Requests",
        "gridPos": {"x": 0, "y": 8, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "vllm:num_requests_running",
            "legendFormat": "{{instance}}",
            "refId": "A"
          }
        ]
      },
      {
        "type": "graph",
        "title": "Queue Length",
        "gridPos": {"x": 12, "y": 8, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "vllm:num_requests_waiting",
            "legendFormat": "{{instance}}",
            "refId": "A"
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 6: Create basic OpenCode service dashboard**

```json
{
  "dashboard": {
    "id": null,
    "title": "OpenCode Service Status",
    "tags": ["opencode"],
    "timezone": "browser",
    "schemaVersion": 16,
    "version": 0,
    "refresh": "10s",
    "panels": [
      {
        "type": "stat",
        "title": "Service Availability",
        "gridPos": {"x": 0, "y": 0, "w": 6, "h": 4},
        "targets": [
          {
            "expr": "spark_monitor_opencode_service_up{service=\"opencode\"}",
            "legendFormat": "{{endpoint}}",
            "refId": "A"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "color": {
              "mode": "thresholds"
            },
            "thresholds": {
              "steps": [
                {
                  "color": "red",
                  "value": null
                },
                {
                  "color": "green",
                  "value": 1
                }
              ]
            }
          }
        }
      },
      {
        "type": "graph",
        "title": "Response Latency (seconds)",
        "gridPos": {"x": 6, "y": 0, "w": 12, "h": 4},
        "targets": [
          {
            "expr": "spark_monitor_opencode_response_latency_seconds{service=\"opencode\"}",
            "legendFormat": "{{endpoint}}",
            "refId": "A"
          }
        ]
      },
      {
        "type": "graph",
        "title": "Request Rate (requests/second)",
        "gridPos": {"x": 0, "y": 4, "w": 12, "h": 4},
        "targets": [
          {
            "expr": "sum by (endpoint) (rate(spark_monitor_opencode_requests_total{service=\"opencode\"}[1m]))",
            "legendFormat": "{{endpoint}}",
            "refId": "A"
          }
        ]
      },
      {
        "type": "graph",
        "title": "Error Rate (errors/second)",
        "gridPos": {"x": 12, "y": 4, "w": 12, "h": 4},
        "targets": [
          {
            "expr": "sum by (endpoint) (rate(spark_monitor_opencode_errors_total{service=\"opencode\"}[1m]))",
            "legendFormat": "{{endpoint}}",
            "refId": "A"
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 7: Commit**

```bash
git add grafana/
git commit -m "feat: add grafana dashboard provisioning and sample dashboards"
```

### Task 4: Create OpenCode Service Health Checker Exporter

**Files:**
- Create: `exporters/opencode_exporter.py`
- Create: `requirements.txt`
- Create: `Dockerfile.opencode_exporter`
- Modify: `docker-compose.yml` (add opencode-exporter service)

- [ ] **Step 1: Create requirements.txt for the exporter**

```text
prometheus-client>=0.0.0
requests>=2.25.0
```

- [ ] **Step 2: Create Dockerfile for OpenCode exporter**

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY exporters/opencode_exporter.py .

EXPOSE 9105

CMD ["python", "opencode_exporter.py"]
```

- [ ] **Step 3: Create OpenCode service health checker exporter**

```python
#!/usr/bin/env python3
"""
OpenCode Service Health Checker Exporter
Exposes health check metrics for OpenCode service endpoints
"""

import time
from prometheus_client import start_http_server, Gauge, Counter
import requests
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Metrics
SERVICE_UP = Gauge('spark_monitor_opencode_service_up', 'Service availability (1=up, 0=down)', ['service'])
RESPONSE_LATENCY = Gauge('spark_monitor_opencode_response_latency_seconds', 'Response latency in seconds', ['service', 'endpoint'])
REQUEST_COUNT = Counter('spark_monitor_opencode_requests_total', 'Total number of requests', ['service', 'endpoint', 'status'])
ERROR_COUNT = Counter('spark_monitor_opencode_errors_total', 'Total number of errors', ['service', 'endpoint'])

# Configuration
SERVICES = {
    'opencode': {
        'endpoints': [
            {'url': 'http://localhost:8000/health', 'name': 'health'},
            {'url': 'http://localhost:8000/api/v1/status', 'name': 'status'}
        ],
        'timeout': 5
    }
}

def check_endpoint(service_name, endpoint):
    """Check a single endpoint and update metrics"""
    url = endpoint['url']
    name = endpoint['name']
    
    start_time = time.time()
    try:
        response = requests.get(url, timeout=SERVICES[service_name]['timeout'])
        latency = time.time() - start_time
        
        # Update metrics
        SERVICE_UP.labels(service=service_name).set(1)
        RESPONSE_LATENCY.labels(service=service_name, endpoint=name).set(latency)
        REQUEST_COUNT.labels(service=service_name, endpoint=name, status=response.status_code).inc()
        
        if response.status_code >= 400:
            ERROR_COUNT.labels(service=service_name, endpoint=name).inc()
            
        logger.info(f"{service_name} {name}: {response.status_code} ({latency:.3f}s)")
        
    except Exception as e:
        latency = time.time() - start_time
        # Update metrics for failure
        SERVICE_UP.labels(service=service_name).set(0)
        RESPONSE_LATENCY.labels(service=service_name, endpoint=name).set(latency)
        REQUEST_COUNT.labels(service=service_name, endpoint=name, status=0).inc()
        ERROR_COUNT.labels(service=service_name, endpoint=name).inc()
        
        logger.error(f"{service_name} {name}: Error - {str(e)}")

def main():
    """Main exporter loop"""
    # Start HTTP server to expose metrics
    start_http_server(9105)
    logger.info("OpenCode exporter started on port 9105")
    
    while True:
        for service_name, config in SERVICES.items():
            for endpoint in config['endpoints']:
                check_endpoint(service_name, endpoint)
        
        # Wait before next check cycle
        time.sleep(30)

if __name__ == '__main__':
    main()
```

- [ ] **Step 4: Update docker-compose.yml to add opencode-exporter service**

Add this service to docker-compose.yml:
```yaml
  # OpenCode service health checker
  opencode-exporter:
    build:
      context: .
      dockerfile: Dockerfile.opencode_exporter
    container_name: opencode_exporter
    ports:
      - "9105:9105"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}  # Pass through if needed
```

- [ ] **Step 5: Commit**

```bash
git add requirements.txt Dockerfile.opencode_exporter exporters/opencode_exporter.py docker-compose.yml
git commit -m "feat: add OpenCode service health checker exporter"
```

### Task 5: Test and Validate the Complete Stack

**Files:**
- Create: `tests/test_docker_compose.py`
- Create: `scripts/health_check.sh`

- [ ] **Step 1: Create health check script**

```bash
#!/bin/bash
# Health check script for Spark-Monitor

echo "Checking Spark-Monitor services..."

# Check Prometheus
echo "Checking Prometheus..."
curl -s http://localhost:9090/-/ready > /dev/null
if [ $? -eq 0 ]; then
    echo "✓ Prometheus is ready"
else
    echo "✗ Prometheus is not ready"
fi

# Check node_exporter
echo "Checking node_exporter..."
curl -s http://localhost:9100/metrics | grep node_cpu_seconds_total > /dev/null
if [ $? -eq 0 ]; then
    echo "✓ node_exporter is serving metrics"
else
    echo "✗ node_exporter is not serving metrics"
fi

# Check dcgm_exporter
echo "Checking dcgm_exporter..."
curl -s http://localhost:9400/metrics | grep DCGM_FI_DEV_GPU_UTIL > /dev/null
if [ $? -eq 0 ]; then
    echo "✓ dcgm_exporter is serving metrics"
else
    echo "✗ dcgm_exporter is not serving metrics"
fi

# Check OpenCode exporter
echo "Checking opencode-exporter..."
curl -s http://localhost:9105/metrics | grep spark_monitor_opencode_service_up > /dev/null
if [ $? -eq 0 ]; then
    echo "✓ opencode-exporter is serving metrics"
else
    echo "✗ opencode-exporter is not serving metrics"
fi

# Check Grafana
echo "Checking Grafana..."
curl -s http://localhost:3000/api/health > /dev/null
if [ $? -eq 0 ]; then
    echo "✓ Grafana is healthy"
else
    echo "✗ Grafana is not healthy"
fi

echo "Health check complete."
```

- [ ] **Step 2: Make health check script executable**

Run: `chmod +x scripts/health_check.sh`
Expected: Script is now executable

- [ ] **Step 3: Run health check script**

Run: `./scripts/health_check.sh`
Expected: All services show healthy status

- [ ] **Step 4: Commit**

```bash
git add scripts/health_check.sh
git commit -m "feat: add health check script for monitoring stack"
```

### Task 6: Documentation and Finalization

**Files:**
- Create: `docs/deployment.md`
- Update: `README.md`

- [ ] **Step 1: Update README.md with deployment instructions**

```markdown
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
3. Access the services:
   - Prometheus: http://localhost:9090
   - Grafana: http://localhost:3000 (admin/admin)
4. Verify all services are healthy:
   ```bash
   ./scripts/health_check.sh
   ```

### Services

- **node_exporter**: System metrics (CPU, memory, I/O) on port 9100
- **dcgm_exporter**: GPU metrics on port 9400
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
```

- [ ] **Step 2: Create detailed deployment documentation**

```markdown
# Spark-Monitor Deployment Guide

## Architecture Overview

Spark-Monitor uses a layered architecture with specialized exporters for each subsystem:

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

## Component Details

### System Metrics (node_exporter)
- **Image**: `prom/node-exporter:latest`
- **Port**: 9100
- **Metrics**: CPU, memory, disk, network, filesystem
- **Configuration**: Optimized for containerized environments

### GPU Metrics (DCGM Exporter)
- **Image**: `nvcr.io/nvidia/k8s/dcgm-exporter:3.1.1`
- **Port**: 9400
- **Metrics**: GPU utilization, memory, temperature, power, clocks, ECC
- **Configuration**: Default metric set with 1-second update frequency

### vLLM Metrics
- **Source**: vLLM built-in Prometheus endpoint
- **Port**: Typically 8000-8001 (configure in vLLM startup)
- **Metrics**: Request latency, throughput, active requests, queue length
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

# Start all services
make up

# Verify services started correctly
./scripts/health_check.sh
```

### 3. Access Dashboards
- Open Grafana at http://localhost:3000
- Login with admin/admin
- Navigate to Dashboards -> Manage to see available dashboards:
  - System Overview
  - GPU Overview  
  - vLLM Overview

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
3. Check DCGM exporter logs for initialization errors

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
- DCGM Exporter frequency can be adjusted via DCGM_EXPORTER_UPDATE_FREQUENCY
- node_exporter collectors can be enabled/disabled via command line flags

## Version Compatibility

- Docker Compose file version: 3.8
- Tested with:
  - Prometheus v2.45.0
  - Grafana v10.2.0
  - node_exporter v1.6.1
  - DCGM Exporter v3.1.1
  - Python 3.9

## Contact

For issues or questions, please refer to the project repository.
```

- [ ] **Step 3: Commit**

```bash
git add README.md docs/deployment.md
git commit -m "docs: update README and add detailed deployment documentation"
```

### Task 7: Create Monitoring Alert Rules

**Files:**
- Create: `prometheus/alert_rules.yml`
- Modify: `prometheus.yml:47-52` (add rule_files section)

- [ ] **Step 1: Create Prometheus alert rules file**

```yaml
groups:
  - name: system-alerts
    rules:
      - alert: HighCPUUsage
        expr: avg by (instance) (100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)) > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High CPU usage on {{ $labels.instance }}"
          description: "CPU usage is above 80% for more than 5 minutes."

      - alert: HighMemoryUsage
        expr: (node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100 > 85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage on {{ $labels.instance }}"
          description: "Memory usage is above 85% for more than 5 minutes."

      - alert: DiskSpaceLow
        expr: (node_filesystem_size_bytes{fstype!="tmpfs"} - node_filesystem_free_bytes{fstype!="tmpfs"}) / node_filesystem_size_bytes{fstype!="tmpfs"} * 100 > 90
        for: 15m
        labels:
          severity: critical
        annotations:
          summary: "Low disk space on {{ $labels.instance }} ({{ $labels.mountpoint }})"
          description: "Disk usage is above 90% for more than 15 minutes."

  - name: gpu-alerts
    rules:
      - alert: GPUTemperatureHigh
        expr: DCGM_FI_DEV_GPU_TEMP > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High GPU temperature on {{ $labels.instance }} GPU {{ $labels.gpu }}"
          description: "GPU temperature is above 80°C for more than 5 minutes."

      - alert: GPUMemoryUsageHigh
        expr: DCGM_FI_DEV_FB_USED / DCGM_FI_DEV_FB_TOTAL * 100 > 90
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High GPU memory usage on {{ $labels.instance }} GPU {{ $labels.gpu }}"
          description: "GPU memory usage is above 90% for more than 5 minutes."

  - name: vllm-alerts
    rules:
      - alert: VLLMLatencyHigh
        expr: histogram_quantile(0.95, sum(rate(vllm:request_latency_seconds_bucket[5m])) by (le)) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High vLLM request latency on {{ $labels.instance }}"
          description: "95th percentile request latency is above 2 seconds for more than 5 minutes."

      - alert: VLLMQueueLengthHigh
        expr: vllm:num_requests_waiting > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High vLLM queue length on {{ $labels.instance }}"
          description: "Number of waiting requests is above 10 for more than 5 minutes."

  - name: opencode-alerts
    rules:
      - alert: OpencodeServiceDown
        expr: spark_monitor_opencode_service_up{service="opencode"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Opencode service {{ $labels.endpoint }} is down"
          description: "Opencode service endpoint has been down for more than 2 minutes."

      - alert: OpencodeHighLatency
        expr: spark_monitor_opencode_response_latency_seconds{service="opencode"} > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High response latency for Opencode service {{ $labels.endpoint }}"
          description: "Response latency is above 5 seconds for more than 5 minutes."

- [ ] **Step 2: Update prometheus.yml to include alert rules**

Modify prometheus.yml to add:
```yaml
rule_files:
  - "alert_rules.yml"
```

- [ ] **Step 3: Commit**

```bash
git add prometheus/alert_rules.yml prometheus.yml
git commit -m "feat: add prometheus alert rules for monitoring"
```

### Task 8: Test and Validate the Complete Stack

**Files:**
- Create: `tests/test_docker_compose.py`
- Create: `scripts/health_check.sh`

- [ ] **Step 1: Create .gitignore file**

```gitignore
# Docker
docker-compose.override.yml
*.log

# Prometheus
prometheus_data/

# Grafana
grafana_data/

# Python
__pycache__
*.py[cod]
*$py.class
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Logs
*.log
logs/

# Temporary
tmp/
temp/
.cache/
```

- [ ] **Step 2: Initialize git repository if not already done**

Run: `git init`
Expected: Git repository initialized

- [ ] **Step 3: Add all files and create initial commit**

Run: `git add .`
Expected: All files staged

Run: `git commit -m "initial commit: Spark-Monitor monitoring system"`
Expected: Initial commit created

- [ ] **Step 4: Final verification**

Run: `make down && make up`
Expected: All services restart cleanly

Run: `./scripts/health_check.sh`
Expected: All services report healthy

- [ ] **Step 5: Commit**

```bash
git add .gitignore
git commit -m "chore: add gitignore and final verification"
```