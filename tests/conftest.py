"""Shared fixtures for Klicky pure-logic tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Allow imports of plugin package without install
ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugin"
if str(PLUGIN) not in sys.path:
    sys.path.insert(0, str(PLUGIN))

from klicky_probe.defaults import PrinterSnapshot  # noqa: E402
from klicky_probe.geometry import DockGeometry  # noqa: E402


@pytest.fixture
def printer_voron_like() -> PrinterSnapshot:
    return PrinterSnapshot(
        stepper_x_position_max=350.0,
        stepper_y_position_max=350.0,
        probe_x_offset=0.0,
        probe_y_offset=25.0,
        probe_z_offset=0.0,
        probe_speed=5.0,
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
    return {
        "dock_x": 0.0,
        "dock_y": 300.0,
        "approach_x": 30.0,
        "approach_y": 0.0,
        "detach_x": 0.0,
        "detach_y": 40.0,
    }
