#!/bin/bash
# Pull latest code, reinstall to ~/.local/share, and print status.
# Usage: ./update.sh [git-ref]
# Example: ./update.sh cursor/tray-active-device-status-b1e7

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REF="${1:-cursor/tray-active-device-status-b1e7}"

cd "$SCRIPT_DIR"

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "Fetching and pulling ${REF}..."
    git fetch origin "$REF"
    git pull origin "$REF"
else
    echo "ERROR: Not a git repository. Clone the project first."
    exit 1
fi

echo
echo "Before install:"
"$SCRIPT_DIR/status.sh" || true

echo
echo "Running install.sh..."
"$SCRIPT_DIR/install.sh"

echo
echo "After install:"
"$SCRIPT_DIR/status.sh"
