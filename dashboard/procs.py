"""Top processes by CPU use, as a short list safe to render every second."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import psutil

TOP_LIMIT = 4
NAME_WIDTH = 24

SKIPPED_ERRORS = (
    psutil.NoSuchProcess,
    psutil.AccessDenied,
    psutil.ZombieProcess,
)


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    name: str
    cpu_percent: float
    memory_percent: float


def read_top_processes(
    limit: int = TOP_LIMIT,
    *,
    processes: Iterable | None = None,
) -> tuple[ProcessInfo, ...]:
    """Return up to ``limit`` processes, busiest CPU first."""
    if processes is None:
        processes = psutil.process_iter(
            ["pid", "name", "cpu_percent", "memory_percent"]
        )

    rows: list[ProcessInfo] = []
    for process in processes:
        try:
            info = process.info
            pid = info.get("pid")
            if pid is None:
                continue
            rows.append(
                ProcessInfo(
                    pid=int(pid),
                    name=_trim(str(info.get("name") or f"pid {pid}")),
                    cpu_percent=float(info.get("cpu_percent") or 0.0),
                    memory_percent=float(info.get("memory_percent") or 0.0),
                )
            )
        except SKIPPED_ERRORS:
            # Processes come and go while iterating; that is not an error.
            continue

    rows.sort(key=lambda row: (row.cpu_percent, row.memory_percent), reverse=True)
    return tuple(rows[:limit])


def _trim(name: str) -> str:
    return name if len(name) <= NAME_WIDTH else name[: NAME_WIDTH - 1] + "…"
