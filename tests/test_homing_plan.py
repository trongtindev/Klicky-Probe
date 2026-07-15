from klicky_probe.homing_plan import HomingRequest, plan_homing


def test_home_all_when_no_axes():
    req = HomingRequest.from_params({})
    assert req.home_x and req.home_y and req.home_z


def test_home_single_axis():
    req = HomingRequest.from_params({"X": "0"})
    assert req.home_x and not req.home_y and not req.home_z


def test_probe_lock_param():
    req = HomingRequest.from_params({"X": "0", "Y": "0", "Z": "0", "PROBE_LOCK": "1"})
    assert req.leave_probe_attached


def test_probe_lock_zero_is_false():
    req = HomingRequest.from_params({"X": "0", "Y": "0", "Z": "0", "PROBE_LOCK": "0"})
    assert req.leave_probe_attached is False


def test_probe_lock_false_string():
    req = HomingRequest.from_params({"PROBE_LOCK": "false"})
    assert req.leave_probe_attached is False


def test_probe_lock_bare_empty():
    req = HomingRequest.from_params({"PROBE_LOCK": ""})
    assert req.leave_probe_attached is True


def test_auto_y_first_when_approach_y_zero():
    req = HomingRequest(home_x=True, home_y=True, home_z=False)
    plan = plan_homing(
        req,
        xy_homed=True,
        home_first="auto",
        approach_y=0.0,
        z_virtual_endstop=False,
        dock_before_z_home=True,
    )
    assert plan.xy_order == ["y", "x"]


def test_auto_x_first_when_approach_y_nonzero():
    req = HomingRequest(home_x=True, home_y=True, home_z=False)
    plan = plan_homing(
        req,
        xy_homed=True,
        home_first="auto",
        approach_y=30.0,
        z_virtual_endstop=False,
        dock_before_z_home=True,
    )
    assert plan.xy_order == ["x", "y"]


def test_force_home_first_x():
    req = HomingRequest(home_x=True, home_y=True, home_z=False)
    plan = plan_homing(
        req,
        xy_homed=True,
        home_first="x",
        approach_y=0.0,
        z_virtual_endstop=False,
        dock_before_z_home=True,
    )
    assert plan.xy_order == ["x", "y"]


def test_virtual_z_attach_and_detach():
    req = HomingRequest(home_x=False, home_y=False, home_z=True)
    plan = plan_homing(
        req,
        xy_homed=True,
        home_first="auto",
        approach_y=0.0,
        z_virtual_endstop=True,
        dock_before_z_home=True,
    )
    assert plan.attach_before_z is True
    assert plan.detach_after_z is True
    assert plan.detach_before_z is False
    assert plan.require_fresh_attach is True


def test_virtual_z_reseat_can_be_disabled():
    req = HomingRequest(home_x=False, home_y=False, home_z=True)
    plan = plan_homing(
        req,
        xy_homed=True,
        home_first="auto",
        approach_y=0.0,
        z_virtual_endstop=True,
        dock_before_z_home=True,
        reseat_before_z_home=False,
    )
    assert plan.require_fresh_attach is False


def test_physical_z_no_require_fresh():
    req = HomingRequest(home_x=False, home_y=False, home_z=True)
    plan = plan_homing(
        req,
        xy_homed=True,
        home_first="auto",
        approach_y=0.0,
        z_virtual_endstop=False,
        dock_before_z_home=True,
        reseat_before_z_home=True,
    )
    assert plan.require_fresh_attach is False


def test_virtual_z_probe_lock_keeps_attached():
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
    )
    assert plan.attach_before_z is True
    assert plan.detach_after_z is False
    assert plan.lock_after_attach is True


def test_virtual_z_dock_zero_leave_without_lock():
    req = HomingRequest(
        home_x=False,
        home_y=False,
        home_z=True,
        leave_probe_attached=True,
        lock_probe=False,
    )
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


def test_physical_z_dock_before():
    req = HomingRequest(home_x=False, home_y=False, home_z=True)
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


def test_z_without_xy_forces_full():
    req = HomingRequest(home_x=False, home_y=False, home_z=True)
    plan = plan_homing(
        req,
        xy_homed=False,
        home_first="auto",
        approach_y=0.0,
        z_virtual_endstop=True,
        dock_before_z_home=True,
    )
    assert plan.force_full_home is True
    assert "x" in plan.xy_order and "y" in plan.xy_order
    assert plan.home_z is True
