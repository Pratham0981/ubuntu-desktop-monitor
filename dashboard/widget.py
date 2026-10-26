"""The compact, dark, translucent widget window."""

from __future__ import annotations

import math

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gdk, GLib, Gtk, Pango

from .format import format_bytes, format_pair, format_percent, format_temp
from .procs import TOP_LIMIT
from .sampler import Snapshot

INTERVAL_MS = 1000

# Painted by the window itself: app-paintable windows get no theme background.
PANEL_COLOR = (0.157, 0.157, 0.169, 0.93)
PANEL_BORDER = (1.0, 1.0, 1.0, 0.10)
PANEL_RADIUS = 8.0

CSS = b"""
window.dashboard label {
    color: #e9eaec;
}
window.dashboard label.caption {
    color: #b3b6bb;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
}
window.dashboard label.value {
    color: #fbfbfc;
    font-size: 13px;
    font-weight: 600;
}
window.dashboard progressbar.trough {
    min-height: 6px;
    border-radius: 3px;
    background-color: rgba(255, 255, 255, 0.14);
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
    background-color: #4f9cff;
}
window.dashboard progressbar.ram progress {
    background-color: #32d583;
}
window.dashboard progressbar.disk progress {
    background-color: #ffb020;
}
window.dashboard label.note {
    color: #a3a6ab;
    font-size: 10px;
}
window.dashboard label.value.disk {
    font-size: 11px;
}
window.dashboard label.process {
    color: #dcdee2;
    font-size: 10px;
}
window.dashboard label.process.stat {
    color: #a3a6ab;
}
window.dashboard separator {
    background-color: rgba(255, 255, 255, 0.10);
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
        self.set_size_request(-1, 46)
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

        _load_css()
        self.set_title("System Dashboard")
        self.set_default_size(300, 400)
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
        self.connect("draw", self._on_draw)
        self.connect("destroy", self._on_destroy)

    # -- painting --------------------------------------------------------
    def _on_draw(self, _widget, cr):
        width = self.get_allocated_width()
        height = self.get_allocated_height()
        if width <= 0 or height <= 0:
            return False

        _rounded_rectangle(cr, 0.5, 0.5, width - 1, height - 1, PANEL_RADIUS)
        cr.set_source_rgba(*PANEL_COLOR)
        cr.fill_preserve()
        cr.set_line_width(1.0)
        cr.set_source_rgba(*PANEL_BORDER)
        cr.stroke()
        return False

    # -- construction ----------------------------------------------------
    def _build_ui(self) -> None:
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        root.set_margin_top(10)
        root.set_margin_bottom(10)
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
        self.disk_value.get_style_context().add_class("disk")
        root.pack_start(disk_header, False, False, 0)
        self.disk_bar = _bar("disk")
        root.pack_start(self.disk_bar, False, False, 0)

        self.mount_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        root.pack_start(self.mount_box, False, False, 0)
        self.mount_rows = []

        self.ssd_note = Gtk.Label(label="", xalign=0.0)
        self.ssd_note.get_style_context().add_class("note")
        root.pack_start(self.ssd_note, False, False, 0)

        root.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

        temp_header, self.temp_value = _row_header("TEMP")
        root.pack_start(temp_header, False, False, 0)

        top_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        caption = Gtk.Label(label="TOP", xalign=0.0)
        caption.get_style_context().add_class("caption")
        legend = Gtk.Label(label="CPU / RAM", xalign=1.0)
        legend.get_style_context().add_class("note")
        top_header.pack_start(caption, True, True, 0)
        top_header.pack_end(legend, False, False, 0)
        root.pack_start(top_header, False, False, 0)

        self.process_rows = []
        for _ in range(TOP_LIMIT):
            row = _process_row()
            root.pack_start(row[0], False, False, 0)
            self.process_rows.append(row)

    # -- data ------------------------------------------------------------
    def refresh(self) -> None:
        """Poll the sampler once and repaint the window."""
        self.update(self._provider())

    def update(self, snapshot: Snapshot) -> None:
        """Repaint every reading from a plain snapshot."""
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
        self.disk_bar.set_fraction(_fraction(disk.root_percent, 100.0))
        self._update_mounts(disk.mounts)
        self.ssd_note.set_text(
            f"SSD {format_bytes(disk.disk_total)} · {format_bytes(disk.disk_free)} free"
        )

        self.temp_value.set_text(format_temp(snapshot.cpu_temp))
        for (line, name, cpu, memory), process in zip(
            self.process_rows, snapshot.processes
        ):
            name.set_text(process.name)
            cpu.set_text(format_percent(process.cpu_percent))
            memory.set_text(format_percent(process.memory_percent))
            line.show_all()
        for line, _name, _cpu, _memory in self.process_rows[len(snapshot.processes):]:
            line.hide()

    def _update_mounts(self, mounts) -> None:
        for index, mount in enumerate(mounts):
            if index == len(self.mount_rows):
                icon_row = _mount_row()
                self.mount_box.pack_start(icon_row[0], False, False, 0)
                self.mount_rows.append(icon_row)
            container, caption, value, bar = self.mount_rows[index]
            caption.set_text(f"DISK {mount.mountpoint}")
            value.set_text(
                f"{format_pair(mount.used, mount.total)} · "
                f"{format_percent(mount.percent)}"
            )
            bar.set_fraction(_fraction(mount.percent, 100.0))
            container.show_all()
        for container, _caption, _value, _bar in self.mount_rows[len(mounts):]:
            container.hide()

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


def _rounded_rectangle(cr, x, y, width, height, radius) -> None:
    cr.new_sub_path()
    cr.arc(x + width - radius, y + radius, radius, -math.pi / 2, 0)
    cr.arc(x + width - radius, y + height - radius, radius, 0, math.pi / 2)
    cr.arc(x + radius, y + height - radius, radius, math.pi / 2, math.pi)
    cr.arc(x + radius, y + radius, radius, math.pi, 3 * math.pi / 2)
    cr.close_path()


def _row_header(caption: str) -> tuple[Gtk.Box, Gtk.Label]:
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    name = Gtk.Label(label=caption, xalign=0.0)
    name.get_style_context().add_class("caption")
    value = Gtk.Label(label="--", xalign=1.0)
    value.get_style_context().add_class("value")
    row.pack_start(name, False, False, 0)
    row.pack_end(value, False, False, 0)
    return row, value


def _mount_row() -> tuple[Gtk.Box, Gtk.Label, Gtk.Label, Gtk.ProgressBar]:
    container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    container.hide()
    header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    caption = Gtk.Label(label="", xalign=0.0)
    caption.get_style_context().add_class("caption")
    value = Gtk.Label(label="--", xalign=1.0)
    value.get_style_context().add_class("value")
    value.get_style_context().add_class("disk")
    header.pack_start(caption, False, False, 0)
    header.pack_end(value, False, False, 0)
    bar = _bar("disk")
    container.pack_start(header, False, False, 0)
    container.pack_start(bar, False, False, 0)
    return container, caption, value, bar


def _process_row() -> tuple[Gtk.Box, Gtk.Label, Gtk.Label, Gtk.Label]:
    line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    line.hide()
    name = Gtk.Label(label="", xalign=0.0)
    name.set_ellipsize(Pango.EllipsizeMode.END)
    name.get_style_context().add_class("process")
    cpu = Gtk.Label(label="", xalign=1.0)
    cpu.get_style_context().add_class("process stat")
    memory = Gtk.Label(label="", xalign=1.0)
    memory.get_style_context().add_class("process stat")
    cpu.set_width_chars(5)
    memory.set_width_chars(5)
    line.pack_start(name, True, True, 0)
    line.pack_end(memory, False, False, 0)
    line.pack_end(cpu, False, False, 0)
    return line, name, cpu, memory


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
