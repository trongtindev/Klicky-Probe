import inspect

import klicky_probe.messages as msg
from klicky_probe.klipper_version import MIN_KLIPPER_VERSION


def test_public_callables_return_nonempty_strings():
    """Every public function in messages returns a non-empty str (no-arg or sample)."""
    samples = {
        "missing_required": (["dock_x", "dock_y"],),
        "home_first_invalid": ("z",),
        "klipper_version_too_old": ("v0.12.0", MIN_KLIPPER_VERSION),
        "klipper_version_unparseable": ("?", MIN_KLIPPER_VERSION),
        "outside_bed": (0.0, 350.0, 0.0, 350.0),
        "verify_failed": ("attach_failed",),
        "geometry_mode_invalid": ("travel",),
        "probe_operation_failed_code": ("attach_failed",),
        "probe_status_report": ("attached", False, 0, 0),
        "log_loading": ("1.0.0",),
        "log_config_ok": (
            "1.0.0",
            "v0.13.0",
            0.0,
            350.0,
            None,
            30.0,
            0.0,
            0.0,
            0.0,
            40.0,
            0.0,
            25.0,
            200.0,
            0.0,
            350.0,
            0.0,
            350.0,
            175.0,
            150.0,
            True,
            True,
            False,
        ),
        "log_resolved_detail": (
            40.0,
            40.0,
            15.0,
            True,
            False,
            True,
            "auto",
            2,
            True,
            False,
            False,
            False,
            False,
        ),
        "feature_dock_servo": ("dock_servo",),
        "ready_banner": ("1.0.0",),
        "ready_geometry_line": (
            0.0,
            350.0,
            None,
            30.0,
            0.0,
            0.0,
            0.0,
            40.0,
            0.0,
        ),
        "ready_motion_line": (25.0, 200.0, 175.0, 150.0, 0.0, 350.0, 0.0, 350.0),
        "ready_features_line": (["G28 override", "auto_attach"],),
        "ready_gcodes_line": (),
        "ready_announce_lines": (
            "1.0.0",
            0.0,
            350.0,
            None,
            30.0,
            0.0,
            0.0,
            0.0,
            40.0,
            0.0,
            25.0,
            200.0,
            175.0,
            150.0,
            0.0,
            350.0,
            0.0,
            350.0,
            ["G28 override"],
        ),
        "log_line_for_ready": ("  features: G28",),
        "skew_frame_active": ("default",),
        "verbose_console": ("probe attached",),
        "debug_console": ("trace",),
        "debug_log": ("trace",),
        "info_log": ("probe attached",),
        "log_dock_retry": ("attach", 2),
    }
    for name, obj in inspect.getmembers(msg, inspect.isfunction):
        if name.startswith("_"):
            continue
        if obj.__module__ != msg.__name__:
            continue
        args = samples.get(name, ())
        result = obj(*args)
        if name == "ready_announce_lines":
            assert isinstance(result, list) and result, name
            for line in result:
                assert isinstance(line, str) and line.strip(), name
            continue
        assert isinstance(result, str) and result.strip(), name


def test_version_messages_include_fix():
    too_old = msg.klipper_version_too_old(found="v0.12.0", required=MIN_KLIPPER_VERSION)
    assert "v0.12.0" in too_old
    assert "0.13.0" in too_old
    assert "Upgrade" in too_old or "upgrade" in too_old.lower()

    bad = msg.klipper_version_unparseable(found="?", required=MIN_KLIPPER_VERSION)
    assert "?" in bad
    assert "0.13.0" in bad


def test_verify_failed_maps_codes():
    assert msg.verify_failed("attach_failed") == msg.attach_failed()
    assert msg.verify_failed("dock_failed") == msg.dock_failed()
    assert "unknown_code" in msg.verify_failed("unknown_code")


def test_adaptive_mentions_full_mesh_fallback():
    text = msg.adaptive_needs_exclude_object()
    assert "exclude_object" in text
    assert "full mesh" in text.lower() or "Using full mesh" in text


def test_session_api_mentions_auto_attach_off():
    text = msg.session_api_required()
    assert "start_probe_session" in text
    assert "auto_attach: False" in text


def test_info_messages():
    assert "already docked" in msg.probe_already_docked().lower()
    assert "ENSURE_PROBE_DOCKED" in msg.probe_docked_ensure()
    assert "paper test" in msg.probe_calibrate_leave_attached().lower()
    status = msg.probe_status_report("attached", True, 1, 0)
    assert "attached" in status
    assert "locked=True" in status
    assert "session=1" in status


def test_startup_messages():
    load = msg.log_loading("1.0.0")
    assert "1.0.0" in load
    assert "loading" in load.lower()

    lines = msg.ready_announce_lines(
        "1.0.0",
        0.0,
        350.0,
        None,
        30.0,
        0.0,
        0.0,
        0.0,
        40.0,
        0.0,
        25.0,
        200.0,
        175.0,
        150.0,
        0.0,
        350.0,
        0.0,
        350.0,
        [msg.feature_g28_override()],
    )
    assert any("initialized" in line for line in lines)
    assert any("gantry" in line for line in lines)
    assert any("G28 override" in line for line in lines)
    assert msg.log_line_for_ready("  dock=...") == "klicky_probe:  dock=..."
