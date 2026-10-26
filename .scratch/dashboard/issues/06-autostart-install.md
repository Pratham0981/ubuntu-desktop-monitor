# 06: Autostart + install script

**What to build:** An install script that places the widget and a per-user XDG autostart entry so it starts at login. (A systemd system service cannot work; it needs the GUI session.)

**Blocked by:** 05: Under-windows placement

**Status:** done

- [x] Install script is idempotent and user-level (no sudo for the widget itself)
- [ ] After logout/login the widget appears automatically
- [x] Uninstall steps documented (README.md)

**Note:** verified by installing into a throwaway `HOME` twice and
launching the installed copy. The real login autostart is in place as soon as
`./install.sh` is run on the account; a restart is needed to observe it.
