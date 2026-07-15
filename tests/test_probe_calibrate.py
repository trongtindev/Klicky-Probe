"""PROBE_CALIBRATE pure helpers + runner orchestration (mocked Klipper)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from klicky_probe.probe_calibrate import (
    PAPER_START_LIFT_MM,
    PROBE_CALIBRATE_STAGING_PARAMS,
    ProbeCalibrateRunner,
    calc_probe_z_offset,
    format_z_offset_result,
    paper_start_z,
)
from klicky_probe.probe_accuracy import PROBE_STAGING_PARAMS
from klicky_probe.probe_session import SessionCounters
from klicky_probe.probe_state import ProbeAttachState, ProbeState


def test_staging_params_shared():
    assert PROBE_CALIBRATE_STAGING_PARAMS == PROBE_STAGING_PARAMS
    assert PROBE_STAGING_PARAMS == frozenset({"MOVE", "X", "Y"})


def test_calc_probe_z_offset_matches_stock_formula():
    # offsets[2] - mpresult.bed_z + ppos.bed_z  (probe.py probe_calibrate_finalize)
    assert calc_probe_z_offset(1.0, 0.2, 2.5) == 3.3
    assert calc_probe_z_offset(0.0, 0.0, 0.0) == 0.0
    assert calc_probe_z_offset(5.0, 5.0, 1.0) == 1.0


def test_format_z_offset_result():
    text = format_z_offset_result("probe", 2.345)
    assert "probe: z_offset: 2.345" in text
    assert "SAVE_CONFIG" in text


def test_paper_start_z_matches_stock_lift():
    assert paper_start_z(1.25) == 1.25 + PAPER_START_LIFT_MM
    assert paper_start_z(0.0) == 5.0


class _FakeToolhead:
    def __init__(self):
        self.pos = [100.0, 50.0, 30.0]
        self.moves = []

    def get_position(self):
        return list(self.pos)

    def get_status(self, _t):
        return {"homed_axes": "xyz"}

    def manual_move(self, coord, speed):
        for i, v in enumerate(coord):
            if v is not None:
                self.pos[i] = float(v)
        self.moves.append((list(coord), speed, list(self.pos)))


class _FakeGcmd:
    def __init__(self, params=None):
        self._params = params or {}
        self.infos = []

    def get_command_parameters(self):
        return dict(self._params)

    def error(self, msg):
        return RuntimeError(msg)

    def respond_info(self, text):
        self.infos.append(text)


def _host(*, disable_docking=False, locked=False, calibrate_move=True):
    th = _FakeToolhead()
    state = ProbeState(
        attach_state=ProbeAttachState.DOCKED,
        locked=locked,
    )
    session = SessionCounters()
    lifecycle = MagicMock()
    dock = MagicMock()
    probe = MagicMock()
    probe.get_offsets.return_value = (0.0, -25.0, 2.5)
    probe.get_status.return_value = {"name": "probe"}
    gcode = MagicMock()
    gcode.create_gcode_command.side_effect = (
        lambda n, c, p: SimpleNamespace(params=p, name=n)
    )
    gcode.respond_info = MagicMock()
    printer = MagicMock()
    configfile = MagicMock()
    printer.lookup_object.return_value = configfile

    host = SimpleNamespace(
        settings=SimpleNamespace(
            disable_docking=disable_docking,
            probe_calibrate_move=calibrate_move,
            probe_calibrate_x=175.0,
            probe_calibrate_y=150.0,
            clearance_z=25.0,
            travel_speed=200.0,
            z_speed=20.0,
        ),
        _toolhead=th,
        reactor=SimpleNamespace(monotonic=lambda: 0.0),
        state=state,
        _session=session,
        lifecycle=lifecycle,
        dock=dock,
        _probe=probe,
        gcode=gcode,
        printer=printer,
        _check_over_bed=MagicMock(),
        _verbose=MagicMock(),
        _run_gcode_template=MagicMock(),
    )
    return host, th, lifecycle, dock, probe


def test_runner_order_attach_probe_dock_manual():
    host, th, lifecycle, dock, probe = _host()
    # bed_* for formula; toolhead Z after sample is trigger height (stock).
    ppos = SimpleNamespace(bed_x=175.0, bed_y=150.0, bed_z=1.0)
    probe_mod = SimpleNamespace(run_single_probe=MagicMock(return_value=ppos))
    manual = SimpleNamespace(
        verify_no_manual_probe=MagicMock(),
        ManualProbeHelper=MagicMock(),
    )
    order = []

    def attach(**kwargs):
        order.append("attach")
        host.state.attach_state = ProbeAttachState.ATTACHED

    moves_after_detach = [0]

    def detach(**kwargs):
        order.append("detach_force=%s" % kwargs.get("force", False))
        assert kwargs.get("force") is True
        host.state.attach_state = ProbeAttachState.DOCKED
        # Dock leaves toolhead high near dock (not over paper XY).
        th.pos = [10.0, 300.0, 25.0]
        moves_after_detach[0] = len(th.moves)

    lifecycle.attach_probe.side_effect = attach
    lifecycle.detach_probe.side_effect = detach
    dock.ensure_clearance.side_effect = lambda: order.append("clearance")

    def run_probe(_p, _g):
        # Hold must be open during sample so session end would not auto-dock.
        assert host._session.hold_depth == 1
        order.append("probe")
        th.pos[2] = 2.5  # last-sample toolhead Z (stock get_position)
        return ppos

    probe_mod.run_single_probe.side_effect = run_probe

    def manual_helper(printer, gcmd, finalize):
        order.append("manual")
        # ManualProbe starts after paper positioning.
        assert th.pos[0] == 175.0 and th.pos[1] == 150.0
        assert th.pos[2] == paper_start_z(2.5)
        finalize(SimpleNamespace(bed_z=0.2))

    manual.ManualProbeHelper.side_effect = manual_helper

    with patch(
        "klicky_probe.probe_calibrate.import_klipper_probe_modules",
        return_value=(probe_mod, manual),
    ):
        ProbeCalibrateRunner(host).run(_FakeGcmd())

    assert order == [
        "attach",
        "clearance",  # stage
        "probe",
        "clearance",  # dock before paper
        "detach_force=True",
        "manual",
    ]
    # Post-dock only (stage XY must not satisfy this slice).
    post_dock = th.moves[moves_after_detach[0] :]
    assert any(
        c[0] == 175.0 and c[1] == 150.0 and spd == 200.0
        for c, spd, _ in post_dock
    ), post_dock
    assert post_dock[-1][2][2] == paper_start_z(2.5)
    assert post_dock[-1][1] == 20.0  # z_speed for paper lower
    host.printer.lookup_object.assert_called_with("configfile")
    host.printer.lookup_object.return_value.set.assert_called_with(
        "probe", "z_offset", "3.300"
    )
    assert host._session.hold_depth == 0
    assert [c.args[0] for c in host._run_gcode_template.call_args_list] == [
        "pre_probe_calibrate_gcode",
        "post_probe_calibrate_gcode",
    ]
    assert all(
        c.kwargs.get("soft") is True for c in host._run_gcode_template.call_args_list
    )


def test_runner_force_dock_even_if_locked():
    host, th, lifecycle, dock, probe = _host(locked=True)
    ppos = SimpleNamespace(bed_x=10.0, bed_y=20.0, bed_z=1.0)
    probe_mod = SimpleNamespace(run_single_probe=MagicMock(return_value=ppos))
    manual = SimpleNamespace(
        verify_no_manual_probe=MagicMock(),
        ManualProbeHelper=MagicMock(),
    )

    with patch(
        "klicky_probe.probe_calibrate.import_klipper_probe_modules",
        return_value=(probe_mod, manual),
    ):
        ProbeCalibrateRunner(host).run(_FakeGcmd({"MOVE": "0"}))

    lifecycle.detach_probe.assert_called_with(force=True)


def test_runner_error_still_force_docks():
    host, th, lifecycle, dock, probe = _host()
    probe_mod = SimpleNamespace(
        run_single_probe=MagicMock(side_effect=RuntimeError("probe fail"))
    )
    manual = SimpleNamespace(
        verify_no_manual_probe=MagicMock(),
        ManualProbeHelper=MagicMock(),
    )

    with patch(
        "klicky_probe.probe_calibrate.import_klipper_probe_modules",
        return_value=(probe_mod, manual),
    ):
        with pytest.raises(RuntimeError, match="probe fail"):
            ProbeCalibrateRunner(host).run(_FakeGcmd({"MOVE": "0"}))

    lifecycle.detach_probe.assert_called_with(force=True)
    assert host._session.hold_depth == 0
    manual.ManualProbeHelper.assert_not_called()
    assert [c.args[0] for c in host._run_gcode_template.call_args_list] == [
        "pre_probe_calibrate_gcode",
        "post_probe_calibrate_gcode",
    ]


def test_manual_probe_helper_ctor_failure_still_runs_post():
    """If ManualProbeHelper raises, post must still fire (paper never owns it)."""
    host, th, lifecycle, dock, probe = _host()
    ppos = SimpleNamespace(bed_x=10.0, bed_y=20.0, bed_z=1.0)
    probe_mod = SimpleNamespace(run_single_probe=MagicMock(return_value=ppos))
    manual = SimpleNamespace(
        verify_no_manual_probe=MagicMock(),
        ManualProbeHelper=MagicMock(side_effect=RuntimeError("ui fail")),
    )

    with patch(
        "klicky_probe.probe_calibrate.import_klipper_probe_modules",
        return_value=(probe_mod, manual),
    ):
        with pytest.raises(RuntimeError, match="ui fail"):
            ProbeCalibrateRunner(host).run(_FakeGcmd({"MOVE": "0"}))

    assert [c.args[0] for c in host._run_gcode_template.call_args_list] == [
        "pre_probe_calibrate_gcode",
        "post_probe_calibrate_gcode",
    ]


def test_session_holding_context_always_ends():
    s = SessionCounters()
    with pytest.raises(RuntimeError):
        with s.holding():
            assert s.hold_depth == 1
            raise RuntimeError("boom")
    assert s.hold_depth == 0
