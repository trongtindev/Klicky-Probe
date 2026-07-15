import pytest

from klicky_probe import messages as msg
from klicky_probe.defaults import (
    PrinterSnapshot,
    resolve_settings,
    validate_homing_conflicts,
)


def test_missing_required_raises(printer_voron_like):
    with pytest.raises(ValueError, match="missing required"):
        resolve_settings({"dock_x": 1}, printer_voron_like)


def test_derived_bed_and_speeds(minimal_user, printer_voron_like):
    s = resolve_settings(minimal_user, printer_voron_like)
    assert s.bed_min_x == 0.0
    assert s.bed_min_y == 0.0
    assert s.bed_max_x == 350.0
    assert s.bed_max_y == 350.0
    # Derived travel is capped at 200 even when max_velocity is higher.
    assert s.travel_speed == 200.0
    assert s.move_accel == 3000.0
    # center 175,175 minus probe offset y=25 → z_home y = 150
    assert s.z_home_x == 175.0
    assert s.z_home_y == 150.0
    assert s.dock_z is None
    assert s.adaptive_mesh is False
    assert s.adaptive_margin == 5.0
    assert s.safe_dock_travel is True
    assert s.reseat_before_z_home is True
    assert s.safe_xy_before_dock is True
    assert s.show_ui_macros is True
    # bed 0..350 → center 175,175 (toolhead frame, not probe-offset z_home)
    assert s.safe_xy_x == 175.0
    assert s.safe_xy_y == 175.0
    # accuracy / calibrate defaults = same formula as z_home default, move on
    assert s.probe_accuracy_move is True
    assert s.probe_accuracy_x == 175.0
    assert s.probe_accuracy_y == 150.0
    assert s.probe_calibrate_move is True
    assert s.probe_calibrate_x == 175.0
    assert s.probe_calibrate_y == 150.0


def test_show_ui_macros_override(minimal_user, printer_voron_like):
    user = dict(minimal_user)
    user["show_ui_macros"] = False
    s = resolve_settings(user, printer_voron_like)
    assert s.show_ui_macros is False


def test_probe_accuracy_xy_independent_of_z_home(minimal_user, printer_voron_like):
    user = dict(minimal_user)
    user["z_home_x"] = 5.0
    user["z_home_y"] = 6.0
    s = resolve_settings(user, printer_voron_like)
    assert s.z_home_x == 5.0
    assert s.z_home_y == 6.0
    assert s.probe_accuracy_x == 175.0
    assert s.probe_accuracy_y == 150.0
    assert s.probe_calibrate_x == 175.0
    assert s.probe_calibrate_y == 150.0


def test_probe_accuracy_overrides(minimal_user, printer_voron_like):
    user = dict(minimal_user)
    user["probe_accuracy_move"] = False
    user["probe_accuracy_x"] = 100.0
    user["probe_accuracy_y"] = 110.0
    s = resolve_settings(user, printer_voron_like)
    assert s.probe_accuracy_move is False
    assert s.probe_accuracy_x == 100.0
    assert s.probe_accuracy_y == 110.0


def test_probe_calibrate_xy_independent_of_accuracy(minimal_user, printer_voron_like):
    user = dict(minimal_user)
    user["probe_accuracy_x"] = 10.0
    user["probe_accuracy_y"] = 20.0
    s = resolve_settings(user, printer_voron_like)
    assert s.probe_accuracy_x == 10.0
    assert s.probe_accuracy_y == 20.0
    assert s.probe_calibrate_x == 175.0
    assert s.probe_calibrate_y == 150.0


def test_probe_calibrate_overrides(minimal_user, printer_voron_like):
    user = dict(minimal_user)
    user["probe_calibrate_move"] = False
    user["probe_calibrate_x"] = 90.0
    user["probe_calibrate_y"] = 95.0
    s = resolve_settings(user, printer_voron_like)
    assert s.probe_calibrate_move is False
    assert s.probe_calibrate_x == 90.0
    assert s.probe_calibrate_y == 95.0


def test_safe_xy_overrides(minimal_user, printer_voron_like):
    user = dict(minimal_user)
    user["safe_xy_x"] = 5.5
    user["safe_xy_y"] = 10.0
    s = resolve_settings(user, printer_voron_like)
    assert s.safe_xy_x == 5.5
    assert s.safe_xy_y == 10.0
    assert s.safe_xy_before_dock is True

    user["safe_xy_before_dock"] = False
    s = resolve_settings(user, printer_voron_like)
    assert s.safe_xy_before_dock is False
    assert s.safe_xy_x == 5.5
    assert s.safe_xy_y == 10.0


def test_travel_speed_respects_low_max_velocity(minimal_user):
    p = PrinterSnapshot(max_velocity=120.0)
    s = resolve_settings(minimal_user, p)
    assert s.travel_speed == 120.0


def test_user_override_wins(minimal_user, printer_voron_like):
    user = dict(minimal_user)
    user.update(
        {
            "bed_max_x": 200.0,
            "travel_speed": 100.0,
            "z_home_x": 10.0,
            "z_home_y": 20.0,
            "adaptive_mesh": True,
            "adaptive_margin": 8.0,
            "clearance_z": 30.0,
            "dock_z": 15.0,
            "safe_dock_travel": False,
            "reseat_before_z_home": False,
            "safe_xy_before_dock": False,
            "safe_xy_x": 12.0,
            "safe_xy_y": 34.0,
        }
    )
    s = resolve_settings(user, printer_voron_like)
    assert s.bed_max_x == 200.0
    assert s.travel_speed == 100.0
    assert s.z_home_x == 10.0
    assert s.z_home_y == 20.0
    # z_home override must not pull accuracy target (still derived center)
    assert s.probe_accuracy_x == 175.0
    assert s.probe_accuracy_y == 150.0
    assert s.adaptive_mesh is True
    assert s.adaptive_margin == 8.0
    assert s.clearance_z == 30.0
    assert s.dock_z == 15.0
    assert s.safe_dock_travel is False
    assert s.reseat_before_z_home is False
    assert s.safe_xy_before_dock is False
    assert s.safe_xy_x == 12.0
    assert s.safe_xy_y == 34.0


def test_dock_servo_requires_fields(minimal_user, printer_voron_like):
    user = dict(minimal_user)
    user["dock_servo"] = True
    with pytest.raises(ValueError, match="servo_name"):
        resolve_settings(user, printer_voron_like)
    user["servo_name"] = "dock"
    with pytest.raises(ValueError, match="servo_deploy_angle"):
        resolve_settings(user, printer_voron_like)
    user["servo_deploy_angle"] = 10
    user["servo_retract_angle"] = 90
    s = resolve_settings(user, printer_voron_like)
    assert s.dock_servo is True
    assert s.servo_name == "dock"


def test_invalid_home_first(minimal_user, printer_voron_like):
    user = dict(minimal_user)
    user["home_first"] = "z"
    with pytest.raises(ValueError, match="home_first"):
        resolve_settings(user, printer_voron_like)


def test_homing_conflict_safe_z_home(minimal_user, printer_voron_like):
    s = resolve_settings(minimal_user, printer_voron_like)
    p = PrinterSnapshot(has_safe_z_home=True)
    err = validate_homing_conflicts(s, p)
    assert err == msg.safe_z_home_conflict()
    assert "safe_z_home" in err


def test_homing_no_conflict_when_disabled(minimal_user, printer_voron_like):
    user = dict(minimal_user)
    user["homing_override"] = False
    s = resolve_settings(user, printer_voron_like)
    p = PrinterSnapshot(has_safe_z_home=True)
    assert validate_homing_conflicts(s, p) is None
