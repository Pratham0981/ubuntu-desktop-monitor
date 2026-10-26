"""The compact, dark, translucent widget window."""

from __future__ import annotations

import math

try:
    import cairo
except ImportError:  # pragma: no cover
    cairo = None

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gdk, GLib, Gtk, Pango

from .format import (
    format_bytes,
    format_pair,
    format_percent,
    format_rate,
    format_temp,
    format_uptime,
)
from .procs import TOP_LIMIT
from .sampler import Snapshot

INTERVAL_MS = 1000

# Painted by the window itself: app-paintable windows get no theme background.
PANEL_COLOR = (0.059, 0.059, 0.102, 0.84)
PANEL_BORDER = (1.0, 1.0, 1.0, 0.09)
PANEL_RADIUS = 18.0

# CPU trace is ultraviolet; any bar turns amber, then red, as load climbs.
ACCENT = (0.62, 0.55, 1.0)
WARN_AT = 0.70
HOT_AT = 0.90
LEVELS = ("ok", "warn", "hot")
WARN_RGB = (1.0, 0.76, 0.28)
HOT_RGB = (1.0, 0.33, 0.44)

CSS = b"""
window.dashboard label {
    color: #f1effa;
    font-family: "Inter", "Ubuntu", sans-serif;
    font-feature-settings: "tnum";
}
window.dashboard label.caption {
    color: #9591ad;
    font-size: 12px;
    font-weight: 500;
}
window.dashboard label.hero {
    font-family: "Inter Display", "Inter", sans-serif;
    font-size: 42px;
    font-weight: 300;
    letter-spacing: -1.5px;
}
window.dashboard label.hero.warn {
    color: #ffc247;
}
window.dashboard label.hero.hot {
    color: #ff5470;
}
window.dashboard label.temp {
    color: #9591ad;
    font-size: 12px;
    font-weight: 500;
}
window.dashboard label.value {
    font-size: 12px;
    font-weight: 500;
}
window.dashboard label.note {
    color: #6e6a86;
    font-family: "JetBrains Mono", "Ubuntu Mono", monospace;
    font-size: 10px;
}
window.dashboard label.process {
    color: #cfcce0;
    font-family: "JetBrains Mono", "Ubuntu Mono", monospace;
    font-size: 11px;
}
window.dashboard label.stat {
    color: #9591ad;
}
window.dashboard progressbar trough {
    min-height: 4px;
    border-radius: 2px;
    background-color: rgba(255, 255, 255, 0.08);
    border: none;
    box-shadow: none;
}
window.dashboard progressbar progress {
    min-height: 4px;
    border-radius: 2px;
    border: none;
    box-shadow: none;
}
window.dashboard progressbar.ram progress {
    background-image: linear-gradient(to right, #3b82f6, #22d3ee);
}
window.dashboard progressbar.disk progress {
    background-image: linear-gradient(to right, #10b981, #6ee7b7);
}
window.dashboard progressbar.warn progress {
    background-image: linear-gradient(to right, #f59e0b, #ffc247);
}
window.dashboard progressbar.hot progress {
    background-image: linear-gradient(to right, #f43f5e, #ff5470);
}
window.dashboard separator {
    background-color: rgba(255, 255, 255, 0.07);
    min-height: 1px;
    margin-top: 4px;
    margin-bottom: 4px;
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

        # Faint scope graticule at the quarter marks.
        cr.set_line_width(1.0)
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.05)
        for fraction in (0.25, 0.5, 0.75):
            y = round(height * fraction) + 0.5
            cr.move_to(0, y)
            cr.line_to(width, y)
        cr.stroke()

        if len(self._history) < 2:
            return False

        # Keep a low floor so quiet machines still show a readable trace.
        scale = max(25.0, max(self._history))
        pad = 4.0
        step = (width - 2 * pad) / (len(self._history) - 1)
        points = [
            (pad + index * step, height - pad - (value / scale) * (height - 2 * pad))
            for index, value in enumerate(self._history)
        ]

        cr.move_to(points[0][0], height)
        for x, y in points:
            cr.line_to(x, y)
        cr.line_to(points[-1][0], height)
        cr.close_path()
        if cairo is not None:
            fade = cairo.LinearGradient(0, 0, 0, height)
            fade.add_color_stop_rgba(0.0, *ACCENT, 0.30)
            fade.add_color_stop_rgba(1.0, *ACCENT, 0.0)
            cr.set_source(fade)
        else:
            cr.set_source_rgba(*ACCENT, 0.16)
        cr.fill()

        cr.set_line_width(1.5)
        cr.set_line_join(1)  # round
        cr.set_source_rgba(*ACCENT, 0.95)
        cr.move_to(*points[0])
        for point in points[1:]:
            cr.line_to(*point)
        cr.stroke()

        # Live dot on the newest sample, with a soft halo.
        last_x, last_y = points[-1]
        cr.set_source_rgba(*ACCENT, 0.25)
        cr.arc(last_x, last_y, 5.0, 0, 2 * math.pi)
        cr.fill()
        cr.set_source_rgba(*ACCENT, 1.0)
        cr.arc(last_x, last_y, 2.2, 0, 2 * math.pi)
        cr.fill()
        return False


class CoreBars(Gtk.DrawingArea):
    """One thin vertical bar per CPU core, so a single pegged core shows."""

    def __init__(self) -> None:
        super().__init__()
        self.set_size_request(-1, 24)
        self._values: tuple[float, ...] = ()
        self.connect("draw", self._on_draw)

    @property
    def values(self) -> tuple[float, ...]:
        return self._values

    def set_values(self, values) -> None:
        values = tuple(values)
        if values != self._values:
            self._values = values
            self.queue_draw()

    def _on_draw(self, _area, cr):
        width = self.get_allocated_width()
        height = self.get_allocated_height()
        count = len(self._values)
        if count == 0 or width <= 0 or height <= 0:
            return False
        gap = 3.0
        bar_width = max(1.0, (width - gap * (count - 1)) / count)
        radius = min(2.0, bar_width / 2)
        for index, value in enumerate(self._values):
            x = index * (bar_width + gap)
            _rounded_rectangle(cr, x, 0, bar_width, height, radius)
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.08)
            cr.fill()
            fraction = min(1.0, max(0.0, value / 100.0))
            fill = max(2.0, height * fraction)
            if fraction >= HOT_AT:
                colour = HOT_RGB
            elif fraction >= WARN_AT:
                colour = WARN_RGB
            else:
                colour = ACCENT
            _rounded_rectangle(cr, x, height - fill, bar_width, fill, radius)
            cr.set_source_rgba(*colour, 0.95)
            cr.fill()
        return False


class DashboardWindow(Gtk.Window):
    """CPU and RAM at a glance, refreshed from a snapshot provider."""

    def __init__(
        self,
        snapshot_provider,
        interval_ms: int = INTERVAL_MS,
        settings: dict | None = None,
    ) -> None:
        _ensure_gtk()
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self._provider = snapshot_provider
        self._interval_ms = interval_ms
        self._timer_id: int = 0
        settings = settings or {}
        self._opacity = _clamp_opacity(settings.get("opacity"))
        self._drag = None
        self.on_top = bool(settings.get("on_top"))
        # The app wires these: remember a setting, move to or from the top layer.
        self.on_setting = None
        self.on_top_changed = None

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
        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
        )

        self._build_ui()
        self.connect("draw", self._on_draw)
        self.connect("destroy", self._on_destroy)
        self.connect("button-press-event", self._on_button_press)
        self.connect("motion-notify-event", self._on_motion)
        self.connect("button-release-event", self._on_button_release)

    # -- painting --------------------------------------------------------
    def _on_draw(self, _widget, cr):
        width = self.get_allocated_width()
        height = self.get_allocated_height()
        if width <= 0 or height <= 0:
            return False

        _rounded_rectangle(cr, 0.5, 0.5, width - 1, height - 1, PANEL_RADIUS)
        cr.set_source_rgba(*PANEL_COLOR[:3], self._opacity)
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

        hero = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.cpu_value = Gtk.Label(label="--", xalign=0.0)
        self.cpu_value.get_style_context().add_class("hero")
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        side.set_valign(Gtk.Align.CENTER)
        cpu_caption = Gtk.Label(label="CPU load", xalign=1.0)
        cpu_caption.get_style_context().add_class("caption")
        self.temp_value = Gtk.Label(label="--", xalign=1.0)
        self.temp_value.get_style_context().add_class("temp")
        side.pack_start(cpu_caption, False, False, 0)
        side.pack_start(self.temp_value, False, False, 0)
        hero.pack_start(self.cpu_value, False, False, 0)
        hero.pack_end(side, False, False, 0)
        root.pack_start(hero, False, False, 0)

        self.sparkline = Sparkline()
        root.pack_start(self.sparkline, False, False, 0)

        self.core_bars = CoreBars()
        root.pack_start(self.core_bars, False, False, 2)

        ram_header, self.ram_value = _row_header("Memory")
        root.pack_start(ram_header, False, False, 0)
        self.ram_bar = _bar("ram")
        root.pack_start(self.ram_bar, False, False, 0)

        root.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

        disk_header, self.disk_value = _row_header("Disk /")
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

        net_header, self.net_value = _row_header("Network")
        root.pack_start(net_header, False, False, 0)

        root.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

        top_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        caption = Gtk.Label(label="Top processes", xalign=0.0)
        caption.get_style_context().add_class("caption")
        legend = Gtk.Label(label="CPU    RAM", xalign=1.0)
        legend.get_style_context().add_class("note")
        top_header.pack_start(caption, True, True, 0)
        top_header.pack_end(legend, False, False, 0)
        root.pack_start(top_header, False, False, 0)

        self.process_rows = []
        for _ in range(TOP_LIMIT):
            row = _process_row()
            root.pack_start(row[0], False, False, 0)
            self.process_rows.append(row)

        self.system_note = Gtk.Label(label="", xalign=0.0)
        self.system_note.get_style_context().add_class("note")
        root.pack_start(self.system_note, False, False, 2)

    # -- data ------------------------------------------------------------
    def refresh(self) -> None:
        """Poll the sampler once and repaint the window."""
        self.update(self._provider())

    def update(self, snapshot: Snapshot) -> None:
        """Repaint every reading from a plain snapshot."""
        self.cpu_value.set_text(format_percent(snapshot.cpu_percent))
        _set_level(self.cpu_value, _fraction(snapshot.cpu_percent, 100.0))
        self.ram_value.set_text(format_pair(snapshot.ram_used, snapshot.ram_total))
        ram_fraction = _fraction(snapshot.ram_used, snapshot.ram_total)
        self.ram_bar.set_fraction(ram_fraction)
        _set_level(self.ram_bar, ram_fraction)
        self.sparkline.set_history(snapshot.cpu_history)
        self.core_bars.set_values(snapshot.core_percents)

        disk = snapshot.disk
        self.disk_value.set_text(
            f"{format_pair(disk.root_used, disk.root_total)} · "
            f"{format_percent(disk.root_percent)}"
        )
        disk_fraction = _fraction(disk.root_percent, 100.0)
        self.disk_bar.set_fraction(disk_fraction)
        _set_level(self.disk_bar, disk_fraction)
        self._update_mounts(disk.mounts)
        self.ssd_note.set_text(
            f"SSD {format_bytes(disk.disk_total)} · {format_bytes(disk.disk_free)} free"
        )

        self.temp_value.set_text(format_temp(snapshot.cpu_temp))
        self.net_value.set_text(
            f"↓ {format_rate(snapshot.net_down)}   ↑ {format_rate(snapshot.net_up)}"
        )
        self.system_note.set_text(_system_line(snapshot))
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
            caption.set_text(f"Disk {mount.mountpoint}")
            value.set_text(
                f"{format_pair(mount.used, mount.total)} · "
                f"{format_percent(mount.percent)}"
            )
            bar.set_fraction(_fraction(mount.percent, 100.0))
            _set_level(bar, _fraction(mount.percent, 100.0))
            container.show_all()
        for container, _caption, _value, _bar in self.mount_rows[len(mounts):]:
            container.hide()

    # -- dragging and the right-click menu ---------------------------------
    def _on_button_press(self, _widget, event) -> bool:
        if event.button == 1:
            x, y = self.get_position()
            self._drag = (event.x_root, event.y_root, x, y)
            return True
        if event.button == 3:
            self._show_menu(event)
            return True
        return False

    def _on_motion(self, _widget, event) -> bool:
        if self._drag is None:
            return False
        start_x, start_y, window_x, window_y = self._drag
        self.move(
            int(window_x + event.x_root - start_x),
            int(window_y + event.y_root - start_y),
        )
        return True

    def _on_button_release(self, _widget, event) -> bool:
        if event.button != 1 or self._drag is None:
            return False
        _sx, _sy, window_x, window_y = self._drag
        self._drag = None
        position = tuple(self.get_position())
        if position != (window_x, window_y):
            self._notify("position", list(position))
        return True

    def _show_menu(self, event) -> None:
        menu = Gtk.Menu()
        on_top = Gtk.CheckMenuItem(label="Always on top")
        on_top.set_active(self.on_top)
        on_top.connect("toggled", self._on_top_toggled)
        menu.append(on_top)

        opacity = Gtk.MenuItem(label="Opacity")
        choices = Gtk.Menu()
        for percent in (50, 65, 80, 95):
            item = Gtk.MenuItem(label=f"{percent}%")
            item.connect("activate", self._on_opacity_chosen, percent / 100)
            choices.append(item)
        opacity.set_submenu(choices)
        menu.append(opacity)

        menu.append(Gtk.SeparatorMenuItem())
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", lambda *_args: self.destroy())
        menu.append(quit_item)
        menu.show_all()
        menu.popup_at_pointer(event)

    def _on_top_toggled(self, item) -> None:
        self.on_top = item.get_active()
        if self.on_top_changed is not None:
            self.on_top_changed(self.on_top)

    def _on_opacity_chosen(self, _item, value: float) -> None:
        self._opacity = _clamp_opacity(value)
        self.queue_draw()
        self._notify("opacity", self._opacity)

    def _notify(self, key: str, value) -> None:
        if self.on_setting is not None:
            self.on_setting(key, value)

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
    cpu.get_style_context().add_class("process")
    cpu.get_style_context().add_class("stat")
    memory = Gtk.Label(label="", xalign=1.0)
    memory.get_style_context().add_class("process")
    memory.get_style_context().add_class("stat")
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


def _clamp_opacity(value) -> float:
    """Panel opacity from settings, kept readable and never fully clear."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return PANEL_COLOR[3]
    return min(1.0, max(0.4, float(value)))


def _system_line(snapshot: Snapshot) -> str:
    parts = []
    if snapshot.uptime is not None:
        parts.append(f"up {format_uptime(snapshot.uptime)}")
    if snapshot.load_avg is not None:
        parts.append("load " + " ".join(f"{value:.2f}" for value in snapshot.load_avg))
    return "  ·  ".join(parts)


def _set_level(widget: Gtk.Widget, fraction: float) -> None:
    """Tag a widget ok, warn or hot so CSS can colour it by load."""
    level = "hot" if fraction >= HOT_AT else "warn" if fraction >= WARN_AT else "ok"
    context = widget.get_style_context()
    for name in LEVELS:
        if name == level:
            context.add_class(name)
        else:
            context.remove_class(name)


def _fraction(part: float, whole: float) -> float:
    if not whole:
        return 0.0
    return min(1.0, max(0.0, float(part) / float(whole)))
