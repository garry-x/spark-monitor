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

# Persistent state file for counter values
STATE_FILE = os.path.expanduser('~/.config/spark-monitor/vllm_counter_state.json')

def load_counter_state():
    """Load persisted counter state from file"""
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load counter state: {e}")
    return {'generation_tokens': 0, 'prompt_tokens': 0, 'last_effective_gen': 0, 'last_effective_prompt': 0, 'model_name': ''}

def save_counter_state(state):
    """Save counter state to file"""
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f)
    except Exception as e:
        logger.warning(f"Failed to save counter state: {e}")

def _clean_model_name(raw_name):
    """
    Extract human-readable model name from a HuggingFace cache path.

    HF cache path format:
        /.../models--org--model/snapshots/<hash>  →  org/model

    Non-HF-cache names (e.g. "meta-llama/Llama-2-7b") pass through unchanged.
    """
    marker = "/models--"
    if marker not in raw_name:
        return raw_name

    try:
        after_marker = raw_name.split(marker, 1)[1]
        org_model = after_marker.split("/snapshots/", 1)[0]
        return org_model.replace("--", "/")
    except (IndexError, ValueError):
        return raw_name


def calculate_effective_counter(current_value, last_value, last_effective):
    """
    Calculate effective counter value, handling vLLM restart resets.
    Returns the effective cumulative value.
    """
    current_value = float(current_value) if current_value else 0
    
    # If current value is less than last known value, vLLM likely restarted
    if current_value < last_value:
        # Add the previous effective value to the current counter
        effective = current_value + last_effective
    else:
        # Normal case: continue from last effective value + increment
        effective = last_effective + (current_value - last_value)
    
    return effective

# Metrics
VLLM_GENERATION_TOKENS_TOTAL = Counter('vllm:generation_tokens_total', 'Total number of generated tokens')
VLLM_PROMPT_TOKENS_TOTAL = Counter('vllm:prompt_tokens_total', 'Total number of prompt tokens')
VLLM_NUM_REQUESTS_WAITING = Gauge('vllm:num_requests_waiting', 'Number of requests waiting in scheduler', ['model_name'])
VLLM_NUM_REQUESTS_RUNNING = Gauge('vllm:num_requests_running', 'Number of requests currently running', ['model_name'])
VLLM_NUM_REQUESTS_SWAPPED = Gauge('vllm:num_requests_swapped', 'Number of requests swapped to CPU', ['model_name'])
VLLM_NUM_REQUESTS_SCHEDULED = Gauge('vllm:num_requests_scheduled', 'Number of requests scheduled', ['model_name'])
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
        self._model_name = None
        
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
        """Parse Prometheus format metrics, extracting values and labels"""
        if not metrics_text:
            return {}

        metrics = {}
        model_name = None

        for line in metrics_text.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # Parse metric line: name{labels} value
            metric_name = ''
            labels = {}
            metric_value = None

            if '{' in line:
                name_part, rest = line.split('{', 1)
                metric_name = name_part.strip()
                label_str, value_str = rest.rsplit('}', 1)
                metric_value = float(value_str.strip())
                # Parse labels
                for pair in label_str.split(','):
                    if '=' in pair:
                        k, v = pair.split('=', 1)
                        labels[k.strip()] = v.strip().strip('"')
            else:
                parts = line.split()
                if len(parts) >= 2:
                    metric_name = parts[0]
                    metric_value = float(parts[1])

            if metric_name and metric_value is not None:
                metrics[metric_name] = {'value': metric_value, 'labels': labels}
                # Capture model_name from any metric that has it
                if 'model_name' in labels and model_name is None:
                    model_name = labels['model_name']

        # Also try vllm:livemodels for model name
        if model_name is None:
            line = None
            for l in metrics_text.split('\n'):
                if 'vllm:livemodels' in l:
                    line = l.strip()
                    break
            if line and '{' in line:
                name_part, rest = line.split('{', 1)
                label_str, value_str = rest.rsplit('}', 1)
                for pair in label_str.split(','):
                    if '=' in pair:
                        k, v = pair.split('=', 1)
                        if k.strip() in ('model_name', 'model'):
                            model_name = v.strip().strip('"')
                            break

        self._model_name = _clean_model_name(model_name) if model_name else None
        return metrics

    @property
    def model_name(self):
        return self._model_name if hasattr(self, '_model_name') else None
    
    def update_metrics(self):
        """Update all metrics from vLLM"""
        counter_state = load_counter_state()
        last_gen = counter_state.get('last_effective_gen', 0)
        last_prompt = counter_state.get('last_effective_prompt', 0)
        
        try:
            metrics_text = self.fetch_metrics()

            if metrics_text:
                VLLM_UP.set(1)
                metrics = self.parse_prometheus_metrics(metrics_text)
                mn = self.model_name or ''

                # Clear stale label combinations from previous models
                for gauge in [VLLM_NUM_REQUESTS_WAITING, VLLM_NUM_REQUESTS_RUNNING,
                              VLLM_NUM_REQUESTS_SWAPPED, VLLM_NUM_REQUESTS_SCHEDULED]:
                    gauge._metrics.clear()

                # Detect model change: reset persistent counter for new model
                prev_model = counter_state.get('model_name', '')
                if mn and mn != prev_model:
                    logger.info(f"Model changed: {prev_model!r} -> {mn!r}, resetting counters")
                    counter_state['generation_tokens'] = 0
                    counter_state['prompt_tokens'] = 0
                    counter_state['last_effective_gen'] = 0
                    counter_state['last_effective_prompt'] = 0
                    last_gen = 0
                    last_prompt = 0
                counter_state['model_name'] = mn

                def val(key):
                    return metrics.get(key, {}).get('value')

                if val('vllm:generation_tokens_total') is not None:
                    current_gen = val('vllm:generation_tokens_total')
                    effective_gen = calculate_effective_counter(current_gen, counter_state.get('generation_tokens', 0), last_gen)
                    VLLM_GENERATION_TOKENS_TOTAL._value.set(effective_gen)
                    counter_state['generation_tokens'] = current_gen
                    counter_state['last_effective_gen'] = effective_gen

                if val('vllm:prompt_tokens_total') is not None:
                    current_prompt = val('vllm:prompt_tokens_total')
                    effective_prompt = calculate_effective_counter(current_prompt, counter_state.get('prompt_tokens', 0), last_prompt)
                    VLLM_PROMPT_TOKENS_TOTAL._value.set(effective_prompt)
                    counter_state['prompt_tokens'] = current_prompt
                    counter_state['last_effective_prompt'] = effective_prompt

                save_counter_state(counter_state)

                if val('vllm:num_requests_waiting') is not None:
                    VLLM_NUM_REQUESTS_WAITING.labels(model_name=mn).set(val('vllm:num_requests_waiting'))

                if val('vllm:num_requests_running') is not None:
                    VLLM_NUM_REQUESTS_RUNNING.labels(model_name=mn).set(val('vllm:num_requests_running'))

                if val('vllm:num_requests_swapped') is not None:
                    VLLM_NUM_REQUESTS_SWAPPED.labels(model_name=mn).set(val('vllm:num_requests_swapped'))

                if val('vllm:num_requests_scheduled') is not None:
                    VLLM_NUM_REQUESTS_SCHEDULED.labels(model_name=mn).set(val('vllm:num_requests_scheduled'))

                if val('vllm:gpu_memory_used') is not None:
                    VLLM_GPU_MEMORY_USED.set(val('vllm:gpu_memory_used'))

                if val('vllm:gpu_memory_total') is not None:
                    VLLM_GPU_MEMORY_TOTAL.set(val('vllm:gpu_memory_total'))

                if val('vllm:gpu_memory_utilization') is not None:
                    VLLM_GPU_MEMORY_UTILIZATION.set(val('vllm:gpu_memory_utilization'))

                if val('vllm:gpu_kvcache_used') is not None:
                    VLLM_GPU_KVCACHE_USED.set(val('vllm:gpu_kvcache_used'))

                if val('vllm:gpu_kvcache_total') is not None:
                    VLLM_GPU_KVCACHE_TOTAL.set(val('vllm:gpu_kvcache_total'))

                if val('vllm:gpu_kvcache_utilization') is not None:
                    VLLM_GPU_KVCACHE_UTILIZATION.set(val('vllm:gpu_kvcache_utilization'))
                    
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