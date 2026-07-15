"""Synthetic GCodeCommand for stock extended handlers.

Klipper wraps extended G-code (non letter+number) as::

    lambda gcmd: orig(self._get_extended_params(gcmd))

``_get_extended_params`` clears ``gcmd._params`` and re-parses KEY=VAL tokens
from the **commandline**. Building::

    create_gcode_command("BED_MESH_CALIBRATE", "BED_MESH_CALIBRATE", {"ADAPTIVE": "1"})

therefore drops ADAPTIVE before stock bed_mesh runs.

Use ``create_stock_gcmd`` when calling a handler from
``register_command(name, None)`` (e.g. BED_MESH_CALIBRATE, PROBE_ACCURACY).
Traditional gcode such as G28 does not reparse and may use raw
``create_gcode_command``.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional


def create_stock_gcmd(gcode, command: str, params: Optional[Mapping[str, Any]]):
    """create_gcode_command with commandline that survives extended reparse."""
    str_params = {str(k).upper(): str(v) for k, v in (params or {}).items()}
    if str_params:
        commandline = "%s %s" % (
            command,
            " ".join("%s=%s" % (k, v) for k, v in str_params.items()),
        )
    else:
        commandline = command
    return gcode.create_gcode_command(command, commandline, str_params)
