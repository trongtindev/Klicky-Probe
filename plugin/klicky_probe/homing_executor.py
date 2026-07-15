"""G28 / Z-home execution using HomingPlan (Klipper I/O)."""

from __future__ import annotations

from . import messages as msg
from .homing_plan import HomingRequest, plan_homing


class HomingExecutor:
    def __init__(self, host):
        self._h = host

    def execute(self, req: HomingRequest) -> None:
        """Shared G28 path (also used by Z_TILT rehome without string re-entry)."""
        h = self._h
        s = h.settings
        th = h._toolhead
        homed = th.get_status(h.reactor.monotonic()).get("homed_axes", "")
        session_manages = bool(s.auto_attach and s.z_virtual_endstop)
        plan = plan_homing(
            req,
            xy_homed=("x" in homed and "y" in homed),
            home_first=s.home_first,
            approach_y=s.approach_y,
            z_virtual_endstop=s.z_virtual_endstop,
            dock_before_z_home=s.dock_before_z_home,
            session_manages_probe=session_manages,
            reseat_before_z_home=s.reseat_before_z_home,
        )
        if plan.reset_lock:
            h.state.unlock()
            h._session.reset_holds()

        h._status_led("HOMING")
        if not homed and s.z_hop_when_unhomed:
            h.dock.z_hop_unhomed(s.clearance_z)

        for axis in plan.xy_order:
            self.home_axis(axis)

        # Fallback oneshot for rare paths where session attach is still deferred
        # (no attach_before_z). Default virtual-Z pre-attaches with require_fresh
        # on attach_probe instead (#231 / z_home XY staging).
        arm_oneshot = bool(
            plan.home_z
            and plan.require_fresh_attach
            and session_manages
            and not plan.attach_before_z
        )
        if arm_oneshot:
            h.lifecycle.arm_require_fresh_oneshot()
        else:
            h.lifecycle.clear_require_fresh_oneshot()

        hold_for_leave = False
        try:
            if plan.home_z:
                if plan.detach_before_z:
                    h.lifecycle.detach_probe()
                if plan.attach_before_z:
                    h.lifecycle.attach_probe(
                        require_fresh=plan.require_fresh_attach
                    )
                    if plan.lock_after_attach:
                        h.state.lock()
                    elif req.leave_probe_attached and not req.lock_probe:
                        h._session.begin_hold()
                        hold_for_leave = True
                try:
                    self.home_z()
                finally:
                    if hold_for_leave:
                        h._session.end_hold()
                if plan.detach_after_z:
                    h.lifecycle.detach_probe()
        finally:
            h.lifecycle.clear_require_fresh_oneshot()

        h.dock.park()
        h._status_led("READY")

    def home_axis(self, axis: str) -> None:
        h = self._h
        s = h.settings
        th = h._toolhead
        homed = th.get_status(h.reactor.monotonic()).get("homed_axes", "")
        if "z" in homed:
            pos = th.get_position()
            if pos[2] < s.clearance_z:
                th.manual_move([pos[0], pos[1], s.clearance_z], s.z_speed)

        key = "home_%s_gcode" % axis
        if key in h._gcode_templates:
            h._run_template(key)
        else:
            self.call_orig_g28(axis.upper())

        backoff = s.endstop_backoff_x if axis == "x" else s.endstop_backoff_y
        if backoff == 0:
            return
        configfile = h.printer.lookup_object("configfile")
        st = configfile.get_status(h.reactor.monotonic()).get("settings", {})
        sect = st.get("stepper_%s" % axis, {})
        endstop = float(sect.get("position_endstop", 0))
        pmin = float(sect.get("position_min", 0))
        pmax = float(sect.get("position_max", 300))
        mid = (pmin + pmax) / 2.0
        pos = th.get_position()
        new = endstop - backoff if endstop > mid else endstop + backoff
        if axis == "x":
            th.manual_move([new, pos[1], pos[2]], s.travel_speed)
        else:
            th.manual_move([pos[0], new, pos[2]], s.travel_speed)

    def call_orig_g28(self, axis_letter: str) -> None:
        h = self._h
        if h._orig_g28 is None:
            raise h.gcode.error(msg.orig_g28_unavailable())
        fo = h.gcode.create_gcode_command("G28", "G28", {axis_letter: "0"})
        h._orig_g28(fo)

    def home_z(self) -> None:
        """Stage z_home XY then stock G28 Z (Klipper probes at current XY)."""
        h = self._h
        s = h.settings
        th = h._toolhead
        if not h._xy_homed():
            raise h.gcode.error(msg.home_xy_before_z())
        # Must run after attach_before_z: attach ends at dock exit.
        th.manual_move(
            [s.z_home_x, s.z_home_y, th.get_position()[2]], s.travel_speed
        )
        self.call_orig_g28("Z")
        h.dock.note_z_homed()
        pos = th.get_position()
        th.manual_move([pos[0], pos[1], s.clearance_z], s.z_speed)
