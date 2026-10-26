# Under-windows placement: chosen approach

**Chosen: XWayland + desktop-layer window hints.** The widget runs as an X11
client on the GNOME Wayland session (`GDK_BACKEND=x11`, forced by the launcher
and by `dashboard/app.py` when `DISPLAY` exists) and asks Mutter for the
desktop layer.

## What the app sets

| Hint | Where |
| --- | --- |
| `_NET_WM_WINDOW_TYPE_DESKTOP` | `Gtk.Window.set_type_hint(DESKTOP)`, before the window maps |
| `_NET_WM_STATE_BELOW` | EWMH client message to the root window, on `map-event` |
| `_NET_WM_STATE_SKIP_TASKBAR`, `_NET_WM_STATE_SKIP_PAGER` | GTK skip hints |
| `WM_HINTS.input = False`, focus-on-map off | `set_accept_focus(False)`, `set_focus_on_map(False)` |
| Top-right corner position | `Gtk.Window.move()` before the window maps |

Two ordering details matter and are easy to regress:

1. The window **type** must be set before the window maps, or Mutter has
   already decided how to place it.
2. The **below** state must be requested after the window maps. GTK rewrites
   `_NET_WM_STATE` from its own hints at map time, and an X property write
   before that is simply deleted.

## Verified on this machine (Ubuntu 24.04, GNOME, Wayland)

Observed with `xprop` on the live session while the widget ran:

```
_NET_WM_WINDOW_TYPE(ATOM) = _NET_WM_WINDOW_TYPE_DESKTOP
_NET_WM_STATE(ATOM) = _NET_WM_STATE_SKIP_PAGER, _NET_WM_STATE_SKIP_TASKBAR,
                      _NET_WM_STATE_BELOW, _NET_WM_STATE_STICKY
_NET_WM_DESKTOP(CARDINAL) = 4294967295        # all desktops
WM_HINTS: Client accepts input or input focus: False
geometry: 300x366 at the top-right corner, Map State: IsViewable
```

Mapping an unfocused desktop-layer window makes Mutter add
`_NET_WM_STATE_DEMANDS_ATTENTION`; the app clears it with a second EWMH
request after the window is placed.

Not covered by automation: whether the widget really looks like it sits behind
normal windows, and whether it stays out of alt-tab. Both need a human glance.

## Fallback

If a future GNOME (or another compositor) stops honouring these hints, the
fallback is a small always-on-top corner panel:

```python
from dashboard import placement
placement.place_top_right(window)
```

`apply_desktop_placement()` returns `False` when there is no X11 window to ask
(no XWayland, or a backend other than X11), and `app.py` switches to the
fallback automatically in that case.
