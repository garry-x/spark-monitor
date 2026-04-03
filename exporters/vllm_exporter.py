#!/usr/bin/env python3
"""
vLLM Metrics Exporter
Exposes metrics from vLLM API for monitoring
"""

import time
import json
from prometheus_client import start_http_server, Gauge, Counter
import requests
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Metrics
VLLM_GENERATION_TOKENS_TOTAL = Counter('vllm:generation_tokens_total', 'Total number of generated tokens')
VLLM_PROMPT_TOKENS_TOTAL = Counter('vllm:prompt_tokens_total', 'Total number of prompt tokens')
VLLM_NUM_REQUESTS_WAITING = Gauge('vllm:num_requests_waiting', 'Number of requests waiting in scheduler')
VLLM_NUM_REQUESTS_RUNNING = Gauge('vllm:num_requests_running', 'Number of requests currently running')
VLLM_NUM_REQUESTS_SWAPPED = Gauge('vllm:num_requests_swapped', 'Number of requests swapped to CPU')
VLLM_NUM_REQUESTS_SCHEDULED = Gauge('vllm:num_requests_scheduled', 'Number of requests scheduled')
VLLM_GPU_MEMORY_USED = Gauge('vllm:gpu_memory_used', 'GPU memory used in bytes')
VLLM_GPU_MEMORY_TOTAL = Gauge('vllm:gpu_memory_total', 'Total GPU memory in bytes')
VLLM_GPU_MEMORY_UTILIZATION = Gauge('vllm:gpu_memory_utilization', 'GPU memory utilization percentage')
VLLM_GPU_KVCACHE_USED = Gauge('vllm:gpu_kvcache_used', 'GPU KV cache used in bytes')
VLLM_GPU_KVCACHE_TOTAL = Gauge('vllm:gpu_kvcache_total', 'Total GPU KV cache in bytes')
VLLM_GPU_KVCACHE_UTILIZATION = Gauge('vllm:gpu_kvcache_utilization', 'GPU KV cache utilization percentage')
VLLM_UP = Gauge('vllm:up', 'vLLM service availability (1=up, 0=down)')

class VLLMExporter:
    def __init__(self, vllm_url="http://localhost:8000", scrape_interval=5):
        self.vllm_url = vllm_url
        self.scrape_interval = scrape_interval
        self.session = requests.Session()
        self.session.timeout = 5
        
    def fetch_metrics(self):
        """Fetch metrics from vLLM API"""
        try:
            # Try to get metrics from /metrics endpoint
            response = self.session.get(f"{self.vllm_url}/metrics", timeout=5)
            if response.status_code == 200:
                return response.text
        except requests.exceptions.RequestException as e:
            logger.debug(f"Could not fetch from /metrics: {e}")
        
        try:
            # Fallback to /v1/metrics endpoint
            response = self.session.get(f"{self.vllm_url}/v1/metrics", timeout=5)
            if response.status_code == 200:
                return response.text
        except requests.exceptions.RequestException as e:
            logger.debug(f"Could not fetch from /v1/metrics: {e}")
            
        try:
            # Fallback to /stats endpoint
            response = self.session.get(f"{self.vllm_url}/stats", timeout=5)
            if response.status_code == 200:
                return response.text
        except requests.exceptions.RequestException as e:
            logger.debug(f"Could not fetch from /stats: {e}")
            
        return None
    
    def parse_prometheus_metrics(self, metrics_text):
        """Parse Prometheus format metrics"""
        if not metrics_text:
            return {}
            
        metrics = {}
        for line in metrics_text.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            # Parse metric line
            parts = line.split()
            if len(parts) >= 2:
                metric_name = parts[0]
                metric_value = parts[1]
                metrics[metric_name] = float(metric_value)
                
        return metrics
    
    def update_metrics(self):
        """Update all metrics from vLLM"""
        try:
            metrics_text = self.fetch_metrics()
            
            if metrics_text:
                VLLM_UP.set(1)
                metrics = self.parse_prometheus_metrics(metrics_text)
                
                # Update metrics if found
                if 'vllm:generation_tokens_total' in metrics:
                    VLLM_GENERATION_TOKENS_TOTAL._value.set(metrics['vllm:generation_tokens_total'])
                    
                if 'vllm:prompt_tokens_total' in metrics:
                    VLLM_PROMPT_TOKENS_TOTAL._value.set(metrics['vllm:prompt_tokens_total'])
                    
                if 'vllm:num_requests_waiting' in metrics:
                    VLLM_NUM_REQUESTS_WAITING.set(metrics['vllm:num_requests_waiting'])
                    
                if 'vllm:num_requests_running' in metrics:
                    VLLM_NUM_REQUESTS_RUNNING.set(metrics['vllm:num_requests_running'])
                    
                if 'vllm:num_requests_swapped' in metrics:
                    VLLM_NUM_REQUESTS_SWAPPED.set(metrics['vllm:num_requests_swapped'])
                    
                if 'vllm:num_requests_scheduled' in metrics:
                    VLLM_NUM_REQUESTS_SCHEDULED.set(metrics['vllm:num_requests_scheduled'])
                    
                if 'vllm:gpu_memory_used' in metrics:
                    VLLM_GPU_MEMORY_USED.set(metrics['vllm:gpu_memory_used'])
                    
                if 'vllm:gpu_memory_total' in metrics:
                    VLLM_GPU_MEMORY_TOTAL.set(metrics['vllm:gpu_memory_total'])
                    
                if 'vllm:gpu_memory_utilization' in metrics:
                    VLLM_GPU_MEMORY_UTILIZATION.set(metrics['vllm:gpu_memory_utilization'])
                    
                if 'vllm:gpu_kvcache_used' in metrics:
                    VLLM_GPU_KVCACHE_USED.set(metrics['vllm:gpu_kvcache_used'])
                    
                if 'vllm:gpu_kvcache_total' in metrics:
                    VLLM_GPU_KVCACHE_TOTAL.set(metrics['vllm:gpu_kvcache_total'])
                    
                if 'vllm:gpu_kvcache_utilization' in metrics:
                    VLLM_GPU_KVCACHE_UTILIZATION.set(metrics['vllm:gpu_kvcache_utilization'])
                    
                logger.debug(f"Updated vLLM metrics: {len(metrics)} metrics found")
            else:
                VLLM_UP.set(0)
                logger.warning("Could not fetch vLLM metrics")
                
        except Exception as e:
            VLLM_UP.set(0)
            logger.error(f"Error updating vLLM metrics: {e}")
    
    def run(self):
        """Main loop to update metrics"""
        logger.info(f"Starting vLLM exporter for {self.vllm_url}")
        
        while True:
            self.update_metrics()
            time.sleep(self.scrape_interval)

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='vLLM Metrics Exporter')
    parser.add_argument('--vllm-url', default=os.getenv('VLLM_URL', 'http://localhost:8000'),
                       help='vLLM API URL (default: http://localhost:8000)')
    parser.add_argument('--port', type=int, default=int(os.getenv('EXPORTER_PORT', 8001)),
                       help='Port to expose metrics on (default: 8001)')
    parser.add_argument('--scrape-interval', type=int, default=int(os.getenv('SCRAPE_INTERVAL', 5)),
                       help='Scrape interval in seconds (default: 5)')
    
    args = parser.parse_args()
    
    # Start HTTP server
    start_http_server(args.port)
    logger.info(f"vLLM exporter started on port {args.port}")
    
    # Create and run exporter
    exporter = VLLMExporter(vllm_url=args.vllm_url, scrape_interval=args.scrape_interval)
    exporter.run()

if __name__ == '__main__':
    main()