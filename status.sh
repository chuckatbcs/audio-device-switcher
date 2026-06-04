#!/bin/bash
# Quick health check for Audio Device Switcher install and running state.

set -euo pipefail

APP_NAME="audio-device-switcher"
DEPLOY_DIR="${HOME}/.local/share/${APP_NAME}"
AUTOSTART_FILE="${HOME}/.config/autostart/${APP_NAME}.desktop"
SETTINGS_FILE="${HOME}/audio-device-switcher-settings.json"
WORKSPACE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "================================================"
echo "Audio Device Switcher — status"
echo "================================================"
echo "Host:     $(hostname)"
echo "User:     ${USER} (${HOME})"
echo "Workspace: ${WORKSPACE_DIR}"
echo

echo "--- Process ---"
APPL_PROC=$(pgrep -f "${DEPLOY_DIR}/.venv/bin/python ${DEPLOY_DIR}/applet.py" 2>/dev/null || true)
if [ -n "$APPL_PROC" ]; then
    ps -p "$APPL_PROC" -o pid,cmd= 2>/dev/null || echo "PID $APPL_PROC"
    echo "✓ Applet process running"
else
    echo "✗ No applet.py process found"
fi
echo

echo "--- Install layout (install.sh targets) ---"
for path in "$DEPLOY_DIR" "$AUTOSTART_FILE" "${HOME}/.local/bin/audio-device-switcher" "${HOME}/.local/bin/audio-device-cycle" "$SETTINGS_FILE"; do
    if [ -e "$path" ]; then
        echo "✓ $path"
    else
        echo "✗ $path (missing)"
    fi
done
echo

echo "--- Deployed vs workspace applet.py ---"
if [ -f "${DEPLOY_DIR}/applet.py" ] && [ -f "${WORKSPACE_DIR}/applet.py" ]; then
    if diff -q "${DEPLOY_DIR}/applet.py" "${WORKSPACE_DIR}/applet.py" >/dev/null 2>&1; then
        echo "✓ Deployed applet.py matches workspace"
    else
        echo "✗ Deployed applet.py differs from workspace"
        diff -u "${DEPLOY_DIR}/applet.py" "${WORKSPACE_DIR}/applet.py" | head -40 || true
    fi
elif [ -f "${WORKSPACE_DIR}/applet.py" ]; then
    echo "✗ No deployed applet.py (workspace copy exists)"
else
    echo "✗ No applet.py in workspace or deploy dir"
fi
echo

echo "--- Tray menu header feature (get_active_device_status) ---"
for f in "${DEPLOY_DIR}/applet.py" "${WORKSPACE_DIR}/applet.py"; do
    if [ -f "$f" ]; then
        if grep -q "get_active_device_status" "$f"; then
            echo "✓ Present in $f"
        else
            echo "✗ Missing in $f"
        fi
    fi
done
echo

echo "--- Dependencies ---"
for cmd in python3 pactl; do
    if command -v "$cmd" >/dev/null 2>&1; then
        echo "✓ $cmd ($(command -v "$cmd"))"
    else
        echo "✗ $cmd not found"
    fi
done
python3 -c "import gi; gi.require_version('Gtk','3.0'); from gi.repository import Gtk; print('✓ python3-gi / Gtk')" 2>/dev/null || echo "✗ python3-gi or Gtk unavailable"
python3 -c "import gi; gi.require_version('Notify','0.7')" 2>/dev/null && echo "✓ gir1.2-notify-0.7" || echo "✗ gir1.2-notify-0.7 not available"
if python3 -c "import gi; gi.require_version('AyatanaAppIndicator3','0.1')" 2>/dev/null; then
    echo "✓ AyatanaAppIndicator3"
elif python3 -c "import gi; gi.require_version('AppIndicator3','0.1')" 2>/dev/null; then
    echo "✓ AppIndicator3"
else
    echo "✗ AppIndicator typelib not available"
fi
if [ -x "${DEPLOY_DIR}/.venv/bin/python" ]; then
    "${DEPLOY_DIR}/.venv/bin/python" -c "import pystray, PIL; print('✓ venv: pystray, pillow')" 2>/dev/null || echo "✗ venv missing pystray/pillow"
elif [ -x "${WORKSPACE_DIR}/.venv/bin/python" ]; then
    "${WORKSPACE_DIR}/.venv/bin/python" -c "import pystray, PIL; print('✓ workspace venv: pystray, pillow')" 2>/dev/null || echo "✗ workspace venv missing pystray/pillow"
else
    echo "✗ No project venv found"
fi
echo

echo "--- Git (workspace) ---"
if git -C "$WORKSPACE_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git -C "$WORKSPACE_DIR" log -1 --oneline
    git -C "$WORKSPACE_DIR" status -sb
else
    echo "(not a git repo)"
fi
echo "================================================"
