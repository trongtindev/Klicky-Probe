#!/usr/bin/env bash
# Install klicky_probe into Klipper's extras directory.
# Usage: ./install.sh [KLIPPER_PATH]
# Env:   KLIPPER_PATH (default: ~/klipper)
set -euo pipefail

# ---------------------------------------------------------------------------
# Colors (only when stdout is a TTY)
# ---------------------------------------------------------------------------
if [[ -t 1 ]]; then
  C_RESET='\033[0m'
  C_BOLD='\033[1m'
  C_DIM='\033[2m'
  C_GREEN='\033[32m'
  C_YELLOW='\033[33m'
  C_RED='\033[31m'
  C_CYAN='\033[36m'
  C_MAGENTA='\033[35m'
else
  C_RESET='' C_BOLD='' C_DIM='' C_GREEN='' C_YELLOW='' C_RED='' C_CYAN='' C_MAGENTA=''
fi

ok()   { echo -e "${C_GREEN}${C_BOLD}  [OK]${C_RESET}  $*"; }
info() { echo -e "${C_CYAN}  [..]${C_RESET}  $*"; }
warn() { echo -e "${C_YELLOW}${C_BOLD}  [!!]${C_RESET}  $*"; }
err()  { echo -e "${C_RED}${C_BOLD}  [ERR]${C_RESET} $*" >&2; }
mode() { echo -e "${C_MAGENTA}${C_BOLD}  [>>]${C_RESET}  $*"; }

print_header() {
  local mode_label="$1"
  echo ""
  echo -e "${C_CYAN}${C_BOLD}"
  cat <<'EOF'
  ============================================================
                    K L I C K Y   P R O B E
                         Installer
  ============================================================
EOF
  echo -e "${C_RESET}"
  mode "Mode: ${mode_label}"
  echo ""
}

print_success() {
  local install_mode="$1"   # new | upgrade
  local target="$2"
  local src="$3"
  local restart_status="$4" # ok | warn
  local restart_msg="$5"
  local prev_detail="${6:-}"

  local title
  if [[ "${install_mode}" == "upgrade" ]]; then
    title="     [OK]  SUCCESS  ·  klicky_probe upgraded successfully"
  else
    title="     [OK]  SUCCESS  ·  klicky_probe installed successfully"
  fi

  echo ""
  echo -e "${C_GREEN}${C_BOLD}"
  echo "  ============================================================"
  echo "${title}"
  echo "  ============================================================"
  echo -e "${C_RESET}"

  if [[ "${install_mode}" == "upgrade" ]]; then
    ok "Mode:     UPGRADE (replaced previous install)"
    [[ -n "${prev_detail}" ]] && info "Previous: ${prev_detail}"
  else
    ok "Mode:     NEW INSTALL"
  fi
  ok "Symlink:  ${target}"
  ok "Source:   ${src}"
  if [[ "${restart_status}" == "ok" ]]; then
    ok "${restart_msg}"
  else
    warn "${restart_msg}"
  fi

  echo ""
  echo -e "${C_BOLD}  Next steps:${C_RESET}"
  if [[ "${install_mode}" == "new" ]]; then
    echo "    1. Add [klicky_probe] to printer.cfg"
    echo "       (see config/sample-klicky.cfg)"
    echo "    2. FIRMWARE_RESTART (if Klipper was not restarted)"
    echo "    3. Verify with: ATTACH_PROBE / DETACH_PROBE"
  else
    echo "    1. FIRMWARE_RESTART (if Klipper was not restarted)"
    echo "    2. Check printer.cfg if sample config gained new options"
    echo "    3. Verify with: ATTACH_PROBE / DETACH_PROBE"
  fi
  echo ""
  if [[ "${install_mode}" == "upgrade" ]]; then
    echo -e "${C_GREEN}${C_BOLD}  Upgrade complete — all good.${C_RESET}"
  else
    echo -e "${C_GREEN}${C_BOLD}  Install complete — all good.${C_RESET}"
  fi
  echo ""
}

# ---------------------------------------------------------------------------
# Detect existing install (before any changes)
# ---------------------------------------------------------------------------
detect_install_mode() {
  # Sets: INSTALL_MODE (new|upgrade), PREV_KIND, PREV_DETAIL
  local target="$1"
  INSTALL_MODE="new"
  PREV_KIND=""
  PREV_DETAIL=""

  if [[ -L "${target}" ]]; then
    INSTALL_MODE="upgrade"
    PREV_KIND="symlink"
    local dest
    dest="$(readlink -f "${target}" 2>/dev/null || readlink "${target}" 2>/dev/null || echo "?")"
    PREV_DETAIL="symlink -> ${dest}"
  elif [[ -d "${target}" ]]; then
    INSTALL_MODE="upgrade"
    PREV_KIND="directory"
    PREV_DETAIL="directory copy at ${target}"
  elif [[ -e "${target}" ]]; then
    INSTALL_MODE="upgrade"
    PREV_KIND="file"
    PREV_DETAIL="file at ${target}"
  fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
SRCDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KLIPPER_PATH="${1:-${KLIPPER_PATH:-$HOME/klipper}}"
EXTRAS_PATH="${KLIPPER_PATH}/klippy/extras"
TARGET="${EXTRAS_PATH}/klicky_probe"
SRC_MODULE="${SRCDIR}/klicky_probe"

if [[ ! -d "${EXTRAS_PATH}" ]]; then
  print_header "unknown (path check failed)"
  err "Klipper extras not found at ${EXTRAS_PATH}"
  echo ""
  echo "  Set KLIPPER_PATH or pass the path as the first argument:"
  echo "    KLIPPER_PATH=/path/to/klipper ./plugin/install.sh"
  echo "    ./plugin/install.sh /path/to/klipper"
  echo ""
  exit 1
fi

detect_install_mode "${TARGET}"

if [[ "${INSTALL_MODE}" == "upgrade" ]]; then
  print_header "UPGRADE"
else
  print_header "NEW INSTALL"
fi

info "Klipper path: ${KLIPPER_PATH}"
info "Extras path:  ${EXTRAS_PATH}"

if [[ "${INSTALL_MODE}" == "upgrade" ]]; then
  info "Existing install detected (${PREV_KIND})"
  info "  ${PREV_DETAIL}"
  # Same source already linked — still a refresh/upgrade of the tree via re-link
  if [[ "${PREV_KIND}" == "symlink" ]]; then
    local_prev="$(readlink -f "${TARGET}" 2>/dev/null || true)"
    local_src="$(readlink -f "${SRC_MODULE}" 2>/dev/null || true)"
    if [[ -n "${local_prev}" && -n "${local_src}" && "${local_prev}" == "${local_src}" ]]; then
      info "Same source path already linked — refreshing install"
    fi
  fi
  info "Removing previous install..."
  rm -rf "${TARGET}"
  ok "Previous install removed"
else
  info "No previous install found — performing new install"
fi

# Prefer symlink for easy updates
ln -s "${SRC_MODULE}" "${TARGET}"
ok "Linked ${TARGET} -> ${SRC_MODULE}"

# Restart Klipper only if the service is active
RESTART_STATUS="warn"
RESTART_MSG="Klipper service not active — skipped restart (run FIRMWARE_RESTART later)"
if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet klipper 2>/dev/null; then
  info "Restarting klipper service..."
  if sudo systemctl restart klipper 2>/dev/null || systemctl restart klipper 2>/dev/null; then
    RESTART_STATUS="ok"
    RESTART_MSG="Klipper service restarted"
  else
    RESTART_MSG="Klipper restart failed — restart manually"
  fi
fi

print_success "${INSTALL_MODE}" "${TARGET}" "${SRC_MODULE}" \
  "${RESTART_STATUS}" "${RESTART_MSG}" "${PREV_DETAIL}"
