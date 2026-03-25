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

# Check gpu_exporter (placeholder)
echo "Checking gpu_exporter..."
curl -s http://localhost:9400/metrics | grep 'GPU metrics placeholder' > /dev/null
if [ $? -eq 0 ]; then
    echo "✓ gpu_exporter is serving metrics"
else
    echo "✗ gpu_exporter is not serving metrics"
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