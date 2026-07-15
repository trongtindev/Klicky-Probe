"""User-facing klicky_probe error messages (WHAT + WHY + HOW FIX).

All messages are functions for a uniform call style: E.name() / E.name(args).
"""

from __future__ import annotations

from typing import Iterable, Optional, Sequence, Tuple, Union

from .klipper_version import format_version_tuple

VersionLike = Union[Tuple[int, int, int], Sequence[int]]


def _fmt_ver(required: VersionLike) -> str:
    if isinstance(required, tuple) and len(required) >= 3:
        return format_version_tuple((int(required[0]), int(required[1]), int(required[2])))
    return str(required)


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
        "version (e.g. v0.13.0-707-g...), or upgrade Klipper."
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


def probe_calibrate_leave_attached():
    return (
        "klicky: leave probe attached for paper test, then DETACH_PROBE "
        "(or DOCK=1). Use PROBE_LOCK=1 to block auto-dock."
    )


def probe_status_report(attach_state, locked, session_depth, hold_depth):
    return (
        "klicky probe state: %s locked=%s session=%d hold=%d"
        % (attach_state, locked, session_depth, hold_depth)
    )
