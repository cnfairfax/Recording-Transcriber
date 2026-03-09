"""Root pytest configuration.

Sets QT_QPA_PLATFORM=offscreen when no display is available so that
PyQt6 widget tests can run in headless CI environments without a
physical or virtual display server.
"""

import os
import sys

if (
    sys.platform.startswith("linux")
    and not os.environ.get("DISPLAY")
    and not os.environ.get("WAYLAND_DISPLAY")
    and not os.environ.get("QT_QPA_PLATFORM")
):
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
