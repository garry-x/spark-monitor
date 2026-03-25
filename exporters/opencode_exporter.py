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