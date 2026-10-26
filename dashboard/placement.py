"""Desktop-layer placement for the widget on GNOME Wayland.

GNOME's Wayland session gives applications no way to ask for "below normal
windows", so the widget runs as an XWayland client and asks the X11 window
manager for the desktop layer instead: window type DESKTOP, plus an EWMH
request to add the ``_NET_WM_STATE_BELOW`` state after the window maps.

GDK rewrites ``_NET_WM_STATE`` from its own hints at map time, which is why the
below request is sent afterwards as a client message rather than written
straight into the property.  When no X11 window manager is reachable, callers
fall back to :func:`place_top_right`, a small always-on-top corner panel.
"""

from __future__ import annotations

import ctypes
import ctypes.util

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from gi.repository import Gdk, Gtk

try:  # GdkX11 is present wherever the app runs on X11/XWayland.
    gi.require_version("GdkX11", "3.0")
    from gi.repository import GdkX11
except (ImportError, ValueError):  # pragma: no cover - Wayland-only systems
    GdkX11 = None

CLIENT_MESSAGE = 33
SUBSTRUCTURE_NOTIFY_MASK = 1 << 19
SUBSTRUCTURE_REDIRECT_MASK = 1 << 20
NET_WM_STATE_REMOVE = 0
NET_WM_STATE_ADD = 1
SOURCE_APPLICATION = 1

CORNER_MARGIN = 24


class _ClientMessageData(ctypes.Union):
    _fields_ = [
        ("b", ctypes.c_char * 20),
        ("s", ctypes.c_short * 10),
        ("l", ctypes.c_long * 5),
    ]


class _ClientMessageEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong),
        ("message_type", ctypes.c_ulong),
        ("format", ctypes.c_int),
        ("data", _ClientMessageData),
    ]


class _XEvent(ctypes.Union):
    _fields_ = [
        ("xclient", _ClientMessageEvent),
        ("pad", ctypes.c_long * 24),
    ]


def prepare_desktop_placement(
    window: Gtk.Window, margin: int = CORNER_MARGIN
) -> None:
    """Ask for the desktop layer and no focus.  Call before showing.

    The window type has to be in place when the window manager first sees the
    window.
    """
    window.set_type_hint(Gdk.WindowTypeHint.DESKTOP)
    window.set_accept_focus(False)
    window.set_focus_on_map(False)
    window.set_skip_taskbar_hint(True)
    window.set_skip_pager_hint(True)
    window.set_keep_above(False)
    _move_top_right(window, margin)


def apply_desktop_placement(window: Gtk.Window) -> bool:
    """Ask the window manager to keep the window below normal windows.

    Call after showing.  Returns False when there is no X11 window to ask, so
    the caller can fall back to :func:`place_top_right`.
    """
    gdk_window = window.get_window()
    if gdk_window is None or GdkX11 is None:
        return False
    if not isinstance(gdk_window, GdkX11.X11Window):
        return False
    xid = int(gdk_window.get_xid())
    below = _change_state_atom(xid, "_NET_WM_STATE_BELOW", add=True)
    # Mapping an unfocused desktop-layer window makes the shell flag it for
    # attention ahead of the element it is meant to sit behind.
    _change_state_atom(xid, "_NET_WM_STATE_DEMANDS_ATTENTION", add=False)
    return below


def place_top_right(window: Gtk.Window, margin: int = CORNER_MARGIN) -> None:
    """Fallback: a corner panel that stays above normal windows."""
    window.set_keep_above(True)
    window.set_type_hint(Gdk.WindowTypeHint.UTILITY)
    _move_top_right(window, margin)


def _move_top_right(window: Gtk.Window, margin: int) -> None:
    screen = window.get_screen()
    width = window.get_allocated_width() or window.get_default_size()[0]
    window.move(max(0, screen.get_width() - width - margin), margin)


def _change_state_atom(xid: int, atom_name: str, *, add: bool) -> bool:
    library = ctypes.util.find_library("X11")
    if not library:
        return False

    x11 = ctypes.CDLL(library)
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XInternAtom.restype = ctypes.c_ulong
    x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    x11.XDefaultRootWindow.restype = ctypes.c_ulong
    x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
    x11.XSendEvent.restype = ctypes.c_int
    x11.XSendEvent.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_int,
        ctypes.c_long,
        ctypes.POINTER(_XEvent),
    ]
    x11.XFlush.argtypes = [ctypes.c_void_p]
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]

    display = x11.XOpenDisplay(None)
    if not display:
        return False
    try:
        root = x11.XDefaultRootWindow(display)
        event = _XEvent()
        event.xclient.type = CLIENT_MESSAGE
        event.xclient.send_event = 1
        event.xclient.display = display
        event.xclient.window = ctypes.c_ulong(xid)
        event.xclient.message_type = x11.XInternAtom(
            display, b"_NET_WM_STATE", 0
        )
        event.xclient.format = 32
        event.xclient.data.l[0] = NET_WM_STATE_ADD if add else NET_WM_STATE_REMOVE
        event.xclient.data.l[1] = x11.XInternAtom(display, atom_name.encode(), 0)
        event.xclient.data.l[2] = 0
        event.xclient.data.l[3] = SOURCE_APPLICATION
        event.xclient.data.l[4] = 0
        sent = x11.XSendEvent(
            display,
            root,
            0,
            SUBSTRUCTURE_REDIRECT_MASK | SUBSTRUCTURE_NOTIFY_MASK,
            ctypes.byref(event),
        )
        x11.XFlush(display)
    finally:
        x11.XCloseDisplay(display)
    return bool(sent)
