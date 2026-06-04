"""Native StatusNotifierItem tray with ToolTip and middle-click status popup."""

import os
import struct

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gio", "2.0")
from gi.repository import Gtk, GLib, Gio

try:
    gi.require_version("DbusmenuGtk3", "0.4")
    from gi.repository import DbusmenuGtk3 as DbusmenuGtk

    HAS_DBUSMENU = True
except ValueError:
    HAS_DBUSMENU = False

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop

from menu_builder import build_gtk_menu
from panel_hover import PanelHoverTracker
from tray_popup import attach_tray_popup

WATCHER_IFACE = "org.kde.StatusNotifierWatcher"

SNI_IFACE = "org.kde.StatusNotifierItem"
PROPS_IFACE = "org.freedesktop.DBus.Properties"
WATCHER_BUS = "org.kde.StatusNotifierWatcher"
WATCHER_PATH = "/StatusNotifierWatcher"


def pil_to_dbus_pixmaps(pil_image, sizes=(64, 32, 22)):
    pixmaps = dbus.Array([], signature="(iiay)")
    for size in sizes:
        resized = pil_image.resize((size, size))
        rgba = resized.tobytes("raw", "RGBA")
        argb = b"".join(
            struct.pack("4B", rgba[i + 3], rgba[i], rgba[i + 1], rgba[i + 2])
            for i in range(0, len(rgba), 4)
        )
        pixmaps.append((size, size, dbus.ByteArray(argb)))
    return pixmaps


def watcher_available():
    try:
        conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        conn.call_sync(
            WATCHER_BUS,
            WATCHER_PATH,
            WATCHER_IFACE,
            "Get",
            GLib.Variant("(ss)", (WATCHER_IFACE, "RegisteredStatusNotifierItems")),
            None,
            Gio.DBusCallFlags.NONE,
            1500,
            None,
        )
        return True
    except Exception:
        return False


class _StatusNotifierItem(dbus.service.Object):
    def __init__(self, bus, app_id, menu_path):
        self._app_id = app_id
        self._menu_path = menu_path
        self._title = app_id
        self._subtitle = ""
        self._icon_name = "audio-speakers"
        self._pixmaps = dbus.Array([], signature="(iiay)")
        self._status = "Active"
        self._popup_cb = None
        super().__init__(bus, "/StatusNotifierItem")

    def set_popup_callback(self, cb):
        self._popup_cb = cb

    def set_text(self, title, subtitle):
        self._title = title or self._app_id
        self._subtitle = subtitle or ""
        self.PropertiesChanged(
            SNI_IFACE,
            {"Title": self._title, "ToolTip": self._tooltip_variant()},
            [],
        )
        self.NewToolTip()
        self.NewTitle()

    def set_pixmaps(self, pixmaps):
        self._pixmaps = pixmaps
        self.PropertiesChanged(SNI_IFACE, {"IconPixmap": self._pixmaps}, [])
        self.NewIcon()

    def _tooltip_variant(self):
        return (self._icon_name, dbus.Array([], signature="(iiay)"), self._title, self._subtitle)

    def _all_props(self):
        return {
            "Category": "ApplicationStatus",
            "Id": self._app_id,
            "Title": self._title,
            "ToolTip": self._tooltip_variant(),
            "IconName": self._icon_name,
            "IconPixmap": self._pixmaps,
            "Menu": dbus.ObjectPath(self._menu_path),
            "Status": self._status,
            "ItemIsMenu": False,
        }

    @dbus.service.method(PROPS_IFACE, in_signature="ss", out_signature="v")
    def Get(self, interface, prop):
        if interface != SNI_IFACE:
            raise dbus.exceptions.DBusException("Unknown interface")
        val = self._all_props().get(prop)
        if val is None:
            raise dbus.exceptions.DBusException("Unknown property")
        return val

    @dbus.service.method(PROPS_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != SNI_IFACE:
            return {}
        return self._all_props()

    @dbus.service.signal(PROPS_IFACE, signature="sa{sv}as")
    def PropertiesChanged(self, interface, changed, invalidated):
        pass

    @dbus.service.signal(SNI_IFACE)
    def NewToolTip(self):
        pass

    @dbus.service.signal(SNI_IFACE)
    def NewTitle(self):
        pass

    @dbus.service.signal(SNI_IFACE)
    def NewIcon(self):
        pass

    @dbus.service.method(SNI_IFACE, in_signature="ii")
    def Activate(self, x, y):
        if self._popup_cb:
            self._popup_cb(self._title, self._subtitle, x, y)

    @dbus.service.method(SNI_IFACE, in_signature="ii")
    def SecondaryActivate(self, x, y):
        if self._popup_cb:
            self._popup_cb(self._title, self._subtitle, x, y)

    @dbus.service.method(SNI_IFACE, in_signature="is")
    def Scroll(self, delta, orientation):
        pass


class SNITray:
    """Full SNI registration — best hover ToolTip + middle-click popup on KDE/COSMIC."""

    APP_ID = "audio-device-switcher"

    def __init__(self, daemon, active_image, inactive_image, quit_callback, status_popup=None):
        if not HAS_DBUSMENU:
            raise RuntimeError("DbusmenuGtk unavailable")
        self.daemon = daemon
        self.active_image = active_image
        self.inactive_image = inactive_image
        self.quit_callback = quit_callback
        self.status_popup = status_popup
        self._current_pil = active_image
        self._status_title = ""
        self._status_subtitle = ""
        self._hover_tracker = PanelHoverTracker(lambda x=-1, y=-1: None, lambda: None)
        attach_tray_popup(self)
        self._bus = None
        self._service_name = f"org.kde.StatusNotifierItem-{os.getpid()}-1"
        self._item = None
        self._menu = None
        self._gtk_menu = None
        self._menu_path = "/Menu"

    def _show_popup(self, title, subtitle, x, y):
        if self.status_popup:
            GLib.idle_add(self.status_popup.show_at, title, subtitle, x, y)

    def set_icon(self, pil_image):
        self._current_pil = pil_image
        if self._item:
            self._item.set_pixmaps(pil_to_dbus_pixmaps(pil_image))

    def set_tooltip(self, title, subtitle=""):
        self._status_title = title or ""
        self._status_subtitle = subtitle or ""
        if self._item:
            self._item.set_text(title, subtitle)

    def set_menu(self):
        for child in list(self._menu.get_children()):
            self._menu.remove(child)
            child.destroy()
        gtk_menu = build_gtk_menu(self.daemon, self.quit_callback, tray=self)
        for child in list(gtk_menu.get_children()):
            gtk_menu.remove(child)
            self._menu.append(child)
            child.show_all()

    def _register_with_watcher(self):
        try:
            watcher = self._bus.get_object(WATCHER_BUS, WATCHER_PATH)
            iface = dbus.Interface(watcher, WATCHER_IFACE)
            iface.RegisterStatusNotifierItem(f"{self._service_name}/StatusNotifierItem")
        except Exception as exc:
            print("SNI watcher registration failed:", exc)

    def start(self):
        DBusGMainLoop(set_as_default=True)
        self._bus = dbus.SessionBus()
        self._menu = DbusmenuGtk.Menu.new('com.audio.device.switcher.menu', '/Menu')
        self._menu_path = '/Menu'
        self._item = _StatusNotifierItem(self._bus, self.APP_ID, self._menu_path)
        self._item.set_popup_callback(self._show_popup)
        self._bus.request_name(self._service_name)
        self._register_with_watcher()
        self.set_icon(self._current_pil)
        self.set_menu()
        self._hover_tracker.start()
        Gtk.main()

    def stop(self):
        self._hover_tracker.stop()
        Gtk.main_quit()


def sni_tray_available():
    return HAS_DBUSMENU and watcher_available()
