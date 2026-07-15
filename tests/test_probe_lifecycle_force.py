"""ProbeLifecycle.detach_probe(force=...) unlock contract."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from klicky_probe.probe_lifecycle import ProbeLifecycle
from klicky_probe.probe_state import ProbeAttachState, ProbeState


@dataclass
class LifecycleHarness:
    """Test doubles for ProbeLifecycle; take only the fields you need."""

    host: Any
    state: Any
    dock: Any


def _host_for_lifecycle(*, attach_state, locked, triggered) -> LifecycleHarness:
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
        _verbose=MagicMock(),
    )
    return LifecycleHarness(host, state, dock)


def test_force_unlocks_even_when_already_docked():
    """force clears PROBE_LOCK even if motion is SKIP_ALREADY_DOCKED."""
    # Hardware reports docked (triggered=True on typical Klicky wiring).
    h = _host_for_lifecycle(
        attach_state=ProbeAttachState.DOCKED,
        locked=True,
        triggered=True,
    )
    life = ProbeLifecycle(h.host)
    life.detach_probe(force=True)

    assert h.state.locked is False
    h.dock.dock_with_retries.assert_not_called()


def test_force_detach_attached_clears_lock_and_docks():
    h = _host_for_lifecycle(
        attach_state=ProbeAttachState.ATTACHED,
        locked=True,
        triggered=False,  # open switch ≈ attached
    )
    life = ProbeLifecycle(h.host)
    life.detach_probe(force=True)

    assert h.state.locked is False
    h.dock.dock_with_retries.assert_called_once()


def test_detach_default_docks_when_attached():
    h = _host_for_lifecycle(
        attach_state=ProbeAttachState.ATTACHED,
        locked=False,
        triggered=False,
    )
    life = ProbeLifecycle(h.host)
    life.detach_probe()

    h.dock.dock_with_retries.assert_called_once()
    h.host._verbose.assert_called()
