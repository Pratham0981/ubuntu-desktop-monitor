"""Disk usage for the root filesystem and the physical disk that holds it.

"Whole SSD" means every partition of the physical disk containing ``/``: the
root ext4 volume, a separate ``/home``, the EFI partition, and any Windows
partition sharing that disk.  Unmounted partitions count toward the total but
cannot report free space, so they add nothing to the free figure.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, replace
from typing import Any, Callable, Iterator

import psutil

# Filesystems shown alongside the root row.  ``/home`` lives on its own
# partition (nvme0n1p4 here).
TRACKED_MOUNTS = ("/home",)

LSBLK_COMMAND = (
    "lsblk",
    "-J",
    "-b",
    "-o",
    "NAME,TYPE,SIZE,FSTYPE,MOUNTPOINTS,PKNAME",
)


@dataclass(frozen=True)
class MountUsage:
    """Usage for one tracked filesystem."""

    mountpoint: str
    used: int
    total: int
    percent: float


@dataclass(frozen=True)
class DiskStats:
    """Root filesystem figures, whole-disk totals and tracked mounts."""

    root_used: int
    root_total: int
    root_percent: float
    disk_total: int
    disk_free: int
    mounts: tuple[MountUsage, ...] = ()


def read_disk(
    root_mount: str = "/",
    *,
    tracked_mounts: tuple[str, ...] = TRACKED_MOUNTS,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    usage: Callable[[str], Any] = psutil.disk_usage,
) -> DiskStats:
    """Read the machine's disk layout, falling back to the root filesystem."""
    try:
        completed = run(
            LSBLK_COMMAND, capture_output=True, text=True, check=True, timeout=5
        )
        payload = json.loads(completed.stdout)
        stats = parse_lsblk(payload, root_mount=root_mount, usage=usage)
    except (OSError, subprocess.SubprocessError, ValueError):
        stats = _root_only(usage(root_mount))
    return replace(stats, mounts=_mount_usage(tracked_mounts, usage))


def parse_lsblk(
    payload: dict,
    root_mount: str = "/",
    *,
    usage: Callable[[str], Any] = psutil.disk_usage,
) -> DiskStats:
    """Turn ``lsblk --json`` output into a DiskStats for ``root_mount``."""
    root_usage = usage(root_mount)
    nodes = list(_walk(payload.get("blockdevices") or []))
    root_node = next(
        (node for node in nodes if root_mount in _mountpoints(node)), None
    )
    if root_node is None:
        return _root_only(root_usage)

    parent = root_node.get("pkname") or root_node.get("name")
    siblings = [node for node in nodes if node.get("pkname") == parent]
    if not siblings:
        siblings = [root_node]

    total = sum(int(node.get("size") or 0) for node in siblings)
    free = 0
    seen: set[str] = set()
    for node in siblings:
        for mount in _mountpoints(node):
            if mount in seen:
                continue
            seen.add(mount)
            try:
                free += int(usage(mount).free)
            except OSError:
                # A mount can vanish between lsblk and this call.
                continue

    return DiskStats(
        root_used=int(root_usage.used),
        root_total=int(root_usage.total),
        root_percent=_percent(root_usage.used, root_usage.total),
        disk_total=total,
        disk_free=free,
    )


def _root_only(root_usage) -> DiskStats:
    return DiskStats(
        root_used=int(root_usage.used),
        root_total=int(root_usage.total),
        root_percent=_percent(root_usage.used, root_usage.total),
        disk_total=int(root_usage.total),
        disk_free=int(root_usage.free),
    )


def _mount_usage(
    mountpoints: tuple[str, ...], usage: Callable[[str], Any]
) -> tuple[MountUsage, ...]:
    rows = []
    for mountpoint in mountpoints:
        try:
            stats = usage(mountpoint)
        except OSError:
            # Not mounted (yet); skip it rather than reporting zeroes.
            continue
        rows.append(
            MountUsage(
                mountpoint=mountpoint,
                used=int(stats.used),
                total=int(stats.total),
                percent=_percent(stats.used, stats.total),
            )
        )
    return tuple(rows)


def _percent(used: float, total: float) -> float:
    if not total:
        return 0.0
    return float(used) / float(total) * 100.0


def _walk(nodes: list[dict]) -> Iterator[dict]:
    for node in nodes:
        yield node
        yield from _walk(node.get("children") or [])


def _mountpoints(node: dict) -> list[str]:
    mounts = node.get("mountpoints")
    if isinstance(mounts, list):
        return [mount for mount in mounts if mount]
    mount = node.get("mountpoint")
    return [mount] if mount else []
