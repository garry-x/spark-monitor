#!/usr/bin/env python3
"""
System Metrics Exporter
Exposes system-level GPU process metrics for monitoring via Prometheus.
Uses NVML (NVIDIA Management Library) via pynvml for reliable containerized access.
Tracks per-PID peak (max) GPU memory usage across process lifetimes.
"""

import time
import json
from prometheus_client import start_http_server, Gauge
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Persistent state file for max memory tracking
STATE_FILE = os.path.expanduser('~/.config/spark-monitor/system_exporter_state.json')

# Metrics
GPU_PROCESS_MEMORY_MAX = Gauge(
    'spark_monitor_gpu_process_memory_max_bytes',
    'Max GPU memory observed per process (peak since exporter start, suitable for topk() in Grafana)',
    ['pid', 'process_name']
)
GPU_PROCESS_COUNT = Gauge(
    'spark_monitor_gpu_process_count',
    'Number of processes using GPU'
)
SYSTEM_UP = Gauge(
    'spark_monitor_system_exporter_up',
    'System exporter availability (1=up, 0=down)'
)

# In-memory max tracker: {pid: {'name': str, 'max_bytes': int}}
_max_tracker = {}


def _load_max_state():
    """Load persisted max memory state from file."""
    global _max_tracker
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                data = json.load(f)
            _max_tracker = {}
            for pid, info in data.items():
                _max_tracker[pid] = {
                    'name': info.get('name', 'unknown'),
                    'max_bytes': info.get('max_bytes', 0),
                }
            logger.debug(f"Loaded max state for {len(_max_tracker)} PIDs")
    except Exception as e:
        logger.warning(f"Failed to load max state: {e}")
        _max_tracker = {}


def _save_max_state():
    """Save max memory state to file."""
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        data = {}
        for pid, info in _max_tracker.items():
            data[pid] = {'name': info['name'], 'max_bytes': info['max_bytes']}
        with open(STATE_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        logger.warning(f"Failed to save max state: {e}")


def query_gpu_processes():
    """Query per-process GPU memory usage. Tries nvidia-smi first (works in containers),
    falls back to pynvml."""
    procs = _query_gpu_processes_nvidia_smi()
    if procs:
        return procs
    return _query_gpu_processes_nvml()


def _query_gpu_processes_nvidia_smi():
    """Fallback: query nvidia-smi for per-process GPU memory usage."""
    import subprocess
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-compute-apps=pid,process_name,used_gpu_memory',
             '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return []

        processes = []
        for line in result.stdout.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 3:
                pid = parts[0]
                name = parts[1]
                try:
                    mem_mb = float(parts[2])
                except ValueError:
                    continue
                mem_bytes = int(mem_mb * 1024 * 1024)
                processes.append({'pid': pid, 'name': name, 'memory_bytes': mem_bytes})

        processes.sort(key=lambda x: x['memory_bytes'], reverse=True)
        return processes
    except FileNotFoundError:
        logger.debug("nvidia-smi not found")
        return []
    except Exception as e:
        logger.warning(f"nvidia-smi query failed: {e}")
        return []


def _query_gpu_processes_nvml():
    """Fallback: query NVML for per-process GPU memory usage across all GPUs."""
    try:
        from pynvml import (nvmlInit, nvmlShutdown, nvmlDeviceGetCount,
                            nvmlDeviceGetHandleByIndex,
                            nvmlDeviceGetComputeRunningProcesses,
                            nvmlSystemGetProcessName)
    except ImportError:
        logger.debug("pynvml not installed")
        return []

    try:
        nvmlInit()
    except Exception as e:
        logger.warning(f"NVML init failed: {e}")
        return []

    try:
        process_map = {}
        gpu_count = nvmlDeviceGetCount()
        for gpu_idx in range(gpu_count):
            handle = nvmlDeviceGetHandleByIndex(gpu_idx)
            try:
                procs = nvmlDeviceGetComputeRunningProcesses(handle)
            except Exception:
                continue

            for proc in procs:
                pid = str(proc.pid)
                mem_bytes = proc.usedGpuMemory
                if pid in process_map:
                    process_map[pid]['memory_bytes'] += mem_bytes
                else:
                    try:
                        name = nvmlSystemGetProcessName(proc.pid)
                        if isinstance(name, bytes):
                            name = name.decode('utf-8', errors='replace')
                    except Exception:
                        name = 'unknown'
                    process_map[pid] = {
                        'pid': pid,
                        'name': name,
                        'memory_bytes': mem_bytes,
                    }

        processes = list(process_map.values())
        processes.sort(key=lambda x: x['memory_bytes'], reverse=True)
        return processes
    except Exception as e:
        logger.warning(f"NVML query failed: {e}")
        return []
    finally:
        try:
            nvmlShutdown()
        except Exception:
            pass


def update_metrics():
    """Update all system metrics, tracking max memory per PID."""
    global _max_tracker

    try:
        SYSTEM_UP.set(1)
        current_procs = query_gpu_processes()

        # Update max tracker: bump max for each currently running PID
        active_pids = set()
        for proc in current_procs:
            pid = proc['pid']
            active_pids.add(pid)
            current_bytes = proc['memory_bytes']
            name = proc['name']

            if pid in _max_tracker:
                if current_bytes > _max_tracker[pid]['max_bytes']:
                    _max_tracker[pid]['max_bytes'] = current_bytes
                # Update name in case process name changed
                _max_tracker[pid]['name'] = name
            else:
                _max_tracker[pid] = {'name': name, 'max_bytes': current_bytes}

        # Build list of (pid, name, max_bytes) sorted by max descending,
        # include active PIDs only (clean up dead PIDs)
        dead_pids = [p for p in _max_tracker if p not in active_pids]
        for pid in dead_pids:
            del _max_tracker[pid]

        proc_list = [
            {'pid': pid, 'name': info['name'], 'memory_bytes': info['max_bytes']}
            for pid, info in _max_tracker.items()
        ]
        proc_list.sort(key=lambda x: x['memory_bytes'], reverse=True)

        # Persist state periodically
        _save_max_state()

        # Expose all tracked processes (Grafana uses topk() to get top N)
        for proc in proc_list:
            GPU_PROCESS_MEMORY_MAX.labels(
                pid=proc['pid'], process_name=proc['name']
            ).set(proc['memory_bytes'])

        GPU_PROCESS_COUNT.set(len(proc_list))

        logger.debug(f"Updated GPU process metrics: {len(proc_list)} processes, "
                     f"top={proc_list[0]['pid'] if proc_list else 'none'}:"
                     f"{proc_list[0]['memory_bytes'] if proc_list else 0}")
    except Exception as e:
        SYSTEM_UP.set(0)
        logger.error(f"Error updating system metrics: {e}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='System Metrics Exporter')
    parser.add_argument('--port', type=int, default=int(os.getenv('EXPORTER_PORT', 9106)),
                       help='Port to expose metrics on (default: 9106)')
    parser.add_argument('--scrape-interval', type=int, default=int(os.getenv('SCRAPE_INTERVAL', 15)),
                       help='Scrape interval in seconds (default: 15)')

    args = parser.parse_args()

    # Load persisted max state on startup
    _load_max_state()

    start_http_server(args.port)
    logger.info(f"System exporter started on port {args.port}")

    while True:
        update_metrics()
        time.sleep(args.scrape_interval)


if __name__ == '__main__':
    main()
