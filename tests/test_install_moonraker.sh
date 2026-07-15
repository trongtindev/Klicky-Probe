#!/usr/bin/env bash
# Fixture tests for Moonraker helpers in plugin/install.sh
#
# Contract when sourcing the installer as a library:
#   KLICKY_INSTALL_LIB=1 source plugin/install.sh
# Mutators take explicit paths:
#   add_updater conf repo_root
#   remove_updater conf
#   find_moonraker_conf [override]  → stdout path; 0|1|2
#   do_moonraker add|remove [override] [repo_root]  → 0|1|2; sets moon_hint_snippet
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../plugin/install.sh
KLICKY_INSTALL_LIB=1 source "${ROOT}/plugin/install.sh"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "OK: $*"; }

tmp="$(mktemp)"
trap 'rm -f "${tmp}" "${tmp}.out" "${tmp}.other" "${tmp}.hand" "${tmp}.stray" "${tmp}.blank"' EXIT

# --- section present ---
cat > "${tmp}" <<'EOF'
[server]
host: 0.0.0.0

# klicky_probe - added by plugin/install.sh
[update_manager klicky_probe]
type: git_repo
path: /home/pi/Klicky-Probe
origin: https://example.com/Klicky-Probe.git
primary_branch: main
install_script: plugin/install.sh
managed_services: klipper

[update_manager other]
type: git_repo
path: /tmp/other
EOF

moonraker_section_present "${tmp}" || fail "expected section present"
pass "moonraker_section_present true"

moonraker_section_is_managed "${tmp}" || fail "expected managed (adjacent marker)"
pass "moonraker_section_is_managed true (adjacent)"

# --- filter removes only klicky section + installer comment ---
filter_moonraker_section < "${tmp}" > "${tmp}.out"

if moonraker_section_present "${tmp}.out"; then
  fail "section still present after filter"
fi
pass "filter removes klicky_probe section"

grep -q '\[update_manager other\]' "${tmp}.out" || fail "other section removed"
grep -q '\[server\]' "${tmp}.out" || fail "server section removed"
grep -q 'klicky_probe - added by plugin' "${tmp}.out" && fail "installer comment not removed"
grep -q 'Klicky-Probe' "${tmp}.out" && fail "klicky body not removed"
pass "neighboring sections preserved"

# --- false positive headers must not match ---
cat > "${tmp}.other" <<'EOF'
[update_manager client]
type: web
[update_manager klicky_probe_extra]
type: git_repo
EOF
if moonraker_section_present "${tmp}.other"; then
  fail "over-matched non-klicky_probe section"
fi
pass "exact section name only"

# --- block generator shape (from moonraker.snippet.conf) ---
block="$(moonraker_update_block "/repo/root" "https://example.com/r.git")"
echo "${block}" | grep -q '\[update_manager klicky_probe\]' || fail "block missing header"
echo "${block}" | grep -q 'path: /repo/root' || fail "block missing path"
echo "${block}" | grep -q 'origin: https://example.com/r.git' || fail "block missing origin"
echo "${block}" | grep -q '# klicky_probe - added by plugin/install.sh' || fail "block missing comment"
echo "${block}" | grep -q 'type: git_repo' || fail "block missing type (snippet)"
echo "${block}" | grep -q 'primary_branch: main' || fail "block missing primary_branch (snippet)"
echo "${block}" | grep -q 'install_script: plugin/install.sh' || fail "block missing install_script (snippet)"
echo "${block}" | grep -q 'managed_services: klipper' || fail "block missing managed_services (snippet)"
echo "${block}" | grep -q 'Single source of truth' && fail "snippet doc comment leaked into block"
pass "moonraker_update_block content"

# --- add_updater: first install (filter + append path) ---
cat > "${tmp}" <<'EOF'
[server]
host: 0.0.0.0
EOF
rc=0
add_updater "${tmp}" "/tmp/klicky-test-repo-A" || rc=$?
[[ "${rc}" -eq 0 ]] || fail "add_updater first install expected 0, got ${rc}"
moonraker_section_present "${tmp}" || fail "section missing after add"
grep -q 'path: /tmp/klicky-test-repo-A' "${tmp}" || fail "path not written on first add"
moonraker_section_is_managed "${tmp}" || fail "marker missing after first add"
pass "add_updater first install"

# --- add_updater: managed rewrite updates path/origin ---
rc=0
add_updater "${tmp}" "/tmp/klicky-test-repo-B" || rc=$?
[[ "${rc}" -eq 0 ]] || fail "add_updater rewrite expected 0, got ${rc}"
grep -q 'path: /tmp/klicky-test-repo-B' "${tmp}" || fail "path not rewritten"
grep -q 'path: /tmp/klicky-test-repo-A' "${tmp}" && fail "old path still present"
marker_count="$(grep -c 'klicky_probe - added by plugin/install.sh' "${tmp}" || true)"
[[ "${marker_count}" -eq 1 ]] || fail "expected one installer marker, got ${marker_count}"
grep -q '\[server\]' "${tmp}" || fail "server lost on rewrite"
pass "add_updater managed rewrite"

# --- add_updater: hand-edited section skipped ---
cat > "${tmp}.hand" <<'EOF'
[server]
host: 0.0.0.0

[update_manager klicky_probe]
type: git_repo
path: /hand/edited/path
origin: https://example.com/hand.git
primary_branch: main
install_script: plugin/install.sh
managed_services: klipper
EOF
rc=0
add_updater "${tmp}.hand" "/tmp/should-not-apply" || rc=$?
[[ "${rc}" -eq 1 ]] || fail "hand-edited skip expected 1, got ${rc}"
grep -q 'path: /hand/edited/path' "${tmp}.hand" || fail "hand-edited path was changed"
grep -q 'path: /tmp/should-not-apply' "${tmp}.hand" && fail "hand-edited section was rewritten"
pass "add_updater hand-edited skip"

# --- marker + blank lines + section → managed; filter removes both ---
cat > "${tmp}.blank" <<'EOF'
[server]
host: 0.0.0.0

# klicky_probe - added by plugin/install.sh

[update_manager klicky_probe]
type: git_repo
path: /old/path
origin: https://example.com/old.git

[update_manager other]
type: git_repo
path: /tmp/other
EOF
moonraker_section_is_managed "${tmp}.blank" || fail "blank-separated marker should be managed"
filter_moonraker_section < "${tmp}.blank" > "${tmp}.out"
moonraker_section_present "${tmp}.out" && fail "section remained after blank-marker filter"
grep -q 'klicky_probe - added by plugin' "${tmp}.out" && fail "orphan marker left after blank-marker filter"
grep -q '\[update_manager other\]' "${tmp}.out" || fail "other section lost (blank-marker case)"
grep -q '\[server\]' "${tmp}.out" || fail "server lost (blank-marker case)"
pass "adjacent marker with blank lines (managed + filter)"

# --- stray marker far above hand section → not managed; add skips ---
cat > "${tmp}.stray" <<'EOF'
# klicky_probe - added by plugin/install.sh
[server]
host: 0.0.0.0

[update_manager klicky_probe]
type: git_repo
path: /hand/with/stray/marker
origin: https://example.com/hand.git
primary_branch: main
install_script: plugin/install.sh
managed_services: klipper
EOF
if moonraker_section_is_managed "${tmp}.stray"; then
  fail "stray non-adjacent marker must not mark section managed"
fi
rc=0
add_updater "${tmp}.stray" "/tmp/should-not-apply" || rc=$?
[[ "${rc}" -eq 1 ]] || fail "stray-marker hand section skip expected 1, got ${rc}"
grep -q 'path: /hand/with/stray/marker' "${tmp}.stray" || fail "stray-marker conf was modified"
pass "stray marker does not force managed rewrite"

# --- section without any marker → not managed ---
cat > "${tmp}.hand" <<'EOF'
[update_manager klicky_probe]
path: /bare
EOF
if moonraker_section_is_managed "${tmp}.hand"; then
  fail "bare section must not be managed"
fi
pass "bare section not managed"

# --- remove_updater ---
cat > "${tmp}" <<'EOF'
[server]
host: 0.0.0.0

# klicky_probe - added by plugin/install.sh
[update_manager klicky_probe]
type: git_repo
path: /home/pi/Klicky-Probe
origin: https://example.com/Klicky-Probe.git
primary_branch: main
install_script: plugin/install.sh
managed_services: klipper

[update_manager other]
type: git_repo
path: /tmp/other
EOF
rc=0
remove_updater "${tmp}" || rc=$?
[[ "${rc}" -eq 0 ]] || fail "remove_updater expected 0, got ${rc}"
moonraker_section_present "${tmp}" && fail "section still present after remove"
grep -q '\[server\]' "${tmp}" || fail "server removed"
grep -q '\[update_manager other\]' "${tmp}" || fail "other section removed"
pass "remove_updater preserves neighbors"

# --- remove_updater skip when absent ---
rc=0
remove_updater "${tmp}" || rc=$?
[[ "${rc}" -eq 1 ]] || fail "remove when absent expected 1, got ${rc}"
pass "remove_updater skip when absent"

# --- remove hand-edited section (uninstall removes any klicky section) ---
cat > "${tmp}.hand" <<'EOF'
[server]
host: 0.0.0.0

[update_manager klicky_probe]
path: /hand/edited
EOF
rc=0
remove_updater "${tmp}.hand" || rc=$?
[[ "${rc}" -eq 0 ]] || fail "remove hand-edited expected 0, got ${rc}"
moonraker_section_present "${tmp}.hand" && fail "hand-edited section remained"
pass "remove_updater removes hand-edited section"

# --- assert_safe_target ---
if (assert_safe_target "/wrong/path" 2>/dev/null); then
  fail "assert_safe_target should refuse wrong path"
fi
if (assert_safe_target "/extras/klicky_probe" 2>/dev/null); then
  fail "assert_safe_target should refuse path not under klippy/extras"
fi
assert_safe_target "/home/pi/klipper/klippy/extras/klicky_probe" || \
  fail "assert_safe_target rejected valid path"
pass "assert_safe_target"

# --- find_moonraker_conf: explicit missing → 2 ---
rc=0
find_moonraker_conf "/no/such/moonraker.conf.$$" >/dev/null || rc=$?
[[ "${rc}" -eq 2 ]] || fail "missing explicit conf expected 2, got ${rc}"
pass "find_moonraker_conf missing override"

# --- find_moonraker_conf: explicit present ---
path="$(find_moonraker_conf "${tmp}")" || fail "explicit present should succeed"
[[ "${path}" == "${tmp}" ]] || fail "explicit path mismatch: ${path}"
pass "find_moonraker_conf explicit present"

# --- find_moonraker_conf: auto-detect empty HOME → 1 ---
rc=0
empty_home="$(mktemp -d)"
HOME="${empty_home}" find_moonraker_conf >/dev/null || rc=$?
rmdir "${empty_home}"
[[ "${rc}" -eq 1 ]] || fail "empty auto-detect expected 1, got ${rc}"
pass "find_moonraker_conf auto-detect miss"

# --- add_updater missing conf file → 2 ---
rc=0
add_updater "/no/such/moonraker.conf.$$" "/tmp/repo" || rc=$?
[[ "${rc}" -eq 2 ]] || fail "add missing conf expected 2, got ${rc}"
pass "add_updater missing conf file"

# --- do_moonraker: missing override → 2 + hint ---
moon_hint_snippet=0
rc=0
do_moonraker add "/no/such/moonraker.conf.$$" "/tmp/repo" >/dev/null || rc=$?
[[ "${rc}" -eq 2 ]] || fail "do_moonraker missing override expected 2, got ${rc}"
[[ "${moon_hint_snippet}" -eq 1 ]] || fail "missing override should set moon_hint_snippet"
pass "do_moonraker missing override"

# --- do_moonraker: first add ---
cat > "${tmp}" <<'EOF'
[server]
host: 0.0.0.0
EOF
moon_hint_snippet=0
rc=0
do_moonraker add "${tmp}" "/tmp/via-apply" >/dev/null || rc=$?
[[ "${rc}" -eq 0 ]] || fail "do_moonraker add expected 0, got ${rc}"
grep -q 'path: /tmp/via-apply' "${tmp}" || fail "do_moonraker add path missing"
[[ "${moon_hint_snippet}" -eq 0 ]] || fail "successful add must not set moon_hint_snippet"
pass "do_moonraker add"

# --- do_moonraker: hand-edit skip → 1, no hint ---
cat > "${tmp}.hand" <<'EOF'
[update_manager klicky_probe]
path: /hand/edited
EOF
moon_hint_snippet=0
rc=0
do_moonraker add "${tmp}.hand" "/tmp/should-not" >/dev/null || rc=$?
[[ "${rc}" -eq 1 ]] || fail "do_moonraker hand-edit expected 1, got ${rc}"
[[ "${moon_hint_snippet}" -eq 0 ]] || fail "hand-edit skip must not set moon_hint_snippet"
pass "do_moonraker hand-edit no hint"

# --- multi-rewrite: blank lines above marker stay stable (no accumulation) ---
count_blanks_before_marker() {
  local conf="$1"
  awk '
    /^# klicky_probe - added by plugin\/install\.sh[[:space:]]*$/ {
      print blanks
      exit
    }
    /^[[:space:]]*$/ { blanks++; next }
    { blanks = 0 }
  ' "${conf}"
}

cat > "${tmp}" <<'EOF'
[server]
host: 0.0.0.0
EOF
rc=0
add_updater "${tmp}" "/tmp/klicky-blank-A" || rc=$?
[[ "${rc}" -eq 0 ]] || fail "blank-stability first add expected 0, got ${rc}"
b1="$(count_blanks_before_marker "${tmp}")"
[[ "${b1}" -eq 1 ]] || fail "expected 1 blank before marker after first add, got ${b1}"

rc=0
add_updater "${tmp}" "/tmp/klicky-blank-B" || rc=$?
[[ "${rc}" -eq 0 ]] || fail "blank-stability second add expected 0, got ${rc}"
b2="$(count_blanks_before_marker "${tmp}")"
[[ "${b2}" -eq 1 ]] || fail "expected 1 blank before marker after second add, got ${b2}"
grep -q 'path: /tmp/klicky-blank-B' "${tmp}" || fail "path not rewritten on second add"

rc=0
add_updater "${tmp}" "/tmp/klicky-blank-C" || rc=$?
[[ "${rc}" -eq 0 ]] || fail "blank-stability third add expected 0, got ${rc}"
b3="$(count_blanks_before_marker "${tmp}")"
[[ "${b3}" -eq 1 ]] || fail "expected 1 blank before marker after third add, got ${b3}"
[[ "${b2}" -eq "${b3}" ]] || fail "blank count grew across rewrites: ${b2} -> ${b3}"
grep -q 'path: /tmp/klicky-blank-C' "${tmp}" || fail "path not rewritten on third add"
total_blanks="$(grep -c '^$' "${tmp}" || true)"
[[ "${total_blanks}" -eq 1 ]] || fail "expected total blank lines == 1 after rewrites, got ${total_blanks}"
pass "multi-rewrite blank lines stable"

# --- conf file mode preserved across rewrite ---
cat > "${tmp}" <<'EOF'
[server]
host: 0.0.0.0
EOF
chmod 644 "${tmp}"
mode_before="$(stat -c '%a' "${tmp}" 2>/dev/null || stat -f '%OLp' "${tmp}" 2>/dev/null || true)"
[[ "${mode_before}" == "644" ]] || fail "setup chmod 644 failed (got ${mode_before:-unknown})"
rc=0
add_updater "${tmp}" "/tmp/klicky-mode-repo" || rc=$?
[[ "${rc}" -eq 0 ]] || fail "mode-preserve add expected 0, got ${rc}"
mode_after="$(stat -c '%a' "${tmp}" 2>/dev/null || stat -f '%OLp' "${tmp}" 2>/dev/null || true)"
[[ "${mode_after}" == "644" ]] || fail "expected mode 644 after add, got ${mode_after:-unknown}"
pass "conf file mode preserved"

echo ""
echo "All install moonraker fixture tests passed."
