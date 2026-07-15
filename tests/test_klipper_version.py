import pytest

from klicky_probe.klipper_version import (
    MIN_KLIPPER_VERSION,
    check_min_klipper_version,
    format_version_tuple,
    parse_klipper_version,
    version_tuple_at_least,
)


def test_min_is_0_13_0():
    assert MIN_KLIPPER_VERSION == (0, 13, 0)
    assert format_version_tuple(MIN_KLIPPER_VERSION) == "0.13.0"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("v0.13.0", (0, 13, 0)),
        ("0.13.0", (0, 13, 0)),
        ("v0.13.0-707-gf604aeeea", (0, 13, 0)),
        ("v0.13.0-707-gf604aeeea-dirty", (0, 13, 0)),
        ("v0.12.0-100-gabcdef", (0, 12, 0)),
        ("v1.0.0", (1, 0, 0)),
    ],
)
def test_parse_ok(raw, expected):
    assert parse_klipper_version(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "?", "  ?", "unknown", "abc", "v"])
def test_parse_unparseable(raw):
    assert parse_klipper_version(raw) is None


def test_version_compare():
    assert version_tuple_at_least((0, 13, 0), (0, 13, 0))
    assert version_tuple_at_least((0, 13, 1), (0, 13, 0))
    assert version_tuple_at_least((0, 14, 0), (0, 13, 0))
    assert not version_tuple_at_least((0, 12, 99), (0, 13, 0))


def test_check_ok():
    assert check_min_klipper_version("v0.13.0") is None
    assert check_min_klipper_version("v0.13.0-707-gf604aeeea") is None
    assert check_min_klipper_version("v0.14.0") is None


def test_check_too_old():
    assert check_min_klipper_version("v0.12.0") == "too_old"
    assert check_min_klipper_version("v0.12.0-999-gdeadbeef") == "too_old"


def test_check_unparseable():
    assert check_min_klipper_version("?") == "unparseable"
    assert check_min_klipper_version("") == "unparseable"
    assert check_min_klipper_version(None) == "unparseable"
