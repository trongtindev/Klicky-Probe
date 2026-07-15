"""G-code command wraps: mesh, leveling, probe calibrate/accuracy."""

from __future__ import annotations

from typing import Callable

from . import messages as msg
from .adaptive_mesh import merge_mesh_params
from .dock_policy import DockIntent, parse_dock_intent, strip_klicky_params
from .gcode_cmd import create_stock_gcmd
from .homing_plan import HomingRequest
from .probe_accuracy import (
    PROBE_STAGING_PARAMS,
    resolve_probe_stage_move,
    resolve_probe_stage_xy,
)
from .probe_calibrate import ProbeCalibrateRunner


class CommandWrappers:
    def __init__(self, host):
        self._h = host

    def dock_intent_from_gcmd(self, gcmd) -> DockIntent:
        return parse_dock_intent(gcmd.get_command_parameters())

    def _run_probe_work(
        self,
        intent: DockIntent,
        pre_hook: str,
        post_hook: str,
        body: Callable[[], None],
        *,
        restore: bool = False,
    ) -> None:
        """
        Shared wrap lifecycle: enter → pre → body → exit → post.

        Pre runs after attach so user hooks see the probe already mounted.
        Post always runs (nested finally) even if exit_probe_work raises.
        """
        h = self._h
        h.lifecycle.enter_probe_work(intent, restore=restore)
        h._run_gcode_template(pre_hook, soft=True)
        try:
            body()
        finally:
            try:
                h.lifecycle.exit_probe_work(intent, restore=restore)
            finally:
                h._run_gcode_template(post_hook, soft=True)

    def install_probe_session_hooks(self) -> None:
        """
        Wrap PrinterProbe.start_probe_session (Klipper v0.13+).

        Session hooks own attach/dock for probe ops without an outer plan
        (bare PROBE, mesh samples, etc.). Virtual-Z G28 also opens a session,
        but HomingExecutor holds auto-dock during stock G28 Z so the **plan**
        remains the single dock owner for home.
        """
        h = self._h
        probe = h._probe
        orig_start = probe.start_probe_session
        lifecycle = h.lifecycle
        # SampleAveragingHelper is a singleton; wrap end_probe_session once.
        end_hooked = {"done": False}

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
            try:
                session = orig_start(gcmd)
            except Exception:
                # begin_session already ran; undo counter without docking.
                # (attach failures are rolled back inside on_session_begin.)
                if h._session.session_depth > 0:
                    h._session.end_session()
                raise
            if not end_hooked["done"]:
                orig_end = session.end_probe_session

                def end_probe_session(*args, **kwargs):
                    try:
                        return orig_end(*args, **kwargs)
                    finally:
                        lifecycle.on_session_end()

                session.end_probe_session = end_probe_session
                end_hooked["done"] = True
            return session

        probe.start_probe_session = start_probe_session
        lifecycle.clear_require_fresh_oneshot()
        h._verbose(msg.log_auto_attach_hooked())

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
                    self._run_probe_work(
                        intent,
                        "pre_leveling_gcode",
                        "post_leveling_gcode",
                        lambda: original(gcmd),
                    )

                return handler

            h.gcode.register_command(cmd, make_handler(prev))

        self.wrap_z_tilt_adjust()

    def wrap_z_tilt_adjust(self) -> None:
        """
        Z_TILT_ADJUST: attach, run stock tilt, rehome Z while attached, then end.
        Dedicated path so leveling factory stays free of name-based branches.

        Internal Z rehome uses HomingExecutor, so pre/post_homing_gcode also fire
        nested under leveling hooks.
        """
        h = self._h
        prev = h.gcode.register_command("Z_TILT_ADJUST", None)
        if prev is None:
            return
        h._wrapped["Z_TILT_ADJUST"] = prev

        def handler(gcmd):
            intent = self.dock_intent_from_gcmd(gcmd)
            z_hold = not (
                intent.lock or intent.leave_attached or intent.force_dock
            )

            def body():
                if z_hold:
                    h._session.begin_hold()
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

            self._run_probe_work(
                intent,
                "pre_leveling_gcode",
                "post_leveling_gcode",
                body,
            )

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
            merged = merge_mesh_params(stock_params, s.adaptive_mesh)

            def body():
                # create_stock_gcmd: extended prev() reparses commandline only.
                fo = create_stock_gcmd(h.gcode, "BED_MESH_CALIBRATE", merged)
                prev(fo)

            self._run_probe_work(
                intent,
                "pre_meshing_gcode",
                "post_meshing_gcode",
                body,
            )

        h.gcode.register_command("BED_MESH_CALIBRATE", handler)

    def wrap_probe_calibrate(self) -> None:
        """
        Replace stock PROBE_CALIBRATE with Klicky sequence.

        Stock handler is unregistered (not called): paper test must run with
        the probe docked. See ProbeCalibrateRunner / klipper probe.py.
        """
        h = self._h
        prev = h.gcode.register_command("PROBE_CALIBRATE", None)
        if prev is None:
            return
        h._wrapped["PROBE_CALIBRATE"] = prev
        runner = ProbeCalibrateRunner(h)
        h.gcode.register_command("PROBE_CALIBRATE", runner.run)

    def wrap_probe_accuracy(self) -> None:
        h = self._h
        prev = h.gcode.register_command("PROBE_ACCURACY", None)
        if prev is None:
            return
        h._wrapped["PROBE_ACCURACY"] = prev

        def handler(gcmd):
            s = h.settings
            params = dict(gcmd.get_command_parameters())
            intent = self.dock_intent_from_gcmd(gcmd)
            do_move = resolve_probe_stage_move(
                params, config_move=s.probe_accuracy_move
            )
            th = h._toolhead
            if "xyz" not in th.get_status(h.reactor.monotonic()).get(
                "homed_axes", ""
            ):
                raise gcmd.error(msg.home_xyz_before_probe_op())
            tx = ty = None
            if do_move:
                try:
                    tx, ty = resolve_probe_stage_xy(
                        params,
                        default_x=s.probe_accuracy_x,
                        default_y=s.probe_accuracy_y,
                    )
                except ValueError as e:
                    raise gcmd.error(str(e)) from e
                h._check_over_bed(xy=(tx, ty))
            else:
                h._check_over_bed()

            def body():
                if do_move:
                    h.dock.ensure_clearance()
                    h._verbose(msg.log_probe_accuracy_stage(tx, ty))
                    pos = th.get_position()
                    th.manual_move([tx, ty, pos[2]], s.travel_speed)
                stock_params = strip_klicky_params(params, PROBE_STAGING_PARAMS)
                fo = create_stock_gcmd(h.gcode, "PROBE_ACCURACY", stock_params)
                prev(fo)

            self._run_probe_work(
                intent,
                "pre_probe_accuracy_gcode",
                "post_probe_accuracy_gcode",
                body,
                restore=True,
            )

        h.gcode.register_command("PROBE_ACCURACY", handler)
