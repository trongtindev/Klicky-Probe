"""create_stock_gcmd must put KEY=VAL on the commandline for extended prev()."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from klicky_probe.command_wrappers import CommandWrappers
from klicky_probe.gcode_cmd import create_stock_gcmd


class _FakeGcode:
    def __init__(self):
        self.handlers = {}
        self.last = None

    def register_command(self, name, handler, *args, **kwargs):
        prev = self.handlers.get(name)
        if handler is None:
            self.handlers.pop(name, None)
            return prev
        self.handlers[name] = handler
        return None

    def create_gcode_command(self, command, commandline, params):
        self.last = SimpleNamespace(
            command=command,
            commandline=commandline,
            params=params,
            get_command_parameters=lambda: params,
        )
        return self.last


def test_create_stock_gcmd_puts_params_on_commandline():
    gcode = _FakeGcode()
    gcmd = create_stock_gcmd(
        gcode,
        "BED_MESH_CALIBRATE",
        {"ADAPTIVE": 1, "PROBE_COUNT": "5,5", "MESH_MIN": "10,10"},
    )
    assert gcmd.command == "BED_MESH_CALIBRATE"
    assert gcmd.commandline.startswith("BED_MESH_CALIBRATE ")
    assert "ADAPTIVE=1" in gcmd.commandline
    assert "PROBE_COUNT=5,5" in gcmd.commandline
    assert "MESH_MIN=10,10" in gcmd.commandline
    assert gcmd.params["ADAPTIVE"] == "1"
    # Old bug: commandline == command only → extended reparse would drop all.
    assert gcmd.commandline != "BED_MESH_CALIBRATE"


def test_create_stock_gcmd_empty_params():
    gcode = _FakeGcode()
    gcmd = create_stock_gcmd(gcode, "PROBE_ACCURACY", None)
    assert gcmd.commandline == "PROBE_ACCURACY"
    assert gcmd.params == {}


def test_bed_mesh_wrapper_forwards_adaptive_on_commandline():
    """Regression: merge injects ADAPTIVE=1 and stock prev must see it on the line."""
    gcode = _FakeGcode()
    stock_prev = MagicMock()
    gcode.handlers["BED_MESH_CALIBRATE"] = stock_prev

    host = SimpleNamespace(
        gcode=gcode,
        settings=SimpleNamespace(adaptive_mesh=True),
        lifecycle=MagicMock(),
        _status_led=MagicMock(),
        _orig_bed_mesh=None,
    )
    wrappers = CommandWrappers(host)
    wrappers.wrap_bed_mesh_calibrate()

    # Caller omits ADAPTIVE; adaptive_mesh default injects it.
    caller = SimpleNamespace(
        get_command_parameters=lambda: {"PROFILE": "default", "DOCK": "0"},
    )
    handler = gcode.handlers["BED_MESH_CALIBRATE"]
    handler(caller)

    stock_prev.assert_called_once()
    fo = stock_prev.call_args[0][0]
    assert "ADAPTIVE=1" in fo.commandline
    assert "PROFILE=default" in fo.commandline
    # Klicky-only DOCK stripped
    assert "DOCK=" not in fo.commandline
    host.lifecycle.enter_probe_work.assert_called_once()
    host.lifecycle.exit_probe_work.assert_called_once()


def test_bed_mesh_wrapper_preserves_explicit_adaptive():
    gcode = _FakeGcode()
    stock_prev = MagicMock()
    gcode.handlers["BED_MESH_CALIBRATE"] = stock_prev

    host = SimpleNamespace(
        gcode=gcode,
        settings=SimpleNamespace(adaptive_mesh=False),
        lifecycle=MagicMock(),
        _status_led=MagicMock(),
        _orig_bed_mesh=None,
    )
    wrappers = CommandWrappers(host)
    wrappers.wrap_bed_mesh_calibrate()

    caller = SimpleNamespace(
        get_command_parameters=lambda: {"ADAPTIVE": "1", "ADAPTIVE_MARGIN": "5"},
    )
    gcode.handlers["BED_MESH_CALIBRATE"](caller)

    fo = stock_prev.call_args[0][0]
    assert "ADAPTIVE=1" in fo.commandline
    assert "ADAPTIVE_MARGIN=5" in fo.commandline
