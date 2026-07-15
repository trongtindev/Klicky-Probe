"""Pure unit tests for early config validation."""

from __future__ import annotations

from dataclasses import replace

from klicky_probe import messages as msg
from klicky_probe.config_validate import validate_klicky_config
from klicky_probe.constants import (
    CONFIG_MIN_APPROACH_MM,
    CONFIG_MIN_DETACH_MM,
    DEFAULT_UMBILICAL_X,
    DEFAULT_UMBILICAL_Y,
)
from klicky_probe.defaults import resolve_settings
from klicky_probe.geometry import absolute_path_xy, dock_geometry_from_settings


def _validate(settings, printer, *, has_servo=True, has_session_api=True):
    """Test helper: host-style flags required by validate_klicky_config."""
    return validate_klicky_config(
        settings,
        printer,
        has_servo=has_servo,
        has_session_api=has_session_api,
    )


def _codes(result, *, severity=None):
    issues = result.issues if severity is None else [
        i for i in result.issues if i.severity == severity
    ]
    return [i.code for i in issues]


def test_valid_minimal_clean(minimal_user, printer_voron_like):
    s = resolve_settings(minimal_user, printer_voron_like)
    result = _validate(s, printer_voron_like)
    assert result.errors == []
    assert result.warnings == []


def test_sample_like_path_points_in_envelope(minimal_user, printer_voron_like):
    """Rear-dock sample: dock, entry, release, clear all inside 0..max."""
    s = resolve_settings(minimal_user, printer_voron_like)
    geo = dock_geometry_from_settings(s)
    labels = {lab for lab, _x, _y in absolute_path_xy(geo)}
    assert "attach_dock_xy" in labels or "detach_dock_xy" in labels
    assert "detach_release_xy" in labels
    assert "detach_clear_xy" in labels
    result = _validate(s, printer_voron_like)
    assert result.errors == []


def test_bed_range_invalid(minimal_user, printer_voron_like):
    user = dict(minimal_user)
    user["bed_min_x"] = 100.0
    user["bed_max_x"] = 50.0
    s = resolve_settings(user, printer_voron_like)
    result = _validate(s, printer_voron_like)
    assert "bed_range_invalid" in _codes(result, severity="error")
    assert "bed_min_x" in result.errors[0].message


def test_speed_non_positive(minimal_user, printer_voron_like):
    user = dict(minimal_user)
    user["attach_speed"] = 0.0
    s = resolve_settings(user, printer_voron_like)
    result = _validate(s, printer_voron_like)
    assert "speed_non_positive" in _codes(result, severity="error")
    assert "attach_speed" in result.errors[0].message


def test_clearance_z_non_positive(minimal_user, printer_voron_like):
    user = dict(minimal_user)
    user["clearance_z"] = 0.0
    s = resolve_settings(user, printer_voron_like)
    result = _validate(s, printer_voron_like)
    assert "clearance_z_non_positive" in _codes(result, severity="error")


def test_dock_retries_negative(minimal_user, printer_voron_like):
    user = dict(minimal_user)
    user["dock_retries"] = -1
    s = resolve_settings(user, printer_voron_like)
    result = _validate(s, printer_voron_like)
    assert "dock_retries_negative" in _codes(result, severity="error")


def test_park_incomplete(minimal_user, printer_voron_like):
    user = dict(minimal_user)
    user["park_after"] = True
    s = resolve_settings(user, printer_voron_like)
    result = _validate(s, printer_voron_like)
    assert "park_incomplete" in _codes(result, severity="error")
    assert "park_x" in result.errors[0].message


def test_park_complete_ok(minimal_user, printer_voron_like):
    user = dict(minimal_user)
    user["park_after"] = True
    user["park_x"] = 10.0
    user["park_y"] = 10.0
    s = resolve_settings(user, printer_voron_like)
    result = _validate(s, printer_voron_like)
    assert "park_incomplete" not in _codes(result)
    assert "staging_outside_machine" not in _codes(result, severity="error")


def test_zero_approach(minimal_user, printer_voron_like):
    user = dict(minimal_user)
    user["approach_x"] = 0.0
    user["approach_y"] = 0.0
    s = resolve_settings(user, printer_voron_like)
    result = _validate(s, printer_voron_like)
    assert "zero_approach" in _codes(result, severity="error")
    assert "1.0" in result.errors[0].message or str(CONFIG_MIN_APPROACH_MM) in result.errors[0].message


def test_zero_detach(minimal_user, printer_voron_like):
    user = dict(minimal_user)
    user["detach_x"] = 0.0
    user["detach_y"] = 0.0
    s = resolve_settings(user, printer_voron_like)
    result = _validate(s, printer_voron_like)
    assert "zero_detach" in _codes(result, severity="error")
    assert "1.0" in result.errors[0].message or str(CONFIG_MIN_DETACH_MM) in result.errors[0].message


def test_zero_attach_entry_when_approach2_cancels(minimal_user, printer_voron_like):
    user = dict(minimal_user)
    user["approach_x"] = 0.0
    user["approach_y"] = 30.0
    user["approach2_x"] = 0.0
    user["approach2_y"] = -30.0  # cancels approach → entry = dock
    s = resolve_settings(user, printer_voron_like)
    result = _validate(s, printer_voron_like)
    assert "zero_attach_entry_offset" in _codes(result, severity="error")


def test_dock_path_outside_machine_dock(minimal_user, printer_voron_like):
    user = dict(minimal_user)
    user["dock_x"] = -50.0
    user["dock_y"] = 300.0
    s = resolve_settings(user, printer_voron_like)
    result = _validate(s, printer_voron_like)
    assert "dock_path_outside_machine" in _codes(result, severity="error")
    assert "machine envelope" in result.errors[0].message


def test_dock_path_outside_machine_entry(minimal_user, printer_voron_like):
    # approach_y < 0 with dock at y max → entry past position_max.
    user = dict(minimal_user)
    user["approach_x"] = 0.0
    user["approach_y"] = -30.0
    user["dock_y"] = 350.0
    s = resolve_settings(user, printer_voron_like)
    result = _validate(s, printer_voron_like)
    assert "dock_path_outside_machine" in _codes(result, severity="error")


def test_dock_path_outside_machine_release(minimal_user, printer_voron_like):
    # dock at X=0 with detach_x=-40 → release at -40 (outside).
    user = dict(minimal_user)
    user["dock_x"] = 0.0
    user["detach_x"] = -40.0
    user["detach_y"] = 0.0
    s = resolve_settings(user, printer_voron_like)
    result = _validate(s, printer_voron_like)
    assert "dock_path_outside_machine" in _codes(result, severity="error")
    assert any("release" in e.message or "detach_release" in e.message for e in result.errors)


def test_staging_umbilical_outside(minimal_user, printer_voron_like):
    user = dict(minimal_user)
    user["umbilical"] = True
    user["umbilical_x"] = -10.0
    user["umbilical_y"] = 10.0
    s = resolve_settings(user, printer_voron_like)
    result = _validate(s, printer_voron_like)
    assert "staging_outside_machine" in _codes(result, severity="error")
    assert "umbilical" in result.errors[0].message


def test_probe_stage_outside_bed(minimal_user, printer_voron_like):
    user = dict(minimal_user)
    user["z_home_x"] = -20.0
    user["z_home_y"] = 100.0
    s = resolve_settings(user, printer_voron_like)
    result = _validate(s, printer_voron_like)
    assert "probe_stage_outside_bed" in _codes(result, severity="error")
    assert "z_home" in result.errors[0].message


def test_accuracy_bed_skipped_when_auto_attach_off(minimal_user, printer_voron_like):
    user = dict(minimal_user)
    user["auto_attach"] = False
    user["probe_accuracy_x"] = -20.0
    user["probe_accuracy_y"] = 100.0
    s = resolve_settings(user, printer_voron_like)
    result = _validate(s, printer_voron_like)
    # z_home still checked when homing_override; accuracy must not force error.
    accuracy_msgs = [e.message for e in result.errors if "probe_accuracy" in e.message]
    assert accuracy_msgs == []


def test_homing_conflict_via_facade(minimal_user, printer_voron_like):
    s = resolve_settings(minimal_user, printer_voron_like)
    p = replace(printer_voron_like, has_safe_z_home=True)
    result = _validate(s, p)
    assert "homing_conflict" in _codes(result, severity="error")
    assert result.errors[0].message == msg.safe_z_home_conflict()


def test_adaptive_needs_bed_mesh(minimal_user, printer_voron_like):
    user = dict(minimal_user)
    user["adaptive_mesh"] = True
    s = resolve_settings(user, printer_voron_like)
    p = replace(printer_voron_like, has_bed_mesh=False, has_exclude_object=True)
    result = _validate(s, p)
    assert "adaptive_needs_bed_mesh" in _codes(result, severity="error")


def test_adaptive_needs_exclude_object(minimal_user, printer_voron_like):
    user = dict(minimal_user)
    user["adaptive_mesh"] = True
    s = resolve_settings(user, printer_voron_like)
    p = replace(printer_voron_like, has_bed_mesh=True, has_exclude_object=False)
    result = _validate(s, p)
    assert "adaptive_needs_exclude_object" in _codes(result, severity="error")


def test_session_api_required(minimal_user, printer_voron_like):
    s = resolve_settings(minimal_user, printer_voron_like)
    result = _validate(s, printer_voron_like, has_session_api=False)
    assert "session_api_required" in _codes(result, severity="error")


def test_session_api_ok_when_present(minimal_user, printer_voron_like):
    s = resolve_settings(minimal_user, printer_voron_like)
    result = _validate(s, printer_voron_like, has_session_api=True)
    assert "session_api_required" not in _codes(result)


def test_servo_missing(minimal_user, printer_voron_like):
    user = dict(minimal_user)
    user["dock_servo"] = True
    user["servo_name"] = "dock"
    user["servo_deploy_angle"] = 10.0
    user["servo_retract_angle"] = 90.0
    s = resolve_settings(user, printer_voron_like)
    result = _validate(s, printer_voron_like, has_servo=False)
    assert "servo_missing" in _codes(result, severity="error")
    assert "dock" in result.errors[0].message


def test_umbilical_equals_safe_xy_warning(minimal_user, printer_voron_like):
    user = dict(minimal_user)
    user["umbilical"] = True
    user["umbilical_x"] = 50.0
    user["umbilical_y"] = 50.0
    user["safe_xy_before_dock"] = True
    user["safe_xy_x"] = 50.0
    user["safe_xy_y"] = 50.0
    s = resolve_settings(user, printer_voron_like)
    result = _validate(s, printer_voron_like)
    assert result.errors == []
    assert "umbilical_equals_safe_xy" in _codes(result, severity="warning")


def test_umbilical_placeholder_warning(minimal_user, printer_voron_like):
    user = dict(minimal_user)
    user["umbilical"] = True
    s = resolve_settings(user, printer_voron_like)
    assert s.umbilical_x == DEFAULT_UMBILICAL_X
    assert s.umbilical_y == DEFAULT_UMBILICAL_Y
    result = _validate(s, printer_voron_like)
    assert "umbilical_placeholder" in _codes(result, severity="warning")


def test_disable_docking_virtual_z_warning(minimal_user, printer_voron_like):
    user = dict(minimal_user)
    user["disable_docking"] = True
    s = resolve_settings(user, printer_voron_like)
    p = replace(printer_voron_like, z_virtual_endstop=True)
    result = _validate(s, p)
    assert "disable_docking_virtual_z" in _codes(result, severity="warning")


def test_homing_override_off_virtual_z_warning(minimal_user, printer_voron_like):
    user = dict(minimal_user)
    user["homing_override"] = False
    s = resolve_settings(user, printer_voron_like)
    p = replace(printer_voron_like, z_virtual_endstop=True)
    result = _validate(s, p)
    assert "homing_override_off_virtual_z" in _codes(result, severity="warning")
    assert result.errors == []


def test_wrap_calibrate_off_warning(minimal_user, printer_voron_like):
    user = dict(minimal_user)
    user["wrap_probe_calibrate"] = False
    s = resolve_settings(user, printer_voron_like)
    result = _validate(s, printer_voron_like)
    assert "wrap_calibrate_off" in _codes(result, severity="warning")


def test_speed_above_printer_max_warning(minimal_user, printer_voron_like):
    user = dict(minimal_user)
    user["travel_speed"] = 9999.0
    s = resolve_settings(user, printer_voron_like)
    result = _validate(s, printer_voron_like)
    assert "speed_above_printer_max" in _codes(result, severity="warning")


def test_clearance_below_probe_warning(minimal_user, printer_voron_like):
    p = replace(printer_voron_like, probe_z_offset=-20.0)
    user = dict(minimal_user)
    user["clearance_z"] = 10.0  # below |-20| + 5 = 25
    s = resolve_settings(user, p)
    result = _validate(s, p)
    assert "clearance_below_probe" in _codes(result, severity="warning")


def test_config_validation_failed_join():
    joined = msg.config_validation_failed(
        ["[klicky_probe] err one", "[klicky_probe] err two"]
    )
    assert "2 errors" in joined
    assert "- err one" in joined
    assert "- err two" in joined
    assert joined.count("[klicky_probe]") == 1
    assert msg.config_validation_failed(["only"]) == "only"


def test_collects_multiple_errors(minimal_user, printer_voron_like):
    user = dict(minimal_user)
    user["approach_x"] = 0.0
    user["approach_y"] = 0.0
    user["detach_x"] = 0.0
    user["detach_y"] = 0.0
    user["park_after"] = True
    s = resolve_settings(user, printer_voron_like)
    result = _validate(s, printer_voron_like)
    codes = _codes(result, severity="error")
    assert "zero_approach" in codes
    assert "zero_detach" in codes
    assert "park_incomplete" in codes
