"""Shared status-popup wiring for all tray backends."""


def attach_tray_popup(tray):
    """Wire menu-open and hover-tracker callbacks on a tray instance."""
    popup = getattr(tray, "status_popup", None)
    if popup is None:
        return

    def show_at_pointer(x=-1, y=-1):
        title = getattr(tray, "_status_title", "")
        subtitle = getattr(tray, "_status_subtitle", "")
        if title:
            popup.show_at(title, subtitle, x, y, timeout_ms=3500)

    def hide_popup():
        popup.hide()

    tray._show_status_popup = show_at_pointer
    tray._hide_status_popup = hide_popup

    tracker = getattr(tray, "_hover_tracker", None)
    if tracker is not None:
        tracker._show = lambda x=-1, y=-1: show_at_pointer(x, y)
        tracker._hide = hide_popup


def on_menu_show(tray):
    """Invoke when the tray menu becomes visible."""
    tracker = getattr(tray, "_hover_tracker", None)
    if tracker is not None:
        tracker.note_menu_opened()
    show = getattr(tray, "_show_status_popup", None)
    if show:
        show()


def on_menu_hide(tray):
    hide = getattr(tray, "_hide_status_popup", None)
    if hide:
        hide()
