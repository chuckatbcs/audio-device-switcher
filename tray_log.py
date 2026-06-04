"""Lightweight file logging for tray backend diagnostics."""

import os
from datetime import datetime

LOG_PATH = os.path.expanduser("~/.local/share/audio-device-switcher/tray.log")


def tray_log(message):
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_PATH, "a", encoding="utf-8") as handle:
            handle.write(f"[{stamp}] {message}\n")
    except Exception:
        pass
    print(message)
