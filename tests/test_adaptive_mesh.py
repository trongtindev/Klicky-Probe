import pytest

from klicky_probe.adaptive_mesh import merge_mesh_params


@pytest.mark.parametrize(
    "caller,adaptive_default,margin_default,expected",
    [
        # ADAPTIVE=1, no margin → inject margin
        ({"ADAPTIVE": 1}, False, 5.0, {"ADAPTIVE": 1, "ADAPTIVE_MARGIN": 5.0}),
        ({"ADAPTIVE": 1}, True, 5.0, {"ADAPTIVE": 1, "ADAPTIVE_MARGIN": 5.0}),
        # ADAPTIVE=1 with margin → keep caller margin
        (
            {"ADAPTIVE": 1, "ADAPTIVE_MARGIN": 10},
            True,
            5.0,
            {"ADAPTIVE": 1, "ADAPTIVE_MARGIN": 10},
        ),
        # ADAPTIVE=0 → full mesh, no forced margin
        ({"ADAPTIVE": 0}, True, 5.0, {"ADAPTIVE": 0}),
        ({"ADAPTIVE": 0}, False, 5.0, {"ADAPTIVE": 0}),
        # no ADAPTIVE + default True → inject adaptive + margin
        ({}, True, 5.0, {"ADAPTIVE": 1, "ADAPTIVE_MARGIN": 5.0}),
        (
            {"PROFILE": "default"},
            True,
            7.0,
            {"PROFILE": "default", "ADAPTIVE": 1, "ADAPTIVE_MARGIN": 7.0},
        ),
        # no ADAPTIVE + default False → pass-through
        ({}, False, 5.0, {}),
        ({"PROFILE": "default"}, False, 5.0, {"PROFILE": "default"}),
        # lowercase keys normalized
        ({"adaptive": 1}, False, 5.0, {"ADAPTIVE": 1, "ADAPTIVE_MARGIN": 5.0}),
    ],
)
def test_merge_mesh_params(caller, adaptive_default, margin_default, expected):
    result = merge_mesh_params(caller, adaptive_default, margin_default)
    assert result == expected


def test_merge_preserves_other_params():
    result = merge_mesh_params(
        {"ADAPTIVE": 1, "MESH_MIN": "10,10", "MESH_MAX": "100,100"},
        True,
        5.0,
    )
    assert result["MESH_MIN"] == "10,10"
    assert result["MESH_MAX"] == "100,100"
    assert result["ADAPTIVE_MARGIN"] == 5.0
