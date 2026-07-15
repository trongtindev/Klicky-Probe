"""Dock attach/detach motion execution (Klipper I/O)."""

from __future__ import annotations

from typing import Callable, Optional

from . import messages as msg
from .geometry import (
    SPEED_ATTACH,
    SPEED_DETACH,
    SPEED_TRAVEL,
    SPEED_Z,
    DockGeometry,
    attach_waypoints,
    clearance_needed,
    detach_waypoints,
    entry_xy,
    travel_to_entry_waypoints,
)


class DockExecutor:
    """Run attach/detach sequences against a KlickyProbe host."""

    def __init__(self, host):
        self._h = host
        self._dock_accel_applied = False
        self._prev_max_accel = None
        # Unhomed Z hop claims current Z as 0 then raises by clearance_z.
        # Only allow once until Z is actually homed — stacking hops (G28 +
        # attach ensure_clearance + dock_retries + failed re-home) walks the
        # toolhead out of the intended Z envelope.
        self._unhomed_z_hop_done = False

    def geometry(self) -> DockGeometry:
        s = self._h.settings
        return DockGeometry(
            dock_x=s.dock_x,
            dock_y=s.dock_y,
            dock_z=s.dock_z,
            approach_x=s.approach_x,
            approach_y=s.approach_y,
            approach_z=s.approach_z,
            detach_x=s.detach_x,
            detach_y=s.detach_y,
            detach_z=s.detach_z,
            approach2_x=s.approach2_x,
            approach2_y=s.approach2_y,
            approach2_z=s.approach2_z,
        )

    def speed(self, role: str) -> float:
        s = self._h.settings
        return {
            SPEED_TRAVEL: s.travel_speed,
            SPEED_ATTACH: s.attach_speed,
            SPEED_DETACH: s.detach_speed,
            SPEED_Z: s.z_speed,
        }.get(role, s.travel_speed)

    def move_wp(self, wp) -> None:
        th = self._h._toolhead
        speed = self.speed(wp.speed)
        pos = th.get_position()
        x = pos[0] if wp.x is None else wp.x
        y = pos[1] if wp.y is None else wp.y
        z = pos[2] if wp.z is None else wp.z
        self._h._debug(
            "move %s -> (%.3f, %.3f, %.3f) @ %.1f" % (wp.label, x, y, z, speed)
        )
        th.manual_move([x, y, z], speed)

    def ensure_clearance(self) -> None:
        s = self._h.settings
        th = self._h._toolhead
        homed = th.get_status(self._h.reactor.monotonic()).get("homed_axes", "")
        pos = th.get_position()
        if "z" in homed:
            self.note_z_homed()
        cur_z = pos[2] if "z" in homed else None
        if not clearance_needed(cur_z, s.clearance_z):
            return
        if "z" not in homed:
            if s.z_hop_when_unhomed:
                self.z_hop_unhomed(s.clearance_z)
            return
        th.manual_move([pos[0], pos[1], s.clearance_z], s.z_speed)

    def note_z_homed(self) -> None:
        """Z is known — next unhomed cycle may hop again."""
        self._unhomed_z_hop_done = False

    def z_hop_unhomed(self, z_hop: float) -> None:
        """
        Raise Z when unhomed — same pattern as klippy/extras/safe_z_home.py.

        Idempotent while still unhomed: each call would re-zero Z at the new
        physical height and hop again, stacking clearance and leaving the
        intended Z path (especially after home failures / dock retries).
        """
        th = self._h._toolhead
        homed = th.get_status(self._h.reactor.monotonic()).get("homed_axes", "")
        if "z" in homed:
            self.note_z_homed()
            return
        if self._unhomed_z_hop_done:
            return
        s = self._h.settings
        pos = th.get_position()
        pos[2] = 0.0
        th.set_position(pos, homing_axes="z")
        th.manual_move([None, None, z_hop], s.z_speed)
        th.get_kinematics().clear_homing_state("z")
        self._unhomed_z_hop_done = True

    def begin_dock_limits(self) -> None:
        s = self._h.settings
        self._dock_accel_applied = False
        self._prev_max_accel = None
        if s is None or not s.move_accel:
            return
        try:
            st = self._h._toolhead.get_status(self._h.reactor.monotonic())
            self._prev_max_accel = st.get("max_accel")
        except Exception:
            self._prev_max_accel = None
        if self._prev_max_accel is not None and abs(
            float(self._prev_max_accel) - float(s.move_accel)
        ) < 1e-6:
            return
        self._h.gcode.run_script_from_command(
            "SET_VELOCITY_LIMIT ACCEL=%.3f" % s.move_accel
        )
        self._dock_accel_applied = True

    def end_dock_limits(self) -> None:
        if not self._dock_accel_applied:
            return
        try:
            if self._prev_max_accel is not None:
                self._h.gcode.run_script_from_command(
                    "SET_VELOCITY_LIMIT ACCEL=%.3f" % self._prev_max_accel
                )
        finally:
            self._dock_accel_applied = False
            self._prev_max_accel = None

    def servo(self, angle) -> None:
        s = self._h.settings
        if not s.dock_servo:
            return
        gcode = self._h.gcode
        gcode.run_script_from_command(
            "SET_SERVO SERVO=%s ANGLE=%s" % (s.servo_name, angle)
        )
        gcode.run_script_from_command("M400")
        gcode.run_script_from_command("G4 P%d" % int(s.servo_delay_ms))
        gcode.run_script_from_command(
            "SET_SERVO SERVO=%s WIDTH=0" % s.servo_name
        )

    def _move_xy_clearance(self, x: float, y: float) -> None:
        s = self._h.settings
        self._h._toolhead.manual_move([x, y, s.clearance_z], s.travel_speed)

    def umbilical(self) -> None:
        s = self._h.settings
        if not s.umbilical:
            return
        if not self._h._xy_homed():
            return
        self._move_xy_clearance(s.umbilical_x, s.umbilical_y)

    def safe_xy(self) -> None:
        """Stage at safe XY before dock (probe mounted → cleaner/brush clearance)."""
        s = self._h.settings
        if not s.safe_xy_before_dock:
            return
        if not self._h._xy_homed():
            return
        self._move_xy_clearance(s.safe_xy_x, s.safe_xy_y)

    def park(self) -> None:
        s = self._h.settings
        if not s.park_after or s.park_x is None or s.park_y is None:
            return
        if not self._h._xy_homed():
            return
        th = self._h._toolhead
        pos = th.get_position()
        z = pos[2] if s.park_z is None else s.park_z
        th.manual_move([s.park_x, s.park_y, z], s.travel_speed)

    def _run_dock_body(self, wps, *, mode: str, pre_name: str, post_name: str) -> None:
        """
        Run dock sequence after staging at entry.

        First waypoint is entry XY by construction; skip when already there.
        """
        s = self._h.settings
        body = list(wps)
        if body:
            pos = self._h._toolhead.get_position()
            ex, ey = entry_xy(self.geometry(), mode)
            if abs(pos[0] - ex) <= 0.01 and abs(pos[1] - ey) <= 0.01:
                body = body[1:]
            else:
                self.move_wp(body[0])
                body = body[1:]
        self.servo(s.servo_deploy_angle)
        self._h._run_template(pre_name)
        for wp in body:
            self.move_wp(wp)
        self.servo(s.servo_retract_angle)
        self._h._run_template(post_name)

    def run_dock_motion(self, mode: str) -> None:
        """Full attach or detach sequence: clearance, umbilical, travel, body."""
        if mode not in ("attach", "detach"):
            raise ValueError(msg.geometry_mode_invalid(mode))
        s = self._h.settings
        geo = self.geometry()
        th = self._h._toolhead
        self.ensure_clearance()
        self.umbilical()
        # Probe is on the toolhead only when docking (detach). Attach travels empty.
        if mode == "detach":
            self.safe_xy()
        pos = th.get_position()
        for wp in travel_to_entry_waypoints(
            geo, pos[0], pos[1], mode=mode, enabled=s.safe_dock_travel
        ):
            self.move_wp(wp)
        if mode == "attach":
            self._run_dock_body(
                attach_waypoints(geo),
                mode="attach",
                pre_name="pre_attach_gcode",
                post_name="post_attach_gcode",
            )
        else:
            self._run_dock_body(
                detach_waypoints(geo),
                mode="detach",
                pre_name="pre_detach_gcode",
                post_name="post_detach_gcode",
            )
        self.ensure_clearance()
        self.park()
        if mode == "detach":
            self._h.gcode.run_script_from_command("G4 P200")

    def dock_with_retries(
        self,
        mode: str,
        verify: Callable[[bool], Optional[str]],
        query_triggered: Callable[[], bool],
    ) -> None:
        """Run attach or detach motion with dock_retries and verify."""
        s = self._h.settings
        self.begin_dock_limits()
        try:
            err = None
            for attempt in range(max(0, s.dock_retries) + 1):
                self.run_dock_motion(mode)
                err = verify(query_triggered())
                if err is None:
                    break
                if attempt < s.dock_retries:
                    self._h._log(msg.log_dock_retry(mode, attempt + 1))
            if err:
                raise self._h.gcode.error(msg.verify_failed(err))
        finally:
            self.end_dock_limits()
