"""Probe attach/detach lifecycle: public ops, session hooks, command begin/end."""

from __future__ import annotations

from . import errors as E
from .dock_policy import DockIntent, apply_dock_intent_to_state
from .probe_session import should_detach_on_session_end
from .probe_state import (
    AttachAction,
    DetachAction,
    ProbeAttachState,
    plan_attach_after_query,
    plan_detach_after_query,
)


class ProbeLifecycle:
    """
    Owns attach/detach planning and session/command enter-exit.

    require_fresh for virtual-Z is a one-shot: arm before stock G28 Z, consumed
    on the outermost session begin, cleared when the homing block ends.
    """

    def __init__(self, host):
        self._h = host
        self._require_fresh_oneshot = False

    def arm_require_fresh_oneshot(self) -> None:
        """Arm reseat-on-next-outermost-session (virtual Z #231)."""
        self._require_fresh_oneshot = True

    def clear_require_fresh_oneshot(self) -> None:
        self._require_fresh_oneshot = False

    def peek_require_fresh_oneshot(self) -> bool:
        return self._require_fresh_oneshot

    def consume_require_fresh_oneshot(self) -> bool:
        """Return and clear the one-shot if set (outermost session only)."""
        if not self._require_fresh_oneshot:
            return False
        self._require_fresh_oneshot = False
        return True

    def attach_probe(self, restore=False, require_fresh=False) -> None:
        h = self._h
        s = h.settings
        triggered = h._query_probe_triggered()
        action = plan_attach_after_query(
            h.state,
            triggered,
            xy_homed=h._xy_homed(),
            disable_docking=s.disable_docking,
            require_fresh=require_fresh,
        )
        h._debug(
            "attach plan → %s (triggered=%s)" % (action.value, triggered)
        )
        if action == AttachAction.ERROR_NOT_HOMED_XY:
            raise h.gcode.error(E.home_xy_before_attach())
        if action in (
            AttachAction.SKIP_DISABLED,
            AttachAction.SKIP_LOCKED,
            AttachAction.SKIP_ALREADY_ATTACHED,
        ):
            h._debug("attach: %s" % action.value)
            return

        was_locked = h.state.locked
        if action == AttachAction.RESEAT:
            h._log("reseat: detach then attach (require_fresh)")
            h.state.unlock()
            try:
                h.dock.dock_with_retries(
                    "detach",
                    h.state.verify_after_detach,
                    h._query_probe_triggered,
                )
            except Exception:
                if was_locked:
                    h.state.lock()
                raise

        th = h._toolhead
        start = th.get_position()[:]
        h._status_led("BUSY")
        try:
            h.dock.dock_with_retries(
                "attach",
                h.state.verify_after_attach,
                h._query_probe_triggered,
            )
        finally:
            if action == AttachAction.RESEAT and was_locked:
                h.state.lock()

        h._log("probe attached")
        h._status_led("READY")
        if restore:
            th.manual_move(
                [start[0], start[1], max(start[2], s.clearance_z)], s.travel_speed
            )

    def detach_probe(self, restore=False, force=False) -> None:
        h = self._h
        s = h.settings
        triggered = h._query_probe_triggered()
        action = plan_detach_after_query(
            h.state,
            triggered,
            xy_homed=h._xy_homed(),
            disable_docking=s.disable_docking,
            force=force,
        )
        h._debug(
            "detach plan → %s (triggered=%s)" % (action.value, triggered)
        )
        if action == DetachAction.ERROR_NOT_HOMED_XY:
            raise h.gcode.error(E.home_xy_before_detach())
        if action in (
            DetachAction.SKIP_DISABLED,
            DetachAction.SKIP_LOCKED,
            DetachAction.SKIP_ALREADY_DOCKED,
        ):
            h._debug("detach: %s" % action.value)
            return

        th = h._toolhead
        start = th.get_position()[:]
        h._status_led("BUSY")
        h.dock.dock_with_retries(
            "detach",
            h.state.verify_after_detach,
            h._query_probe_triggered,
        )
        h._log("probe docked")
        h._status_led("READY")
        if restore:
            th.manual_move(
                [start[0], start[1], max(start[2], s.clearance_z)], s.travel_speed
            )

    def on_session_begin(self, require_fresh=False) -> None:
        h = self._h
        if h._session.begin_session():
            h._debug(
                "probe session begin (require_fresh=%s)" % require_fresh
            )
            self.attach_probe(require_fresh=require_fresh)

    def on_session_end(self) -> None:
        h = self._h
        if not h._session.end_session():
            return
        if should_detach_on_session_end(
            locked=h.state.locked, hold_depth=h._session.hold_depth
        ):
            h._debug("probe session end → dock")
            self.detach_probe()
        else:
            h._debug(
                "probe session end → keep attached "
                "(locked=%s hold=%d)"
                % (h.state.locked, h._session.hold_depth)
            )

    def enter_probe_work(self, intent: DockIntent, restore=False) -> None:
        """Start a wrapped G-code op: attach, then lock or DOCK=0 hold."""
        self.attach_probe(restore=restore)
        if intent.force_dock:
            return
        if intent.lock:
            self._h.state.lock()
        elif intent.leave_attached:
            self._h._session.begin_hold()

    def exit_probe_work(self, intent: DockIntent, restore=False) -> None:
        """Finish a wrapped G-code op per DockIntent."""
        h = self._h
        held = intent.leave_attached and not intent.lock and not intent.force_dock
        try:
            if intent.force_dock:
                h.state.unlock()
                self.detach_probe(restore=restore)
                return
            if intent.leave_attached:
                if intent.lock:
                    h.state.lock()
                return
            should_unlock, should_detach = apply_dock_intent_to_state(
                intent, locked=h.state.locked
            )
            if should_unlock:
                h.state.unlock()
            if should_detach:
                self.detach_probe(restore=restore)
        finally:
            if held:
                h._session.end_hold()

    def ensure_probe_docked(self, gcmd) -> None:
        h = self._h
        force = bool(gcmd.get_int("FORCE", 0))
        if not h._xy_homed():
            raise gcmd.error(E.home_xy_before_ensure())
        triggered = h._query_probe_triggered()
        h.state.set_from_query(triggered)
        if h.state.attach_state == ProbeAttachState.DOCKED:
            gcmd.respond_info(E.probe_already_docked())
            return
        if h.state.locked and not force:
            raise gcmd.error(E.probe_locked_ensure())
        if force and h.state.locked:
            h.state.unlock()
            h._log("ENSURE_PROBE_DOCKED FORCE=1: unlocked")
        self.detach_probe()
        gcmd.respond_info(E.probe_docked_ensure())
