# ============================================================
# Stage 1: Download Prometheus, Grafana, node_exporter binaries
# ============================================================
FROM ubuntu:22.04 AS downloader

ENV DEBIAN_FRONTEND=noninteractive

# aria2 for multi-threaded downloads (much faster than wget)
RUN apt-get update && apt-get install -y --no-install-recommends \
    aria2 ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Helper: download with aria2c (4 connections), fall back to direct URL if mirror fails
# GITHUB_PROXY speeds up GitHub downloads in certain regions
ARG GITHUB_PROXY=

RUN <<'SCRIPT'
set -e

dl() {
    local url="$1"
    local out="$2"
    # Try aria2c with proxy URL first if GITHUB_PROXY is set
    if [ -n "$GITHUB_PROXY" ]; then
        local proxy_url
        proxy_url=$(echo "$url" | sed "s|https://github.com/|${GITHUB_PROXY}https://github.com/|")
        proxy_url=$(echo "$proxy_url" | sed "s|https://dl.grafana.com/|${GITHUB_PROXY}https://dl.grafana.com/|")
        echo "Trying proxy: $proxy_url"
        aria2c -x 4 -s 4 --max-tries=3 --timeout=30 \
            --connect-timeout=15 --max-connection-per-server=4 \
            "$proxy_url" -o "$out" 2>/dev/null && return 0
        echo "Proxy failed, trying direct: $url"
    fi
    aria2c -x 4 -s 4 --max-tries=3 --timeout=30 \
        --connect-timeout=15 --max-connection-per-server=4 \
        "$url" -o "$out"
}

# Prometheus
PROMETHEUS_VERSION=2.53.0
dl "https://github.com/prometheus/prometheus/releases/download/v${PROMETHEUS_VERSION}/prometheus-${PROMETHEUS_VERSION}.linux-arm64.tar.gz" \
   prometheus.tar.gz
tar xzf prometheus.tar.gz
mv prometheus-${PROMETHEUS_VERSION}.linux-arm64 /opt/prometheus
rm prometheus.tar.gz

# Grafana
GRAFANA_VERSION=11.1.0
dl "https://dl.grafana.com/oss/release/grafana-${GRAFANA_VERSION}.linux-arm64.tar.gz" \
   grafana.tar.gz
tar xzf grafana.tar.gz
mv grafana-v${GRAFANA_VERSION} /opt/grafana
rm grafana.tar.gz

# node_exporter
NODE_EXPORTER_VERSION=1.8.0
dl "https://github.com/prometheus/node_exporter/releases/download/v${NODE_EXPORTER_VERSION}/node_exporter-${NODE_EXPORTER_VERSION}.linux-arm64.tar.gz" \
   node_exporter.tar.gz
tar xzf node_exporter.tar.gz
mkdir -p /opt/node_exporter
mv node_exporter-${NODE_EXPORTER_VERSION}.linux-arm64/node_exporter /opt/node_exporter/
rm -rf node_exporter-${NODE_EXPORTER_VERSION}.linux-arm64*
SCRIPT

# ============================================================
# Stage 2: Copy dcgm-exporter from official NVIDIA image
# ============================================================
FROM nvidia/dcgm-exporter:4.5.2-4.8.1-distroless AS dcgm

# ============================================================
# Stage 3: Final image
# ============================================================
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    supervisor \
    sqlite3 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip3 install --no-cache-dir \
    prometheus-client>=0.14.0 \
    requests>=2.25.0 \
    nvidia-ml-py>=12.0.0

# Copy binaries from previous stages
COPY --from=downloader /opt/prometheus /opt/prometheus
COPY --from=downloader /opt/grafana /opt/grafana
COPY --from=downloader /opt/node_exporter /opt/node_exporter

# Copy dcgm-exporter binary and libraries from NVIDIA image
COPY --from=dcgm /usr/bin/dcgm-exporter /opt/dcgm/dcgm-exporter
COPY --from=dcgm /usr/bin/dcgm-exporter-entrypoint.sh /opt/dcgm/dcgm-exporter-entrypoint.sh
COPY --from=dcgm /usr/lib/aarch64-linux-gnu/libdcgm.so.4 /usr/lib/aarch64-linux-gnu/
COPY --from=dcgm /usr/lib/aarch64-linux-gnu/libdcgm.so.4.5.2 /usr/lib/aarch64-linux-gnu/
COPY --from=dcgm /usr/lib/aarch64-linux-gnu/libdcgmmoduleconfig.so.4 /usr/lib/aarch64-linux-gnu/
COPY --from=dcgm /usr/lib/aarch64-linux-gnu/libdcgmmoduleconfig.so.4.5.2 /usr/lib/aarch64-linux-gnu/

# Create directory structure
RUN mkdir -p /app/exporters \
    /etc/spark-monitor/grafana/provisioning/datasources \
    /etc/spark-monitor/grafana/provisioning/dashboards \
    /etc/spark-monitor/grafana/dashboards \
    /etc/spark-monitor/prometheus \
    /var/lib/prometheus \
    /var/lib/grafana \
    /var/log/supervisor \
    /host

# Copy configuration files
COPY prometheus.yml /etc/spark-monitor/prometheus.yml
COPY custom-dcgm-counters.csv /etc/spark-monitor/custom-dcgm-counters.csv
COPY grafana/provisioning/datasources/datasource.yml /etc/spark-monitor/grafana/provisioning/datasources/datasource.yml
COPY grafana/provisioning/dashboards/dashboards.yml /etc/spark-monitor/grafana/provisioning/dashboards/dashboards.yml
COPY grafana/dashboards/dgxspark-overview.json /etc/spark-monitor/grafana/dashboards/dgxspark-overview.json

# Copy Python exporters
COPY exporters/vllm_exporter.py /app/exporters/vllm_exporter.py
COPY exporters/system_exporter.py /app/exporters/system_exporter.py
COPY exporters/agent_exporter.py /app/exporters/agent_exporter.py

# Copy supervisord config
COPY supervisord.conf /etc/supervisor/supervisord.conf

# Set permissions
RUN chmod +x /opt/node_exporter/node_exporter \
    /opt/prometheus/prometheus \
    /opt/grafana/bin/grafana-server \
    /opt/dcgm/dcgm-exporter \
    && ldconfig

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -sf http://localhost:9090/-/ready || exit 1

EXPOSE 9090 3000 9100 9400 8001 9106 9107

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf"]
