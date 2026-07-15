"""User-facing klicky_probe messages (errors, warnings, info, startup).

All messages are functions for a uniform call style: msg.name() / msg.name(args).
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Tuple, Union

from .klipper_version import format_version_tuple

VersionLike = Union[Tuple[int, int, int], Sequence[int]]


def _fmt_ver(required: VersionLike) -> str:
    if isinstance(required, tuple) and len(required) >= 3:
        return format_version_tuple((int(required[0]), int(required[1]), int(required[2])))
    return str(required)


def _fmt_dock_z(dock_z, precision: int = 3) -> str:
    if dock_z is None:
        return "gantry"
    return ("%." + str(precision) + "f") % dock_z


# ---------------------------------------------------------------------------
# Startup / lifecycle (logging + gcode.respond_info)
# ---------------------------------------------------------------------------


def log_loading(version: str) -> str:
    return "klicky_probe v%s: loading [klicky_probe] section" % version


def log_config_ok(
    version: str,
    klipper_version: str,
    dock_x: float,
    dock_y: float,
    dock_z,
    approach_x: float,
    approach_y: float,
    approach_z: float,
    detach_x: float,
    detach_y: float,
    detach_z: float,
    clearance_z: float,
    travel_speed: float,
    bed_min_x: float,
    bed_max_x: float,
    bed_min_y: float,
    bed_max_y: float,
    z_home_x: float,
    z_home_y: float,
    auto_attach: bool,
    homing_override: bool,
    adaptive_mesh: bool,
) -> str:
    return (
        "klicky_probe v%s: config OK (Klipper %s) — "
        "dock=(%.3f,%.3f,%s) approach=(%.3f,%.3f,%.3f) "
        "detach=(%.3f,%.3f,%.3f) clearance_z=%.2f travel=%.1f "
        "bed=(%.1f..%.1f, %.1f..%.1f) z_home=(%.1f,%.1f) "
        "auto_attach=%s homing_override=%s adaptive_mesh=%s"
        % (
            version,
            klipper_version,
            dock_x,
            dock_y,
            _fmt_dock_z(dock_z, 3),
            approach_x,
            approach_y,
            approach_z,
            detach_x,
            detach_y,
            detach_z,
            clearance_z,
            travel_speed,
            bed_min_x,
            bed_max_x,
            bed_min_y,
            bed_max_y,
            z_home_x,
            z_home_y,
            auto_attach,
            homing_override,
            adaptive_mesh,
        )
    )


def log_resolved_detail(
    attach_speed: float,
    detach_speed: float,
    z_speed: float,
    dock_before_z_home: bool,
    reseat_before_z_home: bool,
    safe_dock_travel: bool,
    safe_xy_before_dock: bool,
    safe_xy_x: float,
    safe_xy_y: float,
    home_first: str,
    dock_retries: int,
    wrap_probe_calibrate: bool,
    park_after: bool,
    umbilical: bool,
    dock_servo: bool,
    disable_docking: bool,
) -> str:
    return (
        "resolved detail: attach=%.1f detach=%.1f z_speed=%.1f "
        "dock_before_z_home=%s reseat_before_z_home=%s "
        "safe_dock_travel=%s safe_xy_before_dock=%s safe_xy_x=%.1f safe_xy_y=%.1f "
        "home_first=%s dock_retries=%d "
        "wrap_probe_calibrate=%s park_after=%s umbilical=%s "
        "dock_servo=%s disable_docking=%s"
        % (
            attach_speed,
            detach_speed,
            z_speed,
            dock_before_z_home,
            reseat_before_z_home,
            safe_dock_travel,
            safe_xy_before_dock,
            safe_xy_x,
            safe_xy_y,
            home_first,
            dock_retries,
            wrap_probe_calibrate,
            park_after,
            umbilical,
            dock_servo,
            disable_docking,
        )
    )


def feature_g28_override() -> str:
    return "G28 override"


def feature_probe_session_hooks() -> str:
    return "probe session hooks"


def feature_leveling_wraps() -> str:
    return "leveling wraps"


def feature_bed_mesh_calibrate() -> str:
    return "BED_MESH_CALIBRATE"


def feature_probe_accuracy() -> str:
    return "PROBE_ACCURACY"


def feature_manual_attach_only() -> str:
    return "manual attach only (auto_attach=False)"


def feature_probe_calibrate() -> str:
    return "PROBE_CALIBRATE"


def feature_adaptive_mesh() -> str:
    return "adaptive_mesh"


def feature_dock_servo(servo_name: Optional[str] = None) -> str:
    return "dock_servo(%s)" % (servo_name or "?")


def feature_disable_docking() -> str:
    return "disable_docking"


def feature_none() -> str:
    return "(none)"


def registered_gcodes() -> str:
    return (
        "ATTACH_PROBE DETACH_PROBE LOCK_PROBE UNLOCK_PROBE "
        "GET_PROBE_STATUS ENSURE_PROBE_DOCKED"
    )


def ready_banner(version: str) -> str:
    return "klicky_probe v%s: initialized — ready" % version


def ready_geometry_line(
    dock_x: float,
    dock_y: float,
    dock_z,
    approach_x: float,
    approach_y: float,
    approach_z: float,
    detach_x: float,
    detach_y: float,
    detach_z: float,
) -> str:
    return (
        "  dock=(%.2f, %.2f, %s)  approach=(%.2f, %.2f, %.2f)  "
        "detach=(%.2f, %.2f, %.2f)"
        % (
            dock_x,
            dock_y,
            _fmt_dock_z(dock_z, 2),
            approach_x,
            approach_y,
            approach_z,
            detach_x,
            detach_y,
            detach_z,
        )
    )


def ready_motion_line(
    clearance_z: float,
    travel_speed: float,
    z_home_x: float,
    z_home_y: float,
    bed_min_x: float,
    bed_max_x: float,
    bed_min_y: float,
    bed_max_y: float,
) -> str:
    return (
        "  clearance_z=%.2f  travel=%.1f  z_home=(%.1f, %.1f)  "
        "bed X[%.1f..%.1f] Y[%.1f..%.1f]"
        % (
            clearance_z,
            travel_speed,
            z_home_x,
            z_home_y,
            bed_min_x,
            bed_max_x,
            bed_min_y,
            bed_max_y,
        )
    )


def ready_features_line(features: Iterable[str]) -> str:
    items = list(features) if features else [feature_none()]
    return "  features: %s" % ", ".join(items)


def ready_gcodes_line(gcodes: Optional[str] = None) -> str:
    return "  gcodes: %s" % (gcodes if gcodes is not None else registered_gcodes())


def ready_announce_lines(
    version: str,
    dock_x: float,
    dock_y: float,
    dock_z,
    approach_x: float,
    approach_y: float,
    approach_z: float,
    detach_x: float,
    detach_y: float,
    detach_z: float,
    clearance_z: float,
    travel_speed: float,
    z_home_x: float,
    z_home_y: float,
    bed_min_x: float,
    bed_max_x: float,
    bed_min_y: float,
    bed_max_y: float,
    features: Optional[Iterable[str]] = None,
) -> List[str]:
    """Full multi-line ready summary (console + log)."""
    return [
        ready_banner(version),
        ready_geometry_line(
            dock_x,
            dock_y,
            dock_z,
            approach_x,
            approach_y,
            approach_z,
            detach_x,
            detach_y,
            detach_z,
        ),
        ready_motion_line(
            clearance_z,
            travel_speed,
            z_home_x,
            z_home_y,
            bed_min_x,
            bed_max_x,
            bed_min_y,
            bed_max_y,
        ),
        ready_features_line(features or ()),
        ready_gcodes_line(),
    ]


def log_line_for_ready(line: str) -> str:
    """Prefix indented ready lines for klippy.log."""
    if line.startswith("klicky_probe"):
        return line
    return "klicky_probe:%s" % line


def skew_frame_active(profile_name: str) -> str:
    return (
        "skew profile '%s' active; dock/approach coords use toolhead "
        "(machine) frame — toolhead.manual_move bypasses gcode skew"
        % profile_name
    )


def verbose_console(msg: str) -> str:
    return "klicky: %s" % msg


def debug_console(msg: str) -> str:
    return "klicky debug: %s" % msg


def debug_log(msg: str) -> str:
    return "klicky_probe debug: %s" % msg


def info_log(msg: str) -> str:
    return "klicky_probe: %s" % msg


# ---------------------------------------------------------------------------
# Runtime info logs (bodies; host may prefix via _log / logging)
# ---------------------------------------------------------------------------


def log_auto_attach_hooked() -> str:
    return "auto_attach: hooked probe.start_probe_session"


def log_dock_retry(mode: str, attempt: int) -> str:
    return "%s retry %d" % (mode, attempt)


def log_reseat() -> str:
    return "reseat: detach then attach (require_fresh)"


def log_probe_attached() -> str:
    return "probe attached"


def log_probe_docked() -> str:
    return "probe docked"


def log_ensure_force_unlocked() -> str:
    return "ENSURE_PROBE_DOCKED FORCE=1: unlocked"


def log_probe_locked() -> str:
    return "probe locked"


def log_probe_unlocked() -> str:
    return "probe unlocked"


# ---------------------------------------------------------------------------
# Config / resolve (printer.config_error)
# ---------------------------------------------------------------------------


def probe_section_required():
    return (
        "[klicky_probe] requires a [probe] section. "
        "Add [probe] pin/offsets before [klicky_probe]."
    )


def missing_required(missing_keys: Iterable[str]):
    keys = ", ".join(str(k) for k in missing_keys)
    return (
        "[klicky_probe] missing required options: %s. "
        "Set dock_x, dock_y, approach_x, approach_y, detach_x, detach_y "
        "(see config/sample-klicky.cfg)."
        % keys
    )


def missing_derived_setting(section: str, key: str) -> str:
    return (
        "[klicky_probe] cannot derive defaults: [%s] %s is missing. "
        "Set it in the printer config (Klicky does not invent machine limits)."
        % (section, key)
    )


def home_first_invalid(value=None):
    if value is None:
        return (
            "[klicky_probe] home_first must be auto, x, or y. "
            "Fix home_first in [klicky_probe]."
        )
    return (
        "[klicky_probe] home_first=%r is invalid (must be auto, x, or y). "
        "Fix home_first in [klicky_probe]."
        % (value,)
    )


def dock_servo_needs_name():
    return (
        "[klicky_probe] dock_servo: True requires servo_name. "
        "Set servo_name to your [servo ...] section name, or set dock_servo: False."
    )


def dock_servo_needs_angles():
    return (
        "[klicky_probe] dock_servo: True requires servo_deploy_angle and "
        "servo_retract_angle. Set both angles, or set dock_servo: False."
    )


def safe_z_home_conflict():
    return (
        "[klicky_probe] homing_override conflicts with [safe_z_home]. "
        "Remove the [safe_z_home] section from printer.cfg, or set "
        "homing_override: False."
    )


def homing_override_section_conflict():
    return (
        "[klicky_probe] homing_override conflicts with [homing_override]. "
        "Remove the [homing_override] section from printer.cfg, or set "
        "homing_override: False."
    )


def adaptive_needs_bed_mesh():
    return (
        "[klicky_probe] adaptive_mesh: True requires a [bed_mesh] section. "
        "Add [bed_mesh], or set adaptive_mesh: False."
    )


def adaptive_needs_exclude_object():
    return (
        "[klicky_probe] adaptive_mesh: True requires [exclude_object]. "
        "Klipper otherwise falls back to a full mesh (\"Using full mesh...\"). "
        "Add [exclude_object] and enable Label/Exclude Objects in the slicer, "
        "or set adaptive_mesh: False."
    )


def session_api_required():
    return (
        "[klicky_probe] auto_attach requires probe.start_probe_session "
        "(Klipper v0.13+ session API). Upgrade Klipper, or set "
        "auto_attach: False and use ATTACH_PROBE / DETACH_PROBE. "
        "See docs/install.md."
    )


def klipper_version_too_old(found, required):
    return (
        "[klicky_probe] Klipper %s is too old (need >= v%s). "
        "This plugin needs the probe session API (start_probe_session). "
        "Upgrade Klipper to v%s or newer."
        % (found, _fmt_ver(required), _fmt_ver(required))
    )


def klipper_version_unparseable(found, required):
    return (
        "[klicky_probe] cannot parse Klipper software_version %r "
        "(need >= v%s). Ensure Klipper reports a normal git describe "
        "version (msg.g. v0.13.0-707-g...), or upgrade Klipper."
        % (found, _fmt_ver(required))
    )


# ---------------------------------------------------------------------------
# Runtime (gcode.error / gcmd.error)
# ---------------------------------------------------------------------------


def home_xy_before_attach():
    return (
        "klicky: must home X and Y before ATTACH_PROBE. "
        "Run G28 X Y (or G28) first."
    )


def home_xy_before_detach():
    return (
        "klicky: must home X and Y before DETACH_PROBE. "
        "Run G28 X Y (or G28) first."
    )


def home_xy_before_ensure():
    return (
        "klicky: must home X and Y before ENSURE_PROBE_DOCKED. "
        "Run G28 X Y (or G28) first."
    )


def home_xy_before_z():
    return (
        "klicky: must home X and Y before Z. "
        "Run G28 X Y first, or use full G28."
    )


def home_xyz_before_probe_op():
    return (
        "klicky: must home X, Y and Z first (G28). "
        "PROBE_CALIBRATE / PROBE_ACCURACY need a fully homed toolhead."
    )


def probe_accuracy_xy_incomplete():
    return (
        "klicky: staging requires both X and Y (toolhead coordinates), "
        "or omit both to use config defaults (or derived bed center)."
    )


def log_probe_accuracy_stage(x: float, y: float) -> str:
    return "klicky: PROBE_ACCURACY stage → (%.3f, %.3f)" % (x, y)


def log_probe_calibrate_stage(x: float, y: float) -> str:
    return "klicky: PROBE_CALIBRATE stage → (%.3f, %.3f)" % (x, y)


def log_probe_calibrate_dock_before_paper() -> str:
    return (
        "klicky: docking probe before paper test "
        "(probe tip is below nozzle — leave attached would collide)"
    )


def orig_g28_unavailable():
    return (
        "klicky: original G28 handler is not available. "
        "Check that homing_override is enabled only once and Klipper loaded cleanly."
    )


def probe_query_unavailable():
    return (
        "klicky: cannot read probe attach state (QUERY_PROBE / last_query). "
        "Use a [probe] with endstop query support; check pin wiring."
    )


def attach_failed():
    return (
        "klicky: probe attach failed (switch still reports TRIGGERED ≈ docked). "
        "Check dock_x/y, approach_*, magnets, polarity; run QUERY_PROBE / "
        "GET_PROBE_STATUS; consider dock_retries."
    )


def dock_failed():
    return (
        "klicky: probe dock failed (switch still open ≈ attached). "
        "Check detach_*, dock position, magnets; run QUERY_PROBE; "
        "consider dock_retries."
    )


def probe_locked_ensure():
    return (
        "klicky: probe is locked attached. UNLOCK_PROBE first, or "
        "ENSURE_PROBE_DOCKED FORCE=1."
    )


def outside_bed(bed_min_x, bed_max_x, bed_min_y, bed_max_y):
    return (
        "klicky: toolhead appears outside bed "
        "(bed %.1f..%.1f x %.1f..%.1f). Move over the bed or fix "
        "bed_min_*/bed_max_* in [klicky_probe]."
        % (bed_min_x, bed_max_x, bed_min_y, bed_max_y)
    )


def probe_query_stale_warning():
    return "klicky: probe query failed; reporting last known state"


def probe_operation_failed():
    return "klicky: probe operation failed"


def probe_operation_failed_code(code: str):
    return "klicky: %s" % (code,)


def verify_failed(code: Optional[str]):
    """Map probe_state short codes → full user message."""
    if code == "attach_failed":
        return attach_failed()
    if code == "dock_failed":
        return dock_failed()
    if not code:
        return probe_operation_failed()
    return probe_operation_failed_code(code)


def geometry_mode_invalid(mode=None):
    if mode is None:
        return "klicky: geometry mode must be 'attach' or 'detach'"
    return "klicky: geometry mode %r must be 'attach' or 'detach'" % (mode,)


# ---------------------------------------------------------------------------
# Runtime info / status (gcmd.respond_info — not hard errors)
# ---------------------------------------------------------------------------


def probe_already_docked():
    return "klicky: probe already docked"


def probe_docked_ensure():
    return "klicky: probe docked (ENSURE_PROBE_DOCKED)"


def probe_calibrate_paper_ready():
    return (
        "klicky: probe docked — paper test with nozzle only "
        "(TESTZ / ACCEPT / ABORT; Mainsail/Fluidd manual probe UI)."
    )


def probe_status_report(attach_state, locked, session_depth, hold_depth):
    return (
        "klicky probe state: %s locked=%s session=%d hold=%d"
        % (attach_state, locked, session_depth, hold_depth)
    )


# ---------------------------------------------------------------------------
# G-code command help strings
# ---------------------------------------------------------------------------


def ui_macro_skip_exists(obj_name):
    return (
        "klicky: show_ui_macros skipped '%s' (already defined)" % (obj_name,)
    )


def help_attach_probe():
    return "Attach the Klicky probe from the dock"


def help_detach_probe():
    return "Detach/dock the Klicky probe"


def help_lock_probe():
    return "Lock probe so DETACH_PROBE is ignored until unlock"


def help_unlock_probe():
    return "Unlock probe attach state"


def help_get_probe_status():
    return "Report Klicky probe attach/lock state"


def help_ensure_probe_docked():
    return "Query probe and dock if attached (print-start / recovery; #230)"
