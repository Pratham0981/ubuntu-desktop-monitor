# System Dashboard

A compact desktop widget for Ubuntu/GNOME showing CPU load and five minutes of
history, RAM, root and whole-disk usage, CPU temperature, and the busiest
processes. It sits on the desktop layer underneath normal windows rather than
floating above them.

```
CPU                        42%
[=========-------------------]
RAM              4.1 GB / 8.1 GB
[=======---------------------]
[~~~~~ CPU sparkline ~~~~~]
--------------------------------
DISK /        46.1 GB / 95.6 GB · 48%
[===========-----------------]
SSD 188.5 GB · 101.5 GB free
--------------------------------
TEMP                      53°C
TOP                    CPU / RAM
firefox                  12%    8%
```

## Requirements

- Ubuntu 24.04 / GNOME on Wayland (also works on an X11 session)
- Python 3.10+ with PyGObject (`python3-gi`, GTK 3) and `psutil`
- XWayland, for the under-windows placement

## Install

```sh
./install.sh
```

The installer is user-level and idempotent: it copies the package to
`~/.local/share/dashboard-widget`, writes a launcher to
`~/.local/bin/dashboard-widget`, and adds
`~/.config/autostart/dashboard-widget.desktop` so the widget starts at login.
Nothing outside `$HOME` is touched and no root is needed. Run it again after
pulling changes.

## Run

```sh
dashboard-widget          # if ~/.local/bin is on PATH
~/.local/bin/dashboard-widget
python3 -m dashboard      # from this checkout, no install needed
```

## Test

```sh
python3 -m pytest -q                                            # data tests
xvfb-run -a env DASHBOARD_GUI_TESTS=1 python3 -m pytest -q      # + window tests
```

GUI tests are opt-in so they never open windows on a live desktop; they run
against the Xvfb display only.

## Uninstall

```sh
rm -f ~/.local/bin/dashboard-widget
rm -f ~/.config/autostart/dashboard-widget.desktop
rm -rf ~/.local/share/dashboard-widget
```

It stops appearing at the next login. To stop a running copy now, end its
process (`pkill -f 'python3 -m dashboard'`) or log out.

## How placement works

The widget runs as an XWayland client, asks for the `DESKTOP` window type, and
sends the window manager an EWMH request to keep it below normal windows.If that is unavailable it falls back to an always-on-top corner panel. Run with
`--on-top` to force that panel if the under-windows placement does not look
right on your session. Details, including the ordering traps, are in
[docs/placement.md](docs/placement.md).

## Layout

| Path | Purpose |
| --- | --- |
| `dashboard/sampler.py` | The single data seam: one `snapshot()` per refresh |
| `dashboard/disk.py` | Root filesystem and whole physical disk |
| `dashboard/thermal.py` | CPU temperature, `None` when no sensor exists |
| `dashboard/procs.py` | Top processes by CPU |
| `dashboard/widget.py` | GTK window, bars, sparkline, rows |
| `dashboard/placement.py` | Desktop-layer hints and the corner fallback |
| `dashboard/app.py` | Entry point: backend selection, warm-up, main loop |
| `install.sh` | User-level install + XDG autostart entry |
| `.scratch/dashboard/issues/` | The tickets this was built from |
