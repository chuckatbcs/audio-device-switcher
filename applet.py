import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Notify", "0.7")
from gi.repository import GLib, Notify

from icon_generator import generate_speaker_icon
from daemon import AudioSwitcherDaemon
from audio_state import get_active_device_status, get_tooltip_strings
from tray_factory import create_tray

daemon = None
tray = None
active_img = None
inactive_img = None
last_default_sink = None
last_default_source = None


def init_notify():
    try:
        Notify.init("Audio Device Switcher")
    except Exception as e:
        print("Failed to initialize libnotify:", e)


def show_native_notification(summary, body, icon_name, volume_percent=None):
    try:
        init_notify()
        n = Notify.Notification.new(summary, body, icon_name)
        n.set_hint("desktop-entry", GLib.Variant("s", "audio-device-switcher"))
        if volume_percent is not None:
            n.set_hint("value", GLib.Variant("i", volume_percent))
        n.show()
    except Exception as e:
        print("Error showing system notification:", e)


def quit_app(tray_inst, popup=None):
    print("Exiting Audio Device Switcher...")
    if daemon:
        daemon.stop()
    if tray_inst:
        tray_inst.stop()
    if popup:
        popup.destroy()
    try:
        Notify.uninit()
    except Exception:
        pass
    sys.exit(0)


def update_ui_state():
    global tray, daemon, active_img, inactive_img, last_default_sink, last_default_source
    if not tray or not daemon:
        return

    tray.set_menu()

    if daemon.is_auto_switch_enabled():
        tray.set_icon(active_img)
    else:
        tray.set_icon(inactive_img)

    try:
        current_sink = daemon.get_default_sink()
        current_source = daemon.get_default_source()
        sink_desc, source_desc, output_label, vol_val = get_active_device_status(daemon)
        title, subtitle = get_tooltip_strings(daemon)

        tray.set_tooltip(title, subtitle)

        if last_default_sink is None:
            last_default_sink = current_sink
        if last_default_source is None:
            last_default_source = current_source

        if current_sink != last_default_sink:
            if not daemon.last_switch_was_manual:
                icon_name = (
                    "audio-headphones"
                    if "bluez" in current_sink or "headphone" in current_sink.lower()
                    else "audio-speakers"
                )
                GLib.idle_add(
                    lambda: show_native_notification(
                        "Audio Switcher",
                        f"Output changed to:\n{sink_desc}",
                        icon_name,
                    )
                )
            last_default_sink = current_sink

        if current_source != last_default_source:
            if not daemon.last_switch_was_manual:
                GLib.idle_add(
                    lambda: show_native_notification(
                        "Audio Switcher",
                        f"Input changed to:\n{source_desc}",
                        "audio-input-microphone",
                    )
                )
            last_default_source = current_source

    except Exception as e:
        print("Error in UI state update:", e)


def show_volume_notification(device_desc, volume_percent, is_muted):
    icon_name = (
        "audio-volume-muted"
        if is_muted
        else (
            "audio-headphones"
            if "headphone" in device_desc.lower() or "shokz" in device_desc.lower()
            else "audio-volume-high"
        )
    )
    body = f"{device_desc}\nVolume: {volume_percent}%"
    if is_muted:
        body = f"{device_desc}\nMuted"
    GLib.idle_add(
        lambda: show_native_notification(
            "Volume Adjusted",
            body,
            icon_name,
            volume_percent=volume_percent if not is_muted else 0,
        )
    )


def main():
    global daemon, tray, active_img, inactive_img
    print("Starting Audio Device Switcher Applet...")

    active_img = generate_speaker_icon(active=True)
    inactive_img = generate_speaker_icon(active=False)
    init_notify()

    daemon = AudioSwitcherDaemon(
        on_change_callback=update_ui_state,
        on_volume_change_callback=show_volume_notification,
    )
    daemon.start()

    tray = create_tray(daemon, active_img, inactive_img, quit_app)
    update_ui_state()

    try:
        tray.start()
    except KeyboardInterrupt:
        quit_app(tray)


if __name__ == "__main__":
    main()
