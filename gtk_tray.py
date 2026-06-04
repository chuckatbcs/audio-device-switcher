"""Ayatana AppIndicator + GTK menu tray backend (Pop!_OS / Ubuntu native path)."""

import os
import tempfile

import gi

gi.require_version("Gtk", "3.0")
try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    APPIND = "AyatanaAppIndicator3"
except ValueError:
    gi.require_version("AppIndicator3", "0.1")
    APPIND = "AppIndicator3"

from gi.repository import Gtk, GLib, GdkPixbuf

AppIndicator = gi.module.get_introspection_module(APPIND)

from menu_builder import build_gtk_menu
from sni_tooltip import SNITooltipManager


class GtkAppIndicatorTray:
    """Tray icon via AppIndicator with GTK menu and SNI ToolTip patching."""

    APP_ID = "audio-device-switcher"

    def __init__(self, daemon, active_image, inactive_image, quit_callback, status_popup=None):
        self.daemon = daemon
        self.active_image = active_image
        self.inactive_image = inactive_image
        self.quit_callback = quit_callback
        self.status_popup = status_popup
        self._indicator = None
        self._icon_path = None
        self._tooltip = SNITooltipManager(self.APP_ID)
        self._current_pil = active_image

    def _write_icon(self, pil_image):
        if self._icon_path is None:
            fd, self._icon_path = tempfile.mkstemp(suffix=".png", prefix="ads-tray-")
            os.close(fd)
        pil_image.save(self._icon_path, format="PNG")
        return self._icon_path

    def set_icon(self, pil_image):
        self._current_pil = pil_image
        if not self._indicator:
            return
        path = self._write_icon(pil_image)
        self._indicator.set_icon_full(path, self.APP_ID)

    def set_tooltip(self, title, subtitle=""):
        if self._indicator:
            self._indicator.set_title(title or self.APP_ID)
        self._tooltip.update(title, subtitle)

    def set_menu(self):
        if not self._indicator:
            return
        menu = build_gtk_menu(self.daemon, self.quit_callback)
        self._indicator.set_menu(menu)

    def start(self):
        self._indicator = AppIndicator.Indicator.new(
            self.APP_ID,
            "audio-headphones",
            AppIndicator.IndicatorCategory.APPLICATION_STATUS,
        )
        self._indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.set_icon(self._current_pil)
        self.set_menu()
        Gtk.main()

    def stop(self):
        self._tooltip.stop()
        Gtk.main_quit()
