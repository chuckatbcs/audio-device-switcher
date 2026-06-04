"""pystray fallback tray for environments without AppIndicator/SNI."""

import pystray

from menu_builder import build_pystray_menu


class PystrayTray:
    def __init__(self, daemon, active_image, inactive_image, quit_callback, status_popup=None):
        self.daemon = daemon
        self.active_image = active_image
        self.inactive_image = inactive_image
        self.quit_callback = quit_callback
        self.status_popup = status_popup
        self._icon = None
        self._current_pil = active_image

    def set_icon(self, pil_image):
        self._current_pil = pil_image
        if self._icon:
            self._icon.icon = pil_image

    def set_tooltip(self, title, subtitle=""):
        if self._icon:
            text = title if not subtitle else f"{title}\n{subtitle}"
            self._icon.title = text

    def set_menu(self):
        if self._icon:
            self._icon.menu = build_pystray_menu(
                self.daemon,
                self.quit_callback,
            )

    def start(self):
        self._icon = pystray.Icon(
            "audio_device_switcher",
            self._current_pil,
            "Audio Device Switcher",
            menu=build_pystray_menu(
                self.daemon,
                self.quit_callback,
            ),
        )
        self._icon.run()

    def stop(self):
        if self._icon:
            self._icon.stop()
