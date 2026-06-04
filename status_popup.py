"""Brief GTK status popup for desktops that omit tray hover tooltips."""

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib


class StatusPopup:
    """Small undecorated window showing current output/input near the pointer."""

    def __init__(self):
        self._window = None
        self._output_label = None
        self._input_label = None
        self._hide_source = None

    def _ensure_window(self):
        if self._window is not None:
            return

        self._window = Gtk.Window(type=Gtk.WindowType.POPUP)
        self._window.set_decorated(False)
        self._window.set_resizable(False)
        self._window.set_skip_taskbar_hint(True)
        self._window.set_skip_pager_hint(True)
        self._window.set_type_hint(Gdk.WindowTypeHint.TOOLTIP)
        self._window.set_accept_focus(False)
        self._window.set_keep_above(True)

        frame = Gtk.Frame()
        frame.set_shadow_type(Gtk.ShadowType.OUT)
        frame.get_style_context().add_class("background")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(8)
        box.set_margin_bottom(8)

        self._output_label = Gtk.Label(xalign=0)
        self._input_label = Gtk.Label(xalign=0)
        self._output_label.get_style_context().add_class("title")
        self._input_label.get_style_context().add_class("subtitle")

        box.pack_start(self._output_label, False, False, 0)
        box.pack_start(self._input_label, False, False, 0)
        frame.add(box)
        self._window.add(frame)

    def _position_near_pointer(self, x, y):
        display = Gdk.Display.get_default()
        if display is None:
            return max(0, x), max(0, y + 16)

        monitor = display.get_monitor_at_point(x, y)
        if monitor is None:
            return max(0, x - 20), max(0, y + 16)

        geom = monitor.get_geometry()
        self._window.show_all()
        _, _, win_w, win_h = self._window.get_size()

        pos_x = max(geom.x, min(x - 20, geom.x + geom.width - win_w - 4))
        near_top = y <= geom.y + 72
        if near_top:
            pos_y = min(geom.y + geom.height - win_h - 4, y + 24)
        else:
            pos_y = max(geom.y + 4, y - win_h - 8)

        return pos_x, pos_y

    def show_at(self, title, subtitle, x=-1, y=-1, timeout_ms=2500):
        """Show popup near (x, y) or at the current pointer."""
        self._ensure_window()
        self._output_label.set_text(title)
        self._input_label.set_text(subtitle)

        if self._hide_source is not None:
            GLib.source_remove(self._hide_source)
            self._hide_source = None

        if x < 0 or y < 0:
            display = Gdk.Display.get_default()
            seat = display.get_default_seat()
            device = seat.get_pointer()
            _, x, y = device.get_position()

        pos_x, pos_y = self._position_near_pointer(x, y)
        self._window.move(pos_x, pos_y)
        self._window.show_all()

        def _hide():
            if self._window is not None:
                self._window.hide()
            self._hide_source = None
            return False

        self._hide_source = GLib.timeout_add(timeout_ms, _hide)

    def hide(self):
        if self._hide_source is not None:
            GLib.source_remove(self._hide_source)
            self._hide_source = None
        if self._window is not None:
            self._window.hide()

    def destroy(self):
        self.hide()
        if self._window is not None:
            self._window.destroy()
            self._window = None
