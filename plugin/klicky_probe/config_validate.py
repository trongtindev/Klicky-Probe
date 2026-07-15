"""Early [klicky_probe] config validation (pure logic, no Klipper imports).

Hard errors block connect; warnings are suspicious / policy risks with fix text.
Host emits warnings and raises config_error for errors after resolve_settings.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, List, Sequence, Tuple

from . import messages as msg
from .constants import (
    CONFIG_CLEARANCE_PROBE_PAD_MM,
    CONFIG_MIN_APPROACH_MM,
    CONFIG_MIN_DETACH_MM,
    CONFIG_SEVERITY_ERROR,
    CONFIG_SEVERITY_WARNING,
    CONFIG_XY_EPS_MM,
    DEFAULT_UMBILICAL_X,
    DEFAULT_UMBILICAL_Y,
)
from .defaults import KlickySettings, PrinterSnapshot, validate_homing_conflicts
from .geometry import absolute_path_xy, dock_geometry_from_settings

# Bounds: (xmin, xmax, ymin, ymax)
Bounds = Tuple[float, float, float, float]
# Named point: (label, x, y)
NamedXY = Tuple[str, float, float]
MsgFn = Callable[[str, float, float, float, float, float, float], str]


@dataclass(frozen=True)
class ConfigIssue:
    """One validation finding."""

    severity: str  # CONFIG_SEVERITY_ERROR | CONFIG_SEVERITY_WARNING
    code: str
    message: str


@dataclass
class ValidationResult:
    """Collected config issues (errors and warnings)."""

    issues: List[ConfigIssue] = field(default_factory=list)

    def add(self, severity: str, code: str, message: str) -> None:
        self.issues.append(ConfigIssue(severity=severity, code=code, message=message))

    def error(self, code: str, message: str) -> None:
        self.add(CONFIG_SEVERITY_ERROR, code, message)

    def warning(self, code: str, message: str) -> None:
        self.add(CONFIG_SEVERITY_WARNING, code, message)

    @property
    def errors(self) -> List[ConfigIssue]:
        return [i for i in self.issues if i.severity == CONFIG_SEVERITY_ERROR]

    @property
    def warnings(self) -> List[ConfigIssue]:
        return [i for i in self.issues if i.severity == CONFIG_SEVERITY_WARNING]


def _xy_in_range(x: float, y: float, bounds: Bounds) -> bool:
    xmin, xmax, ymin, ymax = bounds
    return xmin <= x <= xmax and ymin <= y <= ymax


def _require_xy_in(
    result: ValidationResult,
    code: str,
    label: str,
    x: float,
    y: float,
    bounds: Bounds,
    msg_fn: MsgFn,
) -> None:
    if not _xy_in_range(x, y, bounds):
        xmin, xmax, ymin, ymax = bounds
        result.error(code, msg_fn(label, x, y, xmin, xmax, ymin, ymax))


def _require_points_in(
    result: ValidationResult,
    code: str,
    points: Sequence[NamedXY],
    bounds: Bounds,
    msg_fn: MsgFn,
) -> None:
    for label, x, y in points:
        _require_xy_in(result, code, label, x, y, bounds, msg_fn)


def _machine_bounds(printer: PrinterSnapshot) -> Bounds:
    return (
        printer.stepper_x_position_min,
        printer.stepper_x_position_max,
        printer.stepper_y_position_min,
        printer.stepper_y_position_max,
    )


def _bed_bounds(s: KlickySettings) -> Bounds:
    return (s.bed_min_x, s.bed_max_x, s.bed_min_y, s.bed_max_y)


def _check_numeric(result: ValidationResult, s: KlickySettings) -> None:
    if s.bed_min_x >= s.bed_max_x:
        result.error(
            "bed_range_invalid",
            msg.bed_range_invalid("x", s.bed_min_x, s.bed_max_x),
        )
    if s.bed_min_y >= s.bed_max_y:
        result.error(
            "bed_range_invalid",
            msg.bed_range_invalid("y", s.bed_min_y, s.bed_max_y),
        )

    for name, value in (
        ("travel_speed", s.travel_speed),
        ("attach_speed", s.attach_speed),
        ("detach_speed", s.detach_speed),
        ("z_speed", s.z_speed),
        ("move_accel", s.move_accel),
    ):
        if float(value) <= 0.0:
            result.error("speed_non_positive", msg.speed_non_positive(name, value))

    if s.clearance_z <= 0.0:
        result.error(
            "clearance_z_non_positive",
            msg.clearance_z_non_positive(s.clearance_z),
        )

    if s.dock_retries < 0:
        result.error(
            "dock_retries_negative",
            msg.dock_retries_negative(s.dock_retries),
        )

    if s.park_after and (s.park_x is None or s.park_y is None):
        result.error("park_incomplete", msg.park_incomplete())


def _check_vectors(result: ValidationResult, s: KlickySettings) -> None:
    approach_len = math.hypot(s.approach_x, s.approach_y)
    if approach_len < CONFIG_MIN_APPROACH_MM:
        result.error(
            "zero_approach",
            msg.zero_approach(approach_len, CONFIG_MIN_APPROACH_MM),
        )

    detach_len = math.hypot(s.detach_x, s.detach_y)
    if detach_len < CONFIG_MIN_DETACH_MM:
        result.error(
            "zero_detach",
            msg.zero_detach(detach_len, CONFIG_MIN_DETACH_MM),
        )

    # Attach entry uses approach + approach2; near-cancel collapses onto dock.
    total_ax = s.approach_x + s.approach2_x
    total_ay = s.approach_y + s.approach2_y
    attach_offset = math.hypot(total_ax, total_ay)
    if attach_offset < CONFIG_MIN_APPROACH_MM and approach_len >= CONFIG_MIN_APPROACH_MM:
        result.error(
            "zero_attach_entry_offset",
            msg.zero_attach_entry_offset(attach_offset, CONFIG_MIN_APPROACH_MM),
        )


def _staging_machine_points(s: KlickySettings) -> List[NamedXY]:
    points: List[NamedXY] = []
    if s.umbilical:
        points.append(("umbilical_x/y", s.umbilical_x, s.umbilical_y))
    if s.safe_xy_before_dock:
        points.append(("safe_xy_x/y", s.safe_xy_x, s.safe_xy_y))
    if s.park_after and s.park_x is not None and s.park_y is not None:
        points.append(("park_x/y", float(s.park_x), float(s.park_y)))
    return points


def _check_machine_points(
    result: ValidationResult,
    s: KlickySettings,
    printer: PrinterSnapshot,
) -> None:
    bounds = _machine_bounds(printer)
    geo = dock_geometry_from_settings(s)
    # All absolute XY from attach/detach planners (dock, entry, release, clear, …).
    _require_points_in(
        result,
        "dock_path_outside_machine",
        absolute_path_xy(geo),
        bounds,
        msg.point_outside_machine,
    )
    _require_points_in(
        result,
        "staging_outside_machine",
        _staging_machine_points(s),
        bounds,
        msg.point_outside_machine,
    )


def _bed_staging_points(s: KlickySettings) -> List[NamedXY]:
    """Probe-over-bed targets that are actually used by enabled features."""
    points: List[NamedXY] = []
    if s.homing_override:
        points.append(("z_home_x/y", s.z_home_x, s.z_home_y))
    # Accuracy wrap only installs when auto_attach.
    if s.auto_attach and s.probe_accuracy_move:
        points.append(("probe_accuracy_x/y", s.probe_accuracy_x, s.probe_accuracy_y))
    if s.wrap_probe_calibrate and s.probe_calibrate_move:
        points.append(
            ("probe_calibrate_x/y", s.probe_calibrate_x, s.probe_calibrate_y)
        )
    return points


def _check_bed_staging(result: ValidationResult, s: KlickySettings) -> None:
    if s.bed_min_x >= s.bed_max_x or s.bed_min_y >= s.bed_max_y:
        return
    _require_points_in(
        result,
        "probe_stage_outside_bed",
        _bed_staging_points(s),
        _bed_bounds(s),
        msg.point_outside_bed,
    )


def _check_feature_deps(
    result: ValidationResult,
    s: KlickySettings,
    printer: PrinterSnapshot,
    *,
    has_servo: bool,
    has_session_api: bool,
) -> None:
    conflict = validate_homing_conflicts(s, printer)
    if conflict:
        result.error("homing_conflict", conflict)

    if s.adaptive_mesh and not printer.has_bed_mesh:
        result.error("adaptive_needs_bed_mesh", msg.adaptive_needs_bed_mesh())
    if s.adaptive_mesh and not printer.has_exclude_object:
        result.error(
            "adaptive_needs_exclude_object",
            msg.adaptive_needs_exclude_object(),
        )

    if s.auto_attach and not has_session_api:
        result.error("session_api_required", msg.session_api_required())

    if s.dock_servo and not has_servo:
        result.error(
            "servo_missing",
            msg.servo_missing(str(s.servo_name or "")),
        )


def _check_warnings(
    result: ValidationResult,
    s: KlickySettings,
    printer: PrinterSnapshot,
) -> None:
    if (
        s.umbilical
        and s.safe_xy_before_dock
        and math.hypot(s.umbilical_x - s.safe_xy_x, s.umbilical_y - s.safe_xy_y)
        <= CONFIG_XY_EPS_MM
    ):
        result.warning(
            "umbilical_equals_safe_xy",
            msg.umbilical_equals_safe_xy(s.umbilical_x, s.umbilical_y),
        )

    if s.umbilical and (
        abs(s.umbilical_x - DEFAULT_UMBILICAL_X) <= CONFIG_XY_EPS_MM
        and abs(s.umbilical_y - DEFAULT_UMBILICAL_Y) <= CONFIG_XY_EPS_MM
    ):
        result.warning(
            "umbilical_placeholder",
            msg.umbilical_placeholder(s.umbilical_x, s.umbilical_y),
        )

    if s.disable_docking and printer.z_virtual_endstop:
        result.warning(
            "disable_docking_virtual_z",
            msg.disable_docking_virtual_z(),
        )

    if not s.homing_override and printer.z_virtual_endstop:
        result.warning(
            "homing_override_off_virtual_z",
            msg.homing_override_off_virtual_z(),
        )

    # Intentional: stock paper-test with probe mounted is unsafe for Klicky.
    if not s.wrap_probe_calibrate:
        result.warning("wrap_calibrate_off", msg.wrap_calibrate_off())

    if s.travel_speed > printer.max_velocity:
        result.warning(
            "speed_above_printer_max",
            msg.speed_above_printer_max(
                "travel_speed", s.travel_speed, printer.max_velocity
            ),
        )

    recommended = abs(printer.probe_z_offset) + CONFIG_CLEARANCE_PROBE_PAD_MM
    if s.clearance_z < recommended:
        result.warning(
            "clearance_below_probe",
            msg.clearance_below_probe(s.clearance_z, recommended),
        )


def validate_klicky_config(
    settings: KlickySettings,
    printer: PrinterSnapshot,
    *,
    has_servo: bool,
    has_session_api: bool,
) -> ValidationResult:
    """Validate resolved settings against printer snapshot.

    ``has_servo`` / ``has_session_api`` are required host capability flags.
    Checks only apply when the related feature is enabled (``dock_servo`` /
    ``auto_attach``). Callers must pass real discovery results — no silent
    defaults that hide a missing host probe.
    """
    result = ValidationResult()
    _check_numeric(result, settings)
    _check_vectors(result, settings)
    _check_machine_points(result, settings, printer)
    _check_bed_staging(result, settings)
    _check_feature_deps(
        result,
        settings,
        printer,
        has_servo=has_servo,
        has_session_api=has_session_api,
    )
    _check_warnings(result, settings, printer)
    return result
