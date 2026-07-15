"""PROBE_CALIBRATE for dockable probes (Klicky).

Mirrors stock Klipper ``ProbeCommandHelper.cmd_PROBE_CALIBRATE``
(``klippy/extras/probe.py``) with one required change: **dock before paper
test**. The microswitch tip sits below the nozzle; leave-attached paper test
collides with the bed.

Paper UI is stock ``manual_probe.ManualProbeHelper`` (Mainsail/Fluidd TESTZ).

Session hold contract
---------------------
With ``auto_attach``, ``run_single_probe`` opens a probe session whose end
would auto-dock. This runner uses ``SessionCounters.holding()`` only to
**suppress that session auto-dock**, then owns a single ``detach_probe(force=True)``
before paper. Hold is not "leave attached for paper."
"""

from __future__ import annotations

from typing import Any, Tuple

from . import messages as msg
from .dock_policy import strip_klicky_params
from .probe_accuracy import (
    PROBE_STAGING_PARAMS,
    resolve_probe_stage_move,
    resolve_probe_stage_xy,
)

# Alias used by strip / docs
PROBE_CALIBRATE_STAGING_PARAMS = PROBE_STAGING_PARAMS

# Stock cmd_PROBE_CALIBRATE lifts +5 mm above probe trigger before paper UI.
PAPER_START_LIFT_MM = 5.0


def calc_probe_z_offset(
    ppos_bed_z: float,
    mpresult_bed_z: float,
    probe_z_offset: float,
) -> float:
    """Stock formula: offsets[2] - mpresult.bed_z + ppos.bed_z."""
    return float(probe_z_offset) - float(mpresult_bed_z) + float(ppos_bed_z)


def paper_start_z(trigger_z: float, lift: float = PAPER_START_LIFT_MM) -> float:
    """Z for ManualProbe start: toolhead Z after probe sample + stock lift."""
    return float(trigger_z) + float(lift)


def format_z_offset_result(probe_section: str, z_offset: float) -> str:
    return (
        "%s: z_offset: %.3f\n"
        "The SAVE_CONFIG command will update the printer config file\n"
        "with the above and restart the printer."
        % (probe_section, z_offset)
    )


def import_klipper_probe_modules() -> Tuple[Any, Any]:
    """
    Load sibling extras ``probe`` and ``manual_probe``.

    Klipper loads this package as ``extras.klicky_probe`` (see
    ``klippy.py`` load_object). Sibling extras use ``from extras import …``
    or ``from . import probe`` from a single-file extra; from a package the
    parent package path is ``extras``.
    """
    try:
        from extras import probe as probe_mod  # type: ignore
        from extras import manual_probe  # type: ignore

        return probe_mod, manual_probe
    except ImportError:
        pass
    # Relative parent (extras.klicky_probe → extras.probe)
    try:
        from .. import probe as probe_mod  # type: ignore
        from .. import manual_probe  # type: ignore

        return probe_mod, manual_probe
    except ImportError as e:
        raise ImportError(
            "klicky: cannot import Klipper extras.probe / extras.manual_probe"
        ) from e


class ProbeCalibrateRunner:
    """Own attach → probe → force-dock → nozzle ManualProbe sequence."""

    def __init__(self, host):
        self._h = host

    def run(self, gcmd) -> None:
        h = self._h
        s = h.settings
        params = dict(gcmd.get_command_parameters())
        th = h._toolhead

        if "xyz" not in th.get_status(h.reactor.monotonic()).get(
            "homed_axes", ""
        ):
            raise gcmd.error(msg.home_xyz_before_probe_op())

        do_move = resolve_probe_stage_move(
            params, config_move=s.probe_calibrate_move
        )
        tx = ty = None
        if do_move:
            try:
                tx, ty = resolve_probe_stage_xy(
                    params,
                    default_x=s.probe_calibrate_x,
                    default_y=s.probe_calibrate_y,
                )
            except ValueError as e:
                raise gcmd.error(str(e))
            h._check_over_bed(xy=(tx, ty))
        else:
            h._check_over_bed()

        try:
            probe_mod, manual_probe = import_klipper_probe_modules()
        except ImportError as e:
            raise gcmd.error(str(e))

        manual_probe.verify_no_manual_probe(h.printer)
        stock_params = strip_klicky_params(params, PROBE_STAGING_PARAMS)
        # Direct probe helpers read _params (no extended reparse).
        fo = h.gcode.create_gcode_command(
            "PROBE_CALIBRATE",
            "PROBE_CALIBRATE",
            {str(k): str(v) for k, v in stock_params.items()},
        )

        h._run_gcode_template("pre_probe_calibrate_gcode", soft=True)
        post_done = False

        def run_post():
            nonlocal post_done
            if post_done:
                return
            post_done = True
            h._run_gcode_template("post_probe_calibrate_gcode", soft=True)

        # True only after ManualProbeHelper is registered (owns post via finalize).
        paper_owns_post = False
        try:
            if not s.disable_docking:
                h.lifecycle.attach_probe()

            if do_move:
                h.dock.ensure_clearance()
                h._verbose(msg.log_probe_calibrate_stage(tx, ty))
                pos = th.get_position()
                th.manual_move([tx, ty, pos[2]], s.travel_speed)

            # Hold suppresses session auto-dock inside run_single_probe so this
            # runner remains the single dock-before-paper owner.
            if not s.disable_docking:
                with h._session.holding():
                    ppos = probe_mod.run_single_probe(h._probe, fo)
            else:
                ppos = probe_mod.run_single_probe(h._probe, fo)
            # Stock uses toolhead Z after the sample (last sample), not averaged
            # ProbeResult.test_z — capture before dock changes Z.
            trigger_z = th.get_position()[2]

            offsets = h._probe.get_offsets(fo)
            probe_section = (
                h._probe.get_status(h.reactor.monotonic()).get("name")
                or "probe"
            )

            # Collision safety: always dock before paper (probe tip below nozzle).
            self._dock_before_paper()

            # After dock: long XY @ travel_speed (not [probe] speed), then paper
            # Z = trigger_z + 5 like stock cmd_PROBE_CALIBRATE (not clearance_z).
            # [probe] speed remains for run_single_probe only.
            paper_z = paper_start_z(trigger_z)
            curpos = th.get_position()
            travel_z = max(curpos[2], s.clearance_z, paper_z)
            if curpos[2] < travel_z:
                th.manual_move(
                    [curpos[0], curpos[1], travel_z], s.z_speed
                )
                curpos = th.get_position()
            th.manual_move(
                [ppos.bed_x, ppos.bed_y, curpos[2]], s.travel_speed
            )
            # Always command paper Z (avoid float == skip after travel).
            th.manual_move([ppos.bed_x, ppos.bed_y, paper_z], s.z_speed)

            gcmd.respond_info(msg.probe_calibrate_paper_ready())

            def finalize(mpresult):
                try:
                    if mpresult is None:
                        return
                    z_offset = calc_probe_z_offset(
                        ppos.bed_z, mpresult.bed_z, offsets[2]
                    )
                    h.gcode.respond_info(
                        format_z_offset_result(probe_section, z_offset)
                    )
                    configfile = h.printer.lookup_object("configfile")
                    configfile.set(
                        probe_section, "z_offset", "%.3f" % (z_offset,)
                    )
                finally:
                    run_post()

            manual_probe.ManualProbeHelper(h.printer, fo, finalize)
            paper_owns_post = True
        except Exception:
            if not paper_owns_post:
                try:
                    self._dock_before_paper(quiet=True)
                except Exception:
                    pass
                run_post()
            raise

    def _dock_before_paper(self, *, quiet: bool = False) -> None:
        h = self._h
        s = h.settings
        if s.disable_docking:
            return
        h.dock.ensure_clearance()
        if not quiet:
            h._verbose(msg.log_probe_calibrate_dock_before_paper())
        # force=True unlocks + docks (collision-safe before nozzle paper test).
        h.lifecycle.detach_probe(force=True)
