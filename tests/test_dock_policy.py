from klicky_probe.dock_policy import (
    DockIntent,
    apply_dock_intent_to_state,
    parse_bool_token,
    parse_dock_intent,
    strip_klicky_params,
)
from klicky_probe.homing_plan import HomingRequest, plan_homing


def test_parse_bool_token():
    assert parse_bool_token(None) is True
    assert parse_bool_token("") is True
    assert parse_bool_token("1") is True
    assert parse_bool_token("0") is False
    assert parse_bool_token("yes") is True
    assert parse_bool_token("off") is False


def test_probe_lock_leave_and_lock():
    i = parse_dock_intent({"PROBE_LOCK": "1"})
    assert i.leave_attached is True
    assert i.lock is True
    assert i.force_dock is False
    assert i.suppress_auto_detach is True


def test_probe_lock_bare():
    i = parse_dock_intent({"PROBE_LOCK": ""})
    assert i.leave_attached and i.lock


def test_probe_lock_zero():
    i = parse_dock_intent({"PROBE_LOCK": "0"})
    assert i.leave_attached is False
    assert i.lock is False


def test_dock_zero_leave_without_lock():
    i = parse_dock_intent({"DOCK": "0"})
    assert i.leave_attached is True
    assert i.lock is False
    assert i.force_dock is False


def test_dock_zero_with_probe_lock():
    i = parse_dock_intent({"DOCK": "0", "PROBE_LOCK": "1"})
    assert i.leave_attached is True
    assert i.lock is True


def test_dock_one_force():
    i = parse_dock_intent({"DOCK": "1"})
    assert i.force_dock is True
    assert i.leave_attached is False


def test_dock_one_wins_over_probe_lock():
    i = parse_dock_intent({"DOCK": "1", "PROBE_LOCK": "1"})
    assert i.force_dock is True
    assert i.leave_attached is False


def test_default_intent():
    i = parse_dock_intent({})
    assert i == DockIntent()
    assert apply_dock_intent_to_state(i, locked=False) == (False, True)
    assert apply_dock_intent_to_state(i, locked=True) == (False, False)


def test_apply_leave_no_detach():
    i = parse_dock_intent({"DOCK": "0"})
    assert apply_dock_intent_to_state(i, locked=False) == (False, False)


def test_apply_force_even_if_locked():
    i = parse_dock_intent({"DOCK": "1"})
    assert apply_dock_intent_to_state(i, locked=True) == (True, True)


def test_apply_dock_intent_to_state():
    assert apply_dock_intent_to_state(
        parse_dock_intent({"DOCK": "1"}), locked=True
    ) == (True, True)
    assert apply_dock_intent_to_state(
        parse_dock_intent({"PROBE_LOCK": "1"}), locked=False
    ) == (False, False)
    assert apply_dock_intent_to_state(DockIntent(), locked=False) == (False, True)


def test_strip_klicky_params():
    out = strip_klicky_params(
        {"ADAPTIVE": "1", "PROBE_LOCK": "1", "DOCK": "0", "PROFILE": "default"}
    )
    assert "PROBE_LOCK" not in {k.upper() for k in out}
    assert "DOCK" not in {k.upper() for k in out}
    assert out["ADAPTIVE"] == "1"
    assert out["PROFILE"] == "default"


def test_g28_dock_zero_leave_attached():
    req = HomingRequest.from_params({"Z": "0", "DOCK": "0"})
    assert req.leave_probe_attached is True
    assert req.lock_probe is False
    plan = plan_homing(
        req,
        xy_homed=True,
        home_first="auto",
        approach_y=0.0,
        z_virtual_endstop=True,
        dock_before_z_home=True,
    )
    assert plan.detach_after_z is False
    assert plan.lock_after_attach is False


def test_g28_probe_lock_sets_lock_flag():
    req = HomingRequest.from_params({"PROBE_LOCK": "1"})
    assert req.leave_probe_attached is True
    assert req.lock_probe is True
    plan = plan_homing(
        req,
        xy_homed=True,
        home_first="auto",
        approach_y=0.0,
        z_virtual_endstop=True,
        dock_before_z_home=True,
    )
    assert plan.detach_after_z is False
    assert plan.lock_after_attach is True


def test_physical_z_never_skips_detach_before():
    req = HomingRequest.from_params({"Z": "0", "PROBE_LOCK": "1"})
    plan = plan_homing(
        req,
        xy_homed=True,
        home_first="auto",
        approach_y=0.0,
        z_virtual_endstop=False,
        dock_before_z_home=True,
    )
    assert plan.detach_before_z is True
    assert plan.attach_before_z is False
