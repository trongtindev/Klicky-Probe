#!/usr/bin/env bash
# Install klicky_probe into Klipper's extras directory.
# Usage: ./install.sh [KLIPPER_PATH]
# Env:   KLIPPER_PATH (default: ~/klipper)
set -euo pipefail

SRCDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KLIPPER_PATH="${1:-${KLIPPER_PATH:-$HOME/klipper}}"
EXTRAS_PATH="${KLIPPER_PATH}/klippy/extras"
TARGET="${EXTRAS_PATH}/klicky_probe"

if [[ ! -d "${EXTRAS_PATH}" ]]; then
  echo "Error: Klipper extras not found at ${EXTRAS_PATH}"
  echo "Set KLIPPER_PATH or pass the path as the first argument:"
  echo "  KLIPPER_PATH=/path/to/klipper ./plugin/install.sh"
  echo "  ./plugin/install.sh /path/to/klipper"
  exit 1
fi

# Remove previous install (symlink or directory)
if [[ -L "${TARGET}" || -d "${TARGET}" || -f "${TARGET}" ]]; then
  rm -rf "${TARGET}"
fi

# Prefer symlink for easy updates
ln -s "${SRCDIR}/klicky_probe" "${TARGET}"
echo "Installed: ${TARGET} -> ${SRCDIR}/klicky_probe"

# Restart Klipper if systemd unit exists
if command -v systemctl >/dev/null 2>&1; then
  if systemctl is-active --quiet klipper 2>/dev/null; then
    echo "Restarting klipper..."
    sudo systemctl restart klipper || systemctl restart klipper || true
  fi
fi

echo "Done. Add [klicky_probe] to printer.cfg (see config/sample-klicky.cfg)."
