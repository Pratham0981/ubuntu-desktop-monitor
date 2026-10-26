"""CPU and RAM sampling for the desktop widget.

The Sampler is the project's test seam: callers ask for a Snapshot and never
touch psutil themselves.  Sampled values are cheap, so the widget can call
snapshot() as often as its refresh timer likes; the sampler decides whether a
new CPU sample is due.
"""

from __future__ import annotations

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
            self._last_sampled_at = now

        if self._disk is None or now - self._disk_sampled_at >= self._disk_interval:
            self._disk = self._read_disk()
            self._disk_sampled_at = now

        ram_used, ram_total = self._read_memory()
        return Snapshot(
            cpu_percent=self._cpu_percent,
            ram_used=ram_used,
            ram_total=ram_total,
            cpu_history=tuple(self._history),
            disk=self._disk,
            cpu_temp=self._read_temp(),
            processes=self._read_processes(),
        )
