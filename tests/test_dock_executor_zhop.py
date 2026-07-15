"""Unhomed Z-hop must not stack (G28 + attach clearance + failed re-home)."""

from __future__ import annotations

from types import SimpleNamespace

from klicky_probe.dock_executor import DockExecutor


class _FakeKinematics:
    def __init__(self, toolhead: _FakeToolhead):
        self._th = toolhead

    def clear_homing_state(self, axes: str) -> None:
        for a in axes:
            self._th.homed_axes = self._th.homed_axes.replace(a, "")


class _FakeToolhead:
    def __init__(self):
        self.pos = [10.0, 20.0, 5.0]
        self.homed_axes = ""
        self.moves = []
        self.set_position_calls = []
        self._kin = _FakeKinematics(self)

    def get_position(self):
        return list(self.pos)

    def get_status(self, _eventtime):
        return {"homed_axes": self.homed_axes}

    def set_position(self, pos, homing_axes=None):
        self.pos = list(pos)
        self.set_position_calls.append((list(pos), homing_axes))
        if homing_axes:
            for a in homing_axes:
                if a not in self.homed_axes:
                    self.homed_axes += a

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


def _host(clearance_z: float = 25.0, z_hop_when_unhomed: bool = True):
    th = _FakeToolhead()
    settings = SimpleNamespace(
        clearance_z=clearance_z,
        z_hop_when_unhomed=z_hop_when_unhomed,
        z_speed=20.0,
        travel_speed=200.0,
        attach_speed=50.0,
        detach_speed=75.0,
        # geometry unused by hop tests
        dock_x=0.0,
        dock_y=0.0,
        dock_z=None,
        approach_x=0.0,
        approach_y=0.0,
        approach_z=0.0,
        detach_x=0.0,
        detach_y=0.0,
        detach_z=0.0,
        approach2_x=0.0,
        approach2_y=0.0,
        approach2_z=0.0,
    )
    host = SimpleNamespace(
        settings=settings,
        _toolhead=th,
        reactor=_FakeReactor(),
        _debug=lambda *a, **k: None,
    )
    return host, th


def test_z_hop_unhomed_runs_once_while_still_unhomed():
    host, th = _host(clearance_z=25.0)
    dock = DockExecutor(host)

    dock.z_hop_unhomed(25.0)
    dock.z_hop_unhomed(25.0)
    dock.z_hop_unhomed(25.0)

    # One set_position(Z=0) + one raise to clearance — not 3x stacking.
    assert len(th.set_position_calls) == 1
    assert th.set_position_calls[0][0][2] == 0.0
    z_moves = [m for m in th.moves if m[0][2] is not None]
    assert len(z_moves) == 1
    assert z_moves[0][0][2] == 25.0
    assert "z" not in th.homed_axes


def test_ensure_clearance_does_not_stack_unhomed_hops():
    host, th = _host(clearance_z=25.0)
    dock = DockExecutor(host)

    # Same path as G28 start hop + attach/detach ensure_clearance (x2).
    dock.z_hop_unhomed(25.0)
    dock.ensure_clearance()
    dock.ensure_clearance()

    assert len(th.set_position_calls) == 1
    assert sum(1 for m in th.moves if m[0][2] == 25.0) == 1


def test_hop_allowed_again_after_z_homed():
    host, th = _host(clearance_z=25.0)
    dock = DockExecutor(host)

    dock.z_hop_unhomed(25.0)
    assert len(th.set_position_calls) == 1

    # Successful Z home path
    th.homed_axes = "xyz"
    th.pos[2] = 0.5
    dock.note_z_homed()

    # Later unhomed again (e.g. clear_homing / restart kinematics)
    th.homed_axes = "xy"
    dock.z_hop_unhomed(25.0)

    assert len(th.set_position_calls) == 2


def test_ensure_clearance_resets_flag_when_z_homed():
    host, th = _host(clearance_z=25.0)
    dock = DockExecutor(host)

    dock.z_hop_unhomed(25.0)
    th.homed_axes = "xyz"
    th.pos[2] = 30.0  # already above clearance — no move
    dock.ensure_clearance()

    th.homed_axes = ""
    dock.z_hop_unhomed(25.0)
    assert len(th.set_position_calls) == 2


def test_z_hop_skipped_when_disabled():
    host, th = _host(z_hop_when_unhomed=False)
    dock = DockExecutor(host)
    dock.ensure_clearance()
    assert th.set_position_calls == []
    assert th.moves == []
