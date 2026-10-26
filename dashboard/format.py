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
