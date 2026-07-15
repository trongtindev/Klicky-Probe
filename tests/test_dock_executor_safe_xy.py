"""safe_xy_before_dock staging before travel to dock entry."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from klicky_probe.dock_executor import DockExecutor


class _FakeKinematics:
    def __init__(self, toolhead: _FakeToolhead):
        self._th = toolhead

    def clear_homing_state(self, axes: str) -> None:
        for a in axes:
            self._th.homed_axes = self._th.homed_axes.replace(a, "")


class _FakeToolhead:
    def __init__(self):
        self.pos = [100.0, 50.0, 30.0]
        self.homed_axes = "xyz"
        self.moves = []
        self._kin = _FakeKinematics(self)

    def get_position(self):
        return list(self.pos)

    def get_status(self, _eventtime):
        return {"homed_axes": self.homed_axes, "max_accel": 3000.0}

    def set_position(self, pos, homing_axes=None):
        self.pos = list(pos)

    def manual_move(self, coord, speed):
        new = list(self.pos)
        for i, v in enumerate(coord):
            if v is not None:
                new[i] = float(v)
        self.moves.append((list(coord), speed, list(new)))
        self.pos = new

    def get_kinematics(self):
        return self._kin


class _FakeReactor:
    def monotonic(self):
        return 0.0


def _host(
    *,
    safe_xy_before_dock: bool = True,
    safe_xy_x: float = 175.0,
    safe_xy_y: float = 175.0,
    umbilical: bool = False,
    xy_homed: bool = True,
):
    th = _FakeToolhead()
    if not xy_homed:
        th.homed_axes = "z"
    settings = SimpleNamespace(
        clearance_z=25.0,
        z_hop_when_unhomed=True,
        z_speed=20.0,
        travel_speed=200.0,
        attach_speed=50.0,
        detach_speed=75.0,
        move_accel=0.0,
        dock_x=0.0,
        dock_y=300.0,
        dock_z=None,
        approach_x=30.0,
        approach_y=0.0,
        approach_z=0.0,
        detach_x=0.0,
        detach_y=40.0,
        detach_z=0.0,
        approach2_x=0.0,
        approach2_y=0.0,
        approach2_z=0.0,
        safe_dock_travel=False,
        safe_xy_before_dock=safe_xy_before_dock,
        safe_xy_x=safe_xy_x,
        safe_xy_y=safe_xy_y,
        umbilical=umbilical,
        umbilical_x=15.0,
        umbilical_y=15.0,
        park_after=False,
        park_x=None,
        park_y=None,
        park_z=None,
        dock_servo=False,
        servo_name=None,
        servo_deploy_angle=None,
        servo_retract_angle=None,
        servo_delay_ms=250.0,
    )
    host = SimpleNamespace(
        settings=settings,
        _toolhead=th,
        reactor=_FakeReactor(),
        _debug=lambda *a, **k: None,
        _xy_homed=lambda: "x" in th.homed_axes and "y" in th.homed_axes,
        _run_gcode_template=lambda *a, **k: None,
        gcode=MagicMock(),
    )
    return host, th


def test_safe_xy_move_before_entry_when_enabled():
    host, th = _host(safe_xy_before_dock=True, safe_xy_x=5.5, safe_xy_y=10.0)
    dock = DockExecutor(host)
    dock.run_dock_motion("detach")

    # First XY staging target is safe_xy at clearance_z
    assert th.moves[0][0][:2] == [5.5, 10.0]
    assert th.moves[0][0][2] == 25.0
    assert th.moves[0][1] == 200.0
    # Then travel toward detach entry (dock - approach) = (-30, 300)
    entry_moves = [m for m in th.moves if m[0][0] == -30.0 and m[0][1] == 300.0]
    assert entry_moves


def test_safe_xy_skipped_when_disabled():
    host, th = _host(safe_xy_before_dock=False, safe_xy_x=5.5, safe_xy_y=10.0)
    dock = DockExecutor(host)
    dock.run_dock_motion("detach")

    assert not any(m[0][:2] == [5.5, 10.0] for m in th.moves)


def test_safe_xy_skipped_when_xy_not_homed():
    host, th = _host(safe_xy_before_dock=True, safe_xy_x=5.5, safe_xy_y=10.0, xy_homed=False)
    # Already above clearance so ensure_clearance is a no-op without hop path
    th.pos[2] = 30.0
    dock = DockExecutor(host)
    dock.safe_xy()
    assert th.moves == []


def test_safe_xy_after_umbilical_on_detach():
    host, th = _host(
        safe_xy_before_dock=True,
        safe_xy_x=100.0,
        safe_xy_y=100.0,
        umbilical=True,
    )
    dock = DockExecutor(host)
    dock.run_dock_motion("detach")

    assert th.moves[0][0][:2] == [15.0, 15.0]
    assert th.moves[1][0][:2] == [100.0, 100.0]


def test_safe_xy_skipped_on_attach():
    host, th = _host(safe_xy_before_dock=True, safe_xy_x=5.5, safe_xy_y=10.0)
    dock = DockExecutor(host)
    dock.run_dock_motion("attach")

    assert not any(m[0][:2] == [5.5, 10.0] for m in th.moves)
