#!/usr/bin/env python3
"""
Simple HTTP server to serve GPU metrics placeholder
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import time

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/metrics':
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; version=0.0.4')
            self.end_headers()
            
            # Simple GPU metrics placeholder
            metrics = '''# HELP gpu_utilization Placeholder for GPU utilization
# TYPE gpu_utilization gauge
gpu_utilization 0.0
# HELP gpu_memory_used_mb Placeholder for GPU memory used in MB
# TYPE gpu_memory_used_mb gauge
gpu_memory_used_mb 0.0
# HELP gpu_memory_total_mb Placeholder for GPU total memory in MB
# TYPE gpu_memory_total_mb gauge
gpu_memory_total_mb 8192.0
# HELP gpu_temperature_celsius Placeholder for GPU temperature in Celsius
# TYPE gpu_temperature_celsius gauge
gpu_temperature_celsius 35.0
# HELP gpu_power_draw_watts Placeholder for GPU power draw in Watts
# TYPE gpu_power_draw_watts gauge
gpu_power_draw_watts 0.0
'''
            self.wfile.write(metrics.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')

    def log_message(self, format, *args):
        # Suppress log messages
        pass

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 9400), MetricsHandler)
    print('Starting GPU metrics exporter on port 9400...')
    server.serve_forever()