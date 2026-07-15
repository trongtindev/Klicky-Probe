"""Probe attach/lock state machine (pure logic)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ProbeAttachState(str, Enum):
    UNKNOWN = "unknown"
    ATTACHED = "attached"
    DOCKED = "docked"


class AttachAction(str, Enum):
    ATTACH = "attach"
    RESEAT = "reseat"  # detach then attach (fresh attach / #231)
    SKIP_ALREADY_ATTACHED = "skip_already_attached"
    SKIP_LOCKED = "skip_locked"
    SKIP_DISABLED = "skip_disabled"
    ERROR_NOT_HOMED_XY = "error_not_homed_xy"


class DetachAction(str, Enum):
    DETACH = "detach"
    SKIP_ALREADY_DOCKED = "skip_already_docked"
    SKIP_LOCKED = "skip_locked"
    SKIP_DISABLED = "skip_disabled"
    ERROR_NOT_HOMED_XY = "error_not_homed_xy"


@dataclass
class ProbeState:
    attach_state: ProbeAttachState = ProbeAttachState.UNKNOWN
    locked: bool = False

    def set_from_query(self, probe_triggered: bool) -> None:
        """
        Klicky-style: triggered (True) means switch closed / probe NOT attached
        (open when attached on typical mag-probe wiring).
        """
        if probe_triggered:
            self.attach_state = ProbeAttachState.DOCKED
        else:
            self.attach_state = ProbeAttachState.ATTACHED

    def lock(self) -> None:
        self.locked = True

    def unlock(self) -> None:
        self.locked = False

    def plan_attach(
        self,
        xy_homed: bool,
        disable_docking: bool = False,
        *,
        require_fresh: bool = False,
    ) -> AttachAction:
        if disable_docking:
            return AttachAction.SKIP_DISABLED
        if not xy_homed:
            return AttachAction.ERROR_NOT_HOMED_XY
        if self.attach_state == ProbeAttachState.ATTACHED:
            # Safety reseat before virtual Z wins over lock (#231).
            if require_fresh:
                return AttachAction.RESEAT
            return AttachAction.SKIP_ALREADY_ATTACHED
        # require_fresh allows attach even when locked (Z-home safety).
        if self.locked and not require_fresh:
            return AttachAction.SKIP_LOCKED
        return AttachAction.ATTACH

    def plan_detach(
        self,
        xy_homed: bool = True,
        disable_docking: bool = False,
        *,
        force: bool = False,
    ) -> DetachAction:
        if disable_docking:
            return DetachAction.SKIP_DISABLED
        if not xy_homed:
            return DetachAction.ERROR_NOT_HOMED_XY
        if self.locked and not force:
            return DetachAction.SKIP_LOCKED
        if self.attach_state == ProbeAttachState.DOCKED:
            return DetachAction.SKIP_ALREADY_DOCKED
        # UNKNOWN or ATTACHED → attempt detach
        return DetachAction.DETACH

    def verify_after_attach(self, probe_triggered: bool) -> Optional[str]:
        """Return short code if attach failed (map via messages.verify_failed)."""
        self.set_from_query(probe_triggered)
        if self.attach_state != ProbeAttachState.ATTACHED:
            return "attach_failed"
        return None

    def verify_after_detach(self, probe_triggered: bool) -> Optional[str]:
        """Return short code if detach/dock failed (map via messages.verify_failed)."""
        self.set_from_query(probe_triggered)
        if self.attach_state != ProbeAttachState.DOCKED:
            return "dock_failed"
        return None


def plan_attach_after_query(
    state: ProbeState,
    probe_triggered: bool,
    xy_homed: bool,
    disable_docking: bool = False,
    *,
    require_fresh: bool = False,
) -> AttachAction:
    """Sync from hardware query then plan attach (#174)."""
    state.set_from_query(probe_triggered)
    return state.plan_attach(
        xy_homed, disable_docking, require_fresh=require_fresh
    )


def plan_detach_after_query(
    state: ProbeState,
    probe_triggered: bool,
    xy_homed: bool = True,
    disable_docking: bool = False,
    *,
    force: bool = False,
) -> DetachAction:
    """Sync from hardware query then plan detach (#174)."""
    state.set_from_query(probe_triggered)
    return state.plan_detach(xy_homed, disable_docking, force=force)
