#!/usr/bin/env python3
import sys
import os
import subprocess

# Ensure we can load local GObject bindings for Wayland notifications
import gi
gi.require_version('Notify', '0.7')
from gi.repository import Notify, GLib
import time

# Ensure we can load local daemon module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from daemon import AudioSwitcherDaemon

def cycle_audio_devices():
    # Initialize daemon to reuse settings and queries
    daemon = AudioSwitcherDaemon()
    
    # 1. Fetch all connected sinks and filter out exclusions and physically unavailable devices
    sinks = daemon.query_sinks()
    excluded = daemon.get_excluded_devices()
    
    valid_sinks = []
    for s in sinks:
        name = s["name"]
        if name in excluded:
            continue
            
        # Check port availability. If a device (like unplugged headphones or disconnected HDMI)
        # has ports and ALL of them are "not available", we filter it out.
        ports = s.get("ports", [])
        if ports and all(p.get("availability") == "not available" for p in ports):
            continue
            
        valid_sinks.append(s)
    
    if not valid_sinks:
        print("No valid, active output devices available to cycle.")
        show_notification("Audio Switcher", "No active output devices available to cycle.", "dialog-warning")
        return
        
    # 2. Get current default sink name
    current_sink = daemon.get_default_sink()
    
    # 3. Find next sink in rotation (wrap-around)
    next_index = 0
    for idx, s in enumerate(valid_sinks):
        if s["name"] == current_sink:
            next_index = (idx + 1) % len(valid_sinks)
            break
            
    target_sink = valid_sinks[next_index]
    target_sink_name = target_sink["name"]
    target_sink_desc = target_sink.get("description", target_sink_name)
    
    # 4. Switch default output sink
    daemon.switch_default_sink(target_sink_name, manual=True)
    
    # 5. Smart Microphone (Source) Matching Heuristics
    sources = daemon.query_sources()
    valid_sources = []
    for src in sources:
        src_name = src["name"]
        if src_name in excluded:
            continue
            
        # Filter out loopback monitor sources
        if "monitor" in src_name.lower():
            continue
            
        # Check port availability, but bypass for Bluetooth sources (which might temporarily show not available in A2DP)
        ports = src.get("ports", [])
        if ports and "bluez" not in src_name.lower():
            if all(p.get("availability") == "not available" for p in ports):
                continue
        valid_sources.append(src)
    
    target_source_name = None
    target_source_desc = None
    
    # Heuristic A: Hardware Card Association
    sink_props = target_sink.get("properties", {})
    sink_card = sink_props.get("device.name")
    sink_name_lower = target_sink_name.lower()
    sink_desc_lower = target_sink_desc.lower()
    
    # Group candidate sources belonging to the same hardware card
    card_sources = []
    for src in valid_sources:
        src_props = src.get("properties", {})
        src_card = src_props.get("device.name")
        if sink_card and src_card == sink_card:
            card_sources.append(src)
            
    if card_sources:
        # A1: If target output is headphones/headset, prioritize headset/headphones/jack mic input
        if "headphone" in sink_name_lower or "headphone" in sink_desc_lower or "headset" in sink_name_lower or "headset" in sink_desc_lower:
            for src in card_sources:
                src_name_l = src["name"].lower()
                src_desc_l = src.get("description", "").lower()
                if "headset" in src_name_l or "headset" in src_desc_l or "headphone" in src_name_l or "headphone" in src_desc_l or "jack" in src_name_l or "jack" in src_desc_l:
                    target_source_name = src["name"]
                    break
        # A2: If target output is speaker/internal output, prioritize internal mic/mic inputs
        elif "speaker" in sink_name_lower or "speaker" in sink_desc_lower or "internal" in sink_name_lower or "internal" in sink_desc_lower:
            for src in card_sources:
                src_name_l = src["name"].lower()
                src_desc_l = src.get("description", "").lower()
                if ("mic" in src_name_l or "mic" in src_desc_l or "microphone" in src_name_l or "microphone" in src_desc_l) and "headset" not in src_name_l and "headset" not in src_desc_l:
                    target_source_name = src["name"]
                    break
                    
        # A3: Otherwise fallback to the first matching card source
        if not target_source_name:
            target_source_name = card_sources[0]["name"]
            
    # Heuristic B: Fallback Bluetooth MAC address matching
    if not target_source_name:
        mac_address = None
        if "bluez" in sink_name_lower:
            parts = sink_name_lower.split(".")
            for part in parts:
                if len(part) == 17 and part.count("_") == 5:
                    mac_address = part.replace("_", ":").lower()
                    break
                    
        if mac_address:
            # Scan for matching bluetooth input source
            for src in valid_sources:
                src_name_l = src["name"].lower().replace("_", ":")
                if mac_address in src_name_l:
                    target_source_name = src["name"]
                    break
                    
    # Heuristic C: Fallback to the first valid source if no match found
    if not target_source_name and valid_sources:
        target_source_name = valid_sources[0]["name"]
        
    if target_source_name:
        target_source_desc = next((s.get("description", target_source_name) for s in sources if s["name"] == target_source_name), target_source_name)
        daemon.switch_default_source(target_source_name, manual=True)

    # 6. Fire system notification
    notification_msg = f"Output: {target_sink_desc}"
    if target_source_desc:
        notification_msg += f"\nInput: {target_source_desc}"
        
    # Choose icon based on device type
    icon_name = "audio-headphones" if "bluez" in target_sink_name or "headphone" in target_sink_name.lower() else "audio-speakers"
    
    show_notification("Audio Device Switched", notification_msg, icon_name)
    print(f"Cycled default devices to: Output: {target_sink_desc} | Input: {target_source_desc}")

def show_notification(title, message, icon):
    """Fires a desktop notification via native GObject Notify."""
    try:
        Notify.init("Audio Device Switcher")
        # Creating a fresh notification object every time ensures Wayland/COSMIC renders it immediately
        n = Notify.Notification.new(title, message, icon)
        n.set_hint("desktop-entry", GLib.Variant("s", "audio-device-switcher"))
        n.show()
        # Sleep for a moment to allow the D-Bus system to fully display the popup banner before the script exits
        time.sleep(0.5)
    except Exception as e:
        print("Failed to display notification:", e)

if __name__ == '__main__':
    cycle_audio_devices()
