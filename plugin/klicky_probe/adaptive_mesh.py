"""Adaptive bed mesh parameter policy (pure logic)."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

Params = Dict[str, Any]


def merge_mesh_params(
    caller_params: Optional[Mapping[str, Any]],
    adaptive_mesh_default: bool,
) -> Params:
    """
    Merge caller BED_MESH_CALIBRATE params with Klicky adaptive defaults.

    Policy:
    - ADAPTIVE=1 / ADAPTIVE=0 (caller): leave as-is (including ADAPTIVE_MARGIN)
    - no ADAPTIVE + adaptive_mesh_default True: inject ADAPTIVE=1 only
    - no ADAPTIVE + adaptive_mesh_default False: pass-through

    Margin is owned by stock [bed_mesh] adaptive_margin (and optional gcode
    ADAPTIVE_MARGIN). This wrapper never injects ADAPTIVE_MARGIN.
    """
    src: Mapping[str, Any] = caller_params or {}
    # Normalize keys to uppercase for Klipper-style gcode params
    out: Params = {str(k).upper(): v for k, v in src.items()}

    if "ADAPTIVE" in out:
        # Explicit caller choice; do not invent margin
        return out

    if adaptive_mesh_default:
        out["ADAPTIVE"] = 1
        return out

    return out
