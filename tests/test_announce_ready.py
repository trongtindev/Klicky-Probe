"""Ready banner: log at ready, console only after deferred timer."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from klicky_probe import KlickyProbe
from klicky_probe.constants import ANNOUNCE_CONSOLE_DELAY


def _settings_stub():
    return SimpleNamespace(
        dock_x=0.0,
        dock_y=350.0,
        dock_z=None,
        approach_x=30.0,
        approach_y=0.0,
        approach_z=0.0,
        detach_x=0.0,
        detach_y=40.0,
        detach_z=0.0,
        clearance_z=25.0,
        travel_speed=200.0,
        z_home_x=175.0,
        z_home_y=150.0,
        bed_min_x=0.0,
        bed_max_x=350.0,
        bed_min_y=0.0,
        bed_max_y=350.0,
    )


_DEFAULT = object()


def _host_for_announce(*, settings=_DEFAULT, features=None):
    """Minimal host with unbound KlickyProbe announce methods bound on."""
    reactor = SimpleNamespace(
        monotonic=lambda: 100.0,
        NEVER=9999999999999999.0,
        register_timer=MagicMock(),
    )
    if settings is _DEFAULT:
        settings = _settings_stub()
    host = SimpleNamespace(
        settings=settings,
        _ready_features=list(features or ["G28 override"]),
        _pending_ready_console_lines=None,
        gcode=MagicMock(),
        reactor=reactor,
    )
    host._ready_banner_lines = (
        lambda: KlickyProbe._ready_banner_lines(host)
    )
    host._schedule_ready_announce = (
        lambda: KlickyProbe._schedule_ready_announce(host)
    )
    host._announce_ready_console_timer = (
        lambda eventtime: KlickyProbe._announce_ready_console_timer(
            host, eventtime
        )
    )
    return host


def test_ready_banner_lines_empty_without_settings():
    host = _host_for_announce(settings=None)
    assert host._ready_banner_lines() == []


def test_ready_banner_lines_include_version_and_features():
    host = _host_for_announce(features=["G28 override", "probe session hooks"])
    lines = host._ready_banner_lines()
    assert lines
    assert any("initialized" in line for line in lines)
    assert any("G28 override" in line for line in lines)
    assert any("gantry" in line for line in lines)


def test_schedule_logs_and_registers_timer_without_console():
    host = _host_for_announce()
    host._schedule_ready_announce()

    host.gcode.respond_info.assert_not_called()
    assert host._pending_ready_console_lines is not None
    assert len(host._pending_ready_console_lines) >= 1

    host.reactor.register_timer.assert_called_once()
    cb, wake = host.reactor.register_timer.call_args[0]
    assert cb is host._announce_ready_console_timer
    assert abs(wake - (100.0 + ANNOUNCE_CONSOLE_DELAY)) < 1e-9


def test_schedule_noop_without_settings():
    host = _host_for_announce(settings=None)
    host._schedule_ready_announce()
    host.gcode.respond_info.assert_not_called()
    host.reactor.register_timer.assert_not_called()
    assert host._pending_ready_console_lines is None


def test_console_timer_emits_pending_and_is_oneshot():
    host = _host_for_announce()
    host._pending_ready_console_lines = [
        "klicky_probe v1.0.0: initialized — ready",
        "  features: G28 override",
    ]

    ret = host._announce_ready_console_timer(100.0)

    assert ret == host.reactor.NEVER
    assert host._pending_ready_console_lines is None
    assert host.gcode.respond_info.call_count == 2
    for call in host.gcode.respond_info.call_args_list:
        assert call.kwargs.get("log") is False
    first = host.gcode.respond_info.call_args_list[0].args[0]
    assert "initialized" in first


def test_console_timer_empty_pending_is_safe():
    host = _host_for_announce()
    host._pending_ready_console_lines = None
    ret = host._announce_ready_console_timer(0.0)
    assert ret == host.reactor.NEVER
    host.gcode.respond_info.assert_not_called()


def test_schedule_then_timer_full_path():
    """Production orchestrator + one-shot timer end-to-end on a stub host."""
    host = _host_for_announce()
    host._schedule_ready_announce()
    host.gcode.respond_info.assert_not_called()

    cb, _wake = host.reactor.register_timer.call_args[0]
    ret = cb(101.0)

    assert ret == host.reactor.NEVER
    assert host.gcode.respond_info.call_count >= 1
    assert host._pending_ready_console_lines is None
