"""Simulate tray hover on panels (e.g. COSMIC) that ignore SNI ToolTip."""

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib


class PanelHoverTracker:
    """
    After the user opens the tray menu once, remember the pointer position as the
    icon hotspot. When the pointer dwells near that spot on any panel edge,
    show the status popup — the closest we can get to hover without panel support.
    """

    PANEL_STRIP_PX = 64
    HOTSPOT_RADIUS_PX = 48
    DWELL_MS = 200
    POLL_MS = 100

    def __init__(self, show_callback, hide_callback, log=None):
        self._show = show_callback
        self._hide = hide_callback
        self._log = log
        self._hotspot_x = None
        self._hotspot_y = None
        self._dwell_source = None
        self._poll_source = None
        self._popup_visible = False
        self._last_x = None
        self._last_y = None
        self._stable_since = None

    def note_menu_opened(self):
        """Call when the tray menu opens to learn where the icon is on screen."""
        display = Gdk.Display.get_default()
        if display is None:
            return
        seat = display.get_default_seat()
        if seat is None:
            return
        _, x, y = seat.get_pointer().get_position()
        self._hotspot_x = x
        self._hotspot_y = y
        if self._log:
            self._log(f"hover hotspot calibrated at ({x}, {y})")

    def start(self):
        if self._poll_source is None:
            self._poll_source = GLib.timeout_add(self.POLL_MS, self._poll)

    def stop(self):
        if self._poll_source is not None:
            GLib.source_remove(self._poll_source)
            self._poll_source = None
        if self._dwell_source is not None:
            GLib.source_remove(self._dwell_source)
            self._dwell_source = None
        self._popup_visible = False

    def _on_panel_strip(self, x, y, geom):
        """True when pointer is on a top/bottom/left/right panel edge."""
        top = y <= geom.y + self.PANEL_STRIP_PX
        bottom = y >= geom.y + geom.height - self.PANEL_STRIP_PX
        left = x <= geom.x + self.PANEL_STRIP_PX
        right = x >= geom.x + geom.width - self.PANEL_STRIP_PX
        return top or bottom or left or right

    def _poll(self):
        if self._hotspot_x is None:
            return True

        display = Gdk.Display.get_default()
        if display is None:
            return True
        seat = display.get_default_seat()
        if seat is None:
            return True

        _, x, y = seat.get_pointer().get_position()
        monitor = display.get_monitor_at_point(x, y)
        if monitor is None:
            return True

        geom = monitor.get_geometry()
        on_panel_strip = self._on_panel_strip(x, y, geom)
        dx = abs(x - self._hotspot_x)
        dy = abs(y - self._hotspot_y)
        near_icon = dx <= self.HOTSPOT_RADIUS_PX and dy <= self.HOTSPOT_RADIUS_PX

        if not on_panel_strip or not near_icon:
            self._stable_since = None
            if self._popup_visible:
                self._popup_visible = False
                self._hide()
            return True

        now = GLib.get_monotonic_time()
        if self._last_x == x and self._last_y == y:
            if self._stable_since is None:
                self._stable_since = now
            elif not self._popup_visible and (now - self._stable_since) >= self.DWELL_MS * 1000:
                self._popup_visible = True
                if self._log:
                    self._log(f"hover popup at ({x}, {y})")
                self._show(x, y)
        else:
            self._stable_since = now

        self._last_x = x
        self._last_y = y
        return True
