"""Entry point for the dashboard widget."""

from __future__ import annotations

import os
import sys


def _prefer_xwayland() -> None:
    """X11 window hints are needed for desktop placement; Wayland has no peer.

    Only forces the backend when an X display exists, so a session without
    XWayland still starts on Wayland instead of failing to open a window.
    """
    if "GDK_BACKEND" not in os.environ and os.environ.get("DISPLAY"):
        os.environ["GDK_BACKEND"] = "x11"


_prefer_xwayland()

import gi  # noqa: E402

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gdk, Gtk  # noqa: E402

from . import config, placement  # noqa: E402
from .sampler import Sampler  # noqa: E402
from .widget import DashboardWindow  # noqa: E402


def wants_on_top(argv: list[str]) -> bool:
    """True when the user asked for the always-on-top corner panel."""
    return "--on-top" in argv


def _place_window(window, *, on_top: bool, position=None) -> bool:
    # A remembered position wins over the default corner.
    keep_spot = position is not None
    if on_top:
        placement.place_top_left(window, move=not keep_spot)
    elif not placement.apply_desktop_placement(window):
        placement.place_top_left(window, move=not keep_spot)
    return False  # let other handlers see the event


def _saved_position(settings: dict):
    """The remembered window spot, pulled back on screen if the display shrank."""
    value = settings.get("position")
    if not (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and all(isinstance(item, int) and not isinstance(item, bool) for item in value)
    ):
        return None
    screen = Gdk.Screen.get_default()
    width = screen.get_width() if screen else 1920
    height = screen.get_height() if screen else 1080
    return (
        min(max(0, value[0]), max(0, width - 80)),
        min(max(0, value[1]), max(0, height - 80)),
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    on_top = wants_on_top(argv)
    argv = [arg for arg in argv if arg != "--on-top"]
    Gtk.init(argv)
    settings = config.load_settings()
    on_top = on_top or bool(settings.get("on_top"))
    sampler = Sampler()
    # Warm up before the window exists so the first disk scan and CPU window
    # are not paid for while the window is painting.
    sampler.snapshot()
    window = DashboardWindow(sampler.snapshot, settings=settings)
    window.on_top = on_top
    window.connect("destroy", Gtk.main_quit)
    state = {"position": _saved_position(settings)}

    def remember(key, value) -> None:
        settings[key] = value
        if key == "position":
            state["position"] = tuple(value)
        config.save_settings(settings)

    def set_layer(flag: bool) -> None:
        # The window type is only read when a window is mapped, so switch
        # layers by remapping the window where it already sits.
        position = tuple(window.get_position())
        window.hide()
        if flag:
            window.set_keep_above(True)
            window.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        else:
            placement.prepare_desktop_placement(window)
        window.move(*position)
        window.show_all()
        remember("on_top", flag)
        remember("position", list(position))

    window.on_setting = remember
    window.on_top_changed = set_layer

    # Desktop layer under normal windows, with an always-on-top corner panel
    # as the fallback for compositors that ignore the XWayland hints.  The
    # state request has to wait until the window manager has mapped the window.
    window.connect(
        "map-event",
        lambda widget, _event: _place_window(
            widget, on_top=window.on_top, position=state["position"]
        ),
    )
    if not on_top:
        placement.prepare_desktop_placement(window)
    if state["position"] is not None:
        window.move(*state["position"])
    window.show_all()

    window.start()
    Gtk.main()
    return 0
