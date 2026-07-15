"""Unit tests for Mainsail/Fluidd gcode_macro UI shims."""

from __future__ import annotations

from klicky_probe import messages as msg
from klicky_probe import (
    _UI_MACRO_NAMES,
    _UiMacroShim,
    register_ui_macro_shims,
)


class FakePrinter:
    def __init__(self, existing=None):
        self.objects = dict(existing or {})
        self.added = []

    def lookup_object(self, name, default=None):
        if name in self.objects:
            return self.objects[name]
        return default

    def add_object(self, name, obj):
        if name in self.objects:
            raise RuntimeError("Printer object '%s' already created" % (name,))
        self.objects[name] = obj
        self.added.append(name)


def test_register_adds_both_names():
    p = FakePrinter()
    registered = register_ui_macro_shims(p)
    assert registered == [
        "gcode_macro ATTACH_PROBE",
        "gcode_macro DETACH_PROBE",
    ]
    assert p.added == registered
    for name in _UI_MACRO_NAMES:
        obj = p.objects["gcode_macro %s" % (name,)]
        assert isinstance(obj, _UiMacroShim)
        assert obj.get_status(0.0) == {}


def test_register_skips_existing_without_raise():
    existing_name = "gcode_macro ATTACH_PROBE"
    p = FakePrinter(existing={existing_name: object()})
    registered = register_ui_macro_shims(p)
    assert registered == ["gcode_macro DETACH_PROBE"]
    assert existing_name not in p.added
    assert p.added == ["gcode_macro DETACH_PROBE"]
    # Pre-existing object left alone
    assert not isinstance(p.objects[existing_name], _UiMacroShim)


def test_ui_macro_names_are_attach_detach_only():
    assert _UI_MACRO_NAMES == ("ATTACH_PROBE", "DETACH_PROBE")


def test_skip_message_mentions_object():
    text = msg.ui_macro_skip_exists("gcode_macro ATTACH_PROBE")
    assert "show_ui_macros" in text
    assert "gcode_macro ATTACH_PROBE" in text
