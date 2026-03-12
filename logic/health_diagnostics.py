import os
import resource
import importlib
import subprocess
import re

import numpy as np

psutil = None
try:
    psutil = importlib.import_module("psutil")
except Exception:  # pragma: no cover - optional dependency
    psutil = None


def collect_system_health():
    cpu_percent = None
    memory_percent = None
    memory_used_mb = None
    memory_total_mb = None

    if psutil is not None:
        try:
            cpu_percent = float(psutil.cpu_percent(interval=None))
        except Exception:
            cpu_percent = None
        try:
            vm = psutil.virtual_memory()
            memory_percent = float(vm.percent)
            memory_used_mb = float(vm.used) / (1024.0 * 1024.0)
            memory_total_mb = float(vm.total) / (1024.0 * 1024.0)
        except Exception:
            memory_percent = None
            memory_used_mb = None
            memory_total_mb = None

    load_1m = None
    if hasattr(os, "getloadavg"):
        try:
            load_1m = float(os.getloadavg()[0])
        except Exception:
            load_1m = None

    if cpu_percent is None and load_1m is not None:
        try:
            cpu_count = max(1, int(os.cpu_count() or 1))
            cpu_percent = max(0.0, min(100.0, (load_1m / float(cpu_count)) * 100.0))
        except Exception:
            cpu_percent = None

    if memory_percent is None or memory_total_mb is None:
        try:
            page_size = int(os.sysconf("SC_PAGE_SIZE"))
            total_pages = int(os.sysconf("SC_PHYS_PAGES"))
            total_bytes = float(page_size * total_pages)
            memory_total_mb = total_bytes / (1024.0 * 1024.0)

            available_pages_key = "SC_AVPHYS_PAGES"
            if available_pages_key in os.sysconf_names:
                available_pages = int(os.sysconf(available_pages_key))
                available_bytes = float(page_size * available_pages)
                used_bytes = max(0.0, total_bytes - available_bytes)
                memory_used_mb = used_bytes / (1024.0 * 1024.0)
                memory_percent = (used_bytes / total_bytes) * 100.0 if total_bytes > 0 else None
        except Exception:
            pass

    if (memory_percent is None or memory_used_mb is None) and os.name == "posix":
        try:
            vm_stat_output = subprocess.check_output(["vm_stat"], text=True)
            page_size_match = re.search(r"page size of\s+(\d+)\s+bytes", vm_stat_output)
            if page_size_match:
                vm_page_size = int(page_size_match.group(1))
            else:
                vm_page_size = 4096

            counters = {}
            for line in vm_stat_output.splitlines():
                key_val = line.split(":", 1)
                if len(key_val) != 2:
                    continue
                key = key_val[0].strip()
                raw_val = key_val[1].strip().rstrip(".")
                raw_val = raw_val.replace(".", "").replace(",", "")
                if raw_val.isdigit():
                    counters[key] = int(raw_val)

            free_pages = counters.get("Pages free", 0)
            inactive_pages = counters.get("Pages inactive", 0)
            speculative_pages = counters.get("Pages speculative", 0)
            available_pages = free_pages + inactive_pages + speculative_pages

            if memory_total_mb is not None and memory_total_mb > 0:
                total_bytes = memory_total_mb * 1024.0 * 1024.0
                available_bytes = float(available_pages * vm_page_size)
                used_bytes = max(0.0, total_bytes - available_bytes)
                memory_used_mb = used_bytes / (1024.0 * 1024.0)
                memory_percent = (used_bytes / total_bytes) * 100.0
        except Exception:
            pass

    process_mem_mb = None
    try:
        rss_kb = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        if os.name == "posix" and os.uname().sysname == "Darwin":
            process_mem_mb = rss_kb / (1024.0 * 1024.0)
        else:
            process_mem_mb = rss_kb / 1024.0
    except Exception:
        process_mem_mb = None

    return {
        "cpu_percent": cpu_percent,
        "memory_percent": memory_percent,
        "memory_used_mb": memory_used_mb,
        "memory_total_mb": memory_total_mb,
        "load_1m": load_1m,
        "process_mem_mb": process_mem_mb,
    }


def analyze_capture_health(samples, requested_samples):
    data = np.asarray(samples)
    if data.ndim != 1:
        data = data.reshape(-1)

    actual_samples = int(data.size)
    requested_samples = max(1, int(requested_samples))
    dropped_samples = max(0, requested_samples - actual_samples)
    drop_ratio = dropped_samples / float(requested_samples)

    if np.iscomplexobj(data):
        clip_mask = (np.abs(data.real) >= 0.98) | (np.abs(data.imag) >= 0.98)
        magnitude = np.abs(data)
        dc_offset = float(np.abs(np.mean(data))) if actual_samples else 0.0
    else:
        clip_mask = np.abs(data) >= 0.98
        magnitude = np.abs(data)
        dc_offset = float(abs(np.mean(data))) if actual_samples else 0.0

    clipping_ratio = float(np.mean(clip_mask)) if actual_samples else 0.0
    max_abs = float(np.max(magnitude)) if actual_samples else 0.0

    warnings = []
    if dropped_samples > 0:
        warnings.append("Dropped sample count is non-zero")
    if clipping_ratio >= 0.01:
        warnings.append("Clipping ratio is high (>=1%)")
    if max_abs <= 0.02:
        warnings.append("Signal amplitude appears very low")
    if dc_offset >= 0.1:
        warnings.append("DC offset appears elevated")

    status = "Healthy" if not warnings else "Warning"

    return {
        "status": status,
        "requested_samples": requested_samples,
        "actual_samples": actual_samples,
        "dropped_samples": dropped_samples,
        "drop_ratio": drop_ratio,
        "clipping_ratio": clipping_ratio,
        "max_abs": max_abs,
        "dc_offset": dc_offset,
        "warnings": warnings,
    }
