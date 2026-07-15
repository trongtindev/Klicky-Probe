"""Probe XY staging policy (pure logic).

Stock Klipper probes only at the current toolhead XY. Klicky wraps can stage
to a configured or one-shot XY first (PROBE_ACCURACY, PROBE_CALIBRATE, …).

Runtime params (stripped before stock handlers):
- ``MOVE=0/1`` — override config ``*_move``
- ``X=`` / ``Y=`` — one-shot toolhead target (both required)
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Tuple

from . import messages as msg
from .dock_policy import _params_upper, parse_bool_token

# Shared staging keys — strip before stock probe handlers see the gcmd.
PROBE_STAGING_PARAMS = frozenset({"MOVE", "X", "Y"})
# Backward-compatible alias
PROBE_ACCURACY_STAGING_PARAMS = PROBE_STAGING_PARAMS


def resolve_probe_stage_move(
    params: Optional[Mapping[str, Any]],
    *,
    config_move: bool,
) -> bool:
    """Whether to stage XY before a probe op.

    ``MOVE=0/1`` on the command overrides the config default.
    """
    upper = _params_upper(params)
    if "MOVE" in upper:
        return parse_bool_token(upper.get("MOVE"))
    return bool(config_move)


def resolve_probe_stage_xy(
    params: Optional[Mapping[str, Any]],
    *,
    default_x: float,
    default_y: float,
) -> Tuple[float, float]:
    """Resolve toolhead XY for staging.

    Order: gcmd X+Y → caller defaults. Raises ValueError if only one of X/Y.
    """
    upper = _params_upper(params)
    has_x = "X" in upper
    has_y = "Y" in upper
    if has_x ^ has_y:
        raise ValueError(msg.probe_accuracy_xy_incomplete())
    if has_x and has_y:
        return float(upper["X"]), float(upper["Y"])
    return float(default_x), float(default_y)


# Backward-compatible names (PROBE_ACCURACY call sites / tests).
resolve_probe_accuracy_move = resolve_probe_stage_move
resolve_probe_accuracy_xy = resolve_probe_stage_xy
