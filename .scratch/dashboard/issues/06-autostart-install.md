# 06: Autostart + install script

**What to build:** An install script that places the widget and a per-user XDG autostart entry so it starts at login. (A systemd system service cannot work; it needs the GUI session.)

**Blocked by:** 05: Under-windows placement

**Status:** ready-for-agent

- [ ] Install script is idempotent and user-level (no sudo for the widget itself)
- [ ] After logout/login the widget appears automatically
- [ ] Uninstall steps documented
