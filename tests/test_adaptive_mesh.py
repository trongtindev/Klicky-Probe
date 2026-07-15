import pytest

from klicky_probe.adaptive_mesh import merge_mesh_params


@pytest.mark.parametrize(
    "caller,adaptive_default,expected",
    [
        # ADAPTIVE=1 → leave as-is; margin from stock [bed_mesh] / caller only
        ({"ADAPTIVE": 1}, False, {"ADAPTIVE": 1}),
        ({"ADAPTIVE": 1}, True, {"ADAPTIVE": 1}),
        # ADAPTIVE=1 with margin → keep caller margin
        (
            {"ADAPTIVE": 1, "ADAPTIVE_MARGIN": 10},
            True,
            {"ADAPTIVE": 1, "ADAPTIVE_MARGIN": 10},
        ),
        # ADAPTIVE=0 → full mesh
        ({"ADAPTIVE": 0}, True, {"ADAPTIVE": 0}),
        ({"ADAPTIVE": 0}, False, {"ADAPTIVE": 0}),
        # no ADAPTIVE + default True → inject ADAPTIVE=1 only (no margin)
        ({}, True, {"ADAPTIVE": 1}),
        (
            {"PROFILE": "default"},
            True,
            {"PROFILE": "default", "ADAPTIVE": 1},
        ),
        # no ADAPTIVE + default False → pass-through
        ({}, False, {}),
        ({"PROFILE": "default"}, False, {"PROFILE": "default"}),
        # lowercase keys normalized
        ({"adaptive": 1}, False, {"ADAPTIVE": 1}),
        # margin without ADAPTIVE + default on: inject adaptive, keep margin
        (
            {"ADAPTIVE_MARGIN": 7},
            True,
            {"ADAPTIVE_MARGIN": 7, "ADAPTIVE": 1},
        ),
    ],
)
def test_merge_mesh_params(caller, adaptive_default, expected):
    result = merge_mesh_params(caller, adaptive_default)
    assert result == expected


def test_merge_preserves_other_params():
    result = merge_mesh_params(
        {"ADAPTIVE": 1, "MESH_MIN": "10,10", "MESH_MAX": "100,100"},
        True,
    )
    assert result["MESH_MIN"] == "10,10"
    assert result["MESH_MAX"] == "100,100"
    assert "ADAPTIVE_MARGIN" not in result
