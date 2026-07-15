import pytest

from klicky_probe.probe_accuracy import (
    PROBE_ACCURACY_STAGING_PARAMS,
    resolve_probe_accuracy_move,
    resolve_probe_accuracy_xy,
)


def test_staging_params_set():
    assert PROBE_ACCURACY_STAGING_PARAMS == frozenset({"MOVE", "X", "Y"})


def test_resolve_probe_accuracy_move():
    assert resolve_probe_accuracy_move({}, config_move=True) is True
    assert resolve_probe_accuracy_move({}, config_move=False) is False
    assert resolve_probe_accuracy_move({"MOVE": "0"}, config_move=True) is False
    assert resolve_probe_accuracy_move({"MOVE": "1"}, config_move=False) is True
    assert resolve_probe_accuracy_move({"move": "0"}, config_move=True) is False


def test_resolve_probe_accuracy_xy():
    assert resolve_probe_accuracy_xy({}, default_x=1.0, default_y=2.0) == (1.0, 2.0)
    assert resolve_probe_accuracy_xy(
        {"X": "10", "Y": "20"}, default_x=1.0, default_y=2.0
    ) == (10.0, 20.0)
    with pytest.raises(ValueError, match="both X and Y"):
        resolve_probe_accuracy_xy({"X": "10"}, default_x=1.0, default_y=2.0)
    with pytest.raises(ValueError, match="both X and Y"):
        resolve_probe_accuracy_xy({"Y": "20"}, default_x=1.0, default_y=2.0)
