"""Dock attach/detach waypoint planning (pure logic, no Klipper imports)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple


# Speed roles used by the executor
SPEED_TRAVEL = "travel"
SPEED_ATTACH = "attach"
SPEED_DETACH = "detach"
SPEED_Z = "z"


@dataclass(frozen=True)
class DockGeometry:
    dock_x: float
    dock_y: float
    dock_z: Optional[float]  # None = gantry/frame mount (Z not fixed at dock)
    approach_x: float
    approach_y: float
    approach_z: float
    detach_x: float
    detach_y: float
    detach_z: float
    approach2_x: float = 0.0
    approach2_y: float = 0.0
    approach2_z: float = 0.0

    @property
    def is_gantry_dock(self) -> bool:
        return self.dock_z is None


@dataclass(frozen=True)
class Waypoint:
    """A planned move. z=None means leave Z unchanged."""

    x: Optional[float]
    y: Optional[float]
    z: Optional[float]
    speed: str
    label: str = ""


def _xy(x: float, y: float, speed: str, label: str) -> Waypoint:
    return Waypoint(x=x, y=y, z=None, speed=speed, label=label)


def _xyz(x: float, y: float, z: float, speed: str, label: str) -> Waypoint:
    return Waypoint(x=x, y=y, z=z, speed=speed, label=label)


def _z(z: float, speed: str, label: str) -> Waypoint:
    return Waypoint(x=None, y=None, z=z, speed=speed, label=label)


def attach_entry_xy(geo: DockGeometry) -> Tuple[float, float]:
    """Attach staging point: dock - approach - approach2."""
    return (
        geo.dock_x - geo.approach_x - geo.approach2_x,
        geo.dock_y - geo.approach_y - geo.approach2_y,
    )


def detach_entry_xy(geo: DockGeometry) -> Tuple[float, float]:
    """Detach staging point: dock - approach."""
    return (
        geo.dock_x - geo.approach_x,
        geo.dock_y - geo.approach_y,
    )


def entry_xy(geo: DockGeometry, mode: str) -> Tuple[float, float]:
    """Return dock entry XY for attach or detach."""
    if mode == "attach":
        return attach_entry_xy(geo)
    if mode == "detach":
        return detach_entry_xy(geo)
    from . import errors as E

    raise ValueError(E.geometry_mode_invalid(mode))


def travel_to_entry_waypoints(
    geo: DockGeometry,
    cur_x: float,
    cur_y: float,
    *,
    mode: str,
    enabled: bool = True,
    epsilon: float = 0.01,
) -> List[Waypoint]:
    """
    Axis-aligned travel to dock entry (issue #234 / #278).

    Avoids a single diagonal that can clip the dock body when the toolhead is
    behind or off-axis. Dominant approach axis decides order:

    - |approach_x| >= |approach_y|: align Y first, then X (rear docks)
    - otherwise: align X first, then Y (side docks)

    For attach, approach includes approach2 for entry and dominance.
    When enabled is False, returns a single direct move to entry (legacy).
    Zero-length legs are omitted.
    """
    entry_x, entry_y = entry_xy(geo, mode)
    if not enabled:
        if abs(cur_x - entry_x) <= epsilon and abs(cur_y - entry_y) <= epsilon:
            return []
        return [_xy(entry_x, entry_y, SPEED_TRAVEL, "travel_entry_xy")]

    ax = geo.approach_x + (geo.approach2_x if mode == "attach" else 0.0)
    ay = geo.approach_y + (geo.approach2_y if mode == "attach" else 0.0)
    align_y_first = abs(ax) >= abs(ay)

    w: List[Waypoint] = []
    x, y = cur_x, cur_y

    if align_y_first:
        if abs(y - entry_y) > epsilon:
            w.append(_xy(x, entry_y, SPEED_TRAVEL, "travel_align_y"))
            y = entry_y
        if abs(x - entry_x) > epsilon:
            w.append(_xy(entry_x, entry_y, SPEED_TRAVEL, "travel_entry_xy"))
    else:
        if abs(x - entry_x) > epsilon:
            w.append(_xy(entry_x, y, SPEED_TRAVEL, "travel_align_x"))
            x = entry_x
        if abs(y - entry_y) > epsilon:
            w.append(_xy(entry_x, entry_y, SPEED_TRAVEL, "travel_entry_xy"))

    return w


def attach_waypoints(geo: DockGeometry) -> List[Waypoint]:
    """
    Plan toolhead moves to attach the probe (excluding clearance/park/servo).

    Matches historical Klicky attach path:
    entry (dock - approach - approach2) → optional Z steps → intermediate
    (dock - approach2) → dock → exit (dock - approach).

    Executor should prepend travel_to_entry_waypoints and may skip the first
    entry XY when already staged at entry.
    """
    dx, dy = geo.dock_x, geo.dock_y
    ax, ay, az = geo.approach_x, geo.approach_y, geo.approach_z
    a2x, a2y, a2z = geo.approach2_x, geo.approach2_y, geo.approach2_z
    w: List[Waypoint] = []

    ex, ey = attach_entry_xy(geo)
    # Entry XY (may be skipped by executor after travel_to_entry)
    w.append(_xy(ex, ey, SPEED_TRAVEL, "attach_entry_xy"))

    if not geo.is_gantry_dock:
        assert geo.dock_z is not None
        dz = geo.dock_z
        w.append(_z(dz - az - a2z, SPEED_ATTACH, "attach_entry_z2"))
        w.append(_z(dz - az, SPEED_ATTACH, "attach_entry_z1"))

    # Deploy dock happens here in executor (between entry and dock)

    if not geo.is_gantry_dock:
        assert geo.dock_z is not None
        w.append(_z(geo.dock_z, SPEED_ATTACH, "attach_dock_z"))

    # Skip intermediate when approach2 is zero (same point as dock).
    if a2x != 0.0 or a2y != 0.0:
        w.append(_xy(dx - a2x, dy - a2y, SPEED_ATTACH, "attach_intermediate_xy"))
    w.append(_xy(dx, dy, SPEED_ATTACH, "attach_dock_xy"))

    if not geo.is_gantry_dock:
        assert geo.dock_z is not None
        w.append(_z(geo.dock_z - az, SPEED_Z, "attach_exit_z"))

    w.append(_xy(dx - ax, dy - ay, SPEED_DETACH, "attach_exit_xy"))
    # Retract dock in executor
    return w


def detach_waypoints(geo: DockGeometry) -> List[Waypoint]:
    """
    Plan toolhead moves to dock/detach the probe (excluding clearance/park/servo).

    Entry (dock - approach) → dock → release (dock + detach) →
    clear (dock + detach - approach).
    """
    dx, dy = geo.dock_x, geo.dock_y
    ax, ay, az = geo.approach_x, geo.approach_y, geo.approach_z
    rx, ry, rz = geo.detach_x, geo.detach_y, geo.detach_z
    w: List[Waypoint] = []

    w.append(_xy(dx - ax, dy - ay, SPEED_TRAVEL, "detach_entry_xy"))

    if not geo.is_gantry_dock:
        assert geo.dock_z is not None
        w.append(_z(geo.dock_z - az, SPEED_ATTACH, "detach_entry_z"))

    # Deploy dock in executor

    w.append(_xy(dx, dy, SPEED_ATTACH, "detach_dock_xy"))
    if not geo.is_gantry_dock:
        assert geo.dock_z is not None
        w.append(_z(geo.dock_z, SPEED_ATTACH, "detach_dock_z"))

    if not geo.is_gantry_dock:
        assert geo.dock_z is not None
        w.append(_z(geo.dock_z + rz, SPEED_DETACH, "detach_release_z"))

    w.append(_xy(dx + rx, dy + ry, SPEED_DETACH, "detach_release_xy"))
    w.append(
        _xy(
            dx + rx - ax,
            dy + ry - ay,
            SPEED_DETACH,
            "detach_clear_xy",
        )
    )
    # Retract dock in executor
    return w


def clearance_needed(current_z: Optional[float], clearance_z: float) -> bool:
    """True if toolhead should raise to clearance_z before travel."""
    if current_z is None:
        return True
    return current_z < clearance_z


def waypoints_as_tuples(waypoints: Sequence[Waypoint]) -> List[Tuple]:
    """Stable form for golden tests: (x, y, z, speed, label)."""
    return [(wp.x, wp.y, wp.z, wp.speed, wp.label) for wp in waypoints]
