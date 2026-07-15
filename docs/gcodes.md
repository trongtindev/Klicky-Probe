# G-code commands and probe flows

## Lifecycle (mental model)

```text
                    ┌─ PROBE_LOCK / LOCK_PROBE ──────────────┐
                    │  (no auto-dock until UNLOCK_PROBE)     │
Command / session ──┤                                        ├──► DETACH_PROBE
                    │  default: attach → work → dock         │
                    └─ DOCK=0: leave; next op may dock ──────┘
```

With **`auto_attach: True`** (default), Klicky hooks Klipper’s **`probe.start_probe_session` / `end_probe_session`** (Klipper v0.13+). Bed mesh, QGL, Z tilt, `PROBE_ACCURACY`, single `PROBE`, and **virtual Z `G28`** all open a session — attach on begin, dock on end (unless locked/held).

Do **not** put Klicky attach XY motion in `[probe] activate_gcode` — Klipper forbids toolhead moves there.

---

## When to dock (collision-safe)

| Situation | Action | Why |
|-----------|--------|-----|
| End of a **standalone** probe op | **Dock** (default) | Probe off toolhead for free travel / print |
| Before **physical Z** endstop home | **Dock first** | Probe body must not hit the bed |
| Before **virtual Z** home | **Attach first** (session begin) | Probe *is* the Z endstop |
| XY travel to/from dock | Raise Z to **`clearance_z` first** | Built into attach/detach motion |
| Multi-step calibrate / start | **Leave attached** via params | Avoid dock↔attach thrash |
| After **last** probe step | **Dock once** | Clear nozzle path |

---

## How to override

| Want… | Do |
|-------|-----|
| Keep probe across several commands | `PROBE_LOCK=1` on each **or** `LOCK_PROBE` after attach |
| This command only: don’t dock at end | `DOCK=0` |
| Force dock (even if locked) | `DOCK=1` **or** `UNLOCK_PROBE` then `DETACH_PROBE` |
| Full manual control | `auto_attach: False` + `ATTACH_PROBE` / `DETACH_PROBE` (no session hook, no mesh/level/accuracy wraps) |
| Paper-test wrap only | `wrap_probe_calibrate: True` (default; independent of `auto_attach`) |
| Disable all dock motion (debug) | `disable_docking: True` |
| Avoid Klipper probe activate scripts moving head | Leave `activate_gcode` empty of XY dock moves |

Shared params on **`G28`**, **`BED_MESH_CALIBRATE`**, **`QUAD_GANTRY_LEVEL`**, **`Z_TILT_ADJUST`**, **`SCREWS_TILT_CALCULATE`**, **`PROBE_ACCURACY`**, **`PROBE_CALIBRATE`**:

| Param | Effect |
|-------|--------|
| `PROBE_LOCK=1` (or bare `PROBE_LOCK`) | Leave attached **and lock** until `UNLOCK_PROBE` |
| `PROBE_LOCK=0` | Do not leave/lock from this param |
| `DOCK=0` | Leave attached **without** lock (next finishing op may dock) |
| `DOCK=1` | Force unlock + dock at end (**wins** over `PROBE_LOCK`) |

`PROBE_LOCK` / `DOCK` are stripped before stock handlers run.

---

## Flows

### F1 — Default (one command, safe)

```text
BED_MESH_CALIBRATE   # or QGL, PROBE_ACCURACY, …
  → attach (session begin)
  → probe work
  → dock (session end)
```

No params needed. **Default = always dock after the op.**

### F2 — Multi-step without thrash (main override)

```gcode
G28 PROBE_LOCK=1
QUAD_GANTRY_LEVEL PROBE_LOCK=1
BED_MESH_CALIBRATE PROBE_LOCK=1
G28 Z PROBE_LOCK=1
UNLOCK_PROBE
DETACH_PROBE
```

Softer (leave without hard lock):

```gcode
G28 DOCK=0
BED_MESH_CALIBRATE DOCK=0
PROBE_ACCURACY
# last command without DOCK=0 docks by default
```

Prefer **`PROBE_LOCK=1`** for long START macros so an intermediate command cannot dock early.

### F3 — Virtual Z home (`G28` + `probe:z_virtual_endstop`)

```text
[auto_attach]
  attach @ start_probe_session   # inside stock G28 Z
  home Z samples
  dock  @ end_probe_session      # unless PROBE_LOCK / DOCK=0
```

### F4 — Physical Z home

```text
dock before Z (homing plan) → nozzle to endstop → (no attach required)
```

`PROBE_LOCK` never skips **dock-before-Z** on physical endstops (collision safety).

### F5 — `PROBE_CALIBRATE` (paper test)

```text
attach → calibrate UI → leave attached by default
  DOCK=1        → force dock after
  PROBE_LOCK=1  → leave + lock
```

### F6 — Full manual

```ini
# printer.cfg
[klicky_probe]
auto_attach: False
# wrap_probe_calibrate still True by default (PROBE_CALIBRATE attach+leave).
# Set wrap_probe_calibrate: False for stock calibrate with no Klicky wrap.
```

With `auto_attach: False`, Klicky does **not** install session hooks or wraps for mesh / leveling / accuracy. You own every attach/dock:

```gcode
ATTACH_PROBE
LOCK_PROBE
; … your macros …
UNLOCK_PROBE
DETACH_PROBE
```

### F7 — `Z_TILT_ADJUST`

```text
attach → tilt probe points → rehome Z (still attached) → dock per intent
```

No dock between tilt and rehome Z.

---

## Probe dock commands

| Command | Description |
|---------|-------------|
| `ATTACH_PROBE [RESTORE=0\|1]` | Attach from dock. Always **queries hardware first**, then plans. `RESTORE=1` returns to prior XY. |
| `DETACH_PROBE [RESTORE=0\|1]` | Dock/detach. Always **queries hardware first** (so a hand-mounted probe is not skipped as “already docked”). |
| `LOCK_PROBE` | Block auto/manual detach until unlock. |
| `UNLOCK_PROBE` | Allow detach again. |
| `GET_PROBE_STATUS` | Query + report `attached`/`docked`/`unknown`, `locked`, session/hold depths. |
| `ENSURE_PROBE_DOCKED [FORCE=0\|1]` | Query; if attached, dock. Use in print-start when axes may already be homed. `FORCE=1` unlocks then docks. |

### Print start (conditional homing)

If `PRINT_START` only homes when not already homed, a previous probe error can leave the probe on the toolhead with steppers still enabled:

```gcode
{% if "xyz" not in printer.toolhead.homed_axes %}
G28
{% else %}
ENSURE_PROBE_DOCKED
{% endif %}
```

### Virtual Z reseat

With `reseat_before_z_home: True` (default), virtual-Z home forces a **detach + attach** cycle when the switch already reports open/attached. That catches a false “attached” (e.g. open signal wire) before the nozzle is driven into the bed. Safety reseat wins over `LOCK_PROBE` for that cycle (lock is restored after).

---

## Homing (`homing_override: True`)

| Command | Behavior |
|---------|----------|
| `G28` | Klicky-aware XY order; virtual Z uses probe session when `auto_attach` |
| `G28 X` / `Y` / `Z` | Selected axes |
| `G28 … PROBE_LOCK=1` | After virtual Z, leave attached and locked |
| `G28 … DOCK=0` | Leave attached without lock |
| `G28 … DOCK=1` | Force dock after Z (default-like) |

Full all-axes `G28` clears a previous lock at the start, then applies leave/lock for Z.

---

## Wrapped stock commands

| Command | Behavior |
|---------|----------|
| `BED_MESH_CALIBRATE` | When `auto_attach`: adaptive policy + attach/dock; honors `PROBE_LOCK`/`DOCK` |
| `PROBE_CALIBRATE` | When `wrap_probe_calibrate`: attach; leave for paper test unless `DOCK=1` |
| `PROBE_ACCURACY` | When `auto_attach`: attach/run/dock by default; honors params |
| `QUAD_GANTRY_LEVEL` / `Z_TILT_ADJUST` / `SCREWS_TILT_CALCULATE` | When `auto_attach`: attach/dock around op; `Z_TILT` rehomes Z without mid-dock |

Bare **`PROBE`** is not renamed; with `auto_attach` it still attach/docks via the probe **session** API (one session per sample).

---

## Scope: supported vs session-only vs unsupported

Klicky does **not** wrap every Klipper module that can call the probe. Product target is dockable magnetic microswitch on CoreXY / Voron-class printers (homing, mesh, gantry/tilt level, screws, z-offset calibrate, accuracy).

### First-class (wrapped + session)

| Area | Commands |
|------|----------|
| Homing | `G28` (when `homing_override: True`) |
| Mesh | `BED_MESH_CALIBRATE` |
| Leveling | `QUAD_GANTRY_LEVEL`, `Z_TILT_ADJUST`, `SCREWS_TILT_CALCULATE` |
| Probe tools | `PROBE_CALIBRATE`, `PROBE_ACCURACY` |
| Session consumers | Any code path that opens `start_probe_session` (including bare `PROBE` and virtual-Z home) |

Shared `PROBE_LOCK` / `DOCK` params apply to the **wrapped** commands listed above (and `G28`).

### Session-only (no dedicated Klicky wrapper)

These use one probe session (or one per sample) so **`auto_attach` still attach/docks**. There is no Klicky-specific rename, no adaptive policy, and no guaranteed thrash-free multi-point behavior beyond “one session = one attach/dock cycle”.

| Command | Notes |
|---------|--------|
| `BED_TILT_CALIBRATE` | Single `ProbePointsHelper` session — attach once, dock once. Prefer **`Z_TILT_ADJUST`** / **QGL** on typical Klicky machines. |
| `DELTA_CALIBRATE` | Same session pattern; delta + Klicky is not a product focus. |
| Other one-shot session callers | Covered only if they call `start_probe_session`. |

For multi-step macros that mix these with other moves, use **`LOCK_PROBE`** / **`PROBE_LOCK=1`** on wrapped steps, or manual `ATTACH_PROBE` / `DETACH_PROBE`.

### Unsupported / not a Klicky target

| Command / area | Why |
|----------------|-----|
| `TEMPERATURE_PROBE_CALIBRATE` (and related wizard) | Temperature-drift calibration for probes with thermal compensation (e.g. eddy-style stacks), not magnetic microswitch Klicky. |
| Manual / nozzle-only tools | `MANUAL_PROBE`, `BED_SCREWS_ADJUST`, `Z_ENDSTOP_CALIBRATE` — no automatic probe session. |
| Config-only | `QUERY_PROBE`, `Z_OFFSET_APPLY_PROBE` — no dock motion. |

### Axis twist (workaround, no dedicated wrap)

`AXIS_TWIST_COMPENSATION_CALIBRATE` probes **each** point with a separate `run_single_probe` (separate session). With default `auto_attach` that means **attach → probe → dock on every sample** (slow/noisy) but still safe.

There is **no** first-class Klicky wrapper. To avoid thrash:

```gcode
ATTACH_PROBE
LOCK_PROBE
AXIS_TWIST_COMPENSATION_CALIBRATE
UNLOCK_PROBE
DETACH_PROBE
```

(Paper-test steps in the wizard use the nozzle; keeping the probe attached for the whole wizard is fine.)

---

## Status (`klicky_probe` object)

- `probe_state`: `unknown` \| `attached` \| `docked`
- `locked`: boolean
- `session_depth` / `hold_depth`: internal counters (debug)

---

## Klipper API note

Implemented against **probe session API** (`start_probe_session` / `end_probe_session`), as in Klipper v0.13+ (verified on tree `v0.13.0-707`). There is no `multi_probe_begin`/`end` in current Klipper.
