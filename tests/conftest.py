"""Shared fixtures for Klicky pure-logic tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Prefer editable install (`pip install -e ".[dev]"`). Fallback: put plugin/ on
# sys.path so pytest works without an install (local one-off runs).
try:
    import klicky_probe  # noqa: F401
except ImportError:
    _plugin = Path(__file__).resolve().parents[1] / "plugin"
    if str(_plugin) not in sys.path:
        sys.path.insert(0, str(_plugin))

from klicky_probe.defaults import PrinterSnapshot
from klicky_probe.geometry import DockGeometry


@pytest.fixture
def printer_voron_like() -> PrinterSnapshot:
    return PrinterSnapshot(
        stepper_x_position_max=350.0,
        stepper_y_position_max=350.0,
        probe_x_offset=0.0,
        probe_y_offset=25.0,
        probe_z_offset=0.0,
        max_velocity=300.0,
        max_accel=3000.0,
        z_virtual_endstop=False,
        has_bed_mesh=True,
        has_exclude_object=True,
    )


@pytest.fixture
def gantry_dock() -> DockGeometry:
    """Back extrusion gantry dock (no fixed Z)."""
    return DockGeometry(
        dock_x=0.0,
        dock_y=350.0,
        dock_z=None,
        approach_x=30.0,
        approach_y=0.0,
        approach_z=0.0,
        detach_x=0.0,
        detach_y=40.0,
        detach_z=0.0,
    )


@pytest.fixture
def fixed_z_dock() -> DockGeometry:
    return DockGeometry(
        dock_x=250.0,
        dock_y=0.0,
        dock_z=20.0,
        approach_x=0.0,
        approach_y=30.0,
        approach_z=5.0,
        detach_x=0.0,
        detach_y=-40.0,
        detach_z=0.0,
    )


@pytest.fixture
def euclid_like_dock() -> DockGeometry:
    return DockGeometry(
        dock_x=300.0,
        dock_y=295.0,
        dock_z=None,
        approach_x=-70.0,
        approach_y=0.0,
        approach_z=0.0,
        detach_x=0.0,
        detach_y=-40.0,
        detach_z=0.0,
        approach2_x=0.0,
        approach2_y=40.0,
        approach2_z=0.0,
    )


@pytest.fixture
def minimal_user() -> dict:
    # Rear dock: approach from bed side; dock_x inset so release (dock+detach)
    # stays inside the default 0..max envelope (printer_voron_like).
    return {
        "dock_x": 40.0,
        "dock_y": 300.0,
        "approach_x": 0.0,
        "approach_y": 30.0,
        "detach_x": -40.0,
        "detach_y": 0.0,
    }
