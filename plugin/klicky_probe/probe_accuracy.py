"""PROBE_ACCURACY staging policy (pure logic).

Stock Klipper probes only at the current toolhead XY. When the wrap is
installed, Klicky can stage to a configured or one-shot XY first.

Runtime params (stripped before stock handler):
- ``MOVE=0/1`` — override ``probe_accuracy_move`` config
- ``X=`` / ``Y=`` — one-shot toolhead target (both required)
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Tuple

from . import messages as msg
from .dock_policy import _params_upper, parse_bool_token

# Accuracy-only keys — never put these in the global KLICKY_GCODE_PARAMS set.
PROBE_ACCURACY_STAGING_PARAMS = frozenset({"MOVE", "X", "Y"})


def resolve_probe_accuracy_move(
    params: Optional[Mapping[str, Any]],
    *,
    config_move: bool,
) -> bool:
    """Whether to stage XY before stock PROBE_ACCURACY.

    ``MOVE=0/1`` on the command overrides ``probe_accuracy_move`` config.
    """
    upper = _params_upper(params)
    if "MOVE" in upper:
        return parse_bool_token(upper.get("MOVE"))
    return bool(config_move)


def resolve_probe_accuracy_xy(
    params: Optional[Mapping[str, Any]],
    *,
    default_x: float,
    default_y: float,
) -> Tuple[float, float]:
    """Resolve toolhead XY for PROBE_ACCURACY staging.

    Order: gcmd X+Y → caller defaults (settings.probe_accuracy_*).
    Raises ValueError if only one of X/Y is present.
    """
    upper = _params_upper(params)
    has_x = "X" in upper
    has_y = "Y" in upper
    if has_x ^ has_y:
        raise ValueError(msg.probe_accuracy_xy_incomplete())
    if has_x and has_y:
        return float(upper["X"]), float(upper["Y"])
    return float(default_x), float(default_y)
