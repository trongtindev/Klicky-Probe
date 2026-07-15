from klicky_probe.probe_state import (
    AttachAction,
    DetachAction,
    ProbeAttachState,
    ProbeState,
    plan_attach_after_query,
    plan_detach_after_query,
)


def test_query_triggered_means_docked():
    st = ProbeState()
    st.set_from_query(True)
    assert st.attach_state == ProbeAttachState.DOCKED
    st.set_from_query(False)
    assert st.attach_state == ProbeAttachState.ATTACHED


def test_attach_requires_xy_homed():
    st = ProbeState()
    assert st.plan_attach(xy_homed=False) == AttachAction.ERROR_NOT_HOMED_XY


def test_attach_skip_when_attached():
    st = ProbeState(attach_state=ProbeAttachState.ATTACHED)
    assert st.plan_attach(xy_homed=True) == AttachAction.SKIP_ALREADY_ATTACHED


def test_attach_reseat_when_attached_and_require_fresh():
    st = ProbeState(attach_state=ProbeAttachState.ATTACHED)
    assert st.plan_attach(xy_homed=True, require_fresh=True) == AttachAction.RESEAT


def test_attach_reseat_wins_over_lock():
    st = ProbeState(attach_state=ProbeAttachState.ATTACHED, locked=True)
    assert st.plan_attach(xy_homed=True, require_fresh=True) == AttachAction.RESEAT


def test_attach_skip_when_locked():
    st = ProbeState(attach_state=ProbeAttachState.DOCKED, locked=True)
    assert st.plan_attach(xy_homed=True) == AttachAction.SKIP_LOCKED


def test_attach_when_docked():
    st = ProbeState(attach_state=ProbeAttachState.DOCKED)
    assert st.plan_attach(xy_homed=True) == AttachAction.ATTACH


def test_attach_require_fresh_when_docked_is_attach():
    st = ProbeState(attach_state=ProbeAttachState.DOCKED)
    assert st.plan_attach(xy_homed=True, require_fresh=True) == AttachAction.ATTACH


def test_detach_requires_xy_homed():
    st = ProbeState(attach_state=ProbeAttachState.ATTACHED)
    assert st.plan_detach(xy_homed=False) == DetachAction.ERROR_NOT_HOMED_XY


def test_detach_blocked_when_locked():
    st = ProbeState(attach_state=ProbeAttachState.ATTACHED, locked=True)
    assert st.plan_detach(xy_homed=True) == DetachAction.SKIP_LOCKED


def test_detach_force_when_locked():
    st = ProbeState(attach_state=ProbeAttachState.ATTACHED, locked=True)
    assert st.plan_detach(xy_homed=True, force=True) == DetachAction.DETACH


def test_detach_skip_when_docked():
    st = ProbeState(attach_state=ProbeAttachState.DOCKED)
    assert st.plan_detach(xy_homed=True) == DetachAction.SKIP_ALREADY_DOCKED


def test_detach_when_attached():
    st = ProbeState(attach_state=ProbeAttachState.ATTACHED)
    assert st.plan_detach(xy_homed=True) == DetachAction.DETACH


def test_disable_docking():
    st = ProbeState(attach_state=ProbeAttachState.DOCKED)
    assert st.plan_attach(xy_homed=True, disable_docking=True) == AttachAction.SKIP_DISABLED
    st = ProbeState(attach_state=ProbeAttachState.ATTACHED)
    assert st.plan_detach(xy_homed=True, disable_docking=True) == DetachAction.SKIP_DISABLED


def test_verify_attach_detach():
    st = ProbeState()
    assert st.verify_after_attach(probe_triggered=True) == "attach_failed"
    assert st.verify_after_attach(probe_triggered=False) is None
    assert st.attach_state == ProbeAttachState.ATTACHED
    assert st.verify_after_detach(probe_triggered=False) == "dock_failed"
    assert st.verify_after_detach(probe_triggered=True) is None
    assert st.attach_state == ProbeAttachState.DOCKED


def test_lock_unlock():
    st = ProbeState()
    st.lock()
    assert st.locked
    st.unlock()
    assert not st.locked


# --- #174: plan after hardware query (manual attach / desync) ---


def test_plan_detach_after_query_manual_attach():
    """Software thought docked; hardware says attached (open) → DETACH."""
    st = ProbeState(attach_state=ProbeAttachState.DOCKED)
    action = plan_detach_after_query(st, probe_triggered=False, xy_homed=True)
    assert st.attach_state == ProbeAttachState.ATTACHED
    assert action == DetachAction.DETACH


def test_plan_detach_after_query_already_docked():
    st = ProbeState(attach_state=ProbeAttachState.UNKNOWN)
    action = plan_detach_after_query(st, probe_triggered=True, xy_homed=True)
    assert action == DetachAction.SKIP_ALREADY_DOCKED


def test_plan_attach_after_query_manual_dock():
    """Software thought attached; hardware says docked (triggered) → ATTACH."""
    st = ProbeState(attach_state=ProbeAttachState.ATTACHED)
    action = plan_attach_after_query(st, probe_triggered=True, xy_homed=True)
    assert st.attach_state == ProbeAttachState.DOCKED
    assert action == AttachAction.ATTACH


def test_plan_attach_after_query_require_fresh_reseat():
    st = ProbeState()
    action = plan_attach_after_query(
        st, probe_triggered=False, xy_homed=True, require_fresh=True
    )
    assert action == AttachAction.RESEAT
