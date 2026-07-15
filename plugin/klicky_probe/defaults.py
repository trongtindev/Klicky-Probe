"""Resolve Klicky settings: user override wins, else derive from printer config."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from . import messages as msg


@dataclass
class PrinterSnapshot:
    """Subset of Klipper config used for defaults (tests + runtime)."""

    stepper_x_position_max: float = 300.0
    stepper_y_position_max: float = 300.0
    stepper_x_position_min: float = 0.0
    stepper_y_position_min: float = 0.0
    probe_x_offset: float = 0.0
    probe_y_offset: float = 0.0
    probe_z_offset: float = 0.0
    probe_speed: float = 5.0
    max_velocity: float = 300.0
    max_accel: float = 3000.0
    z_virtual_endstop: bool = False
    has_bed_mesh: bool = False
    has_exclude_object: bool = False
    has_safe_z_home: bool = False
    has_homing_override: bool = False


@dataclass
class KlickySettings:
    """Fully resolved runtime settings."""

    # Geometry (required from user)
    dock_x: float
    dock_y: float
    dock_z: Optional[float]
    approach_x: float
    approach_y: float
    approach_z: float
    detach_x: float
    detach_y: float
    detach_z: float
    approach2_x: float
    approach2_y: float
    approach2_z: float

    # Features
    homing_override: bool
    auto_attach: bool
    wrap_probe_calibrate: bool
    dock_before_z_home: bool
    disable_docking: bool
    verbose: bool
    debug: bool
    adaptive_mesh: bool
    adaptive_margin: float

    # Resolved motion / safety
    clearance_z: float
    z_hop_when_unhomed: bool
    travel_speed: float
    attach_speed: float
    detach_speed: float
    z_speed: float
    move_accel: float
    bed_min_x: float
    bed_min_y: float
    bed_max_x: float
    bed_max_y: float
    z_home_x: float
    z_home_y: float
    endstop_backoff_x: float
    endstop_backoff_y: float
    home_first: str  # auto | x | y
    safe_dock_travel: bool  # L-path to entry (#234)
    reseat_before_z_home: bool  # detach+attach if already "attached" (#231)

    # Optional behaviors
    park_after: bool
    park_x: Optional[float]
    park_y: Optional[float]
    park_z: Optional[float]  # None = XY only when parking
    umbilical: bool
    umbilical_x: float
    umbilical_y: float
    dock_servo: bool
    servo_name: Optional[str]
    servo_deploy_angle: Optional[float]
    servo_retract_angle: Optional[float]
    servo_delay_ms: float
    dock_retries: int

    # Derived flags from printer
    z_virtual_endstop: bool
    has_bed_mesh: bool
    has_exclude_object: bool


# Keys that must be supplied by the user (not derived)
REQUIRED_USER_KEYS = (
    "dock_x",
    "dock_y",
    "approach_x",
    "approach_y",
    "detach_x",
    "detach_y",
)


def _get(user: Dict[str, Any], key: str, default: Any) -> Any:
    if key in user and user[key] is not None:
        return user[key]
    return default


def derive_z_home_xy(printer: PrinterSnapshot) -> tuple:
    bed_cx = (printer.stepper_x_position_min + printer.stepper_x_position_max) / 2.0
    bed_cy = (printer.stepper_y_position_min + printer.stepper_y_position_max) / 2.0
    return bed_cx - printer.probe_x_offset, bed_cy - printer.probe_y_offset


def derive_clearance_z(printer: PrinterSnapshot, user_default: float = 25.0) -> float:
    # Keep a comfortable travel height; at least above typical probe stickout.
    from_probe = abs(printer.probe_z_offset) + 5.0
    return max(user_default, from_probe)


def resolve_settings(
    user: Dict[str, Any],
    printer: PrinterSnapshot,
) -> KlickySettings:
    """
    Merge user overrides with printer-derived defaults.

    `user` only contains keys the operator declared (or explicit Nones omitted).
    Missing optional keys are filled from `printer`.
    """
    missing = [k for k in REQUIRED_USER_KEYS if k not in user]
    if missing:
        raise ValueError(msg.missing_required(missing))

    z_home_x_d, z_home_y_d = derive_z_home_xy(printer)
    clearance_d = derive_clearance_z(printer)

    dock_z = user.get("dock_z", None)  # optional; None = gantry

    home_first = str(_get(user, "home_first", "auto")).lower()
    if home_first not in ("auto", "x", "y"):
        raise ValueError(msg.home_first_invalid(home_first))

    dock_servo = bool(_get(user, "dock_servo", False))
    servo_name = _get(user, "servo_name", None)
    servo_deploy = _get(user, "servo_deploy_angle", None)
    servo_retract = _get(user, "servo_retract_angle", None)
    if dock_servo:
        if not servo_name:
            raise ValueError(msg.dock_servo_needs_name())
        if servo_deploy is None or servo_retract is None:
            raise ValueError(msg.dock_servo_needs_angles())

    # Cap derived travel speed; full override still allowed via travel_speed.
    DEFAULT_TRAVEL_SPEED_CAP = 200.0
    travel = float(
        _get(
            user,
            "travel_speed",
            min(float(printer.max_velocity), DEFAULT_TRAVEL_SPEED_CAP),
        )
    )
    probe_speed = float(printer.probe_speed) if printer.probe_speed else 5.0

    return KlickySettings(
        dock_x=float(user["dock_x"]),
        dock_y=float(user["dock_y"]),
        dock_z=None if dock_z is None else float(dock_z),
        approach_x=float(user["approach_x"]),
        approach_y=float(user["approach_y"]),
        approach_z=float(_get(user, "approach_z", 0.0)),
        detach_x=float(user["detach_x"]),
        detach_y=float(user["detach_y"]),
        detach_z=float(_get(user, "detach_z", 0.0)),
        approach2_x=float(_get(user, "approach2_x", 0.0)),
        approach2_y=float(_get(user, "approach2_y", 0.0)),
        approach2_z=float(_get(user, "approach2_z", 0.0)),
        homing_override=bool(_get(user, "homing_override", True)),
        auto_attach=bool(_get(user, "auto_attach", True)),
        wrap_probe_calibrate=bool(_get(user, "wrap_probe_calibrate", True)),
        dock_before_z_home=bool(_get(user, "dock_before_z_home", True)),
        disable_docking=bool(_get(user, "disable_docking", False)),
        verbose=bool(_get(user, "verbose", True)),
        debug=bool(_get(user, "debug", False)),
        adaptive_mesh=bool(_get(user, "adaptive_mesh", False)),
        adaptive_margin=float(_get(user, "adaptive_margin", 5.0)),
        clearance_z=float(_get(user, "clearance_z", clearance_d)),
        z_hop_when_unhomed=bool(_get(user, "z_hop_when_unhomed", True)),
        travel_speed=travel,
        attach_speed=float(_get(user, "attach_speed", 50.0)),
        detach_speed=float(_get(user, "detach_speed", 75.0)),
        z_speed=float(_get(user, "z_speed", 20.0)),
        move_accel=float(_get(user, "move_accel", printer.max_accel)),
        bed_min_x=float(_get(user, "bed_min_x", printer.stepper_x_position_min)),
        bed_min_y=float(_get(user, "bed_min_y", printer.stepper_y_position_min)),
        bed_max_x=float(_get(user, "bed_max_x", printer.stepper_x_position_max)),
        bed_max_y=float(_get(user, "bed_max_y", printer.stepper_y_position_max)),
        z_home_x=float(_get(user, "z_home_x", z_home_x_d)),
        z_home_y=float(_get(user, "z_home_y", z_home_y_d)),
        endstop_backoff_x=float(_get(user, "endstop_backoff_x", 10.0)),
        endstop_backoff_y=float(_get(user, "endstop_backoff_y", 10.0)),
        home_first=home_first,
        safe_dock_travel=bool(_get(user, "safe_dock_travel", True)),
        reseat_before_z_home=bool(_get(user, "reseat_before_z_home", True)),
        park_after=bool(_get(user, "park_after", False)),
        park_x=_get(user, "park_x", None),
        park_y=_get(user, "park_y", None),
        park_z=_get(user, "park_z", None),
        umbilical=bool(_get(user, "umbilical", False)),
        umbilical_x=float(_get(user, "umbilical_x", 15.0)),
        umbilical_y=float(_get(user, "umbilical_y", 15.0)),
        dock_servo=dock_servo,
        servo_name=servo_name,
        servo_deploy_angle=None if servo_deploy is None else float(servo_deploy),
        servo_retract_angle=None if servo_retract is None else float(servo_retract),
        servo_delay_ms=float(_get(user, "servo_delay_ms", 250.0)),
        dock_retries=int(_get(user, "dock_retries", 0)),
        z_virtual_endstop=printer.z_virtual_endstop,
        has_bed_mesh=printer.has_bed_mesh,
        has_exclude_object=printer.has_exclude_object,
    )


def validate_homing_conflicts(
    settings: KlickySettings,
    printer: PrinterSnapshot,
) -> Optional[str]:
    """Return error message if homing ownership conflicts, else None."""
    if not settings.homing_override:
        return None
    if printer.has_safe_z_home:
        return msg.safe_z_home_conflict()
    if printer.has_homing_override:
        return msg.homing_override_section_conflict()
    return None
