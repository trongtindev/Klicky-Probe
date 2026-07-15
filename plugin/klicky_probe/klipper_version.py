"""Parse and check Klipper software_version (pure logic)."""

from __future__ import annotations

import re
from typing import Optional, Tuple

# Product floor: probe session API era (start_probe_session / end_probe_session).
MIN_KLIPPER_VERSION = (0, 13, 0)

VersionTuple = Tuple[int, int, int]

# v0.13.0, v0.13.0-707-gf604aeeea, 0.13.0-dirty, etc.
_VERSION_RE = re.compile(
    r"^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)",
    re.IGNORECASE,
)


def format_version_tuple(version: VersionTuple) -> str:
    """Format (0, 13, 0) → '0.13.0'."""
    return "%d.%d.%d" % (version[0], version[1], version[2])


def parse_klipper_version(software_version) -> Optional[VersionTuple]:
    """
    Parse Klipper software_version → (major, minor, patch) or None.

    Accepts git-describe style: v0.13.0-707-g..., v0.13.0, 0.13.0-dirty.
    Rejects empty, '?', and unparseable strings.
    """
    if software_version is None:
        return None
    text = str(software_version).strip()
    if not text or text == "?":
        return None
    # Drop common trailing noise before match is fine; regex anchors at start.
    m = _VERSION_RE.match(text)
    if not m:
        return None
    return (int(m.group("major")), int(m.group("minor")), int(m.group("patch")))


def version_tuple_at_least(found: VersionTuple, minimum: VersionTuple) -> bool:
    return found >= minimum


def check_min_klipper_version(
    software_version,
    minimum: VersionTuple = MIN_KLIPPER_VERSION,
) -> Optional[str]:
    """
    Return None if version is OK; else a reason code:
      - "too_old"
      - "unparseable"
    """
    parsed = parse_klipper_version(software_version)
    if parsed is None:
        return "unparseable"
    if not version_tuple_at_least(parsed, minimum):
        return "too_old"
    return None
