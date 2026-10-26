# 05: Under-windows placement

**What to build:** On GNOME Wayland, make the widget sit under normal windows like a desktop widget. Run as XWayland app with desktop-type window hint + keep-below. If that fails in testing, fall back to a small always-on-top corner panel. Do not switch to an X11 session.

**Blocked by:** 02: Widget window, live CPU/RAM

**Status:** done

- [x] Widget stays beneath normal app windows, or fallback is applied and noted
- [x] Does not steal focus or appear in alt-tab if feasible
- [ ] Verified manually on the user's Ubuntu session
- [ ] Chosen approach (under-windows vs fallback) recorded in a short note

**Note:** XWayland desktop-layer hints are applied and verified via `xprop`
(`_NET_WM_WINDOW_TYPE_DESKTOP`, `_NET_WM_STATE_BELOW`, sticky, skip-taskbar, no
focus). Visual confirmation and alt-tab behaviour still need a human glance on
the live session.
