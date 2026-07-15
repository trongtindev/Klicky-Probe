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
