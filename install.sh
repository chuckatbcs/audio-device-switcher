#!/bin/bash
# Audio Device Switcher - Installer and Packager Script
# Installs the system tray applet cleanly in user-space with autostart support.

set -e

# Configuration
APP_NAME="audio-device-switcher"
DEPLOY_DIR="$HOME/.local/share/$APP_NAME"
AUTOSTART_DIR="$HOME/.config/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/$APP_NAME.desktop"

# Tray applet needs system PyGObject/GTK typelibs — not Conda's python3 on PATH.
if [ -x /usr/bin/python3 ]; then
    PYTHON3=/usr/bin/python3
elif command -v python3 &>/dev/null; then
    PYTHON3=$(command -v python3)
    echo "WARNING: Using $PYTHON3 — if dependency checks fail, run: conda deactivate"
else
    PYTHON3=""
fi

echo "================================================"
echo "Installing Audio Device Switcher Tray Applet..."
echo "================================================"
echo "Python: ${PYTHON3:-not found}"

# 1. Dependency Checks
echo "[1/6] Checking system dependencies..."
MISSING_DEPS=0

if [ -z "$PYTHON3" ]; then
    echo "ERROR: python3 is not installed."
    MISSING_DEPS=1
fi

if ! command -v pactl &>/dev/null; then
    echo "ERROR: pactl (pulseaudio-utils) is not installed. This is required to monitor audio devices."
    MISSING_DEPS=1
fi

# Check for python3-venv by trying to run venv module
if ! "$PYTHON3" -c "import venv" &>/dev/null; then
    echo "ERROR: python3-venv is not installed."
    echo "Please install it by running: sudo apt install python3-venv"
    MISSING_DEPS=1
fi

# Check for python3-gi (PyGObject) which is standard on Pop!_OS
if ! "$PYTHON3" -c "import gi" &>/dev/null; then
    echo "ERROR: python3-gi (PyGObject) is not installed."
    echo "Install system packages (Conda python cannot use apt GI bindings):"
    echo "  sudo apt install python3-gi python3-venv gir1.2-notify-0.7 gir1.2-ayatanaappindicator3-0.1"
    MISSING_DEPS=1
fi

if ! "$PYTHON3" -c "import gi; gi.require_version('Notify', '0.7')" &>/dev/null; then
    echo "ERROR: gir1.2-notify-0.7 is not installed (required for desktop notifications)."
    echo "Please install it by running: sudo apt install gir1.2-notify-0.7"
    MISSING_DEPS=1
fi

if ! "$PYTHON3" -c "import dbus" &>/dev/null; then
    echo "ERROR: python3-dbus is not installed (required for native tray tooltips)."
    echo "Please install it by running: sudo apt install python3-dbus"
    MISSING_DEPS=1
fi

if ! "$PYTHON3" -c "import gi; gi.require_version('DbusmenuGtk3', '0.4')" &>/dev/null; then
    echo "NOTICE: gir1.2-dbusmenu-gtk3-0.4 not found — native SNI tray will fall back to AppIndicator."
    echo "Install for best hover support: sudo apt install gir1.2-dbusmenu-gtk3-0.4"
fi

if [ $MISSING_DEPS -eq 1 ]; then
    echo "Installation aborted due to missing dependencies."
    exit 1
fi
echo "✓ System core dependencies verified."

# 2. Check and install native Wayland AppIndicator support for GObject Introspection
# This ensures pystray can load '_appindicator' which sends standard SNI DBus messages
# directly to the Wayland-native COSMIC Notification Tray.
echo "Checking for native Wayland AppIndicator libraries..."
HAS_APPIND=0
if "$PYTHON3" -c "import gi; gi.require_version('AyatanaAppIndicator3', '0.1')" &>/dev/null; then
    HAS_APPIND=1
elif "$PYTHON3" -c "import gi; gi.require_version('AppIndicator3', '0.1')" &>/dev/null; then
    HAS_APPIND=1
fi

if [ $HAS_APPIND -eq 0 ]; then
    echo "Notice: Native Wayland AppIndicator GObject typelib libraries are missing."
    echo "This is required to render status icons natively in COSMIC's Notification Tray on Wayland."
    echo "Installing gir1.2-ayatanaappindicator3-0.1 via apt (requires sudo)..."
    
    # Run apt-get with sudo. If running inside an interactive user terminal,
    # the user will be prompted for their password.
    sudo apt-get update
    sudo apt-get install -y gir1.2-ayatanaappindicator3-0.1 || {
        echo "WARNING: Failed to install Ayatana AppIndicator package."
        echo "The applet will attempt to fall back to standard GTK, which may be invisible on Wayland."
    }
else
    echo "✓ Native Wayland AppIndicator support is already available."
fi

# 3. Workspace Setup
echo "[2/6] Setting up deployment directory at $DEPLOY_DIR..."
mkdir -p "$DEPLOY_DIR"

# 4. Copy Application Files
echo "[3/6] Deploying application scripts..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"

cp "$SCRIPT_DIR/applet.py" "$DEPLOY_DIR/"
cp "$SCRIPT_DIR/daemon.py" "$DEPLOY_DIR/"
cp "$SCRIPT_DIR/icon_generator.py" "$DEPLOY_DIR/"
cp "$SCRIPT_DIR/cycle.py" "$DEPLOY_DIR/"
for mod in audio_state.py menu_builder.py gtk_tray.py sni_tray.py sni_tooltip.py status_popup.py pystray_tray.py tray_factory.py panel_hover.py tray_popup.py menu_open_detector.py tray_log.py; do
    cp "$SCRIPT_DIR/$mod" "$DEPLOY_DIR/"
done

# If settings.json exists locally, copy it, otherwise daemon will generate it
if [ -f "$SCRIPT_DIR/settings.json" ]; then
    cp "$SCRIPT_DIR/settings.json" "$DEPLOY_DIR/"
fi

chmod +x "$DEPLOY_DIR/applet.py"
echo "✓ Scripts deployed successfully."

# 5. Virtual Environment Configuration
echo "[4/6] Creating isolated sandboxed environment with system package links..."
# Create a venv that can access the host system's GObject/GTK/AppIndicator libraries (essential for Wayland compatibility)
"$PYTHON3" -m venv --system-site-packages "$DEPLOY_DIR/.venv"
echo "✓ Virtual environment created."

# 6. Dependency Installation
echo "[5/6] Installing Python package dependencies (pystray, pillow)..."
# Using the venv's pip ensures we stay safe from PEP 668 external environment blocks
"$DEPLOY_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$DEPLOY_DIR/.venv/bin/pip" install --quiet pystray pillow
echo "✓ Python dependencies installed."

# 7. Autostart & Application Menu Registration
echo "[6/6] Configuring XDG Autostart and Application Menu..."
mkdir -p "$AUTOSTART_DIR"
mkdir -p "$HOME/.local/share/applications"
mkdir -p "$HOME/.local/bin"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Audio Device Switcher
Comment=Automatically switch default audio to the newest connected device
Exec=$DEPLOY_DIR/.venv/bin/python $DEPLOY_DIR/applet.py
Icon=audio-headphones
Terminal=false
Categories=Utility;Audio;
X-GNOME-Autostart-enabled=true
EOF

chmod +x "$DESKTOP_FILE"

# Copy to applications directory so it shows up in COSMIC / Gnome launcher!
cp "$DESKTOP_FILE" "$HOME/.local/share/applications/audio-device-switcher.desktop"

# Create a command-line wrapper in ~/.local/bin for quick terminal launching
cat > "$HOME/.local/bin/audio-device-switcher" <<LAUNCHER
#!/bin/bash
# Terminal wrapper to start Audio Device Switcher cleanly
nohup $DEPLOY_DIR/.venv/bin/python $DEPLOY_DIR/applet.py >/dev/null 2>&1 &
echo "Audio Device Switcher started in the background."
LAUNCHER

chmod +x "$HOME/.local/bin/audio-device-switcher"

# Create a command-line cycling wrapper in ~/.local/bin
cat > "$HOME/.local/bin/audio-device-cycle" <<LAUNCHER
#!/bin/bash
# Terminal wrapper to cycle default output and input devices
$DEPLOY_DIR/.venv/bin/python $DEPLOY_DIR/cycle.py
LAUNCHER

chmod +x "$HOME/.local/bin/audio-device-cycle"

echo "✓ Autostart registered at $DESKTOP_FILE"
echo "✓ Registered in Application Menu launcher."
echo "✓ CLI Command 'audio-device-switcher' registered in ~/.local/bin/"
echo "✓ CLI Command 'audio-device-cycle' registered in ~/.local/bin/"

# 7.5. Automated Keyboard Shortcut Configuration (Super + Z / Windows + Z)
echo "Registering global keyboard shortcut (Super + Z) to cycle audio devices..."
"$PYTHON3" -c '
import os, subprocess
home_dir = os.path.expanduser("~")
target_cmd = os.path.join(home_dir, ".local/bin/audio-device-cycle")

# 1. COSMIC Shortcut Registration
try:
    config_dir = os.path.join(home_dir, ".config/cosmic/com.system76.CosmicSettings.Shortcuts/v1")
    config_file = os.path.join(config_dir, "custom")
    shortcut_entry = f"""    (
        modifiers: [
            Super,
        ],
        key: "z",
        description: Some("Cycle Audio Devices"),
    ): Spawn("{target_cmd}"),"""

    os.makedirs(config_dir, exist_ok=True)
    if not os.path.exists(config_file):
        with open(config_file, "w") as f:
            f.write("{\n" + shortcut_entry + "\n}\n")
        print("✓ Created COSMIC custom shortcut configuration (Super + Z).")
    else:
        with open(config_file, "r") as f:
            content = f.read().strip()
        if "Cycle Audio Devices" in content or "audio-device-cycle" in content:
            print("✓ Shortcut already registered in COSMIC settings.")
        else:
            if content.startswith("{") and content.endswith("}"):
                inner_content = content[1:-1].strip()
                if inner_content:
                    if not inner_content.endswith(","):
                        inner_content += ","
                    new_content = "{\n" + inner_content + "\n" + shortcut_entry + "\n}\n"
                else:
                    new_content = "{\n" + shortcut_entry + "\n}\n"
                with open(config_file, "w") as f:
                    f.write(new_content)
                print("✓ Appended shortcut to COSMIC custom shortcuts (Super + Z).")
except Exception as e:
    print("COSMIC shortcut registration skipped or failed:", e)

# 2. GNOME Shortcut Registration (as robust fallback)
try:
    if subprocess.run(["which", "gsettings"], capture_output=True).returncode == 0:
        out = subprocess.run(["gsettings", "get", "org.gnome.settings-daemon.plugins.media-keys", "custom-keybindings"], capture_output=True, text=True).stdout.strip()
        import ast
        if out.startswith("@as"):
            bindings = []
        else:
            bindings = ast.literal_eval(out)
            
        my_path = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom-audio-cycle/"
        if my_path not in bindings:
            bindings.append(my_path)
            bindings_str = str(bindings).replace(" ", "")
            subprocess.run(["gsettings", "set", "org.gnome.settings-daemon.plugins.media-keys", "custom-keybindings", bindings_str], check=True)
            
        subprocess.run(["gsettings", "set", "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:" + my_path, "name", "Cycle Audio Devices"], check=True)
        subprocess.run(["gsettings", "set", "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:" + my_path, "command", target_cmd], check=True)
        subprocess.run(["gsettings", "set", "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:" + my_path, "binding", "<Super>z"], check=True)
        print("✓ Registered custom shortcut in GNOME settings (Super + Z).")
except Exception as e:
    pass
'

# 8. Start Immediately
echo "------------------------------------------------"
echo "Finalizing installation..."

# Kill any existing running instances of the applet to prevent double indicators
echo "Stopping any existing instances..."
pkill -f "$DEPLOY_DIR/applet.py" || true
pkill -f "audio-device-switcher/applet.py" || true
sleep 0.5

echo "Starting Audio Device Switcher Applet in the background..."
# Run the applet in the background, fully detached
nohup "$DEPLOY_DIR/.venv/bin/python" "$DEPLOY_DIR/applet.py" >/dev/null 2>&1 &

echo "================================================"
echo "SUCCESS: Audio Device Switcher has been installed!"
echo "------------------------------------------------"
echo "The system tray applet is now running on your panel."
echo "It will automatically load at every login."
echo "================================================"
