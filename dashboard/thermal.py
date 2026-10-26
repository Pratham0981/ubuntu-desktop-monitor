"""CPU temperature, from hwmon (via psutil) or the kernel thermal zones.

Machines without a usable sensor are normal: every path here returns ``None``
rather than raising.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import psutil

ZONE_ROOT = "/sys/class/thermal"

# Most specific first.  Laptop ACPI sensors are a last resort.
PREFERRED_ZONE_TYPES = (
    "x86_pkg_temp",
    "coretemp",
    "k10temp",
    "zenpower",
    "cpu_thermal",
    "soc_thermal",
)
PREFERRED_HWMON_KEYS = PREFERRED_ZONE_TYPES + ("acpitz",)

PLAUSIBLE_MIN_C = -20.0
PLAUSIBLE_MAX_C = 125.0


def read_cpu_temp(
    zone_root: str | Path = ZONE_ROOT,
    *,
    sensors: Callable[[], dict] = psutil.sensors_temperatures,
) -> float | None:
    """Return the CPU temperature in Celsius, or None when unavailable."""
    try:
        hwmon = sensors()
    except (OSError, AttributeError):
        hwmon = {}
    from_hwmon = _from_hwmon(hwmon)
    if from_hwmon is not None:
        return from_hwmon
    return _from_sysfs(Path(zone_root))


def _from_hwmon(readings: dict) -> float | None:
    for key in PREFERRED_HWMON_KEYS:
        for entry in readings.get(key) or ():
            current = getattr(entry, "current", None)
            if current is not None and _plausible(current):
                return float(current)
    return None


def _from_sysfs(root: Path) -> float | None:
    zones: list[tuple[str, float]] = []
    try:
        paths = sorted(root.glob("thermal_zone*"))
    except OSError:
        return None

    for zone in paths:
        try:
            name = (zone / "type").read_text().strip()
            celsius = int((zone / "temp").read_text().strip()) / 1000.0
        except (OSError, ValueError):
            continue
        if _plausible(celsius):
            zones.append((name, celsius))

    for preferred in PREFERRED_ZONE_TYPES:
        for name, celsius in zones:
            if name == preferred:
                return celsius
    for name, celsius in zones:
        if name.startswith("acpitz") or "cpu" in name:
            return celsius
    return None


def _plausible(celsius: float) -> bool:
    return PLAUSIBLE_MIN_C < float(celsius) < PLAUSIBLE_MAX_C
