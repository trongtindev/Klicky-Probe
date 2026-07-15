"""ProbeLifecycle.detach_probe(force=...) unlock contract."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from klicky_probe.probe_lifecycle import ProbeLifecycle
from klicky_probe.probe_state import ProbeAttachState, ProbeState


def _host_for_lifecycle(*, attach_state, locked, triggered):
    state = ProbeState(attach_state=attach_state, locked=locked)
    dock = MagicMock()
    host = SimpleNamespace(
        settings=SimpleNamespace(disable_docking=False, clearance_z=25.0, travel_speed=200.0),
        state=state,
        dock=dock,
        gcode=MagicMock(),
        _toolhead=SimpleNamespace(
            get_position=lambda: [0.0, 0.0, 30.0],
            manual_move=MagicMock(),
        ),
        _xy_homed=lambda: True,
        _query_probe_triggered=lambda: triggered,
        _debug=MagicMock(),
        _log=MagicMock(),
        _status_led=MagicMock(),
    )
    return host, state, dock


def test_force_unlocks_even_when_already_docked():
    """force clears PROBE_LOCK even if motion is SKIP_ALREADY_DOCKED."""
    # Hardware reports docked (triggered=True on typical Klicky wiring).
    host, state, dock = _host_for_lifecycle(
        attach_state=ProbeAttachState.DOCKED,
        locked=True,
        triggered=True,
    )
    life = ProbeLifecycle(host)
    life.detach_probe(force=True)

    assert state.locked is False
    dock.dock_with_retries.assert_not_called()
    # No READY flash when status_led default and skip path — skip returns early.
    host._status_led.assert_not_called()


def test_force_detach_attached_clears_lock_and_docks():
    host, state, dock = _host_for_lifecycle(
        attach_state=ProbeAttachState.ATTACHED,
        locked=True,
        triggered=False,  # open switch ≈ attached
    )
    life = ProbeLifecycle(host)
    life.detach_probe(force=True, status_led=False)

    assert state.locked is False
    dock.dock_with_retries.assert_called_once()
    # status_led=False: no BUSY/READY from detach
    host._status_led.assert_not_called()


def test_detach_default_sets_ready_led():
    host, state, dock = _host_for_lifecycle(
        attach_state=ProbeAttachState.ATTACHED,
        locked=False,
        triggered=False,
    )
    life = ProbeLifecycle(host)
    life.detach_probe()

    assert [c.args[0] for c in host._status_led.call_args_list] == [
        "BUSY",
        "READY",
    ]
