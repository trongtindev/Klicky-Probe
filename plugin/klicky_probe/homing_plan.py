"""Homing axis order and Z attach/dock decisions (pure logic)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .dock_policy import parse_dock_intent


@dataclass(frozen=True)
class HomingRequest:
    """Which axes the user asked to home. Empty axes = home all."""

    home_x: bool
    home_y: bool
    home_z: bool
    leave_probe_attached: bool = False  # PROBE_LOCK / DOCK=0
    lock_probe: bool = False  # PROBE_LOCK (stay locked after leave)

    @classmethod
    def from_params(cls, params: dict) -> "HomingRequest":
        """Parse G28-like params: keys X/Y/Z present means home those; none = all."""
        has_x = "X" in params or "x" in params
        has_y = "Y" in params or "y" in params
        has_z = "Z" in params or "z" in params
        if not (has_x or has_y or has_z):
            has_x = has_y = has_z = True
        intent = parse_dock_intent(params)
        # force_dock on G28 means normal dock-after-Z (leave_attached False)
        leave = intent.leave_attached and not intent.force_dock
        lock = leave and intent.lock
        return cls(
            home_x=has_x,
            home_y=has_y,
            home_z=has_z,
            leave_probe_attached=leave,
            lock_probe=lock,
        )


@dataclass(frozen=True)
class HomingPlan:
    """Ordered steps the executor should run."""

    # Order of XY homing: list of 'x' and/or 'y'
    xy_order: List[str]
    home_z: bool
    # Before Z home:
    attach_before_z: bool
    detach_before_z: bool
    # After Z home:
    detach_after_z: bool
    lock_after_attach: bool
    force_full_home: bool  # Z requested but XY not homed
    reset_lock: bool  # full G28 all axes
    # Virtual Z: force detach+attach if query says already attached (#231)
    require_fresh_attach: bool = False


def plan_homing(
    request: HomingRequest,
    *,
    xy_homed: bool,
    home_first: str,
    approach_y: float,
    z_virtual_endstop: bool,
    dock_before_z_home: bool,
    reseat_before_z_home: bool = True,
) -> HomingPlan:
    """
    Build a homing plan.

    Ownership (virtual Z)
    ---------------------
    The **homing plan owns** attach-before-Z and dock-after-Z. Klipper stock
    G28 Z opens a probe session, but that session must not decide dock for G28
    (executor holds session auto-dock during stock G28 Z). Session hooks remain
    the owner for bare PROBE / mesh / leveling when no outer plan exists.

    home_first:
      - auto: if approach_y == 0, home Y first (dock on Y extrusion style), else X first
      - x / y: force that axis first

    reseat_before_z_home:
      When True and virtual Z, require_fresh_attach so a false "attached"
      (e.g. open wire) is caught by a dock+attach cycle before Z home (#231).
    """
    home_x, home_y, home_z = request.home_x, request.home_y, request.home_z
    force_full = False
    if home_z and not xy_homed:
        # Need XY before Z
        home_x = home_y = home_z = True
        force_full = True

    reset_lock = request.home_x and request.home_y and request.home_z and not force_full
    if force_full:
        reset_lock = True

    # XY order
    if home_first == "y":
        prefer_y_first = True
    elif home_first == "x":
        prefer_y_first = False
    else:
        # auto: Y first when attach approach has no Y component (dock on back)
        prefer_y_first = approach_y == 0

    xy_order: List[str] = []
    if prefer_y_first:
        if home_y:
            xy_order.append("y")
        if home_x:
            xy_order.append("x")
    else:
        if home_x:
            xy_order.append("x")
        if home_y:
            xy_order.append("y")

    attach_before_z = False
    detach_before_z = False
    detach_after_z = False
    lock_after = False
    require_fresh = False

    if home_z:
        if z_virtual_endstop:
            leave = request.leave_probe_attached
            lock_after = bool(leave and request.lock_probe)
            require_fresh = bool(reseat_before_z_home)
            # Attach before home_z(): attach ends at dock exit; Klipper stock
            # G28 Z probes at current XY (no re-center). Stage z_home_* after.
            attach_before_z = True
            # Plan owns post-Z dock unless leave (PROBE_LOCK / DOCK=0).
            detach_after_z = not leave
        else:
            # Physical Z: clear probe before Z home when configured —
            # never skip detach_before_z for leave_attached (collision risk).
            if dock_before_z_home:
                detach_before_z = True
            else:
                detach_after_z = not request.leave_probe_attached
            if request.leave_probe_attached and request.lock_probe:
                lock_after = True

    return HomingPlan(
        xy_order=xy_order,
        home_z=home_z,
        attach_before_z=attach_before_z,
        detach_before_z=detach_before_z,
        detach_after_z=detach_after_z,
        lock_after_attach=lock_after,
        force_full_home=force_full,
        reset_lock=reset_lock,
        require_fresh_attach=require_fresh,
    )
