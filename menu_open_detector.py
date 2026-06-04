"""Detect when the panel opens our DBusMenu and trigger the status popup.

COSMIC (and some other panels) render tray menus remotely via
com.canonical.dbusmenu GetLayout — local Gtk menu show signals never fire.
A session-bus message filter catches those calls reliably.
"""

import dbus
from gi.repository import GLib

from sni_tooltip import find_sni_service

DBUSMENU_IFACE = "com.canonical.dbusmenu"
SNI_IFACE = "org.kde.StatusNotifierItem"
PROPS_IFACE = "org.freedesktop.DBus.Properties"
MENU_METHODS = frozenset({"GetLayout", "GetGroupProperties", "AboutToShow"})


def get_sni_menu_path(service_name):
    """Read the Menu object path from a StatusNotifierItem service."""
    try:
        import gi

        gi.require_version("Gio", "2.0")
        from gi.repository import Gio

        conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        proxy = Gio.DBusProxy.new_sync(
            conn,
            Gio.DBusProxyFlags.NONE,
            None,
            service_name,
            "/StatusNotifierItem",
            PROPS_IFACE,
            None,
        )
        variant = proxy.call_sync(
            "Get",
            GLib.Variant("(ss)", (SNI_IFACE, "Menu")),
            Gio.DBusCallFlags.NONE,
            1500,
            None,
        )
        return str(variant.unpack()[0])
    except Exception:
        return None


class MenuOpenDetector:
    """Watch incoming DBusMenu method calls and invoke a callback."""

    def __init__(self, on_open_callback, log=None):
        self._paths = set()
        self._callback = on_open_callback
        self._log = log
        self._filter_added = False
        self._conn = None
        self._poll_source = None
        self._last_trigger = 0

    def add_path(self, path):
        if path:
            self._paths.add(str(path))
            self._debug(f"watching menu path {path}")

    def start(self, bus=None, app_id=None, known_paths=None):
        self._conn = bus or dbus.SessionBus()
        if not self._filter_added:
            self._conn.add_message_filter(self._filter)
            self._filter_added = True

        for path in known_paths or ():
            self.add_path(path)

        if app_id:
            self._poll_for_menu_path(app_id)

    def stop(self):
        if self._poll_source is not None:
            GLib.source_remove(self._poll_source)
            self._poll_source = None
        if self._conn and self._filter_added:
            self._conn.remove_message_filter(self._filter)
            self._filter_added = False

    def _poll_for_menu_path(self, app_id):
        attempts = [0]

        def poll():
            attempts[0] += 1
            service = find_sni_service(app_id)
            if service:
                path = get_sni_menu_path(service)
                if path and path not in ("", "/"):
                    self.add_path(path)
                    return False
            if attempts[0] >= 60:
                self._debug(f"gave up discovering menu path for {app_id}")
                return False
            return True

        self._poll_source = GLib.timeout_add(500, poll)

    def _filter(self, _conn, message):
        if message.get_type() != dbus.lowlevel.METHOD_CALL_MESSAGE:
            return dbus.lowlevel.HANDLER_RESULT_NOT_YET_HANDLED

        if message.get_interface() != DBUSMENU_IFACE:
            return dbus.lowlevel.HANDLER_RESULT_NOT_YET_HANDLED

        if message.get_member() not in MENU_METHODS:
            return dbus.lowlevel.HANDLER_RESULT_NOT_YET_HANDLED

        path = message.get_path()
        if path not in self._paths:
            return dbus.lowlevel.HANDLER_RESULT_NOT_YET_HANDLED

        now = GLib.get_monotonic_time()
        if now - self._last_trigger < 300_000:
            return dbus.lowlevel.HANDLER_RESULT_NOT_YET_HANDLED

        self._last_trigger = now
        self._debug(f"menu open via {message.get_member()} on {path}")
        GLib.idle_add(self._trigger)
        return dbus.lowlevel.HANDLER_RESULT_NOT_YET_HANDLED

    def _trigger(self):
        if self._callback:
            self._callback()
        return False

    def _debug(self, msg):
        if self._log:
            self._log(msg)
