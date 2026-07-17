# Agent instructions — Klicky Probe Plugin

Klipper Python plugin for the Klicky magnetic probe. Hardware/STLs live under `files/` (and a separate hardware repo); **software work is under `plugin/`, `tests/`, `docs/`, `config/`**.

## Source of truth

| Concern | Canonical location |
|---------|-------------------|
| Shared constants / named defs | `plugin/klicky_probe/constants.py` (see **No hardcoding**; includes `KLICKY_PROBE_VERSION`) |
| Parsed config keys + defaults | `plugin/klicky_probe/__init__.py` (`_parse_user_config`, hook templates) + `plugin/klicky_probe/defaults.py` (`resolve_settings`) |
| Early config validation (errors + warnings) | `plugin/klicky_probe/config_validate.py` (`validate_klicky_config`) — wired at connect in `__init__.py` |
| User-facing / log strings | `plugin/klicky_probe/messages.py` |
| Full option reference | `docs/configuration.md` |
| Comment/uncomment template | `config/sample-klicky.cfg` |
| G-codes, params, flows F1–F7 | `docs/gcodes.md` |
| Install / Moonraker | `docs/install.md`, `plugin/install.sh`, `plugin/moonraker.snippet.conf` |
| Legacy macro → plugin migration | `docs/migration.md` |
| Overview + minimal sketch | `README.md` |
| Mechanical lint (Ruff) + dev deps | `pyproject.toml` (`[tool.ruff]`, `[project.optional-dependencies] dev`) |

Do **not** invent config keys that the parser does not accept. Prefer existing helpers, messages, and test fakes over one-off paths.

## Mandatory: keep docs + sample in sync with code

**Any** change that adds, removes, renames, or changes behavior/default of:

- `[klicky_probe]` options (including gcode hooks)
- G-code commands or shared params (`PROBE_LOCK`, `DOCK`, `MOVE`, …)
- Lifecycle / dock-path / homing / wrap policy
- Installer or Moonraker integration
- Klipper version requirements or hard prerequisites

**must** update the matching docs **in the same change** (same PR/commit series). Incomplete code-only edits are not done.

### Checklist by change type

| Code change | Update |
|-------------|--------|
| New/changed/removed config option or default | `docs/configuration.md` tables + `config/sample-klicky.cfg` (if user-facing toggle) + `README.md` minimal sketch if required/default geometry or gates change |
| New/changed G-code or runtime param | `docs/gcodes.md` (+ `configuration.md` if option-related) |
| Install / Moonraker / symlink behavior | `docs/install.md` (+ README install blurb if user-visible) |
| Flow / attach-dock policy | `docs/gcodes.md` + any feature-gate wording in `configuration.md` / sample |
| Legacy macro migration / variable map | `docs/migration.md` only (do not restate long migration essays in install/config/gcodes) |

### Sample vs full docs (do not drift roles)

- **`config/sample-klicky.cfg`**: short comment/uncomment template only. Group by **feature sections**. One-line notes; no long policy essays or F2 recipes. Link to docs.
- **`docs/configuration.md`**: full defaults, when-to-use, policy tables. Section order should match the sample banners.
- **`docs/gcodes.md`**: commands and flows — not a second option catalog.
- **`docs/migration.md`**: legacy macro suite → plugin only; checklists and variable map — not a second option catalog or F1–F7 rewrite.
- **`README.md`**: keep the minimal sketch **aligned** with sample geometry and active feature gates; do not invent a different “default” story (e.g. `adaptive_mesh` default is `False`).

### Consistency rules

1. Defaults in docs/sample must match `defaults.py` / `resolve_settings`.
2. Sample keys must be a subset of keys accepted by `_parse_user_config` + `_GCODE_TEMPLATE_NAMES` (no dead keys).
3. Cross-links and markdown anchors: fix targets when headings move.
4. Prefer not duplicating the same long explanation in sample and docs — detail lives in docs once.
5. Rare overrides may stay docs-only (e.g. `bed_min/max_*`, `move_accel`, `endstop_backoff_*`) unless they become common toggles.

### Before finishing a task

- [ ] Code + tests green if behavior changed (`pytest tests/ -q` when relevant)
- [ ] `ruff check plugin tests` clean when Python under `plugin/` or `tests/` changed
- [ ] Docs/sample updated per checklist above
- [ ] No contradiction between README sketch, sample active keys, and code defaults

## Repo map (software)

```text
plugin/klicky_probe/   # Klipper extra
plugin/install.sh      # install / uninstall
config/sample-klicky.cfg
docs/                  # install, migration, configuration, gcodes
tests/                 # pure-logic unit tests (no full Klipper)
pyproject.toml         # package meta, dev deps (.[dev]), Ruff config
```

## Code style (forced)

Match existing `plugin/klicky_probe/` and `tests/` style.

**Ruff** is the automated linter (`ruff check plugin tests`). Config lives in `pyproject.toml` (`[tool.ruff]`). This document remains the source for architecture and product style (relative imports, `%` messages, pure vs I/O, constants). New code that fights either Ruff or these rules is wrong even if it “works.”

### When the user changes code style

If the user asks to **change, adopt, or relax** a code style (formatting, quotes, line length, import layout, message formatting, naming, tooling like Black/Ruff, …):

1. Apply the style change in the code (scope they asked for — do not mass-reformat the whole tree unless they say so).
2. **Update this `AGENTS.md` Code style section in the same change** so the written rules match the new house style.
3. Remove or rewrite rules that would contradict the new style; do not leave stale “forced” rules behind.
4. If the change is partial/experimental, note the temporary exception in `AGENTS.md` (or ask) rather than silently keeping two standards.

Code-style edits without updating these rules are incomplete.

### Formatting

| Rule | Required |
|------|----------|
| Indent | **4 spaces** (never tabs) |
| Newlines | **LF** only |
| Quotes | Prefer **double quotes** `"..."` for strings |
| Line length | Soft wrap ~**88–100** columns (`ruff` `line-length = 100`; `E501` not enforced) |
| Trailing whitespace | None |
| Final newline | Files end with a single newline |
| Encoding | UTF-8 source |
| Formatter | `ruff format` settings exist for editors; **not** enforced in CI — do not mass-format unless asked |

### Module boilerplate

Every new module under `plugin/klicky_probe/` **must**:

```python
"""One-line (or short) module purpose."""

from __future__ import annotations
```

- Module docstring at top (except `__init__.py`, which may keep the license/header comment block).
- `from __future__ import annotations` first real import.
- Public pure-logic modules state **“pure logic, no Klipper imports”** in the docstring when that is true.

Tests: prefer the same future-import; small tests may omit module docstring if names are obvious.

### Imports

| Location | Style |
|----------|--------|
| Inside `plugin/klicky_probe/` | **Relative** only: `from .defaults import …`, `from . import messages as msg` |
| Inside `tests/` | **Package absolute**: `from klicky_probe.… import …` (path via `tests/conftest.py`) |
| Stdlib / third party | Absolute, stdlib first, then third party, then local — blank line between groups |
| Typing | `from typing import …` as needed; prefer modern builtins (`list`, `dict`, `tuple[…]`) only if already used in that file — stay consistent within the file |

Do **not** add `from klicky_probe…` imports inside the plugin package itself.

### Architecture boundaries (hard)

1. **Pure logic** (geometry, dock_policy, homing_plan, probe_state planners, defaults resolution, messages text builders, version parse, …): **no** `printer`, `gcode`, `toolhead`, or Klipper imports. Unit-test without a Klipper tree.
2. **Executors / wrappers / `__init__`**: own Klipper I/O, motion, `register_command`, config parse. Call pure helpers; do not re-implement policy in the I/O layer.
3. Prefer **`@dataclass` / `@dataclass(frozen=True)`** for value objects (geometry, intents, plans, settings snapshots).
4. Prefer small functions that return data over giant stateful methods when the decision is pure.

When adding behavior: put the **decision** in pure logic + tests first; wire Klipper last.

### Prefer reuse — do not dump logic in one place

**Forced:** extend what already exists; do not grow a single god-module/god-method.

1. **Reuse first.** Before writing new helpers, search for an existing function, planner, policy, message, constant, or test fake that already does the job (or 80% of it). Prefer call + small extension over a parallel copy.
2. **No logic clones.** Do not paste the same attach/dock/path/param-strip/bool-token rules into a second file. One implementation; other sites import it.
3. **Thin I/O, fat pure helpers.** Executors / command wrappers / `__init__` orchestrate (lookup objects, move toolhead, raise `gcode.error`). Decisions (when to dock, waypoint order, intent parse, default resolve) stay in dedicated pure modules (`geometry`, `dock_policy`, `homing_plan`, `probe_state`, `defaults`, …).
4. **Split by responsibility, not by ticket.** New behavior belongs next to its domain:
   - dock path / waypoints → `geometry` + `dock_executor`
   - leave/lock/params → `dock_policy`
   - attach state machine → `probe_state` / `probe_lifecycle`
   - G28 plan → `homing_plan` / `homing_executor`
   - mesh adaptive → `adaptive_mesh`
   - strings → `messages`; shared literals → `constants`
   Do **not** pile unrelated branches into `__init__.py` or one giant `cmd_*` method.
5. **Extract when a block grows.** If a method is doing planning + motion + messaging + param parsing, split: pure function(s) + thin caller. Prefer several short named functions over one 200-line path.
6. **Compose, don’t nest forever.** Prefer a pipeline of small steps (parse → plan → execute → verify) over deep nested conditionals that re-implement policy inline.
7. **Tests follow the split.** Pure pieces get pure unit tests; do not only cover behavior through a monolithic host mock when a direct test of the helper exists or should exist.
8. **Refactor on touch.** If you must edit a hotspot that already concentrates too much logic, leave it *slightly* better (extract the piece you needed) instead of adding another inline branch.

Anti-patterns (reject in review / self-check):

- New “util.py” dumping unrelated helpers
- Copy-paste of dock/attach sequences with one flag flipped
- Entire feature implemented only inside `__init__.py` or a single executor method
- Re-implementing `parse_bool_token` / param strip / entry XY math ad hoc

### No hardcoding — unified constants

**Do not** scatter magic numbers, magic strings, param name sets, or product floors inline in executors, planners, or wrappers.

| Kind of value | Where it lives |
|---------------|----------------|
| Shared numeric defaults, limits, lifts, retries floors, speed **role** ids, G-code param name sets, version floors, plugin identity strings used in more than one place | **`plugin/klicky_probe/constants.py`** — single unified module for named `UPPER_SNAKE` consts (and tiny pure helpers only if they define a constant-like def used widely) |
| User-facing / log message text | **`messages.py`** only (`msg.foo(...)`) — not raw long strings in call sites |
| How defaults are **resolved** from printer config | **`defaults.py`** (`resolve_settings`, derive helpers) — but the numeric/string **literals** those helpers use must be named consts imported from `constants.py` |
| Config **option key** lists parsed at load | Prefer `constants.py` (or one import from there) so sample/docs checks and parser stay aligned; do not re-type the same key list in three files |

**Rules (forced):**

1. **No bare magic in logic.** Prefer `attach_speed = float(_get(user, "attach_speed", DEFAULT_ATTACH_SPEED))` over `50.0` at the call site. Same for timeouts, lifts (e.g. paper start mm), placeholder umbilical XY, backoff defaults, etc.
2. **One home for shared consts:** add or extend names in `constants.py`. Do **not** invent a second `consts.py` / `config_defaults.py` / per-feature constants file unless the user explicitly asks to split.
3. **Import and use** the name at call sites (`from .constants import …` inside the plugin). Duplicating the same literal in two modules is a bug even if values match today.
4. **Domain-private only when truly single-use:** a private `_RE = re.compile(...)` next to the only function that needs it is OK. If a second module needs the same value, **move it** to `constants.py` (or `messages.py` if it is text).
5. **G-code param tokens** (`PROBE_LOCK`, `DOCK`, `MOVE`, `X`, `Y`, …) live as frozensets/names in `constants.py` (or re-exported from there), not re-listed as string literals in strip/parse call sites.
6. **When you touch hardcoded legacy literals** still sitting in older modules (`geometry.SPEED_*`, `dock_policy.KLICKY_GCODE_PARAMS`, inline `25.0` / `5.0` in `defaults.py`, …): **migrate them into `constants.py`** as part of that change rather than copying the pattern.
7. **Tests** assert against the named constant (or behavior), not a second copy of the magic number, when the value is part of the contract.

If `constants.py` does not exist yet, **create it** on the first change that needs a shared const — do not keep adding module-level strays.

### Naming

| Kind | Convention |
|------|------------|
| Modules / files | `snake_case.py` |
| Functions / methods | `snake_case` |
| Classes | `PascalCase` |
| Private helpers | leading `_` (`_params_upper`, `_UiMacroShim`) |
| G-code command handlers | `cmd_ATTACH_PROBE` style (match Klipper) |
| Constants | `UPPER_SNAKE` (`KLICKY_GCODE_PARAMS`, `SPEED_TRAVEL`) |
| Config option names | `snake_case` keys matching Klipper section options |
| Booleans in settings | positive or established names (`auto_attach`, `disable_docking`) — do not invent parallel synonyms |

### Types and returns

- Annotate **public** pure-logic functions and dataclass fields (returns + parameters).
- Klipper boundary methods may stay lightly typed (`config`, `gcmd`, `printer`) where Klipper has no stubs — still annotate pure results (`-> None`, `-> DockIntent`, etc.) when obvious.
- Prefer `Optional[T]` / `T | None` consistently **within a file**; do not mix randomly in one module.
- Do not add `Any` to silence problems — narrow types or keep the existing untyped Klipper object.

### Strings, logging, user messages

| Do | Don’t |
|----|--------|
| User-facing and log text via **`messages.py`** as `msg.foo(...)` functions | Inline long error strings scattered in executors |
| **`%` formatting** for message templates (`"… %s …" % (x,)`) | f-strings / `.format()` for `messages.py` and Klipper-facing logs (repo standard is `%`) |
| `logging` / host `_verbose` / `_debug` / `gcode.respond_info` | `print()` |
| Prefix user-visible lines with `klicky` / `klicky_probe` where existing helpers already do | Invent a new brand prefix |

Adding a new error/warning/info string ⇒ add a function in `messages.py` and call it. Tests that assert text import `messages` (or match stable substrings).

### Errors

| Layer | Pattern |
|-------|---------|
| Config load / connect | `raise self.printer.config_error(msg.…())` |
| G-code runtime | `raise self.gcode.error(msg.…())` or `raise h.gcode.error(msg.…())` |
| Pure logic invalid input | `raise ValueError(msg.…())` (or plain `ValueError` only if no user-facing helper fits yet — prefer `msg`) |
| Soft hooks | Log + continue (existing soft-fail); do not convert soft hooks into hard aborts without an explicit product decision |

Never bare `except:` that swallows everything without re-raise or explicit soft-fail path. Narrow `except Exception` only at known Klipper/optional boundaries (see `_config_has`).

### No silent failures — log / raise at the right severity

**Forced:** do not hide failed or degraded paths. Silent `except` on the **primary** outcome, empty fallbacks, and “temp code so the bug goes away” make failures hard to find and fix. Prefer a clear raise or a named log line.

Config option **`log_level`** (`warning` \| `info` \| `verbose` \| `debug`, default **`info`**) gates host emit helpers. Runtime progress uses **`h._verbose` / `h._debug`** (one `_emit` path: klippy.log + console). Soft-hook **warnings always emit** (not gated). Ready banner is separate: pure `ready_lines_for_log_level` (banner at info+, detail at verbose+), then deferred console. Connect geometry dump is verbose+ and **klippy.log-only**. Severity labels below are product intent.

| Situation | Severity / action | Host helper (typical) |
|-----------|-------------------|------------------------|
| Expected / correct alternate path (by design: already attached, `SKIP_*`, feature off, intentional policy branch) | **debug** | `h._debug` for design/idempotent policy skips and plan detail |
| Operator progress (attach done, stage start, ready detail lines, …) | **verbose** | `h._verbose` via `msg.…()` — requires `log_level: verbose` or higher |
| Sparse user-facing status (short ready banner only) | **info** | ready announce via `ready_lines_for_log_level` — default `log_level: info` |
| **try / recover fallback** — attempt failed or optional path unavailable; continue with degraded or alternate behavior | **warning** | `logging.warning` with what failed and what you do instead. Soft hooks: `_run_gcode_template(name, soft=True)` (`msg.hook_failed` + warning + continue). New soft recoveries follow that pattern — do not invent a second soft-fail API |
| Invalid state / cannot continue safely | **error** — **raise** | `gcode.error` / `config_error` / `ValueError` via `msg.…()` |

**Rules:**

1. **No silent error on the primary path.** Catching a real failure and continuing without a log or re-raise is wrong unless the path is proven impossible to care about *and* documented (rare). Default is: log or raise.
2. **Correct-by-design fallback → debug (not warning).** If the alternate path is *supposed* to happen (policy branch, idempotent skip, optional feature disabled), do not warn. Prefer `h._debug`; promote to `h._verbose` only when operators should see it with `log_level: verbose`.
3. **try-style / recover fallback → warning.** If you `try` something and fall back because it failed or is missing (optional object, soft hook, best-effort query), log **warning** with enough context (what failed, what you do instead). Soft hooks stay soft-fail via `_run_gcode_template(..., soft=True)` — do not upgrade to hard abort without an explicit product decision.
4. **No blind fallback.** Do not invent defaults, swallow the primary `Exception` with no log, return magic `None`/`0`/`False`, or “just continue” to make a test or printer path pass when the real condition is unknown. Fix the root cause or raise a clear error.
5. **No temporary paper-over.** Do not land workaround code whose only job is to hide a bug or avoid a hard path without: a **warning** log, a short comment why, and a real fix path. Prefer failing loudly over masking.
6. **User-facing strings stay in `messages.py`.** New **warning**, **verbose**, and operator-facing log bodies go through `msg.…()`. Short `_debug`-only lines may stay inline unless reused or asserted in tests.
7. **Do not spam info.** Routine attach/dock/lock/stage messages are **verbose**, not info. Default `log_level: info` should stay quiet beyond the ready banner (and command replies via `gcmd.respond_info`).

**Allowed narrow `except` (not silent primary failure):**

- After a higher-severity log/raise already recorded the real outcome (e.g. secondary `gcode.respond_info` inside `_verbose` / `_debug` / soft-hook console emit).
- Documented optional / Klipper-API shape probes (e.g. `_config_has`) — same rule as the **Errors** section above.

Anti-patterns (reject):

- Bare `except:` or `except Exception: pass` on the **primary** failure path (no prior log/raise of the real outcome)
- `except Exception: return default` with no log of the primary failure
- Catch-all that “keeps printing” while attach/dock/homing state is wrong
- Duplicating a second code path that papers over a planner bug instead of fixing the planner

### G-code / Klipper integration habits

- Strip Klicky params before calling stock handlers (`strip_klicky_params` / extras).
- Extended stock commands: use `create_stock_gcmd` so KEY=VAL survives reparse (`gcode_cmd.py`).
- Register commands with `desc=msg.help_…()` where helpers exist.
- Do not put dock XY motion in `[probe] activate_gcode` guidance or samples.

### Tests (style)

- Pure-logic tests only under `tests/` (no full Klipper process).
- Reuse fixtures/fakes from `tests/conftest.py` and existing fake modules.
- Test names: `test_<behavior>_<condition>` snake_case.
- Prefer assert on **returned plans/intents/settings**, not on private Klipper mocks, when logic is pure.
- When behavior changes: update or add tests in the **same** change.
- Run: `pip install -e ".[dev]"` then `ruff check plugin tests` and `pytest tests/ -q`.

### What not to do

- No new top-level package layout without need; keep the Klipper extra as `plugin/klicky_probe/`.
- No drive-by reformat of unrelated files.
- No **`ruff format`** mass reformat unless the user explicitly asks (would churn history). Safe `ruff check --fix` on files you touch is expected when lint fails.
- No adding dependencies beyond `pyproject.toml` `[project.optional-dependencies] dev` / runtime needs without asking.
- No f-string conversion pass across `messages.py` (Ruff ignores `UP031` for `%` formatting).
- No copying legacy macro-suite style (`klicky-variables.cfg`, `Attach_Probe` macro names) into the plugin.

### Style self-check before finishing code

- [ ] Pure vs I/O boundary respected
- [ ] Reused existing helpers/modules — no parallel clone; no new god-method
- [ ] No new magic numbers/strings at call sites — named consts in **`constants.py`** (messages in **`messages.py`**)
- [ ] New user strings live in `messages.py` (`%` format)
- [ ] No silent failures: design fallbacks = `_debug` (or `_verbose` if operators need it); try/recover = warning; hard failures = raise (see **No silent failures**)
- [ ] Relative imports in plugin; `klicky_probe.*` in tests
- [ ] `from __future__ import annotations` + module docstring on new plugin modules
- [ ] Naming matches table above
- [ ] If user requested a style change: **`AGENTS.md` Code style rules updated** to match
- [ ] `ruff check plugin tests` clean when Python changed
- [ ] Tests updated; `pytest tests/ -q` when behavior changed
- [ ] Docs/sample checklist satisfied if options/commands/flows changed

## Tests

```bash
pip install -e ".[dev]"
ruff check plugin tests
pytest tests/ -q
```

Prefer extending existing tests and fakes in `tests/` over ad-hoc scripts.

## Out of scope for plugin docs sync

Hardware assembly under `files/`, usermods, and legacy `klicky-variables.cfg` / old macro suites are **not** compatible with this plugin and are not the place to document modern `[klicky_probe]` options.
