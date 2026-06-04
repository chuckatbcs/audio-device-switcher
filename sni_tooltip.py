"""Update SNI ToolTip/Title on the tray item (AppIndicator or native SNI)."""

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib


SNI_IFACE = "org.kde.StatusNotifierItem"
PROPS_IFACE = "org.freedesktop.DBus.Properties"
APP_ID = "audio-device-switcher"


def _list_session_names():
    try:
        conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        variant = conn.call_sync(
            "org.freedesktop.DBus",
            "/org/freedesktop/DBus",
            "org.freedesktop.DBus",
            "ListNames",
            None,
            None,
            Gio.DBusCallFlags.NONE,
            2000,
            None,
        )
        return list(variant.unpack()[0])
    except Exception:
        return []


def find_sni_service(app_id=APP_ID):
    """Find org.kde.StatusNotifierItem-* bus name for our application Id."""
    for name in _list_session_names():
        if not name.startswith("org.kde.StatusNotifierItem-"):
            continue
        try:
            conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            proxy = Gio.DBusProxy.new_sync(
                conn,
                Gio.DBusProxyFlags.NONE,
                None,
                name,
                "/StatusNotifierItem",
                PROPS_IFACE,
                None,
            )
            id_variant = proxy.call_sync(
                "Get",
                GLib.Variant("(ss)", (SNI_IFACE, "Id")),
                Gio.DBusCallFlags.NONE,
                1000,
                None,
            )
            if id_variant.unpack()[0] == app_id:
                return name
        except Exception:
            continue
    return None


class SNITooltipManager:
    """Keeps org.kde.StatusNotifierItem ToolTip and Title in sync."""

    def __init__(self, app_id=APP_ID, icon_name="audio-speakers"):
        self.app_id = app_id
        self.icon_name = icon_name
        self._service = None
        self._title = ""
        self._subtitle = ""
        self._retry_source = None

    def update(self, title, subtitle=""):
        self._title = title or ""
        self._subtitle = subtitle or ""
        if not self._service:
            self._service = find_sni_service(self.app_id)
        if self._service:
            self._apply(self._service)
        elif self._retry_source is None:
            self._retry_source = GLib.timeout_add_seconds(2, self._retry_find)

    def _retry_find(self):
        self._retry_source = None
        self._service = find_sni_service(self.app_id)
        if self._service:
            self._apply(self._service)
        else:
            self._retry_source = GLib.timeout_add_seconds(2, self._retry_find)
        return False

    def _apply(self, service_name):
        try:
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
            tooltip = GLib.Variant("(sa(iiay)ss)", (self.icon_name, [], self._title, self._subtitle))
            proxy.call_sync(
                "Set",
                GLib.Variant("(ssv)", (SNI_IFACE, "ToolTip", tooltip)),
                Gio.DBusCallFlags.NONE,
                1000,
                None,
            )
            title_variant = GLib.Variant("s", self._title)
            proxy.call_sync(
                "Set",
                GLib.Variant("(ssv)", (SNI_IFACE, "Title", title_variant)),
                Gio.DBusCallFlags.NONE,
                1000,
                None,
            )
            item_proxy = Gio.DBusProxy.new_sync(
                conn,
                Gio.DBusProxyFlags.NONE,
                None,
                service_name,
                "/StatusNotifierItem",
                SNI_IFACE,
                None,
            )
            item_proxy.call_sync("NewToolTip", None, Gio.DBusCallFlags.NONE, 1000, None)
            item_proxy.call_sync("NewTitle", None, Gio.DBusCallFlags.NONE, 1000, None)
        except Exception as exc:
            print("SNI tooltip update failed:", exc)
            self._service = None

    def stop(self):
        if self._retry_source is not None:
            GLib.source_remove(self._retry_source)
            self._retry_source = None
