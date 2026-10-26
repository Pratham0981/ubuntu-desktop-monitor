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

from gi.repository import Gtk  # noqa: E402

from .sampler import Sampler  # noqa: E402
from .widget import DashboardWindow  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    Gtk.init(argv)
    sampler = Sampler()
    # Warm up before the window exists so the first disk scan and CPU window
    # are not paid for while the window is painting.
    sampler.snapshot()
    window = DashboardWindow(sampler.snapshot)
    window.connect("destroy", Gtk.main_quit)
    window.show_all()
    window.start()
    Gtk.main()
    return 0
