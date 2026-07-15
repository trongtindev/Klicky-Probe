from klicky_probe.geometry import (
    SPEED_ATTACH,
    SPEED_DETACH,
    SPEED_TRAVEL,
    attach_entry_xy,
    attach_waypoints,
    clearance_needed,
    detach_entry_xy,
    detach_waypoints,
    travel_to_entry_waypoints,
    waypoints_as_tuples,
)


def test_gantry_attach_waypoints(gantry_dock):
    wps = waypoints_as_tuples(attach_waypoints(gantry_dock))
    # approach2 is zero → no intermediate (would duplicate dock XY)
    assert wps[0] == (-30.0, 350.0, None, SPEED_TRAVEL, "attach_entry_xy")
    assert wps[1] == (0.0, 350.0, None, SPEED_ATTACH, "attach_dock_xy")
    assert wps[2] == (-30.0, 350.0, None, SPEED_DETACH, "attach_exit_xy")
    assert all(wp[2] is None for wp in wps)
    assert not any(wp[4] == "attach_intermediate_xy" for wp in wps)


def test_gantry_detach_waypoints(gantry_dock):
    wps = waypoints_as_tuples(detach_waypoints(gantry_dock))
    assert wps[0] == (-30.0, 350.0, None, SPEED_TRAVEL, "detach_entry_xy")
    assert wps[1] == (0.0, 350.0, None, SPEED_ATTACH, "detach_dock_xy")
    assert wps[2] == (0.0, 390.0, None, SPEED_DETACH, "detach_release_xy")
    assert wps[3] == (-30.0, 390.0, None, SPEED_DETACH, "detach_clear_xy")


def test_fixed_z_attach_includes_z(fixed_z_dock):
    wps = waypoints_as_tuples(attach_waypoints(fixed_z_dock))
    labels = [w[4] for w in wps]
    assert "attach_entry_z2" in labels
    assert "attach_entry_z1" in labels
    assert "attach_dock_z" in labels
    assert "attach_exit_z" in labels
    # dock z = 20, approach_z = 5, approach2_z = 0
    entry_z2 = next(w for w in wps if w[4] == "attach_entry_z2")
    assert entry_z2[2] == 15.0  # 20 - 5 - 0
    dock_z = next(w for w in wps if w[4] == "attach_dock_z")
    assert dock_z[2] == 20.0


def test_fixed_z_detach_includes_z(fixed_z_dock):
    wps = waypoints_as_tuples(detach_waypoints(fixed_z_dock))
    labels = [w[4] for w in wps]
    assert "detach_entry_z" in labels
    assert "detach_dock_z" in labels
    assert "detach_release_z" in labels


def test_euclid_approach2(euclid_like_dock):
    wps = waypoints_as_tuples(attach_waypoints(euclid_like_dock))
    # entry: dock - approach - approach2 = 300 - (-70) - 0 = 370, 295 - 0 - 40 = 255
    assert wps[0][0] == 370.0
    assert wps[0][1] == 255.0
    # intermediate: dock - approach2 = 300, 255
    assert wps[1] == (300.0, 255.0, None, SPEED_ATTACH, "attach_intermediate_xy")
    assert wps[2] == (300.0, 295.0, None, SPEED_ATTACH, "attach_dock_xy")
    # exit: dock - approach = 370, 295
    assert wps[3] == (370.0, 295.0, None, SPEED_DETACH, "attach_exit_xy")


def test_clearance_needed():
    assert clearance_needed(None, 25.0) is True
    assert clearance_needed(10.0, 25.0) is True
    assert clearance_needed(25.0, 25.0) is False
    assert clearance_needed(30.0, 25.0) is False


def test_attach_entry_xy(gantry_dock):
    assert attach_entry_xy(gantry_dock) == (-30.0, 350.0)


def test_detach_entry_xy(gantry_dock):
    assert detach_entry_xy(gantry_dock) == (-30.0, 350.0)


def test_travel_behind_rear_dock_aligns_y_first(gantry_dock):
    """Issue #234: behind dock (wrong X, past Y) → align Y then X."""
    # Gantry dock approach is mainly X (|30| >= |0|) → Y first
    wps = waypoints_as_tuples(
        travel_to_entry_waypoints(
            gantry_dock, cur_x=100.0, cur_y=340.0, mode="detach", enabled=True
        )
    )
    assert wps[0] == (100.0, 350.0, None, SPEED_TRAVEL, "travel_align_y")
    assert wps[1] == (-30.0, 350.0, None, SPEED_TRAVEL, "travel_entry_xy")


def test_travel_side_dock_aligns_x_first(fixed_z_dock):
    """Side dock approach mainly Y → align X first."""
    # fixed_z: approach (0, 30) → dominant Y → X first
    entry = detach_entry_xy(fixed_z_dock)  # (250, -30)
    wps = waypoints_as_tuples(
        travel_to_entry_waypoints(
            fixed_z_dock, cur_x=100.0, cur_y=50.0, mode="detach", enabled=True
        )
    )
    assert wps[0] == (entry[0], 50.0, None, SPEED_TRAVEL, "travel_align_x")
    assert wps[1] == (entry[0], entry[1], None, SPEED_TRAVEL, "travel_entry_xy")


def test_travel_already_at_entry_empty(gantry_dock):
    wps = travel_to_entry_waypoints(
        gantry_dock, cur_x=-30.0, cur_y=350.0, mode="attach", enabled=True
    )
    assert wps == []


def test_travel_disabled_direct(gantry_dock):
    wps = waypoints_as_tuples(
        travel_to_entry_waypoints(
            gantry_dock, cur_x=100.0, cur_y=200.0, mode="attach", enabled=False
        )
    )
    assert wps == [(-30.0, 350.0, None, SPEED_TRAVEL, "travel_entry_xy")]


def test_travel_only_one_axis_needed(gantry_dock):
    # Already at entry Y, only need X
    wps = waypoints_as_tuples(
        travel_to_entry_waypoints(
            gantry_dock, cur_x=50.0, cur_y=350.0, mode="attach", enabled=True
        )
    )
    assert wps == [(-30.0, 350.0, None, SPEED_TRAVEL, "travel_entry_xy")]
