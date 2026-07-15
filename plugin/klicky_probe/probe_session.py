"""
Probe session / command hold counters (pure logic).

Klipper (v0.13+) uses start_probe_session / end_probe_session — not multi_probe_*.
Klicky attaches on outermost session begin and may dock on outermost session end.
"""

from __future__ import annotations

from dataclasses import dataclass


def should_detach_on_session_end(*, locked: bool, hold_depth: int) -> bool:
    """Dock when a probe session closes, unless locked or command hold is open."""
    return (not locked) and hold_depth <= 0


@dataclass
class SessionCounters:
    """Tracks nested probe sessions and DOCK=0 command holds."""

    session_depth: int = 0
    hold_depth: int = 0

    def begin_session(self) -> bool:
        """Return True if this is the outermost session open (caller should attach)."""
        self.session_depth += 1
        return self.session_depth == 1

    def end_session(self) -> bool:
        """
        Close one session level.

        Return True if this was the outermost close (caller may detach).
        Underflow (end without begin) is fail-closed: return False, never
        treat as outermost close so a stray end cannot force dock.
        """
        if self.session_depth <= 0:
            self.session_depth = 0
            return False
        self.session_depth -= 1
        return self.session_depth == 0

    def begin_hold(self) -> None:
        """Command-level leave (DOCK=0): block auto-dock until end_hold."""
        self.hold_depth += 1

    def end_hold(self) -> None:
        self.hold_depth = max(0, self.hold_depth - 1)

    def reset_holds(self) -> None:
        self.hold_depth = 0
