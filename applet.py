import os
import sys
import time
import threading
import pystray
from pystray import MenuItem as item
from pystray import Menu
from PIL import Image

# Import GTK and GObject-Introspection libraries
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Notify', '0.7')
from gi.repository import Gtk, Gdk, GLib, Notify

# Import local components
from icon_generator import generate_speaker_icon
from daemon import AudioSwitcherDaemon

# Global references
daemon = None
icon = None
active_img = None
inactive_img = None
notification = None
last_default_sink = None
last_default_source = None

def init_notify():
    """Initializes the libnotify system."""
    try:
        Notify.init("Audio Device Switcher")
    except Exception as e:
        print("Failed to initialize libnotify:", e)

def show_native_notification(summary, body, icon_name, volume_percent=None):
    """
    Fires a native system desktop notification in the notifications area.
    Constructs a fresh notification object on every display call to guarantee
    Wayland/COSMIC notification server compatibility.
    """
    try:
        init_notify()
        
        # Create a fresh notification object
        n = Notify.Notification.new(summary, body, icon_name)
        n.set_hint("desktop-entry", GLib.Variant("s", "audio-device-switcher"))
        
        # If a volume percentage is provided, set the system progress hint
        if volume_percent is not None:
            n.set_hint("value", GLib.Variant("i", volume_percent))
            
        n.show()
    except Exception as e:
        print("Error showing system notification:", e)

def quit_app(icon_inst, daemon_inst):
    """Gracefully shuts down the daemon and applet."""
    print("Exiting Audio Device Switcher...")
    if daemon_inst:
        daemon_inst.stop()
    if icon_inst:
        icon_inst.stop()
    try:
        Notify.uninit()
    except Exception:
        pass
    sys.exit(0)

# Helper closure creators to satisfy PyStray's strict argument-count check (max 2 arguments)
def make_sink_callback(daemon_inst, sink_name):
    return lambda icon_ref, it: daemon_inst.switch_default_sink(sink_name, manual=True)

def make_source_callback(daemon_inst, source_name):
    return lambda icon_ref, it: daemon_inst.switch_default_source(source_name, manual=True)

def make_exclusion_callback(daemon_inst, device_name):
    return lambda icon_ref, it: daemon_inst.toggle_exclusion(device_name)

def rebuild_menu(daemon_inst):
    """
    Dynamically constructs the tray menu structure based on current PipeWire state,
    available outputs/inputs, settings, and connection history.
    """
    sinks = daemon_inst.query_sinks()
    sources = daemon_inst.query_sources()
    default_sink = daemon_inst.get_default_sink()
    default_source = daemon_inst.get_default_source()
    
    auto_switch_item = item(
        "✓ Auto-Switch Connected Devices" if daemon_inst.is_auto_switch_enabled() else "  Auto-Switch Connected Devices",
        lambda icon_ref, it: daemon_inst.set_auto_switch(not daemon_inst.is_auto_switch_enabled())
    )
    
    sink_items = []
    for s in sinks:
        name = s["name"]
        desc = s.get("description", name)
        is_active = (name == default_sink)
        
        prefix = "● " if is_active else "  "
        sink_items.append(item(
            f"{prefix}{desc}",
            make_sink_callback(daemon_inst, name)
        ))
    outputs_menu = Menu(*sink_items) if sink_items else Menu(item("  No outputs found", lambda icon_ref, it: None, enabled=False))
    outputs_submenu = item("Select Output Device", outputs_menu)
    
    source_items = []
    for src in sources:
        name = src["name"]
        desc = src.get("description", name)
        is_active = (name == default_source)
        
        prefix = "● " if is_active else "  "
        source_items.append(item(
            f"{prefix}{desc}",
            make_source_callback(daemon_inst, name)
        ))
    inputs_menu = Menu(*source_items) if source_items else Menu(item("  No inputs found", lambda icon_ref, it: None, enabled=False))
    inputs_submenu = item("Select Input Device", inputs_menu)
    
    excl_items = []
    for s in sinks:
        name = s["name"]
        desc = s.get("description", name)
        is_excl = daemon_inst.is_excluded(name)
        status = "[✓] " if is_excl else "[ ] "
        excl_items.append(item(
            f"{status}[Out] {desc}",
            make_exclusion_callback(daemon_inst, name)
        ))
    for src in sources:
        name = src["name"]
        desc = src.get("description", name)
        is_excl = daemon_inst.is_excluded(name)
        status = "[✓] " if is_excl else "[ ] "
        excl_items.append(item(
            f"{status}[In] {desc}",
            make_exclusion_callback(daemon_inst, name)
        ))
    exclusions_menu = Menu(*excl_items) if excl_items else Menu(item("  No devices to exclude", lambda icon_ref, it: None, enabled=False))
    exclusions_submenu = item("Configure Exclusions", exclusions_menu)
    
    hist_entries = daemon_inst.get_history()
    hist_items = []
    for entry in hist_entries[:8]:
        hist_items.append(item(f"  {entry}", lambda icon_ref, it: None, enabled=False))
    if not hist_items:
        hist_items.append(item("  No events logged", lambda icon_ref, it: None, enabled=False))
    history_menu = Menu(*hist_items)
    history_submenu = item("Connection History", history_menu)
    
    main_menu = Menu(
        auto_switch_item,
        Menu.SEPARATOR,
        outputs_submenu,
        inputs_submenu,
        exclusions_submenu,
        Menu.SEPARATOR,
        history_submenu,
        Menu.SEPARATOR,
        item("Exit Switcher", lambda icon_ref, it: quit_app(icon_ref, daemon_inst))
    )
    return main_menu

def update_ui_state():
    """Callback function executed on daemon state changes to update panel icons and menu structures."""
    global icon, daemon, active_img, inactive_img, last_default_sink, last_default_source
    if not icon or not daemon:
        return
    
    # 1. Rebuild dynamic menu
    icon.menu = rebuild_menu(daemon)
    
    # 2. Update state-based panel icon
    if daemon.is_auto_switch_enabled():
        icon.icon = active_img
    else:
        icon.icon = inactive_img

    # 3. Dynamic Tooltip and Notification Check
    try:
        current_sink = daemon.get_default_sink()
        current_source = daemon.get_default_source()
        sinks = daemon.query_sinks()
        sources = daemon.query_sources()
        
        sink_desc = next((s.get("description", current_sink) for s in sinks if s["name"] == current_sink), current_sink)
        source_desc = next((s.get("description", current_source) for s in sources if s["name"] == current_source), current_source)
        
        # Extract volume level of default output
        vol_val = 0
        vol_str = ""
        for s in sinks:
            if s["name"] == current_sink:
                vol_dict = s.get("volume", {})
                if vol_dict:
                    first_channel = list(vol_dict.values())[0]
                    val_pct = first_channel.get("value_percent", "0%")
                    vol_str = f" ({val_pct})"
                    try:
                        vol_val = int(val_pct.strip("%"))
                    except ValueError:
                        vol_val = 0
                break
                
        # Set small panel icon hover tooltip dynamically
        icon.title = f"Audio Switcher\nOutput: {sink_desc}{vol_str}\nInput: {source_desc}"
        
        # Populate initial tracking states without notifying
        if last_default_sink is None:
            last_default_sink = current_sink
        if last_default_source is None:
            last_default_source = current_source
            
        # Trigger native notification popup if Output Sink changed (only for auto-switches)
        if current_sink != last_default_sink:
            if not daemon.last_switch_was_manual:
                icon_name = "audio-headphones" if "bluez" in current_sink or "headphone" in current_sink.lower() else "audio-speakers"
                GLib.idle_add(lambda: show_native_notification(
                    "Audio Switcher", 
                    f"Output changed to:\n{sink_desc}", 
                    icon_name
                ))
            last_default_sink = current_sink
            
        # Trigger native notification popup if Input Source changed (only for auto-switches)
        if current_source != last_default_source:
            if not daemon.last_switch_was_manual:
                GLib.idle_add(lambda: show_native_notification(
                    "Audio Switcher", 
                    f"Input changed to:\n{source_desc}", 
                    "audio-input-microphone"
                ))
            last_default_source = current_source
            
    except Exception as e:
        print("Error in UI state update:", e)

def show_volume_notification(device_desc, volume_percent, is_muted):
    """Callback triggered on volume changes to update/show a native system notification card in-place."""
    icon_name = "audio-volume-muted" if is_muted else ("audio-headphones" if "headphone" in device_desc.lower() or "shokz" in device_desc.lower() else "audio-volume-high")
    
    # Generate content
    body = f"{device_desc}\nVolume: {volume_percent}%"
    if is_muted:
        body = f"{device_desc}\nMuted"
        
    GLib.idle_add(lambda: show_native_notification(
        "Volume Adjusted",
        body,
        icon_name,
        volume_percent=volume_percent if not is_muted else 0
    ))

def main():
    global daemon, icon, active_img, inactive_img
    print("Starting Audio Device Switcher Applet...")
    
    # Generate procedural state icons
    active_img = generate_speaker_icon(active=True)
    inactive_img = generate_speaker_icon(active=False)
    
    # Pre-initialize libnotify
    init_notify()
    
    # Initialize the backend daemon with our UI and volume callbacks
    daemon = AudioSwitcherDaemon(on_change_callback=update_ui_state, on_volume_change_callback=show_volume_notification)
    daemon.start()
    
    # Initialize the system tray icon
    initial_icon = active_img if daemon.is_auto_switch_enabled() else inactive_img
    icon = pystray.Icon(
        "audio_device_switcher",
        initial_icon,
        "Audio Device Switcher",
        menu=rebuild_menu(daemon)
    )
    
    # Set initial hover tooltip title
    update_ui_state()
    
    # Start the PyStray event loop (runs on main thread)
    try:
        icon.run()
    except KeyboardInterrupt:
        quit_app(icon, daemon)

if __name__ == '__main__':
    main()
