#!/usr/bin/env bash
# Install or uninstall klicky_probe into Klipper's extras directory and
# optionally register/remove the Moonraker update_manager section.
#
# Usage: ./install.sh [-k KLIPPER_PATH] [-m MOONRAKER_CONF] [-u] [-h] [KLIPPER_PATH]
# Env:   KLIPPER_PATH (default: ~/klipper)
#        MOONRAKER_CONF (optional override for moonraker.conf path)
#
# Pure helpers and mutators are sourcable for tests:
#   KLICKY_INSTALL_LIB=1 source plugin/install.sh
#
# Mutator exit codes: 0 = mutated, 1 = skipped, 2 = soft-fail
# find_moonraker_conf [override]: prints path; exit 0 found, 1 not found, 2 override missing
# moonraker_update_block reads plugin/moonraker.snippet.conf (single key source)
set -euo pipefail

DEFAULT_ORIGIN="https://github.com/trongtindev/Klicky-Probe.git"
SECTION_NAME="klicky_probe"
INSTALLER_MARKER="# ${SECTION_NAME} - added by plugin/install.sh"
# Exact section: [update_manager klicky_probe] (one or more spaces)
SECTION_HEADER_RE="^\\[update_manager[[:space:]]+${SECTION_NAME}\\]"
INSTALLER_MARKER_RE="^# ${SECTION_NAME} - added by plugin/install\\.sh[[:space:]]*$"

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

usage() {
  cat <<EOF
Usage: $(basename "$0") [-k KLIPPER_PATH] [-m MOONRAKER_CONF] [-u] [-h] [KLIPPER_PATH]

  -k PATH   Klipper root directory (default: \$KLIPPER_PATH or ~/klipper)
  -m PATH   Path to moonraker.conf (default: auto-detect)
  -u        Uninstall klicky_probe (extras link + Moonraker update section)
  -h        Show this help

Env:
  KLIPPER_PATH     Same as -k
  MOONRAKER_CONF   Same as -m

Examples:
  ./plugin/install.sh
  ./plugin/install.sh -k /home/pi/klipper
  ./plugin/install.sh -m ~/printer_data/config/moonraker.conf
  ./plugin/install.sh -u
EOF
  exit "${1:-0}"
}

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

print_success_banner() {
  local title="$1"
  echo ""
  echo -e "${C_GREEN}${C_BOLD}"
  echo "  ============================================================"
  echo "     [OK]  SUCCESS  ·  ${title}"
  echo "  ============================================================"
  echo -e "${C_RESET}"
}

print_next_steps() {
  if (($# == 0)); then
    return 0
  fi
  echo ""
  echo -e "${C_BOLD}  Next steps:${C_RESET}"
  local i=1
  local step
  for step in "$@"; do
    echo "    ${i}. ${step}"
    i=$((i + 1))
  done
}

print_done() {
  local title="$1"
  shift
  print_success_banner "${title}"
  print_next_steps "$@"
  echo ""
  echo -e "${C_GREEN}${C_BOLD}  Done.${C_RESET}"
  echo ""
}

# ---------------------------------------------------------------------------
# Detect existing install (before any changes)
# Sets: INSTALL_MODE (new|upgrade), PREV_KIND, PREV_DETAIL
# ---------------------------------------------------------------------------
detect_install_mode() {
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

# Refuse rm -rf unless target is klicky_probe under a klippy/extras directory.
assert_safe_target() {
  local target="$1"
  local base parent
  base="$(basename "${target}")"
  parent="$(dirname "${target}")"
  if [[ "${base}" != "klicky_probe" ]]; then
    err "Refusing to remove unexpected path: ${target}"
    err "Basename must be klicky_probe"
    exit 1
  fi
  case "${parent}" in
    */klippy/extras|*/klippy/extras/) ;;
    *)
      err "Refusing to remove unexpected path: ${target}"
      err "Parent must end with klippy/extras (got: ${parent})"
      exit 1
      ;;
  esac
}

# ---------------------------------------------------------------------------
# Moonraker helpers
# ---------------------------------------------------------------------------

# find_moonraker_conf [override]
#   stdout: path on success only (no log noise — safe for $(...))
#   exit: 0 found, 1 not found (auto-detect), 2 explicit override missing
find_moonraker_conf() {
  local override="${1:-}"

  if [[ -n "${override}" ]]; then
    if [[ -f "${override}" ]]; then
      printf '%s\n' "${override}"
      return 0
    fi
    return 2
  fi

  local candidates=(
    "${HOME}/printer_data/config/moonraker.conf"
    "${HOME}/klipper_config/moonraker.conf"
    "${HOME}/moonraker.conf"
  )
  local c
  for c in "${candidates[@]}"; do
    if [[ -f "${c}" ]]; then
      printf '%s\n' "${c}"
      return 0
    fi
  done
  return 1
}

moonraker_section_present() {
  local conf="$1"
  [[ -f "${conf}" ]] || return 1
  grep -qE "${SECTION_HEADER_RE}" "${conf}" 2>/dev/null
}

# One adjacency model for filter + managed check.
# MODE via ENVIRON MOONRAKER_AWK_MODE:
#   filter  — stdin → stdout without klicky section + adjacent installer marker
#   managed — exit 0 iff klicky header exists with adjacent marker (blank lines OK)
# Patterns via ENVIRON (not -v): awk -v interprets \[, which breaks the header match.
_moonraker_awk() {
  SECTION_HEADER_RE="${SECTION_HEADER_RE}" \
  INSTALLER_MARKER_RE="${INSTALLER_MARKER_RE}" \
  MOONRAKER_AWK_MODE="${1}" \
  awk '
    BEGIN {
      header_re = ENVIRON["SECTION_HEADER_RE"]
      marker_re = ENVIRON["INSTALLER_MARKER_RE"]
      mode = ENVIRON["MOONRAKER_AWK_MODE"]
      skip = 0
      bn = 0
      managed = 0
    }

    function flush_buf(   i) {
      if (mode == "filter") {
        for (i = 1; i <= bn; i++) print buf[i]
      }
      bn = 0
    }

    # Shared adjacency: last non-blank above header is the installer marker.
    # filter: drop marker (+ trailing blanks) and keep earlier buffered lines.
    # managed: set managed=1 when marker is adjacent.
    function drop_adjacent_marker(   i, j) {
      i = bn
      while (i >= 1 && buf[i] ~ /^[[:space:]]*$/) i--
      if (i >= 1 && buf[i] ~ marker_re) {
        managed = 1
        if (mode == "filter") {
          i--
          for (j = 1; j <= i; j++) print buf[j]
        }
        bn = 0
        return
      }
      flush_buf()
    }

    {
      if (skip) {
        if ($0 ~ /^\[/) {
          skip = 0
        } else {
          next
        }
      }

      if ($0 ~ header_re) {
        drop_adjacent_marker()
        if (mode == "managed") {
          exit
        }
        skip = 1
        next
      }

      if ($0 ~ /^\[/) {
        flush_buf()
        if (mode == "filter") print
        next
      }

      bn++
      buf[bn] = $0
    }

    END {
      if (mode == "managed") {
        exit managed ? 0 : 1
      }
      if (!skip) flush_buf()
    }
  '
}

# Managed iff installer marker is immediately above the section (blank lines OK).
moonraker_section_is_managed() {
  local conf="$1"
  [[ -f "${conf}" ]] || return 1
  _moonraker_awk managed < "${conf}"
}

# Pure filter: stdin → stdout without [update_manager klicky_probe] and without
# its adjacent installer marker (blank lines between marker and header included).
filter_moonraker_section() {
  _moonraker_awk filter
}

# Directory containing this install.sh (works when sourced from tests).
_install_sh_dir() {
  cd "$(dirname "${BASH_SOURCE[0]}")" && pwd
}

# Path to moonraker.snippet.conf (single source of truth for update_manager keys).
_moonraker_snippet_path() {
  printf '%s\n' "$(_install_sh_dir)/moonraker.snippet.conf"
}

# Emit managed block: installer marker + snippet body with path/origin substituted.
# Snippet comments above the first [section] are omitted. Exit 2 if snippet missing.
moonraker_update_block() {
  local root="$1"
  local origin="$2"
  local snippet line in_section=0

  snippet="$(_moonraker_snippet_path)"
  if [[ ! -f "${snippet}" ]]; then
    return 2
  fi

  # No leading blank: _write_moonraker_conf owns the separator.
  printf '%s\n' "${INSTALLER_MARKER}"
  while IFS= read -r line || [[ -n "${line}" ]]; do
    if [[ "${in_section}" -eq 0 ]]; then
      if [[ "${line}" == \[* ]]; then
        in_section=1
        printf '%s\n' "${line}"
      fi
      continue
    fi
    if [[ "${line}" =~ ^[[:space:]]*path[[:space:]]*: ]]; then
      printf 'path: %s\n' "${root}"
    elif [[ "${line}" =~ ^[[:space:]]*origin[[:space:]]*: ]]; then
      printf 'origin: %s\n' "${origin}"
    else
      printf '%s\n' "${line}"
    fi
  done < "${snippet}"
}

repo_origin() {
  local root="$1"
  local origin
  origin="$(git -C "${root}" remote get-url origin 2>/dev/null || true)"
  if [[ -n "${origin}" ]]; then
    printf '%s' "${origin}"
  else
    printf '%s' "${DEFAULT_ORIGIN}"
  fi
}

# Strip trailing blank lines in-place (stable join for managed rewrites).
_strip_trailing_blank_lines() {
  local file="$1"
  local out
  out="$(mktemp "${file}.XXXXXX" 2>/dev/null || mktemp 2>/dev/null)" || return 1
  # Drop empty lines at EOF only.
  if ! awk 'BEGIN{n=0} {lines[++n]=$0} END{
    while (n >= 1 && lines[n] ~ /^[[:space:]]*$/) n--
    for (i = 1; i <= n; i++) print lines[i]
  }' "${file}" > "${out}"; then
    rm -f "${out}"
    return 1
  fi
  if ! mv "${out}" "${file}" 2>/dev/null; then
    rm -f "${out}"
    return 1
  fi
  return 0
}

# Best-effort file mode for chmod (Linux first; macOS fallback for dev).
_conf_file_mode() {
  local conf="$1"
  local mode
  mode="$(stat -c '%a' "${conf}" 2>/dev/null || true)"
  if [[ -n "${mode}" ]]; then
    printf '%s' "${mode}"
    return 0
  fi
  mode="$(stat -f '%OLp' "${conf}" 2>/dev/null || true)"
  if [[ -n "${mode}" ]]; then
    printf '%s' "${mode}"
    return 0
  fi
  return 1
}

# Filter conf, optionally append managed block, atomic replace (no pipe/subshell).
# root empty → strip only. Returns 0 ok, 2 fail.
# Trailing blanks are normalized so rewrites do not accumulate empty lines.
# Original conf mode is preserved when stat/chmod succeed.
_write_moonraker_conf() {
  local conf="$1"
  local root="${2:-}"
  local dir tmp origin mode=""

  dir="$(dirname "${conf}")"
  mode="$(_conf_file_mode "${conf}" 2>/dev/null || true)"

  if tmp="$(mktemp "${dir}/.klicky.XXXXXX" 2>/dev/null)"; then
    :
  elif tmp="$(mktemp 2>/dev/null)"; then
    :
  else
    return 2
  fi

  if ! filter_moonraker_section < "${conf}" > "${tmp}"; then
    rm -f "${tmp}"
    return 2
  fi

  if ! _strip_trailing_blank_lines "${tmp}"; then
    rm -f "${tmp}"
    return 2
  fi

  if [[ -n "${root}" ]]; then
    origin="$(repo_origin "${root}")"
    # Exactly one blank separator when prior content remains.
    if [[ -s "${tmp}" ]]; then
      printf '\n' >> "${tmp}"
    fi
    if ! moonraker_update_block "${root}" "${origin}" >> "${tmp}"; then
      rm -f "${tmp}"
      return 2
    fi
  fi

  if [[ -n "${mode}" ]]; then
    chmod "${mode}" "${tmp}" 2>/dev/null || true
  fi

  if ! mv "${tmp}" "${conf}" 2>/dev/null; then
    rm -f "${tmp}"
    return 2
  fi
  return 0
}

# Args: conf repo_root
# Exit: 0 mutated, 1 skipped (hand-edited), 2 soft-fail
add_updater() {
  local conf="$1"
  local root="$2"

  if [[ ! -f "${conf}" ]]; then
    warn "Moonraker conf not found: ${conf}"
    return 2
  fi

  if moonraker_section_present "${conf}" && ! moonraker_section_is_managed "${conf}"; then
    info "Moonraker update_manager klicky_probe already present (hand-edited; path not updated)"
    return 1
  fi

  if ! _write_moonraker_conf "${conf}" "${root}"; then
    warn "Could not write Moonraker conf (permission?) — add plugin/moonraker.snippet.conf manually"
    return 2
  fi
  ok "Moonraker update_manager section written (${conf})"
  return 0
}

# Args: conf
# Exit: 0 removed, 1 skipped, 2 soft-fail
remove_updater() {
  local conf="$1"

  if [[ ! -f "${conf}" ]]; then
    warn "Moonraker conf not found: ${conf}"
    return 2
  fi

  if ! moonraker_section_present "${conf}"; then
    info "No [update_manager klicky_probe] section in moonraker.conf"
    return 1
  fi

  if ! _write_moonraker_conf "${conf}" ""; then
    warn "Could not edit moonraker.conf — remove [update_manager klicky_probe] manually"
    return 2
  fi
  ok "Removed [update_manager klicky_probe] from ${conf}"
  return 0
}

# Find conf + add|remove. Exit 0|1|2 only (no code 3).
# Sets moon_hint_snippet=1 when install should suggest copying the snippet.
#   do_moonraker add "$override" "$repo_root"
#   do_moonraker remove "$override"
do_moonraker() {
  local action="$1"
  local override="${2:-}"
  local root="${3:-}"
  local conf find_rc=0 rc=0

  moon_hint_snippet=0

  conf="$(find_moonraker_conf "${override}")" || find_rc=$?
  if [[ "${find_rc}" -eq 2 ]]; then
    warn "Configured moonraker.conf not found: ${override}"
    moon_hint_snippet=1
    return 2
  fi
  if [[ "${find_rc}" -ne 0 ]]; then
    if [[ "${action}" == "remove" ]]; then
      info "Moonraker conf not found — nothing to remove for update_manager"
    else
      info "Moonraker conf not found — skipped update_manager (see plugin/moonraker.snippet.conf)"
      moon_hint_snippet=1
    fi
    return 1
  fi

  if [[ "${action}" == "remove" ]]; then
    remove_updater "${conf}"
    return $?
  fi

  add_updater "${conf}" "${root}" || rc=$?
  if [[ "${rc}" -eq 2 ]]; then
    moon_hint_snippet=1
  fi
  return "${rc}"
}

# Exit: 0 restarted, 1 skipped, 2 failed.
restart_service() {
  local svc="$1"

  if ! command -v systemctl >/dev/null 2>&1; then
    return 1
  fi
  if ! systemctl is-active --quiet "${svc}" 2>/dev/null; then
    return 1
  fi

  info "Restarting ${svc} service..."
  # sudo -n: never prompt for a password (avoids hang in non-interactive shells)
  if sudo -n systemctl restart "${svc}" 2>/dev/null || systemctl restart "${svc}" 2>/dev/null; then
    return 0
  fi
  return 2
}

# Print restart outcome; returns same code as restart_service.
try_restart() {
  local svc="$1"
  local label="${2:-$1}"
  local rc=0
  restart_service "${svc}" || rc=$?
  case "${rc}" in
    0) ok "${label} service restarted" ;;
    1) info "${label} service not active — skipped restart" ;;
    *) warn "${label} restart failed — restart manually" ;;
  esac
  return "${rc}"
}

# ---------------------------------------------------------------------------
# Main (skipped when sourced for tests: KLICKY_INSTALL_LIB=1)
# ---------------------------------------------------------------------------
klicky_install_main() {
  local SRCDIR REPO_ROOT UNINSTALL KLIPPER_PATH MOONRAKER_OVERRIDE
  local EXTRAS_PATH TARGET SRC_MODULE
  local INSTALL_MODE PREV_KIND PREV_DETAIL
  local moon_rc klip_rc OPTION
  local moon_hint_snippet=0
  local extras_removed=0
  local -a steps=()

  SRCDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  REPO_ROOT="$(cd "${SRCDIR}/.." && pwd)"
  UNINSTALL=0
  KLIPPER_PATH="${KLIPPER_PATH:-$HOME/klipper}"
  MOONRAKER_OVERRIDE="${MOONRAKER_CONF:-}"
  OPTIND=1

  while getopts ":k:m:uh" OPTION; do
    case "${OPTION}" in
      k) KLIPPER_PATH="${OPTARG}" ;;
      m) MOONRAKER_OVERRIDE="${OPTARG}" ;;
      u) UNINSTALL=1 ;;
      h) usage 0 ;;
      *) usage 1 ;;
    esac
  done
  shift $((OPTIND - 1))
  [[ $# -ge 1 ]] && KLIPPER_PATH="$1"

  if [[ "${EUID}" -eq 0 ]]; then
    err "Do not run this script as root (run as the user that owns Klipper)"
    exit 1
  fi

  EXTRAS_PATH="${KLIPPER_PATH}/klippy/extras"
  TARGET="${EXTRAS_PATH}/klicky_probe"
  SRC_MODULE="${SRCDIR}/klicky_probe"

  # --- Uninstall ---
  if [[ "${UNINSTALL}" -eq 1 ]]; then
    print_header "UNINSTALL"
    info "Klipper path: ${KLIPPER_PATH}"
    info "Extras path:  ${EXTRAS_PATH}"
    info "Repo root:    ${REPO_ROOT}"

    if [[ -e "${TARGET}" || -L "${TARGET}" ]]; then
      assert_safe_target "${TARGET}"
      info "Removing ${TARGET}..."
      rm -rf "${TARGET}"
      ok "Removed ${TARGET}"
      extras_removed=1
    else
      info "No install found at ${TARGET}"
    fi

    moon_rc=0
    do_moonraker remove "${MOONRAKER_OVERRIDE}" || moon_rc=$?

    klip_rc=1
    if [[ "${extras_removed}" -eq 1 ]]; then
      klip_rc=0
      try_restart klipper "Klipper" || klip_rc=$?
    fi
    [[ "${moon_rc}" -eq 0 ]] && try_restart moonraker "Moonraker" || true

    steps=(
      "Remove [klicky_probe] from printer.cfg (if present)"
      "Optionally delete the git clone directory"
    )
    if [[ "${extras_removed}" -eq 1 && "${klip_rc}" -ne 0 ]]; then
      steps+=("FIRMWARE_RESTART if services were not restarted")
    fi
    if [[ "${extras_removed}" -eq 1 || "${moon_rc}" -eq 0 ]]; then
      print_done "klicky_probe uninstalled" "${steps[@]}"
    else
      print_done "uninstall complete (nothing to remove)" "${steps[@]}"
    fi
    return 0
  fi

  # --- Install / upgrade ---
  if [[ ! -d "${EXTRAS_PATH}" ]]; then
    print_header "unknown (path check failed)"
    err "Klipper extras not found at ${EXTRAS_PATH}"
    echo ""
    echo "  Set KLIPPER_PATH, use -k, or pass the path as the first argument:"
    echo "    KLIPPER_PATH=/path/to/klipper ./plugin/install.sh"
    echo "    ./plugin/install.sh -k /path/to/klipper"
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
  info "Repo root:    ${REPO_ROOT}"

  if [[ "${INSTALL_MODE}" == "upgrade" ]]; then
    info "Existing install detected (${PREV_KIND}): ${PREV_DETAIL}"
    assert_safe_target "${TARGET}"
    info "Removing previous install..."
    rm -rf "${TARGET}"
  else
    info "No previous install found — performing new install"
  fi

  ln -sfn "${SRC_MODULE}" "${TARGET}"
  ok "Symlink: ${TARGET} -> ${SRC_MODULE}"

  moon_rc=0
  moon_hint_snippet=0
  do_moonraker add "${MOONRAKER_OVERRIDE}" "${REPO_ROOT}" || moon_rc=$?

  klip_rc=0
  try_restart klipper "Klipper" || klip_rc=$?
  [[ "${moon_rc}" -eq 0 ]] && try_restart moonraker "Moonraker" || true

  if [[ "${INSTALL_MODE}" == "upgrade" ]]; then
    ok "Mode: UPGRADE (replaced previous install)"
    [[ -n "${PREV_DETAIL}" ]] && info "Previous: ${PREV_DETAIL}"
  else
    ok "Mode: NEW INSTALL"
  fi

  steps=()
  [[ "${INSTALL_MODE}" == "new" ]] && \
    steps+=("Add [klicky_probe] to printer.cfg (see config/sample-klicky.cfg)")
  # Snippet hint: conf missing or soft-fail — not hand-edit skip (moon_hint_snippet).
  if [[ "${moon_hint_snippet}" -eq 1 ]]; then
    steps+=("Add Moonraker update manager block (optional): copy plugin/moonraker.snippet.conf")
  fi
  [[ "${klip_rc}" -ne 0 ]] && steps+=("FIRMWARE_RESTART (if Klipper was not restarted)")
  [[ "${INSTALL_MODE}" == "upgrade" ]] && \
    steps+=("Check printer.cfg if sample config gained new options")
  steps+=("Verify with: ATTACH_PROBE / DETACH_PROBE")

  if [[ "${INSTALL_MODE}" == "upgrade" ]]; then
    print_done "klicky_probe upgraded successfully" "${steps[@]}"
  else
    print_done "klicky_probe installed successfully" "${steps[@]}"
  fi
}

if [[ "${KLICKY_INSTALL_LIB:-0}" != "1" ]]; then
  klicky_install_main "$@"
fi
