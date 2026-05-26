import subprocess
import json
import os
import time
import threading
from datetime import datetime

SETTINGS_FILE = os.path.expanduser("~/audio-device-switcher-settings.json")

class AudioSwitcherDaemon:
    def __init__(self, on_change_callback=None, on_volume_change_callback=None):
        self.lock = threading.Lock()
        self.on_change_callback = on_change_callback
        self.on_volume_change_callback = on_volume_change_callback
        
        # Load settings
        self.settings = self.load_settings()
        
        # Keep track of known devices to detect new connections
        self.known_sinks = set()
        self.known_sources = set()
        
        # Volume caching to track shifts
        self.last_volume = None
        self.last_mute = None
        self.last_default_sink_name = None
        self.last_default_source_name = None
        self.last_switch_was_manual = True
        
        # History log (in-memory, last 20 events)
        self.history = []
        
        # Daemon running flag
        self.running = False
        self.listener_thread = None
        
        # Pre-populate known devices
        self.scan_devices(initial=True)

    def load_settings(self):
        """Loads user settings from file or creates defaults."""
        defaults = {
            "auto_switch": True,
            "excluded_devices": []
        }
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    loaded = json.load(f)
                    # Merge to ensure all keys exist
                    defaults.update(loaded)
                    return defaults
            except Exception as e:
                self.add_history(f"Error loading settings: {e}")
        return defaults

    def save_settings(self):
        """Saves current settings to disk thread-safely."""
        with self.lock:
            try:
                with open(SETTINGS_FILE, 'w') as f:
                    json.dump(self.settings, f, indent=4)
            except Exception as e:
                self.add_history(f"Error saving settings: {e}")

    def add_history(self, message):
        """Adds an event to the history log with a timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}"
        print(entry)  # Log to stdout/journal
        with self.lock:
            self.history.insert(0, entry)
            # Cap history at 20 entries
            if len(self.history) > 20:
                self.history = self.history[:20]

    def get_history(self):
        with self.lock:
            return list(self.history)

    def set_auto_switch(self, enabled):
        """Enables or disables auto-switching."""
        with self.lock:
            self.settings["auto_switch"] = enabled
        self.save_settings()
        status_str = "ENABLED" if enabled else "DISABLED"
        self.add_history(f"Automatic switching {status_str}")
        if self.on_change_callback:
            self.on_change_callback()

    def is_auto_switch_enabled(self):
        with self.lock:
            return self.settings["auto_switch"]

    def toggle_exclusion(self, device_name):
        """Toggles exclusion status for a device."""
        with self.lock:
            excluded = self.settings["excluded_devices"]
            if device_name in excluded:
                excluded.remove(device_name)
                state = "included"
            else:
                excluded.append(device_name)
                state = "excluded"
        self.save_settings()
        self.add_history(f"Device '{device_name}' is now {state}")
        if self.on_change_callback:
            self.on_change_callback()

    def is_excluded(self, device_name):
        with self.lock:
            return device_name in self.settings["excluded_devices"]

    def get_excluded_devices(self):
        with self.lock:
            return list(self.settings["excluded_devices"])

    def run_cmd(self, args):
        """Helper to run a shell command and return stdout."""
        try:
            result = subprocess.run(args, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            # Don't raise, return empty/error to keep daemon running
            return ""

    def query_sinks(self):
        """Queries connected sinks in JSON format."""
        out = self.run_cmd(["pactl", "-f", "json", "list", "sinks"])
        if not out:
            return []
        try:
            return json.loads(out)
        except Exception:
            # In some rare cases list output might be empty or single dict
            return []

    def query_sources(self):
        """Queries connected sources in JSON format."""
        out = self.run_cmd(["pactl", "-f", "json", "list", "sources"])
        if not out:
            return []
        try:
            return json.loads(out)
        except Exception:
            return []

    def query_sink_inputs(self):
        """Queries active audio playback streams (sink inputs)."""
        out = self.run_cmd(["pactl", "-f", "json", "list", "sink-inputs"])
        if not out:
            return []
        try:
            data = json.loads(out)
            # If there's only one stream, pactl sometimes outputs a single dict instead of a list
            if isinstance(data, dict):
                return [data]
            return data
        except Exception:
            return []

    def query_source_outputs(self):
        """Queries active audio recording streams (source outputs)."""
        out = self.run_cmd(["pactl", "-f", "json", "list", "source-outputs"])
        if not out:
            return []
        try:
            data = json.loads(out)
            if isinstance(data, dict):
                return [data]
            return data
        except Exception:
            return []

    def get_default_sink(self):
        return self.run_cmd(["pactl", "get-default-sink"])

    def get_default_source(self):
        return self.run_cmd(["pactl", "get-default-source"])

    def switch_default_sink(self, sink_name, manual=True):
        """Manually switches the default audio output sink."""
        self.last_switch_was_manual = manual
        self.run_cmd(["pactl", "set-default-sink", sink_name])
        # Move active streams
        inputs = self.query_sink_inputs()
        moved_count = 0
        for stream in inputs:
            stream_idx = stream.get("index")
            if stream_idx is not None:
                self.run_cmd(["pactl", "move-sink-input", str(stream_idx), sink_name])
                moved_count += 1
        
        mode = "Manual" if manual else "Automatic"
        self.add_history(f"{mode} switch output to: {sink_name} (moved {moved_count} streams)")
        if self.on_change_callback:
            self.on_change_callback()

    def switch_default_source(self, source_name, manual=True):
        """Manually switches the default audio input source."""
        self.last_switch_was_manual = manual
        self.run_cmd(["pactl", "set-default-source", source_name])
        # Move recording streams
        outputs = self.query_source_outputs()
        moved_count = 0
        for stream in outputs:
            stream_idx = stream.get("index")
            if stream_idx is not None:
                self.run_cmd(["pactl", "move-source-output", str(stream_idx), source_name])
                moved_count += 1

        mode = "Manual" if manual else "Automatic"
        self.add_history(f"{mode} switch input to: {source_name} (moved {moved_count} streams)")
        if self.on_change_callback:
            self.on_change_callback()

    def scan_devices(self, initial=False):
        """
        Scans sinks and sources, compares against cache to identify newly connected devices,
        and automatically routes default audio if auto-switching is enabled.
        """
        self.last_switch_was_manual = True
        sinks = self.query_sinks()
        sources = self.query_sources()
        
        # Populate our name-to-description caches
        self.sink_descriptions = {s["name"]: s.get("description", s["name"]) for s in sinks}
        self.source_descriptions = {s["name"]: s.get("description", s["name"]) for s in sources}
        
        # Volume change detection
        try:
            default_sink = self.get_default_sink()
            self.last_default_sink_name = default_sink
            
            default_source = self.get_default_source()
            self.last_default_source_name = default_source
            
            current_volume = None
            current_mute = False
            
            for s in sinks:
                if s["name"] == default_sink:
                    vol_dict = s.get("volume", {})
                    if vol_dict:
                        first_channel = list(vol_dict.values())[0]
                        vol_percent_str = first_channel.get("value_percent", "0%")
                        try:
                            current_volume = int(vol_percent_str.strip("%"))
                        except ValueError:
                            current_volume = 0
                    current_mute = s.get("mute", False)
                    break
                    
            if current_volume is not None:
                if not initial and self.on_volume_change_callback:
                    if self.last_volume is not None and (current_volume != self.last_volume or current_mute != self.last_mute):
                        sink_desc = self.sink_descriptions.get(default_sink, default_sink)
                        self.on_volume_change_callback(sink_desc, current_volume, current_mute)
                self.last_volume = current_volume
                self.last_mute = current_mute
        except Exception as e:
            print("Error in volume check:", e)
        
        current_sink_names = {s["name"] for s in sinks}
        current_source_names = {s["name"] for s in sources}
        
        if initial:
            self.known_sinks = current_sink_names
            self.known_sources = current_source_names
            self.add_history("Daemon initialized. Monitoring active devices...")
            return False

        # Identify newly connected sinks
        new_sinks = current_sink_names - self.known_sinks
        new_sources = current_source_names - self.known_sources
        
        # Identify disconnected devices to clean cache
        removed_sinks = self.known_sinks - current_sink_names
        removed_sources = self.known_sources - current_source_names

        for name in removed_sinks:
            # Find description for log
            desc = next((s["description"] for s in sinks if s["name"] == name), name)
            self.add_history(f"Disconnected output: {desc}")

        for name in removed_sources:
            desc = next((s["description"] for s in sources if s["name"] == name), name)
            self.add_history(f"Disconnected input: {desc}")

        # Update cache first so we don't repeatedly trigger on them
        self.known_sinks = current_sink_names
        self.known_sources = current_source_names

        triggered = False

        # Handle newly connected sinks
        for sink_name in new_sinks:
            # Find description
            sink_desc = next((s.get("description", sink_name) for s in sinks if s["name"] == sink_name), sink_name)
            self.add_history(f"Detected connection of output: {sink_desc}")
            
            # Check if auto_switch is enabled and device not excluded
            auto = self.is_auto_switch_enabled()
            excl = self.is_excluded(sink_name)
            
            if auto and not excl:
                self.add_history(f"Auto-switching default output to: {sink_desc}")
                self.switch_default_sink(sink_name, manual=False)
                triggered = True
            else:
                reason = "Excluded" if excl else "Auto-Switch Disabled"
                self.add_history(f"Skipping auto-switch for output: {sink_desc} ({reason})")

        # Handle newly connected sources
        for source_name in new_sources:
            source_desc = next((s.get("description", source_name) for s in sources if s["name"] == source_name), source_name)
            self.add_history(f"Detected connection of input: {source_desc}")
            
            auto = self.is_auto_switch_enabled()
            excl = self.is_excluded(source_name)
            
            if auto and not excl:
                self.add_history(f"Auto-switching default input to: {source_desc}")
                self.switch_default_source(source_name, manual=False)
                triggered = True
            else:
                reason = "Excluded" if excl else "Auto-Switch Disabled"
                self.add_history(f"Skipping auto-switch for input: {source_desc} ({reason})")

        return triggered

    def check_volume_and_defaults(self):
        """
        Lightweight check run on volume key events or default changes. 
        Avoids full card/device scans and menu rebuilds, preventing desktop lag.
        """
        try:
            current_sink = self.get_default_sink()
            current_source = self.get_default_source()
            
            defaults_changed = False
            if self.last_default_sink_name is not None and current_sink != self.last_default_sink_name:
                defaults_changed = True
            if self.last_default_source_name is not None and current_source != self.last_default_source_name:
                defaults_changed = True
                
            self.last_default_sink_name = current_sink
            self.last_default_source_name = current_source
            
            if defaults_changed:
                # Trigger a menu checkmark shift by running a full scan first to update descriptions
                self.scan_devices()
                if self.on_change_callback:
                    self.on_change_callback()
                return
                    
            # Check volume changes for active output using symbolic target (super fast, <2ms)
            vol_out = self.run_cmd(["pactl", "get-sink-volume", "@DEFAULT_SINK@"])
            current_volume = None
            pct_idx = vol_out.find("%")
            if pct_idx != -1:
                start_idx = vol_out.rfind("/", 0, pct_idx)
                if start_idx != -1:
                    try:
                        current_volume = int(vol_out[start_idx+1:pct_idx].strip())
                    except ValueError:
                        current_volume = 0
                        
            mute_out = self.run_cmd(["pactl", "get-sink-mute", "@DEFAULT_SINK@"]).lower()
            current_mute = "yes" in mute_out
            
            if current_volume is not None:
                if self.last_volume is not None and (current_volume != self.last_volume or current_mute != self.last_mute):
                    if self.on_volume_change_callback:
                        # Use cached description mapping to resolve name instantly without subprocesses
                        sink_desc = getattr(self, "sink_descriptions", {}).get(current_sink, current_sink)
                        self.on_volume_change_callback(sink_desc, current_volume, current_mute)
                self.last_volume = current_volume
                self.last_mute = current_mute
                
        except Exception as e:
            print("Error checking volume and defaults:", e)

    def start(self):
        """Starts the background PipeWire/PulseAudio event subscriber daemon."""
        if self.running:
            return
        
        self.running = True
        self.listener_thread = threading.Thread(target=self._listener_loop, daemon=True)
        self.listener_thread.start()
        self.add_history("Event listener thread started.")

    def stop(self):
        """Stops the daemon."""
        self.running = False
        self.add_history("Daemon shutting down.")

    def _listener_loop(self):
        """Runs the pactl subscribe process and parses events."""
        # Use a debouncing mechanism: when we receive events, wait a split second
        # and consume any queued events so we only run ONE scan for a burst of events
        # (e.g. connecting a Bluetooth headset triggers several card/sink/source events at once)
        
        cmd = ["pactl", "subscribe"]
        process = None
        
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.add_history("Listening to system audio events...")
            
            # Non-blocking event trigger
            last_event_time = 0
            debounce_delay = 0.25 # seconds
            
            while self.running:
                # Read stdout line-by-line
                line = process.stdout.readline()
                if not line:
                    break
                
                # Check if it's an event we care about
                line_lower = line.lower()
                if any(x in line_lower for x in ["sink", "source", "card", "server"]):
                    # If a hardware device was connected or disconnected (new/remove)
                    # or server/card settings changed (e.g., default sink changed in panel):
                    # do a full scan & rebuild menu!
                    if "new" in line_lower or "remove" in line_lower or "card" in line_lower or "server" in line_lower:
                        now = time.time()
                        if now - last_event_time > debounce_delay:
                            last_event_time = now
                            # Wait a tiny moment for PipeWire to finalize registration
                            time.sleep(debounce_delay)
                            self.scan_devices()
                            
                            # Trigger UI update
                            if self.on_change_callback:
                                self.on_change_callback()
                    # If it's just a change event on a sink/source (volume key adjusted or default changed)
                    # run a highly optimized, light volume scan to prevent desktop lag!
                    elif "change" in line_lower:
                        self.check_volume_and_defaults()
                            
        except Exception as e:
            self.add_history(f"Exception in event loop: {e}")
        finally:
            if process:
                process.terminate()
                process.wait()
            self.running = False
            self.add_history("Listener thread stopped.")

if __name__ == '__main__':
    # Local quick-test run
    print("Testing AudioSwitcherDaemon...")
    daemon = AudioSwitcherDaemon()
    daemon.start()
    
    try:
        # Keep main thread alive for a few seconds to verify
        for _ in range(5):
            time.sleep(1)
            print("Sinks:", [s["description"] for s in daemon.query_sinks()])
            print("Default Sink:", daemon.get_default_sink())
    except KeyboardInterrupt:
        pass
    finally:
        daemon.stop()
