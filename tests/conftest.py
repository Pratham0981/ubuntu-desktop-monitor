"""Keep GTK tests on a test X server, never on the developer's session.

GTK prefers Wayland whenever WAYLAND_DISPLAY is set, which would put test
windows on the real desktop.  GUI tests are therefore opt-in:

    xvfb-run -a env DASHBOARD_GUI_TESTS=1 python3 -m pytest
"""

import os

if os.environ.get("DISPLAY") and os.environ.get("DASHBOARD_GUI_TESTS"):
    os.environ["GDK_BACKEND"] = "x11"
    os.environ.pop("WAYLAND_DISPLAY", None)
