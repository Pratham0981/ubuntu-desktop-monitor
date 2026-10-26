"""Small formatting helpers so every row of the widget reads the same way."""

from __future__ import annotations

_UNITS = ("B", "KB", "MB", "GB", "TB", "PB")


def format_bytes(count: float) -> str:
    """Render a byte count with binary units, e.g. ``4.0 GB``."""
    value = float(count)
    unit = _UNITS[0]
    for unit in _UNITS:
        if value < 1024 or unit == _UNITS[-1]:
            break
        value /= 1024
    if unit == "B":
        return f"{int(value)} B"
    return f"{value:.1f} {unit}"


def format_pair(used: float, total: float) -> str:
    """Render ``used / total`` for a resource row."""
    return f"{format_bytes(used)} / {format_bytes(total)}"


def format_percent(value: float) -> str:
    """Render a percentage as a whole number, e.g. ``42%``."""
    return f"{value:.0f}%"


def format_temp(celsius: float | None) -> str:
    """Render a temperature, or ``n/a`` when the sensor is missing."""
    if celsius is None:
        return "n/a"
    return f"{celsius:.0f}°C"


def format_rate(bytes_per_second: float) -> str:
    """Render a transfer speed, e.g. ``1.2 MB/s``."""
    value = max(0.0, float(bytes_per_second))
    unit = "B/s"
    for unit in ("B/s", "KB/s", "MB/s", "GB/s"):
        if value < 1024 or unit == "GB/s":
            break
        value /= 1024
    if unit == "B/s":
        return f"{value:.0f} {unit}"
    return f"{value:.1f} {unit}"


def format_uptime(seconds: float) -> str:
    """Render an uptime as its two largest units, e.g. ``3d 4h``."""
    minutes = int(max(0.0, seconds) // 60)
    days, minutes = divmod(minutes, 1440)
    hours, minutes = divmod(minutes, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"
