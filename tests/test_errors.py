import inspect

import klicky_probe.errors as E
from klicky_probe.klipper_version import MIN_KLIPPER_VERSION


def test_public_callables_return_nonempty_strings():
    """Every public function in errors returns a non-empty str (no-arg or sample)."""
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
    }
    for name, obj in inspect.getmembers(E, inspect.isfunction):
        if name.startswith("_"):
            continue
        if obj.__module__ != E.__name__:
            continue
        args = samples.get(name, ())
        msg = obj(*args)
        assert isinstance(msg, str) and msg.strip(), name
        assert "klicky" in msg.lower() or "[klicky_probe]" in msg, name


def test_version_messages_include_fix():
    too_old = E.klipper_version_too_old(found="v0.12.0", required=MIN_KLIPPER_VERSION)
    assert "v0.12.0" in too_old
    assert "0.13.0" in too_old
    assert "Upgrade" in too_old or "upgrade" in too_old.lower()

    bad = E.klipper_version_unparseable(found="?", required=MIN_KLIPPER_VERSION)
    assert "?" in bad
    assert "0.13.0" in bad


def test_verify_failed_maps_codes():
    assert E.verify_failed("attach_failed") == E.attach_failed()
    assert E.verify_failed("dock_failed") == E.dock_failed()
    assert "unknown_code" in E.verify_failed("unknown_code")


def test_adaptive_mentions_full_mesh_fallback():
    msg = E.adaptive_needs_exclude_object()
    assert "exclude_object" in msg
    assert "full mesh" in msg.lower() or "Using full mesh" in msg


def test_session_api_mentions_auto_attach_off():
    msg = E.session_api_required()
    assert "start_probe_session" in msg
    assert "auto_attach: False" in msg


def test_info_messages():
    assert "already docked" in E.probe_already_docked().lower()
    assert "ENSURE_PROBE_DOCKED" in E.probe_docked_ensure()
    assert "paper test" in E.probe_calibrate_leave_attached().lower()
    status = E.probe_status_report("attached", True, 1, 0)
    assert "attached" in status
    assert "locked=True" in status
    assert "session=1" in status
