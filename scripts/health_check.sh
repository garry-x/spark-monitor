#!/bin/bash
# Health check script for Spark-Monitor (single-container mode)

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

# Check gpu_exporter (DCGM)
echo "Checking gpu_exporter..."
curl -s http://localhost:9400/metrics | grep DCGM > /dev/null
if [ $? -eq 0 ]; then
    echo "✓ gpu_exporter is serving metrics"
else
    echo "✗ gpu_exporter is not serving metrics"
fi

# Check vllm_exporter
echo "Checking vllm_exporter..."
curl -s http://localhost:8001/metrics | grep vllm:up > /dev/null
if [ $? -eq 0 ]; then
    echo "✓ vllm_exporter is serving metrics"
else
    echo "✗ vllm_exporter is not serving metrics"
fi

# Check system_exporter
echo "Checking system_exporter..."
curl -s http://localhost:9106/metrics | grep spark_monitor_system_exporter_up > /dev/null
if [ $? -eq 0 ]; then
    echo "✓ system_exporter is serving metrics"
else
    echo "✗ system_exporter is not serving metrics"
fi

# Check agent_exporter
echo "Checking agent_exporter..."
curl -s http://localhost:9107/metrics | grep spark_monitor_agent_tokens_total > /dev/null
if [ $? -eq 0 ]; then
    echo "✓ agent_exporter is serving metrics"
else
    echo "✗ agent_exporter is not serving metrics"
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
