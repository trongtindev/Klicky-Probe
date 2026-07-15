"""Shared named constants for klicky_probe (pure defs, no Klipper imports).

Single home for magic numbers, speed role ids, G-code param name sets, product
floors, and other literals used in more than one place. Call sites import names
from here instead of hardcoding.

User-facing strings stay in ``messages.py``. Default *resolution* stays in
``defaults.py`` (import literals from this module when migrating).

Migration of existing module-level strays (e.g. geometry ``SPEED_*``,
``dock_policy.KLICKY_GCODE_PARAMS``, inline defaults) is intentional follow-up
work — add new shared consts here; move old ones when those call sites are
touched.
"""

from __future__ import annotations

# Plugin identity (console banner, logs). Single source for packaging too
# (pyproject.toml dynamic version → this attr). Bump here only.
KLICKY_PROBE_VERSION = "1.0.0"

# Seconds after klippy:ready before console banner via gcode.respond_info.
# Moonraker only calls gcode/subscribe_output after it observes READY (poll
# interval ~0.25s); messages during the ready callback never reach Mainsail.
ANNOUNCE_CONSOLE_DELAY = 1.0

# Plugin log_level ladder (config option + host _verbose/_debug gates).
# Emit when rank(wanted) <= rank(configured). Warnings always emit separately.
LOG_LEVEL_WARNING = "warning"
LOG_LEVEL_INFO = "info"
LOG_LEVEL_VERBOSE = "verbose"
LOG_LEVEL_DEBUG = "debug"
LOG_LEVEL_DEFAULT = LOG_LEVEL_INFO
# Rank order (quiet → loud); single source for set + user-facing choices text.
LOG_LEVEL_ORDER = (
    LOG_LEVEL_WARNING,
    LOG_LEVEL_INFO,
    LOG_LEVEL_VERBOSE,
    LOG_LEVEL_DEBUG,
)
LOG_LEVEL_RANK = {name: i + 1 for i, name in enumerate(LOG_LEVEL_ORDER)}
LOG_LEVELS = frozenset(LOG_LEVEL_ORDER)
LOG_LEVEL_CHOICES = ", ".join(LOG_LEVEL_ORDER)

# Early config validation (config_validate.py) — thresholds only.
CONFIG_SEVERITY_ERROR = "error"
CONFIG_SEVERITY_WARNING = "warning"
# Min XY length for approach / detach vectors (mm). Zero vectors collapse paths.
CONFIG_MIN_APPROACH_MM = 1.0
CONFIG_MIN_DETACH_MM = 1.0
# Points considered the same for umbilical vs safe_xy overlap.
CONFIG_XY_EPS_MM = 0.5
# Default umbilical coords when umbilical: True (placeholder — not machine-specific).
DEFAULT_UMBILICAL_X = 15.0
DEFAULT_UMBILICAL_Y = 15.0
# clearance_z should stay above |probe z_offset| + this pad (matches derive_clearance_z).
CONFIG_CLEARANCE_PROBE_PAD_MM = 5.0


def log_level_enabled(configured: str, wanted: str) -> bool:
    """True when *wanted* should emit under configured *log_level*."""
    return LOG_LEVEL_RANK[wanted] <= LOG_LEVEL_RANK[configured]


def ready_lines_for_log_level(
    banner: str,
    detail: list[str],
    log_level: str,
) -> list[str]:
    """Select ready announce lines: banner at info+, detail at verbose+.

    Pure filter — no Klipper. Empty when log_level is warning (or quieter).
    """
    if not log_level_enabled(log_level, LOG_LEVEL_INFO):
        return []
    lines = [banner]
    if log_level_enabled(log_level, LOG_LEVEL_VERBOSE):
        lines.extend(detail)
    return lines
