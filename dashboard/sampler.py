"""CPU and RAM sampling for the desktop widget.

The Sampler is the project's test seam: callers ask for a Snapshot and never
touch psutil themselves.  Sampled values are cheap, so the widget can call
snapshot() as often as its refresh timer likes; the sampler decides whether a
new CPU sample is due.
"""

from __future__ import annotations

import os
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable

import psutil

from .disk import DiskStats, read_disk as _read_system_disk
from .procs import ProcessInfo, read_top_processes as _read_system_processes
from .thermal import read_cpu_temp as _read_system_temp

HISTORY_SECONDS = 300
SAMPLE_INTERVAL = 1.0
DISK_INTERVAL = 30.0


@dataclass(frozen=True)
class Snapshot:
    """A plain, immutable reading of the machine."""

    cpu_percent: float
    ram_used: int
    ram_total: int
    cpu_history: tuple[float, ...]
    disk: DiskStats
    cpu_temp: float | None
    processes: tuple[ProcessInfo, ...]
    core_percents: tuple[float, ...] = ()
    net_down: float = 0.0
    net_up: float = 0.0
    load_avg: tuple[float, float, float] | None = None
    uptime: float | None = None


class _PsutilCpuReader:
    """psutil CPU reader with a meaningful first reading.

    psutil reports 0.0 on the first non-blocking call, and a non-blocking call
    straight after priming measures a near-zero window (often 100%).  So the
    first reading blocks for a tenth of a second, once, at startup.
    """

    def __init__(self) -> None:
        self._primed = False

    def __call__(self) -> float:
        if not self._primed:
            self._primed = True
            return psutil.cpu_percent(interval=0.1)
        return psutil.cpu_percent(interval=None)


class _PsutilCoreReader:
    """Per-core load; the first reading blocks briefly, like the CPU reader."""

    def __init__(self) -> None:
        self._primed = False

    def __call__(self) -> tuple[float, ...]:
        if not self._primed:
            self._primed = True
            return tuple(psutil.cpu_percent(interval=0.1, percpu=True))
        return tuple(psutil.cpu_percent(interval=None, percpu=True))


def _psutil_net_reader() -> tuple[int, int]:
    """Total bytes received and sent, ignoring the loopback interface."""
    received = sent = 0
    for name, counters in psutil.net_io_counters(pernic=True).items():
        if name == "lo":
            continue
        received += counters.bytes_recv
        sent += counters.bytes_sent
    return received, sent


def _system_reader() -> tuple[tuple[float, float, float] | None, float | None]:
    try:
        load = os.getloadavg()
    except OSError:
        load = None
    try:
        uptime = max(0.0, time.time() - psutil.boot_time())
    except (OSError, AttributeError):
        uptime = None
    return load, uptime


def _psutil_memory_reader() -> tuple[int, int]:
    memory = psutil.virtual_memory()
    return memory.used, memory.total


class Sampler:
    """Collects CPU load and RAM usage, keeping ~5 minutes of CPU history."""

    def __init__(
        self,
        *,
        interval: float = SAMPLE_INTERVAL,
        history_seconds: float = HISTORY_SECONDS,
        disk_interval: float = DISK_INTERVAL,
        clock: Callable[[], float] = time.monotonic,
        read_cpu: Callable[[], float] | None = None,
        read_memory: Callable[[], tuple[int, int]] | None = None,
        read_disk: Callable[[], DiskStats] | None = None,
        read_temp: Callable[[], float | None] | None = None,
        read_processes: Callable[[], tuple[ProcessInfo, ...]] | None = None,
        read_cores: Callable[[], tuple[float, ...]] | None = None,
        read_net: Callable[[], tuple[int, int]] | None = None,
        read_system: Callable[[], tuple] | None = None,
    ) -> None:
        if interval <= 0:
            raise ValueError("interval must be positive")
        self._interval = interval
        self._disk_interval = disk_interval
        self._clock = clock
        self._read_cpu = read_cpu or _PsutilCpuReader()
        self._read_memory = read_memory or _psutil_memory_reader
        self._read_disk = read_disk or (lambda: _read_system_disk())
        self._read_temp = read_temp or (lambda: _read_system_temp())
        self._read_processes = read_processes or (lambda: _read_system_processes())
        self._read_cores = read_cores or _PsutilCoreReader()
        self._read_net = read_net or _psutil_net_reader
        self._read_system = read_system or _system_reader
        self._cores: tuple[float, ...] = ()
        self._net_last: tuple[float, int, int] | None = None
        self._net_down = 0.0
        self._net_up = 0.0
        self._history: deque[float] = deque(
            maxlen=max(1, round(history_seconds / interval))
        )
        self._last_sampled_at: float | None = None
        self._cpu_percent = 0.0
        self._disk: DiskStats | None = None
        self._disk_sampled_at = 0.0

    def snapshot(self) -> Snapshot:
        """Return the current reading, taking a new CPU sample when one is due."""
        now = self._clock()
        if self._last_sampled_at is None or now - self._last_sampled_at >= self._interval:
            self._cpu_percent = min(100.0, max(0.0, float(self._read_cpu())))
            self._history.append(self._cpu_percent)
            self._cores = tuple(
                min(100.0, max(0.0, float(value))) for value in self._read_cores()
            )
            received, sent = self._read_net()
            if self._net_last is not None:
                elapsed = now - self._net_last[0]
                if elapsed > 0:
                    self._net_down = max(0.0, (received - self._net_last[1]) / elapsed)
                    self._net_up = max(0.0, (sent - self._net_last[2]) / elapsed)
            self._net_last = (now, received, sent)
            self._last_sampled_at = now

        if self._disk is None or now - self._disk_sampled_at >= self._disk_interval:
            self._disk = self._read_disk()
            self._disk_sampled_at = now

        ram_used, ram_total = self._read_memory()
        load_avg, uptime = self._read_system()
        return Snapshot(
            cpu_percent=self._cpu_percent,
            ram_used=ram_used,
            ram_total=ram_total,
            cpu_history=tuple(self._history),
            disk=self._disk,
            cpu_temp=self._read_temp(),
            processes=self._read_processes(),
            core_percents=self._cores,
            net_down=self._net_down,
            net_up=self._net_up,
            load_avg=load_avg,
            uptime=uptime,
        )
