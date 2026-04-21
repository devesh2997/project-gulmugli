#!/usr/bin/env python3
"""
JARVIS System Monitor -- Jetson Orin Nano

Monitors RAM, GPU VRAM, CPU/GPU temperature, and per-process memory usage.
Outputs as JSON for dashboard integration, or as a human-readable table.

Usage:
    python3 monitor.py                 # one-shot, human-readable
    python3 monitor.py --json          # one-shot, JSON output
    python3 monitor.py --loop          # continuous monitoring (2s interval)
    python3 monitor.py --loop --json   # continuous JSON (one object per line)
    python3 monitor.py --interval 5    # custom interval in seconds

Can also run as a systemd service for continuous monitoring.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# ── Data classes ────────────────────────────────────────────────────

@dataclass
class MemoryInfo:
    total_mb: int = 0
    used_mb: int = 0
    available_mb: int = 0
    swap_total_mb: int = 0
    swap_used_mb: int = 0
    usage_percent: float = 0.0


@dataclass
class GpuInfo:
    utilization_percent: int = 0
    clock_mhz: int = 0
    # On Jetson, VRAM is shared with CPU RAM (unified memory).
    # There is no separate VRAM counter. The GPU "VRAM" usage is
    # part of the total RAM reported by /proc/meminfo.
    # We report estimated GPU memory based on known model sizes.
    estimated_gpu_mb: int = 0


@dataclass
class ThermalInfo:
    cpu_temp_c: float = 0.0
    gpu_temp_c: float = 0.0
    soc_temp_c: float = 0.0


@dataclass
class ProcessInfo:
    name: str = ""
    pid: int = 0
    rss_mb: float = 0.0
    cpu_percent: float = 0.0


@dataclass
class SystemSnapshot:
    timestamp: float = 0.0
    platform: str = ""
    memory: MemoryInfo = field(default_factory=MemoryInfo)
    gpu: GpuInfo = field(default_factory=GpuInfo)
    thermal: ThermalInfo = field(default_factory=ThermalInfo)
    processes: list = field(default_factory=list)
    alerts: list = field(default_factory=list)


# ── Platform detection ──────────────────────────────────────────────

def detect_platform() -> str:
    """Returns 'jetson', 'mac', 'linux', or 'unknown'."""
    import platform as plat
    if plat.system() == "Darwin":
        return "mac"
    if os.path.exists("/etc/nv_tegra_release"):
        return "jetson"
    if plat.system() == "Linux":
        return "linux"
    return "unknown"


# ── Memory ──────────────────────────────────────────────────────────

def get_memory_info() -> MemoryInfo:
    """Read system memory from /proc/meminfo (Linux) or vm_stat (macOS)."""
    info = MemoryInfo()

    try:
        meminfo_path = Path("/proc/meminfo")
        if meminfo_path.exists():
            text = meminfo_path.read_text()
            values = {}
            for line in text.splitlines():
                parts = line.split()
                if len(parts) >= 2:
                    key = parts[0].rstrip(":")
                    val = int(parts[1])  # in kB
                    values[key] = val

            info.total_mb = values.get("MemTotal", 0) // 1024
            info.available_mb = values.get("MemAvailable", 0) // 1024
            info.used_mb = info.total_mb - info.available_mb
            info.swap_total_mb = values.get("SwapTotal", 0) // 1024
            info.swap_used_mb = (values.get("SwapTotal", 0) - values.get("SwapFree", 0)) // 1024

            if info.total_mb > 0:
                info.usage_percent = round(info.used_mb / info.total_mb * 100, 1)
        else:
            # macOS fallback using vm_stat
            result = subprocess.run(
                ["vm_stat"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                pages = {}
                for line in result.stdout.splitlines():
                    match = re.match(r"(.+?):\s+(\d+)", line)
                    if match:
                        pages[match.group(1).strip()] = int(match.group(2))

                page_size = 16384  # ARM64 macOS default
                # Try to get actual page size
                ps_match = re.search(r"page size of (\d+) bytes", result.stdout)
                if ps_match:
                    page_size = int(ps_match.group(1))

                free = pages.get("Pages free", 0) * page_size // (1024 * 1024)
                active = pages.get("Pages active", 0) * page_size // (1024 * 1024)
                inactive = pages.get("Pages inactive", 0) * page_size // (1024 * 1024)
                wired = pages.get("Pages wired down", 0) * page_size // (1024 * 1024)

                info.total_mb = free + active + inactive + wired
                info.used_mb = active + wired
                info.available_mb = free + inactive
                if info.total_mb > 0:
                    info.usage_percent = round(info.used_mb / info.total_mb * 100, 1)
    except Exception:
        pass

    return info


# ── GPU (Jetson tegrastats) ─────────────────────────────────────────

def get_gpu_info() -> GpuInfo:
    """
    Read GPU utilization from tegrastats (Jetson) or return empty (other platforms).

    tegrastats output format:
        GR3D [80%@1020]
    meaning: GPU 3D engine at 80% utilization, 1020 MHz clock.
    """
    info = GpuInfo()

    try:
        # Method 1: Read from sysfs (no sudo needed, instant)
        gpu_load_path = Path("/sys/devices/gpu.0/load")
        if gpu_load_path.exists():
            # Value is 0-1000 (permille)
            load = int(gpu_load_path.read_text().strip())
            info.utilization_percent = load // 10

        gpu_freq_path = Path("/sys/devices/17000000.ga10b/devfreq/17000000.ga10b/cur_freq")
        if not gpu_freq_path.exists():
            # Try alternative path
            for p in Path("/sys/devices/").glob("*/devfreq/*/cur_freq"):
                if "ga10b" in str(p) or "gpu" in str(p):
                    gpu_freq_path = p
                    break

        if gpu_freq_path.exists():
            freq_hz = int(gpu_freq_path.read_text().strip())
            info.clock_mhz = freq_hz // 1_000_000

    except Exception:
        pass

    return info


# ── Thermal ─────────────────────────────────────────────────────────

def get_thermal_info() -> ThermalInfo:
    """
    Read temperatures from thermal zones.

    Jetson thermal zones vary by JetPack version. Common mappings:
        thermal_zone0: CPU
        thermal_zone1: GPU
        thermal_zone2: SoC (CV/DLA)

    Values are in millidegrees Celsius (e.g., 52000 = 52.0 C).
    """
    info = ThermalInfo()

    try:
        thermal_base = Path("/sys/devices/virtual/thermal")
        if not thermal_base.exists():
            return info

        temps = {}
        for zone_dir in sorted(thermal_base.glob("thermal_zone*")):
            temp_file = zone_dir / "temp"
            type_file = zone_dir / "type"
            if temp_file.exists():
                try:
                    temp_mc = int(temp_file.read_text().strip())
                    temp_c = temp_mc / 1000.0
                    zone_type = ""
                    if type_file.exists():
                        zone_type = type_file.read_text().strip().lower()
                    temps[zone_type] = temp_c
                except (ValueError, OSError):
                    pass

        # Map zone types to our fields
        # Jetson Orin Nano typical types: CPU-therm, GPU-therm, SOC0-therm, SOC1-therm, SOC2-therm, tj-therm
        for zone_type, temp in temps.items():
            if "cpu" in zone_type:
                info.cpu_temp_c = temp
            elif "gpu" in zone_type:
                info.gpu_temp_c = temp
            elif "soc" in zone_type and info.soc_temp_c == 0:
                info.soc_temp_c = temp
            elif "tj" in zone_type:
                # tj = junction temperature (hottest point). Use as CPU if CPU zone not found.
                if info.cpu_temp_c == 0:
                    info.cpu_temp_c = temp

        # Fallback: if no typed zones found, use zone0 as CPU temp
        if info.cpu_temp_c == 0.0:
            zone0_temp = Path("/sys/devices/virtual/thermal/thermal_zone0/temp")
            if zone0_temp.exists():
                try:
                    info.cpu_temp_c = int(zone0_temp.read_text().strip()) / 1000.0
                except (ValueError, OSError):
                    pass

    except Exception:
        pass

    return info


# ── Per-process memory ──────────────────────────────────────────────

# Process names to monitor (partial match on command line)
MONITORED_PROCESSES = [
    "ollama",
    "python",        # JARVIS assistant
    "mpv",           # Music playback
    "chromium",      # Dashboard kiosk
    "pulseaudio",    # Audio server
    "pipewire",      # Audio server (alternative)
]


def get_process_info() -> list:
    """Get memory usage for JARVIS-related processes."""
    processes = []

    try:
        # Use ps for cross-platform compatibility
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return processes

        for line in result.stdout.splitlines()[1:]:  # skip header
            parts = line.split(None, 10)  # max 11 fields
            if len(parts) < 11:
                continue

            pid = int(parts[1])
            cpu_pct = float(parts[2])
            rss_kb = int(parts[5])  # RSS in KB (field index 5)
            command = parts[10]

            # Check if this process matches any of our monitored names
            cmd_lower = command.lower()
            for name in MONITORED_PROCESSES:
                if name in cmd_lower:
                    # Use a friendlier name
                    display_name = name
                    if "main.py" in command:
                        display_name = "jarvis-assistant"
                    elif "ollama serve" in command or "ollama_llama_server" in cmd_lower:
                        display_name = "ollama"
                    elif "chromium" in cmd_lower:
                        display_name = "chromium"

                    processes.append(ProcessInfo(
                        name=display_name,
                        pid=pid,
                        rss_mb=round(rss_kb / 1024, 1),
                        cpu_percent=cpu_pct,
                    ))
                    break

    except Exception:
        pass

    # Sort by RSS descending, deduplicate by grouping same-name processes
    grouped = {}
    for p in processes:
        key = p.name
        if key not in grouped:
            grouped[key] = p
        else:
            # Aggregate: sum RSS and CPU, keep highest PID
            grouped[key].rss_mb += p.rss_mb
            grouped[key].cpu_percent += p.cpu_percent
            grouped[key].rss_mb = round(grouped[key].rss_mb, 1)

    result = sorted(grouped.values(), key=lambda p: p.rss_mb, reverse=True)
    return [asdict(p) for p in result]


# ── Alerts ──────────────────────────────────────────────────────────

def check_alerts(snapshot: SystemSnapshot) -> list:
    """Generate alerts based on system state."""
    alerts = []

    mem = snapshot.memory
    if mem.usage_percent > 90:
        alerts.append({
            "level": "critical",
            "message": f"RAM usage at {mem.usage_percent}% ({mem.used_mb}/{mem.total_mb}MB). OOM kill risk!",
        })
    elif mem.usage_percent > 80:
        alerts.append({
            "level": "warning",
            "message": f"RAM usage at {mem.usage_percent}% ({mem.used_mb}/{mem.total_mb}MB).",
        })

    thermal = snapshot.thermal
    if thermal.cpu_temp_c > 85:
        alerts.append({
            "level": "critical",
            "message": f"CPU temperature {thermal.cpu_temp_c}C -- thermal throttling likely.",
        })
    elif thermal.cpu_temp_c > 70:
        alerts.append({
            "level": "warning",
            "message": f"CPU temperature {thermal.cpu_temp_c}C -- monitor closely.",
        })

    if thermal.gpu_temp_c > 85:
        alerts.append({
            "level": "critical",
            "message": f"GPU temperature {thermal.gpu_temp_c}C -- thermal throttling likely.",
        })

    return alerts


# ── Snapshot ────────────────────────────────────────────────────────

def take_snapshot() -> SystemSnapshot:
    """Collect a full system snapshot."""
    snapshot = SystemSnapshot(
        timestamp=time.time(),
        platform=detect_platform(),
        memory=get_memory_info(),
        gpu=get_gpu_info(),
        thermal=get_thermal_info(),
        processes=get_process_info(),
    )
    snapshot.alerts = check_alerts(snapshot)
    return snapshot


# ── Output formatters ───────────────────────────────────────────────

def format_human(snapshot: SystemSnapshot) -> str:
    """Format snapshot as a human-readable table."""
    lines = []
    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(snapshot.timestamp))
    lines.append(f"JARVIS System Monitor -- {ts} ({snapshot.platform})")
    lines.append("=" * 60)

    # Memory
    mem = snapshot.memory
    bar_len = 30
    filled = int(bar_len * mem.usage_percent / 100)
    bar = "#" * filled + "-" * (bar_len - filled)
    lines.append(f"RAM:  [{bar}] {mem.usage_percent}%")
    lines.append(f"      {mem.used_mb}/{mem.total_mb} MB used, {mem.available_mb} MB available")
    if mem.swap_total_mb > 0:
        lines.append(f"Swap: {mem.swap_used_mb}/{mem.swap_total_mb} MB")

    # GPU
    gpu = snapshot.gpu
    if gpu.utilization_percent > 0 or gpu.clock_mhz > 0:
        lines.append(f"GPU:  {gpu.utilization_percent}% utilization @ {gpu.clock_mhz} MHz")

    # Thermal
    thermal = snapshot.thermal
    temp_parts = []
    if thermal.cpu_temp_c > 0:
        temp_parts.append(f"CPU {thermal.cpu_temp_c:.0f}C")
    if thermal.gpu_temp_c > 0:
        temp_parts.append(f"GPU {thermal.gpu_temp_c:.0f}C")
    if thermal.soc_temp_c > 0:
        temp_parts.append(f"SoC {thermal.soc_temp_c:.0f}C")
    if temp_parts:
        lines.append(f"Temp: {', '.join(temp_parts)}")

    # Processes
    if snapshot.processes:
        lines.append("")
        lines.append(f"{'Process':<25} {'PID':>8} {'RSS MB':>10} {'CPU%':>8}")
        lines.append("-" * 55)
        for p in snapshot.processes:
            lines.append(
                f"{p['name']:<25} {p['pid']:>8} {p['rss_mb']:>10.1f} {p['cpu_percent']:>7.1f}%"
            )

    # Alerts
    if snapshot.alerts:
        lines.append("")
        for alert in snapshot.alerts:
            level = alert["level"].upper()
            lines.append(f"!!! {level}: {alert['message']}")

    return "\n".join(lines)


def format_json(snapshot: SystemSnapshot) -> str:
    """Format snapshot as a JSON string."""
    data = asdict(snapshot)
    return json.dumps(data, separators=(",", ":"))


# ── Main ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="JARVIS System Monitor")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--loop", action="store_true", help="Continuous monitoring")
    parser.add_argument("--interval", type=float, default=2.0, help="Seconds between snapshots (default: 2)")
    args = parser.parse_args()

    formatter = format_json if args.json else format_human

    if args.loop:
        try:
            while True:
                snapshot = take_snapshot()
                output = formatter(snapshot)
                if args.json:
                    print(output, flush=True)
                else:
                    # Clear screen for human-readable mode
                    print("\033[2J\033[H", end="")
                    print(output, flush=True)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nMonitor stopped.", file=sys.stderr)
    else:
        snapshot = take_snapshot()
        print(formatter(snapshot))

        # Exit with non-zero if critical alerts
        if any(a["level"] == "critical" for a in snapshot.alerts):
            sys.exit(1)


if __name__ == "__main__":
    main()
