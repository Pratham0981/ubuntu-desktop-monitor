"""The compact, dark, translucent widget window."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gdk, GLib, Gtk

from .format import format_bytes, format_pair, format_percent
from .sampler import Snapshot

INTERVAL_MS = 1000

CSS = b"""
window.dashboard {
    background-color: rgba(16, 18, 22, 0.82);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 14px;
}
window.dashboard label {
    color: #e8eaed;
}
window.dashboard label.caption {
    color: #9aa0a6;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
}
window.dashboard label.value {
    color: #f1f3f4;
    font-size: 13px;
    font-weight: 600;
}
window.dashboard progressbar.trough {
    min-height: 6px;
    border-radius: 3px;
    background-color: rgba(255, 255, 255, 0.10);
    box-shadow: none;
    border: none;
}
window.dashboard progressbar progress {
    min-height: 6px;
    border-radius: 3px;
    border: none;
    box-shadow: none;
}
window.dashboard progressbar.cpu progress {
    background-color: #4aa8ff;
}
window.dashboard progressbar.ram progress {
    background-color: #7bd88f;
}
window.dashboard progressbar.disk progress {
    background-color: #f5c451;
}
window.dashboard label.note {
    color: #9aa0a6;
    font-size: 10px;
}
window.dashboard label.value.disk {
    font-size: 11px;
}
window.dashboard separator {
    background-color: rgba(255, 255, 255, 0.08);
    min-height: 1px;
    margin-top: 2px;
    margin-bottom: 2px;
}
"""

_css_loaded = False


def _ensure_gtk() -> None:
    if not Gtk.init_check([])[0]:
        raise RuntimeError("GTK could not open a display")


def _load_css() -> None:
    global _css_loaded
    if _css_loaded:
        return
    screen = Gdk.Screen.get_default()
    if screen is None:
        return
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_screen(
        screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    _css_loaded = True


class Sparkline(Gtk.DrawingArea):
    """A small filled line chart of recent CPU load."""

    def __init__(self) -> None:
        super().__init__()
        self.set_size_request(-1, 52)
        self._history: tuple[float, ...] = ()
        self.connect("draw", self._on_draw)

    @property
    def history(self) -> tuple[float, ...]:
        return self._history

    def set_history(self, history) -> None:
        history = tuple(history)
        if history != self._history:
            self._history = history
            self.queue_draw()

    def _on_draw(self, _area, cr):
        width = self.get_allocated_width()
        height = self.get_allocated_height()
        if width <= 0 or height <= 0:
            return False

        cr.set_source_rgba(1.0, 1.0, 1.0, 0.05)
        cr.rectangle(0, 0, width, height)
        cr.fill()

        if len(self._history) < 2:
            return False

        # Keep a low floor so quiet machines still show a readable line.
        scale = max(10.0, max(self._history))
        step = width / (len(self._history) - 1)
        points = [
            (index * step, height - (value / scale) * (height - 2) - 1)
            for index, value in enumerate(self._history)
        ]

        cr.move_to(points[0][0], height)
        for x, y in points:
            cr.line_to(x, y)
        cr.line_to(width, height)
        cr.close_path()
        cr.set_source_rgba(0.29, 0.66, 1.0, 0.26)
        cr.fill()

        cr.set_line_width(1.6)
        cr.set_source_rgba(0.42, 0.75, 1.0, 0.95)
        cr.move_to(*points[0])
        for point in points[1:]:
            cr.line_to(*point)
        cr.stroke()
        return False


class DashboardWindow(Gtk.Window):
    """CPU and RAM at a glance, refreshed from a snapshot provider."""

    def __init__(self, snapshot_provider, interval_ms: int = INTERVAL_MS) -> None:
        _ensure_gtk()
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self._provider = snapshot_provider
        self._interval_ms = interval_ms
        self._timer_id: int = 0
        self._snapshot: Snapshot | None = None

        _load_css()
        self.set_title("System Dashboard")
        self.set_default_size(300, 254)
        self.set_resizable(False)
        self.set_decorated(False)
        self.set_app_paintable(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        visual = self.get_screen().get_rgba_visual()
        if visual is not None:
            self.set_visual(visual)
        self.get_style_context().add_class("dashboard")

        self._build_ui()
        self.connect("destroy", self._on_destroy)

    # -- construction ----------------------------------------------------
    def _build_ui(self) -> None:
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        root.set_margin_top(12)
        root.set_margin_bottom(12)
        root.set_margin_start(14)
        root.set_margin_end(14)
        self.add(root)

        cpu_header, self.cpu_value = _row_header("CPU")
        root.pack_start(cpu_header, False, False, 0)
        self.cpu_bar = _bar("cpu")
        root.pack_start(self.cpu_bar, False, False, 0)

        ram_header, self.ram_value = _row_header("RAM")
        root.pack_start(ram_header, False, False, 0)
        self.ram_bar = _bar("ram")
        root.pack_start(self.ram_bar, False, False, 0)

        self.sparkline = Sparkline()
        root.pack_start(self.sparkline, False, False, 2)

        root.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

        disk_header, self.disk_value = _row_header("DISK /")
        root.pack_start(disk_header, False, False, 0)
        self.disk_bar = _bar("disk")
        root.pack_start(self.disk_bar, False, False, 0)

        self.ssd_note = Gtk.Label(label="", xalign=0.0)
        self.ssd_note.get_style_context().add_class("note")
        root.pack_start(self.ssd_note, False, False, 0)

    # -- data ------------------------------------------------------------
    def refresh(self) -> None:
        """Poll the sampler once and repaint the window."""
        self.update(self._provider())

    def update(self, snapshot: Snapshot) -> None:
        """Repaint every reading from a plain snapshot."""
        self._snapshot = snapshot
        self.cpu_value.set_text(format_percent(snapshot.cpu_percent))
        self.cpu_bar.set_fraction(_fraction(snapshot.cpu_percent, 100.0))
        self.ram_value.set_text(format_pair(snapshot.ram_used, snapshot.ram_total))
        self.ram_bar.set_fraction(_fraction(snapshot.ram_used, snapshot.ram_total))
        self.sparkline.set_history(snapshot.cpu_history)

        disk = snapshot.disk
        self.disk_value.set_text(
            f"{format_pair(disk.root_used, disk.root_total)} · "
            f"{format_percent(disk.root_percent)}"
        )
        self.disk_value.get_style_context().add_class("disk")
        self.disk_bar.set_fraction(_fraction(disk.root_percent, 100.0))
        self.ssd_note.set_text(
            f"SSD {format_bytes(disk.disk_total)} · {format_bytes(disk.disk_free)} free"
        )

    # -- refresh timer ---------------------------------------------------
    def start(self) -> None:
        if self._timer_id:
            return
        self.refresh()
        self._timer_id = GLib.timeout_add(self._interval_ms, self._on_tick)

    def stop(self) -> None:
        if self._timer_id:
            GLib.source_remove(self._timer_id)
            self._timer_id = 0

    def _on_tick(self) -> bool:
        self.refresh()
        return True

    def _on_destroy(self, *_args) -> None:
        self.stop()


def _row_header(caption: str) -> tuple[Gtk.Box, Gtk.Label]:
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    name = Gtk.Label(label=caption, xalign=0.0)
    name.get_style_context().add_class("caption")
    value = Gtk.Label(label="--", xalign=1.0)
    value.get_style_context().add_class("value")
    row.pack_start(name, False, False, 0)
    row.pack_end(value, False, False, 0)
    return row, value


def _bar(style_class: str) -> Gtk.ProgressBar:
    bar = Gtk.ProgressBar()
    bar.set_show_text(False)
    bar.set_size_request(-1, 6)
    bar.get_style_context().add_class(style_class)
    return bar


def _fraction(part: float, whole: float) -> float:
    if not whole:
        return 0.0
    return min(1.0, max(0.0, float(part) / float(whole)))
