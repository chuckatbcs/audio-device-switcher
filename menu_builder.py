"""Build tray menus for GTK/DbusMenu and pystray backends."""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from audio_state import get_active_device_status


def _gtk_separator():
    return Gtk.SeparatorMenuItem()


def build_gtk_menu(daemon_inst, quit_callback, tray=None):
    """Build a Gtk.Menu mirroring the pystray menu structure."""
    menu = Gtk.Menu()

    _, source_desc, output_label, _ = get_active_device_status(daemon_inst)

    for label in (output_label, source_desc):
        item = Gtk.MenuItem(label=f"  {label}")
        item.set_sensitive(False)
        menu.append(item)

    menu.append(_gtk_separator())

    auto_label = (
        "✓ Auto-Switch Connected Devices"
        if daemon_inst.is_auto_switch_enabled()
        else "  Auto-Switch Connected Devices"
    )
    auto_item = Gtk.MenuItem(label=auto_label)
    auto_item.connect(
        "activate",
        lambda *_: daemon_inst.set_auto_switch(not daemon_inst.is_auto_switch_enabled()),
    )
    menu.append(auto_item)
    menu.append(_gtk_separator())

    outputs = Gtk.MenuItem(label="Select Output Device")
    outputs_sub = Gtk.Menu()
    default_sink = daemon_inst.get_default_sink()
    for s in daemon_inst.query_sinks():
        name = s["name"]
        desc = s.get("description", name)
        prefix = "● " if name == default_sink else "  "
        item = Gtk.MenuItem(label=f"{prefix}{desc}")
        item.connect("activate", lambda _w, n=name: daemon_inst.switch_default_sink(n, manual=True))
        outputs_sub.append(item)
    if not daemon_inst.query_sinks():
        item = Gtk.MenuItem(label="  No outputs found")
        item.set_sensitive(False)
        outputs_sub.append(item)
    outputs.set_submenu(outputs_sub)
    menu.append(outputs)

    inputs = Gtk.MenuItem(label="Select Input Device")
    inputs_sub = Gtk.Menu()
    default_source = daemon_inst.get_default_source()
    for src in daemon_inst.query_sources():
        name = src["name"]
        desc = src.get("description", name)
        prefix = "● " if name == default_source else "  "
        item = Gtk.MenuItem(label=f"{prefix}{desc}")
        item.connect("activate", lambda _w, n=name: daemon_inst.switch_default_source(n, manual=True))
        inputs_sub.append(item)
    if not daemon_inst.query_sources():
        item = Gtk.MenuItem(label="  No inputs found")
        item.set_sensitive(False)
        inputs_sub.append(item)
    inputs.set_submenu(inputs_sub)
    menu.append(inputs)

    exclusions = Gtk.MenuItem(label="Configure Exclusions")
    excl_sub = Gtk.Menu()
    for s in daemon_inst.query_sinks():
        name = s["name"]
        desc = s.get("description", name)
        status = "[✓] " if daemon_inst.is_excluded(name) else "[ ] "
        item = Gtk.MenuItem(label=f"{status}[Out] {desc}")
        item.connect("activate", lambda _w, n=name: daemon_inst.toggle_exclusion(n))
        excl_sub.append(item)
    for src in daemon_inst.query_sources():
        name = src["name"]
        desc = src.get("description", name)
        status = "[✓] " if daemon_inst.is_excluded(name) else "[ ] "
        item = Gtk.MenuItem(label=f"{status}[In] {desc}")
        item.connect("activate", lambda _w, n=name: daemon_inst.toggle_exclusion(n))
        excl_sub.append(item)
    if not excl_sub.get_children():
        item = Gtk.MenuItem(label="  No devices to exclude")
        item.set_sensitive(False)
        excl_sub.append(item)
    exclusions.set_submenu(excl_sub)
    menu.append(exclusions)
    menu.append(_gtk_separator())

    history = Gtk.MenuItem(label="Connection History")
    hist_sub = Gtk.Menu()
    hist_entries = daemon_inst.get_history()[:8]
    if hist_entries:
        for entry in hist_entries:
            item = Gtk.MenuItem(label=f"  {entry}")
            item.set_sensitive(False)
            hist_sub.append(item)
    else:
        item = Gtk.MenuItem(label="  No events logged")
        item.set_sensitive(False)
        hist_sub.append(item)
    history.set_submenu(hist_sub)
    menu.append(history)
    menu.append(_gtk_separator())

    exit_item = Gtk.MenuItem(label="Exit Switcher")
    exit_item.connect("activate", lambda *_: quit_callback())
    menu.append(exit_item)

    if tray is not None:
        from tray_popup import on_menu_show, on_menu_hide
        menu.connect("show", lambda *_: on_menu_show(tray))
        menu.connect("hide", lambda *_: on_menu_hide(tray))

    menu.show_all()
    return menu


def build_pystray_menu(daemon_inst, quit_callback):
    """Build pystray Menu (fallback backend)."""
    from pystray import MenuItem as PyMenuItem
    from pystray import Menu as PyMenu

    def make_sink_callback(sink_name):
        return lambda icon_ref, it: daemon_inst.switch_default_sink(sink_name, manual=True)

    def make_source_callback(source_name):
        return lambda icon_ref, it: daemon_inst.switch_default_source(source_name, manual=True)

    def make_exclusion_callback(device_name):
        return lambda icon_ref, it: daemon_inst.toggle_exclusion(device_name)

    sinks = daemon_inst.query_sinks()
    sources = daemon_inst.query_sources()
    default_sink = daemon_inst.get_default_sink()
    default_source = daemon_inst.get_default_source()

    auto_switch_item = PyMenuItem(
        "✓ Auto-Switch Connected Devices" if daemon_inst.is_auto_switch_enabled() else "  Auto-Switch Connected Devices",
        lambda icon_ref, it: daemon_inst.set_auto_switch(not daemon_inst.is_auto_switch_enabled()),
    )

    sink_items = []
    for s in sinks:
        name = s["name"]
        desc = s.get("description", name)
        prefix = "● " if name == default_sink else "  "
        sink_items.append(PyMenuItem(f"{prefix}{desc}", make_sink_callback(name)))
    outputs_menu = PyMenu(*sink_items) if sink_items else PyMenu(
        PyMenuItem("  No outputs found", lambda icon_ref, it: None, enabled=False)
    )

    source_items = []
    for src in sources:
        name = src["name"]
        desc = src.get("description", name)
        prefix = "● " if name == default_source else "  "
        source_items.append(PyMenuItem(f"{prefix}{desc}", make_source_callback(name)))
    inputs_menu = PyMenu(*source_items) if source_items else PyMenu(
        PyMenuItem("  No inputs found", lambda icon_ref, it: None, enabled=False)
    )

    excl_items = []
    for s in sinks:
        name = s["name"]
        desc = s.get("description", name)
        status = "[✓] " if daemon_inst.is_excluded(name) else "[ ] "
        excl_items.append(PyMenuItem(f"{status}[Out] {desc}", make_exclusion_callback(name)))
    for src in sources:
        name = src["name"]
        desc = src.get("description", name)
        status = "[✓] " if daemon_inst.is_excluded(name) else "[ ] "
        excl_items.append(PyMenuItem(f"{status}[In] {desc}", make_exclusion_callback(name)))
    exclusions_menu = PyMenu(*excl_items) if excl_items else PyMenu(
        PyMenuItem("  No devices to exclude", lambda icon_ref, it: None, enabled=False)
    )

    hist_items = []
    for entry in daemon_inst.get_history()[:8]:
        hist_items.append(PyMenuItem(f"  {entry}", lambda icon_ref, it: None, enabled=False))
    if not hist_items:
        hist_items.append(PyMenuItem("  No events logged", lambda icon_ref, it: None, enabled=False))

    _, source_desc, output_label, _ = get_active_device_status(daemon_inst)

    return PyMenu(
        PyMenuItem(f"  {output_label}", lambda icon_ref, it: None, enabled=False),
        PyMenuItem(f"  {source_desc}", lambda icon_ref, it: None, enabled=False),
        PyMenu.SEPARATOR,
        auto_switch_item,
        PyMenu.SEPARATOR,
        PyMenuItem("Select Output Device", outputs_menu),
        PyMenuItem("Select Input Device", inputs_menu),
        PyMenuItem("Configure Exclusions", exclusions_menu),
        PyMenu.SEPARATOR,
        PyMenuItem("Connection History", PyMenu(*hist_items)),
        PyMenu.SEPARATOR,
        PyMenuItem("Exit Switcher", lambda icon_ref, it: quit_callback()),
    )
