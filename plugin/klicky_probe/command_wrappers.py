"""G-code command wraps: mesh, leveling, probe calibrate/accuracy."""

from __future__ import annotations

from .adaptive_mesh import merge_mesh_params
from .dock_policy import DockIntent, parse_dock_intent, strip_klicky_params
from .homing_plan import HomingRequest
from . import errors as E


class CommandWrappers:
    def __init__(self, host):
        self._h = host

    def dock_intent_from_gcmd(self, gcmd) -> DockIntent:
        return parse_dock_intent(gcmd.get_command_parameters())

    def install_probe_session_hooks(self) -> None:
        """
        Wrap PrinterProbe.start_probe_session (Klipper v0.13+).

        Mesh, QGL, Z_TILT, PROBE_ACCURACY, PROBE, and virtual-Z G28 all use this API.
        """
        h = self._h
        probe = h._probe
        orig_start = probe.start_probe_session
        lifecycle = h.lifecycle

        def start_probe_session(gcmd):
            # Consume one-shot only on outermost begin so nested samples
            # do not reseat every probe point.
            require_fresh = False
            if (
                h._session.session_depth == 0
                and lifecycle.peek_require_fresh_oneshot()
            ):
                require_fresh = lifecycle.consume_require_fresh_oneshot()
            lifecycle.on_session_begin(require_fresh=require_fresh)
            session = orig_start(gcmd)
            orig_end = session.end_probe_session

            def end_probe_session(*args, **kwargs):
                try:
                    return orig_end(*args, **kwargs)
                finally:
                    lifecycle.on_session_end()

            session.end_probe_session = end_probe_session
            return session

        probe.start_probe_session = start_probe_session
        lifecycle.clear_require_fresh_oneshot()
        h._log("auto_attach: hooked probe.start_probe_session")

    def wrap_leveling_commands(self) -> None:
        """QGL and SCREWS — generic begin/original/end (no Z_TILT special case)."""
        h = self._h
        for cmd in ("QUAD_GANTRY_LEVEL", "SCREWS_TILT_CALCULATE"):
            prev = h.gcode.register_command(cmd, None)
            if prev is None:
                continue
            h._wrapped[cmd] = prev

            def make_handler(original):
                def handler(gcmd):
                    intent = self.dock_intent_from_gcmd(gcmd)
                    h.lifecycle.enter_probe_work(intent)
                    h._status_led("LEVELING")
                    try:
                        original(gcmd)
                    finally:
                        h.lifecycle.exit_probe_work(intent)

                return handler

            h.gcode.register_command(cmd, make_handler(prev))

        self.wrap_z_tilt_adjust()

    def wrap_z_tilt_adjust(self) -> None:
        """
        Z_TILT_ADJUST: attach, run stock tilt, rehome Z while attached, then end.
        Dedicated path so leveling factory stays free of name-based branches.
        """
        h = self._h
        prev = h.gcode.register_command("Z_TILT_ADJUST", None)
        if prev is None:
            return
        h._wrapped["Z_TILT_ADJUST"] = prev

        def handler(gcmd):
            intent = self.dock_intent_from_gcmd(gcmd)
            h.lifecycle.enter_probe_work(intent)
            z_hold = not (
                intent.lock or intent.leave_attached or intent.force_dock
            )
            if z_hold:
                h._session.begin_hold()
            h._status_led("LEVELING")
            try:
                prev(gcmd)
                leave = HomingRequest(
                    home_x=False,
                    home_y=False,
                    home_z=True,
                    leave_probe_attached=True,
                    lock_probe=bool(intent.lock),
                )
                was_locked = h.state.locked
                if not was_locked:
                    h.state.lock()
                try:
                    h.homing.execute(leave)
                finally:
                    if not intent.lock and not was_locked:
                        h.state.unlock()
            finally:
                if z_hold:
                    h._session.end_hold()
                h.lifecycle.exit_probe_work(intent)

        h.gcode.register_command("Z_TILT_ADJUST", handler)

    def wrap_bed_mesh_calibrate(self) -> None:
        h = self._h
        prev = h.gcode.register_command("BED_MESH_CALIBRATE", None)
        if prev is None:
            return
        h._orig_bed_mesh = prev

        def handler(gcmd):
            s = h.settings
            intent = self.dock_intent_from_gcmd(gcmd)
            stock_params = strip_klicky_params(dict(gcmd.get_command_parameters()))
            merged = merge_mesh_params(
                stock_params, s.adaptive_mesh, s.adaptive_margin
            )
            h._status_led("MESHING")
            h.lifecycle.enter_probe_work(intent)
            try:
                fo = h.gcode.create_gcode_command(
                    "BED_MESH_CALIBRATE",
                    "BED_MESH_CALIBRATE",
                    {str(k): str(v) for k, v in merged.items()},
                )
                prev(fo)
            finally:
                h.lifecycle.exit_probe_work(intent)

        h.gcode.register_command("BED_MESH_CALIBRATE", handler)

    def wrap_probe_calibrate(self) -> None:
        h = self._h
        prev = h.gcode.register_command("PROBE_CALIBRATE", None)
        if prev is None:
            return
        h._wrapped["PROBE_CALIBRATE"] = prev

        def handler(gcmd):
            s = h.settings
            intent = self.dock_intent_from_gcmd(gcmd)
            th = h._toolhead
            if "xyz" not in th.get_status(h.reactor.monotonic()).get(
                "homed_axes", ""
            ):
                raise gcmd.error(E.home_xyz_before_probe_op())
            h._check_over_bed()
            # Paper test: default leave attached unless DOCK=1.
            if not intent.force_dock and not intent.leave_attached:
                intent = DockIntent(
                    leave_attached=True, lock=intent.lock, force_dock=False
                )
            if not s.disable_docking:
                h.lifecycle.enter_probe_work(intent)
            h._status_led("CALIBRATING_Z")
            try:
                prev(gcmd)
            finally:
                if not s.disable_docking:
                    h.lifecycle.exit_probe_work(intent)
            gcmd.respond_info(E.probe_calibrate_leave_attached())

            h._status_led("READY")

        h.gcode.register_command("PROBE_CALIBRATE", handler)

    def wrap_probe_accuracy(self) -> None:
        h = self._h
        prev = h.gcode.register_command("PROBE_ACCURACY", None)
        if prev is None:
            return
        h._wrapped["PROBE_ACCURACY"] = prev

        def handler(gcmd):
            intent = self.dock_intent_from_gcmd(gcmd)
            th = h._toolhead
            if "xyz" not in th.get_status(h.reactor.monotonic()).get(
                "homed_axes", ""
            ):
                raise gcmd.error(E.home_xyz_before_probe_op())
            h._check_over_bed()
            h.lifecycle.enter_probe_work(intent, restore=True)
            try:
                prev(gcmd)
            finally:
                h.lifecycle.exit_probe_work(intent, restore=True)

        h.gcode.register_command("PROBE_ACCURACY", handler)
