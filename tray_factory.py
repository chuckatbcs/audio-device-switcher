"""Select the best tray backend for the current desktop session."""

from status_popup import StatusPopup


def create_tray(daemon, active_image, inactive_image, quit_callback):
    """
    Priority:
      1. Native SNI + DbusMenu (KDE, COSMIC, most modern panels — hover + middle-click)
      2. Ayatana AppIndicator + GTK menu (Pop!_OS / Ubuntu)
      3. pystray (legacy fallback)
    """
    popup = StatusPopup()
    tray_holder = {"tray": None}

    def wrapped_quit():
        quit_callback(tray_holder["tray"], popup)

    try:
        from sni_tray import SNITray, sni_tray_available

        if sni_tray_available():
            print("Tray backend: native StatusNotifierItem (SNI)")
            tray = SNITray(daemon, active_image, inactive_image, wrapped_quit, popup)
            tray_holder["tray"] = tray
            return tray
    except Exception as exc:
        print("Native SNI tray unavailable:", exc)

    try:
        from gtk_tray import GtkAppIndicatorTray

        print("Tray backend: Ayatana AppIndicator + GTK menu")
        tray = GtkAppIndicatorTray(daemon, active_image, inactive_image, wrapped_quit, popup)
        tray_holder["tray"] = tray
        return tray
    except Exception as exc:
        print("AppIndicator tray unavailable:", exc)

    from pystray_tray import PystrayTray

    print("Tray backend: pystray (fallback)")
    tray = PystrayTray(daemon, active_image, inactive_image, wrapped_quit, popup)
    tray_holder["tray"] = tray
    return tray
