"""User gcode templates: soft-fail side effects and hard-fail axis home."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import klicky_probe.messages as msg
from klicky_probe import KlickyProbe


def _host_with_templates(templates: dict):
    host = SimpleNamespace(
        _gcode_templates=templates,
        gcode=MagicMock(),
    )
    host._run_gcode_template = (
        lambda name, *, soft=False: KlickyProbe._run_gcode_template(
            host, name, soft=soft
        )
    )
    return host


def test_soft_missing_is_noop():
    host = _host_with_templates({})
    host._run_gcode_template("pre_homing_gcode", soft=True)
    host.gcode.run_script_from_command.assert_not_called()
    host.gcode.respond_info.assert_not_called()


def test_soft_fail_reports_name_and_does_not_raise():
    host = _host_with_templates({"pre_homing_gcode": "BAD_CMD"})
    host.gcode.run_script_from_command.side_effect = RuntimeError("unknown command")

    host._run_gcode_template("pre_homing_gcode", soft=True)

    host.gcode.respond_info.assert_called_once()
    text = host.gcode.respond_info.call_args[0][0]
    assert "pre_homing_gcode" in text
    assert "unknown command" in text
    assert text == msg.hook_failed(
        "pre_homing_gcode", RuntimeError("unknown command")
    )


def test_soft_success_runs_script():
    host = _host_with_templates({"post_attach_gcode": "STATUS_READY"})
    host._run_gcode_template("post_attach_gcode", soft=True)
    host.gcode.run_script_from_command.assert_called_once_with("STATUS_READY")
    host.gcode.respond_info.assert_not_called()


def test_hard_fail_reraises():
    host = _host_with_templates({"home_x_gcode": "G28 X"})
    host.gcode.run_script_from_command.side_effect = RuntimeError("home failed")

    try:
        host._run_gcode_template("home_x_gcode", soft=False)
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "home failed" in str(e)
    host.gcode.respond_info.assert_not_called()


def test_hook_failed_message_format():
    text = msg.hook_failed("pre_meshing_gcode", ValueError("x"))
    assert text.startswith("klicky: hook pre_meshing_gcode failed:")
    assert "x" in text
