"""Behaviour of the compact widget window, exercised on a real GTK display.

Run the suite under `xvfb-run -a env DASHBOARD_GUI_TESTS=1 python3 -m pytest`;
the tests skip themselves otherwise so they never open windows on a live
desktop session.
"""

import os
import subprocess

import pytest

pytestmark = pytest.mark.skipif(
    not (os.environ.get("DISPLAY") and os.environ.get("DASHBOARD_GUI_TESTS")),
    reason="GUI tests are opt-in: xvfb-run -a env DASHBOARD_GUI_TESTS=1 python3 -m pytest",
)

gi = pytest.importorskip("gi")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from dashboard.disk import DiskStats, MountUsage  # noqa: E402
from dashboard.procs import ProcessInfo  # noqa: E402
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
    cpu_temp=53.4,
    processes=(
        ProcessInfo(pid=11, name="firefox", cpu_percent=12.3, memory_percent=7.5),
        ProcessInfo(pid=12, name="python3", cpu_percent=8.0, memory_percent=1.2),
    ),
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
    assert 120 <= height <= 420
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


def test_update_shows_temperature_and_top_processes():
    window = DashboardWindow(lambda: SNAP)

    window.update(SNAP)

    assert window.temp_value.get_text() == "53°C"
    rows = window.process_rows
    assert rows[0][1].get_text() == "firefox"
    assert rows[0][2].get_text() == "12%"
    assert rows[0][3].get_text() == "8%"
    assert rows[0][0].get_visible() is True
    assert rows[2][0].get_visible() is False


def test_update_shows_na_when_the_sensor_is_missing():
    window = DashboardWindow(lambda: SNAP)
    without_temp = Snapshot(
        cpu_percent=SNAP.cpu_percent,
        ram_used=SNAP.ram_used,
        ram_total=SNAP.ram_total,
        cpu_history=SNAP.cpu_history,
        disk=SNAP.disk,
        cpu_temp=None,
        processes=(),
    )

    window.update(without_temp)

    assert window.temp_value.get_text() == "n/a"
    assert all(not row[0].get_visible() for row in window.process_rows)


# -- placement on XWayland -------------------------------------------------


def pump():
    while Gtk.events_pending():
        Gtk.main_iteration_do(False)


def xprop(window, prop):
    xid = window.get_window().get_xid()
    result = subprocess.run(
        ["xprop", "-id", hex(xid), prop], capture_output=True, text=True
    )
    return result.stdout


def test_desktop_placement_sets_desktop_type_and_below_state():
    from dashboard import placement

    window = DashboardWindow(lambda: SNAP)
    placement.prepare_desktop_placement(window)
    window.show_all()
    pump()

    assert placement.apply_desktop_placement(window) is True
    pump()

    assert "_NET_WM_WINDOW_TYPE_DESKTOP" in xprop(window, "_NET_WM_WINDOW_TYPE")
    # The below request goes to the window manager as an EWMH client message;
    # Xvfb has no WM, so only the client-side hints are observable here.
    assert "_NET_WM_STATE_SKIP_TASKBAR" in xprop(window, "_NET_WM_STATE")
    assert "accepts input or input focus: False" in xprop(window, "WM_HINTS")


def test_placement_reports_failure_without_an_x11_window():
    from dashboard import placement

    window = DashboardWindow(lambda: SNAP)

    assert placement.apply_desktop_placement(window) is False


def test_fallback_keeps_the_window_above_and_in_the_corner():
    from dashboard import placement

    window = DashboardWindow(lambda: SNAP)
    window.show_all()
    pump()

    placement.place_top_left(window, margin=24)
    pump()

    assert window.get_position() == (24, 56)


def test_prepare_positions_the_window_with_its_real_width_before_allocation():
    from dashboard import placement

    window = DashboardWindow(lambda: SNAP)
    placement.prepare_desktop_placement(window, margin=24)
    window.show_all()
    pump()

    assert window.get_position() == (24, 56)


def window_pixel(window, x, y):
    pixbuf = Gdk.pixbuf_get_from_window(window.get_window(), x, y, 1, 1)
    return tuple(pixbuf.get_pixels()[:4])


def test_panel_paints_a_semi_opaque_grey_with_rounded_corners():
    window = DashboardWindow(lambda: SNAP)
    window.show_all()
    pump()
    window.update(SNAP)
    pump()

    red, green, blue, alpha = window_pixel(window, 150, 300)

    assert alpha >= 220, "panel must not be transparent"
    assert 20 <= red <= 70, "panel should be grey-black, not the desktop"
    assert abs(red - green) <= 4 and abs(green - blue) <= 8
    assert window_pixel(window, 1, 1)[3] == 0, "corner should be rounded away"


def test_update_shows_a_row_per_tracked_mount():
    window = DashboardWindow(lambda: SNAP)
    with_home = Snapshot(
        cpu_percent=SNAP.cpu_percent,
        ram_used=SNAP.ram_used,
        ram_total=SNAP.ram_total,
        cpu_history=SNAP.cpu_history,
        disk=DiskStats(
            root_used=SNAP.disk.root_used,
            root_total=SNAP.disk.root_total,
            root_percent=SNAP.disk.root_percent,
            disk_total=SNAP.disk.disk_total,
            disk_free=SNAP.disk.disk_free,
            mounts=(
                MountUsage(
                    mountpoint="/home",
                    used=66_000_000_000,
                    total=94_637_993_984,
                    percent=69.7,
                ),
            ),
        ),
        cpu_temp=SNAP.cpu_temp,
        processes=SNAP.processes,
    )

    window.update(with_home)

    container, caption, value, bar = window.mount_rows[0]
    assert caption.get_text() == "DISK /home"
    assert value.get_text() == "61.5 GB / 88.1 GB · 70%"
    assert bar.get_fraction() == pytest.approx(0.697)
    assert container.get_visible() is True

    window.update(SNAP)

    assert container.get_visible() is False
