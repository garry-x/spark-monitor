#!/usr/bin/env python3
"""
Llama Metrics Exporter
Exposes metrics from Llama.cpp /metrics endpoint for monitoring
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
LLAMA_PROMPT_TOKENS_TOTAL = Counter('llama:prompt_tokens_total', 'Total number of prompt tokens processed')
LLAMA_GENERATION_TOKENS_TOTAL = Counter('llama:generation_tokens_total', 'Total number of generation tokens predicted')
LLAMA_PROMPT_SECONDS_TOTAL = Counter('llama:prompt_seconds_total', 'Total time spent processing prompts')
LLAMA_GENERATION_SECONDS_TOTAL = Counter('llama:generation_seconds_total', 'Total time spent generating tokens')
LLAMA_PROMPT_TOKENS_PER_SECOND = Gauge('llama:prompt_tokens_per_second', 'Average prompt throughput in tokens/second')
LLAMA_GENERATION_TOKENS_PER_SECOND = Gauge('llama:generation_tokens_per_second', 'Average generation throughput in tokens/second')
LLAMA_REQUESTS_PROCESSING = Gauge('llama:requests_processing', 'Number of requests currently being processed')
LLAMA_REQUESTS_DEFERRED = Gauge('llama:requests_deferred', 'Number of requests deferred')
LLAMA_N_DECODE_TOTAL = Counter('llama:n_decode_total', 'Total number of llama_decode() calls')
LLAMA_N_TOKENS_MAX = Counter('llama:n_tokens_max', 'Largest observed n_tokens')
LLAMA_UP = Gauge('llama:up', 'Llama service availability (1=up, 0=down)')


class LlamaExporter:
    def __init__(self, llama_url="http://localhost:9000", scrape_interval=5):
        self.llama_url = llama_url
        self.scrape_interval = scrape_interval
        self.session = requests.Session()
        self.session.timeout = (5, 5)

    def fetch_metrics(self):
        """Fetch metrics from Llama /metrics endpoint"""
        try:
            response = self.session.get(f"{self.llama_url}/metrics", timeout=5)
            if response.status_code == 200:
                return response.text
        except requests.exceptions.RequestException as e:
            logger.debug(f"Could not fetch from /metrics: {e}")

        try:
            # Fallback to /v1/metrics endpoint
            response = self.session.get(f"{self.llama_url}/v1/metrics", timeout=5)
            if response.status_code == 200:
                return response.text
        except requests.exceptions.RequestException as e:
            logger.debug(f"Could not fetch from /v1/metrics: {e}")

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
        """Update all metrics from Llama"""
        try:
            metrics_text = self.fetch_metrics()

            if metrics_text:
                LLAMA_UP.set(1)
                metrics = self.parse_prometheus_metrics(metrics_text)

                prompt_tokens = metrics.get('llamacpp:prompt_tokens_total') or metrics.get('llamacpp_prompt_tokens_total')
                if prompt_tokens is not None:
                    LLAMA_PROMPT_TOKENS_TOTAL._value.set(prompt_tokens)

                generation_tokens = metrics.get('llamacpp:tokens_predicted_total') or metrics.get('llamacpp_tokens_predicted_total')
                if generation_tokens is not None:
                    LLAMA_GENERATION_TOKENS_TOTAL._value.set(generation_tokens)

                prompt_seconds = metrics.get('llamacpp:prompt_seconds_total') or metrics.get('llamacpp_prompt_seconds_total')
                if prompt_seconds is not None:
                    LLAMA_PROMPT_SECONDS_TOTAL._value.set(prompt_seconds)

                generation_seconds = metrics.get('llamacpp:tokens_predicted_seconds_total') or metrics.get('llamacpp_tokens_predicted_seconds_total')
                if generation_seconds is not None:
                    LLAMA_GENERATION_SECONDS_TOTAL._value.set(generation_seconds)

                prompt_tps = metrics.get('llamacpp:prompt_tokens_seconds') or metrics.get('llamacpp_prompt_tokens_seconds')
                if prompt_tps is not None:
                    LLAMA_PROMPT_TOKENS_PER_SECOND.set(prompt_tps)

                gen_tps = metrics.get('llamacpp:predicted_tokens_seconds') or metrics.get('llamacpp_predicted_tokens_seconds')
                if gen_tps is not None:
                    LLAMA_GENERATION_TOKENS_PER_SECOND.set(gen_tps)

                requests_processing = metrics.get('llamacpp:requests_processing') or metrics.get('llamacpp_requests_processing')
                if requests_processing is not None:
                    LLAMA_REQUESTS_PROCESSING.set(requests_processing)

                requests_deferred = metrics.get('llamacpp:requests_deferred') or metrics.get('llamacpp_requests_deferred')
                if requests_deferred is not None:
                    LLAMA_REQUESTS_DEFERRED.set(requests_deferred)

                n_decode = metrics.get('llamacpp:n_decode_total') or metrics.get('llamacpp_n_decode_total')
                if n_decode is not None:
                    LLAMA_N_DECODE_TOTAL._value.set(n_decode)

                n_tokens_max = metrics.get('llamacpp:n_tokens_max') or metrics.get('llamacpp_n_tokens_max') or metrics.get('llamacpp:n_past_max') or metrics.get('llamacpp_n_past_max')
                if n_tokens_max is not None:
                    LLAMA_N_TOKENS_MAX._value.set(n_tokens_max)

                logger.debug(f"Updated Llama metrics: {len(metrics)} metrics found")
            else:
                LLAMA_UP.set(0)
                logger.warning("Could not fetch Llama metrics")

        except Exception as e:
            LLAMA_UP.set(0)
            logger.error(f"Error updating Llama metrics: {e}")

    def run(self):
        """Main loop to update metrics"""
        logger.info(f"Starting Llama exporter for {self.llama_url}")

        while True:
            self.update_metrics()
            time.sleep(self.scrape_interval)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Llama Metrics Exporter')
    parser.add_argument('--llama-url', default=os.getenv('LLAMA_URL', 'http://localhost:9000'),
                       help='Llama API URL (default: http://localhost:9000)')
    parser.add_argument('--port', type=int, default=int(os.getenv('EXPORTER_PORT', 8002)),
                       help='Port to expose metrics on (default: 8002)')
    parser.add_argument('--scrape-interval', type=int, default=int(os.getenv('SCRAPE_INTERVAL', 5)),
                       help='Scrape interval in seconds (default: 5)')

    args = parser.parse_args()

    # Start HTTP server
    start_http_server(args.port)
    logger.info(f"Llama exporter started on port {args.port}")

    # Create and run exporter
    exporter = LlamaExporter(llama_url=args.llama_url, scrape_interval=args.scrape_interval)
    exporter.run()


if __name__ == '__main__':
    main()