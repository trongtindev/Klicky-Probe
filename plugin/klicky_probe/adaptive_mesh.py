"""Adaptive bed mesh parameter policy (pure logic)."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional


Params = Dict[str, Any]


def _as_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def merge_mesh_params(
    caller_params: Optional[Mapping[str, Any]],
    adaptive_mesh_default: bool,
    adaptive_margin_default: float,
) -> Params:
    """
    Merge caller BED_MESH_CALIBRATE params with Klicky adaptive defaults.

    Policy:
    - ADAPTIVE=1 (caller): adaptive on; margin = caller or config default if omitted
    - ADAPTIVE=0 (caller): full mesh; do not inject margin
    - no ADAPTIVE + adaptive_mesh_default True: inject ADAPTIVE=1 + margin default if no margin
    - no ADAPTIVE + adaptive_mesh_default False: pass-through
    """
    src: Mapping[str, Any] = caller_params or {}
    # Normalize keys to uppercase for Klipper-style gcode params
    out: Params = {str(k).upper(): v for k, v in src.items()}

    has_adaptive = "ADAPTIVE" in out
    has_margin = "ADAPTIVE_MARGIN" in out

    if has_adaptive:
        adaptive_val = _as_int(out.get("ADAPTIVE"), 0)
        if adaptive_val == 1 and not has_margin and adaptive_margin_default > 0:
            out["ADAPTIVE_MARGIN"] = adaptive_margin_default
        # ADAPTIVE=0: leave as-is, no forced margin
        return out

    if adaptive_mesh_default:
        out["ADAPTIVE"] = 1
        if not has_margin:
            out["ADAPTIVE_MARGIN"] = adaptive_margin_default
        return out

    return out
