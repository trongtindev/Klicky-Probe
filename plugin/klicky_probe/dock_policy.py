"""
Dock / leave-attached policy for probe-using G-code commands (pure logic).

Collision-safe defaults
-----------------------
1. **Default after each probe op: dock** — probe off the toolhead so free
   travel / printing cannot snag a hanging probe on the bed, clips, or parts.
2. **Always raise Z to clearance before XY travel** to/from the dock
   (executor responsibility; not decided here).
3. **Physical Z endstop:** dock *before* Z home so the probe body cannot
   hit the bed while the nozzle finds the switch.
4. **Virtual Z endstop:** attach *before* Z home; default dock *after*
   unless the caller asks to leave the probe on.
5. **Multi-step calibration / start sequences:** pass ``PROBE_LOCK=1`` (or
   ``DOCK=0``) on each intermediate command so the machine does not thrash
   dock→attach between steps; **dock once** after the last probe step
   (``DETACH_PROBE`` or final command without leave, or ``DOCK=1``).

G-code params (any overridden command)
--------------------------------------
- ``PROBE_LOCK=1`` (or bare ``PROBE_LOCK``): after the op, **leave attached
  and lock** so auto-detach from later ops is skipped until ``UNLOCK_PROBE``.
- ``PROBE_LOCK=0``: do not leave/lock from this param (default dock policy).
- ``DOCK=0``: after the op, **leave attached** without locking (next command
  that finishes without leave/lock may dock).
- ``DOCK=1``: **force dock** at end (unlocks if needed, then detach).

If both are set: ``DOCK=1`` wins (force dock). ``DOCK=0`` + ``PROBE_LOCK=1``
→ leave attached and lock.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional


# Params consumed by klicky_probe wrappers — strip before calling stock handlers.
KLICKY_GCODE_PARAMS = frozenset({"PROBE_LOCK", "DOCK"})


@dataclass(frozen=True)
class DockIntent:
    """Caller intent for attach lifecycle after one probe-using command."""

    leave_attached: bool = False
    lock: bool = False
    force_dock: bool = False

    @property
    def suppress_auto_detach(self) -> bool:
        """True when session end / wrappers must not dock for this leave intent."""
        return self.leave_attached and not self.force_dock


def parse_bool_token(value: Any) -> bool:
    """
    Truthiness for PROBE_LOCK / DOCK style tokens.

    True for bare/empty presence or 1/true/yes/on.
    False for 0/false/no/off.
    Unknown non-empty strings → False (safe default: do not leave attached).
    """
    if value is None:
        return True
    s = str(value).strip().lower()
    if s in ("", "1", "true", "yes", "on"):
        return True
    if s in ("0", "false", "no", "off"):
        return False
    return False


def _params_upper(params: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    if not params:
        return {}
    return {str(k).upper(): v for k, v in params.items()}


def parse_dock_intent(params: Optional[Mapping[str, Any]]) -> DockIntent:
    """Parse PROBE_LOCK / DOCK from a G-code parameter mapping."""
    upper = _params_upper(params)
    has_lock = "PROBE_LOCK" in upper
    has_dock = "DOCK" in upper

    probe_lock = parse_bool_token(upper.get("PROBE_LOCK")) if has_lock else False
    dock_on: Optional[bool] = None
    if has_dock:
        dock_on = parse_bool_token(upper.get("DOCK"))

    # DOCK=1 always force-docks at end.
    if dock_on is True:
        return DockIntent(leave_attached=False, lock=False, force_dock=True)

    # DOCK=0 → leave attached; lock only if PROBE_LOCK truthy.
    if dock_on is False:
        return DockIntent(
            leave_attached=True,
            lock=bool(probe_lock),
            force_dock=False,
        )

    # PROBE_LOCK only
    if has_lock and probe_lock:
        return DockIntent(leave_attached=True, lock=True, force_dock=False)

    return DockIntent()


def strip_klicky_params(params: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Drop Klicky-only keys so stock Klipper handlers never see them."""
    if not params:
        return {}
    return {
        k: v
        for k, v in params.items()
        if str(k).upper() not in KLICKY_GCODE_PARAMS
    }


def apply_dock_intent_to_state(
    intent: DockIntent,
    *,
    locked: bool,
) -> tuple[bool, bool]:
    """
    Pure decision after a successful probe op.

    Returns (should_unlock, should_detach).
    If force_dock, unlock then detach.
    If leave + lock, caller should set locked=True (not returned as unlock).
    """
    if intent.force_dock:
        return True, True
    if intent.leave_attached:
        return False, False
    if locked:
        return False, False
    return False, True
