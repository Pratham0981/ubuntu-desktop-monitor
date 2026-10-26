# 05: Under-windows placement

**What to build:** On GNOME Wayland, make the widget sit under normal windows like a desktop widget. Run as XWayland app with desktop-type window hint + keep-below. If that fails in testing, fall back to a small always-on-top corner panel. Do not switch to an X11 session.

**Blocked by:** 02: Widget window, live CPU/RAM

**Status:** ready-for-agent

- [ ] Widget stays beneath normal app windows, or fallback is applied and noted
- [ ] Does not steal focus or appear in alt-tab if feasible
- [ ] Verified manually on the user's Ubuntu session
- [ ] Chosen approach (under-windows vs fallback) recorded in a short note
