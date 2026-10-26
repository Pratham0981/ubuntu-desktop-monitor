"""Behaviour of the compact widget window, exercised on a real GTK display.

Run the suite under `xvfb-run -a python3 -m pytest` to avoid windows on the
live session; the tests skip themselves when no display is available.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY"), reason="needs an X display (use xvfb-run)"
)

gi = pytest.importorskip("gi")
gi.require_version("Gtk", "3.0")
from gi.repository import GLib  # noqa: E402

from dashboard.disk import DiskStats  # noqa: E402
from dashboard.sampler import Snapshot  # noqa: E402
from dashboard.widget import DashboardWindow  # noqa: E402

DISK = DiskStats(
    root_used=49_505_730_560,
    root_total=102_683_975_680,
    root_percent=48.2,
    disk_total=202_369_925_120,
    disk_free=109_033_067_008,
)

SNAP = Snapshot(
    cpu_percent=42.0,
    ram_used=4_294_967_296,
    ram_total=8_589_934_592,
    cpu_history=(5.0, 12.0, 42.0),
    disk=DISK,
)


def run_loop(milliseconds):
    loop = GLib.MainLoop()
    GLib.timeout_add(milliseconds, loop.quit)
    loop.run()


def test_update_shows_cpu_and_ram_as_numbers_and_bars():
    window = DashboardWindow(lambda: SNAP)

    window.update(SNAP)

    assert window.cpu_value.get_text() == "42%"
    assert window.ram_value.get_text() == "4.0 GB / 8.0 GB"
    assert window.cpu_bar.get_fraction() == pytest.approx(0.42)
    assert window.ram_bar.get_fraction() == pytest.approx(0.5)


def test_window_is_compact_and_painted_by_css():
    window = DashboardWindow(lambda: SNAP)

    width, height = window.get_default_size()

    assert 200 <= width <= 360
    assert 120 <= height <= 320
    assert window.get_app_paintable() is True


def test_refresh_polls_the_sampler_on_every_interval():
    calls = []

    def provider():
        calls.append(1)
        return SNAP

    window = DashboardWindow(provider, interval_ms=40)
    window.start()

    run_loop(250)

    assert len(calls) >= 3


def test_stop_halts_the_refresh_timer():
    calls = []

    def provider():
        calls.append(1)
        return SNAP

    window = DashboardWindow(provider, interval_ms=40)
    window.start()
    run_loop(120)
    window.stop()
    seen = len(calls)
    run_loop(150)

    assert len(calls) == seen


def test_update_shows_the_root_filesystem_and_whole_disk():
    window = DashboardWindow(lambda: SNAP)

    window.update(SNAP)

    assert window.disk_value.get_text() == "46.1 GB / 95.6 GB · 48%"
    assert window.disk_bar.get_fraction() == pytest.approx(0.482)
    assert window.ssd_note.get_text() == "SSD 188.5 GB · 101.5 GB free"
