from klicky_probe.homing_plan import HomingRequest, plan_homing
from klicky_probe.probe_session import SessionCounters, should_detach_on_session_end


def test_session_depth_outermost():
    c = SessionCounters()
    assert c.begin_session() is True
    assert c.begin_session() is False
    assert c.end_session() is False
    assert c.end_session() is True


def test_end_session_underflow_fail_closed():
    c = SessionCounters()
    assert c.end_session() is False
    assert c.session_depth == 0
    assert c.end_session() is False
    assert c.session_depth == 0


def test_should_detach_respects_lock_and_hold():
    assert should_detach_on_session_end(locked=False, hold_depth=0) is True
    assert should_detach_on_session_end(locked=True, hold_depth=0) is False
    assert should_detach_on_session_end(locked=False, hold_depth=1) is False


def test_hold_depth():
    c = SessionCounters()
    c.begin_hold()
    assert c.hold_depth == 1
    c.end_hold()
    assert c.hold_depth == 0
    c.end_hold()
    assert c.hold_depth == 0


def test_virtual_z_session_manages_default_no_plan_detach():
    req = HomingRequest(home_x=False, home_y=False, home_z=True)
    plan = plan_homing(
        req,
        xy_homed=True,
        home_first="auto",
        approach_y=0.0,
        z_virtual_endstop=True,
        dock_before_z_home=True,
        session_manages_probe=True,
    )
    assert plan.attach_before_z is False
    assert plan.detach_after_z is False


def test_virtual_z_session_manages_leave_pre_attaches():
    req = HomingRequest(
        home_x=False,
        home_y=False,
        home_z=True,
        leave_probe_attached=True,
        lock_probe=True,
    )
    plan = plan_homing(
        req,
        xy_homed=True,
        home_first="auto",
        approach_y=0.0,
        z_virtual_endstop=True,
        dock_before_z_home=True,
        session_manages_probe=True,
    )
    assert plan.attach_before_z is True
    assert plan.detach_after_z is False
    assert plan.lock_after_attach is True


def test_virtual_z_without_session_still_plan_managed():
    req = HomingRequest(home_x=False, home_y=False, home_z=True)
    plan = plan_homing(
        req,
        xy_homed=True,
        home_first="auto",
        approach_y=0.0,
        z_virtual_endstop=True,
        dock_before_z_home=True,
        session_manages_probe=False,
    )
    assert plan.attach_before_z is True
    assert plan.detach_after_z is True
