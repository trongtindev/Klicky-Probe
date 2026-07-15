# Configuration reference

Section name: **`[klicky_probe]`**

Rule: **if you do not set an option, it is derived from existing Klipper config** (printer max velocity/accel, stepper bed size, probe offsets, etc.). Declaring a key overrides the default.

Comment/uncomment template: [`config/sample-klicky.cfg`](../config/sample-klicky.cfg).

## Required

| Option | Description |
|--------|-------------|
| `dock_x`, `dock_y` | Toolhead XY at the dock |
| `approach_x`, `approach_y` | Relative approach vector for attach (**entry XY = dock − approach** [− `approach2` on attach]). Sign matters so entry stays inside the machine envelope |
| `detach_x`, `detach_y` | Relative slide to release magnets when docking |

## Config validation (connect-time)

At `klippy:connect`, after options resolve, the plugin runs pure checks and either **fails config** or logs **warnings** (always, not gated by `log_level`). Messages include a short fix. Full text is in `klippy.log`; if any warnings fired, the ready console note says `N config warning(s) — see klippy.log` (at `log_level: info`+).

| Severity | Examples |
|----------|----------|
| **Error** (blocks load) | Missing/invalid required resolve fields; `bed_min_*` ≥ `bed_max_*`; speed/accel/`clearance_z` ≤ 0; `dock_retries` < 0; `park_after` without `park_x`/`park_y`; approach/detach XY length ≈ 0; approach+approach2 cancel (attach entry on dock); **full attach/detach path XY** (dock, entry, intermediate, release, clear from planners) or enabled staging XY outside **stepper** `position_min/max`; z_home (if `homing_override`) / accuracy (if `auto_attach` + move) / calibrate (if wrap + move) XY outside **bed_***; homing ownership conflicts; `adaptive_mesh` missing deps; `auto_attach` without session API; `dock_servo` servo object missing |
| **Warning** (loads) | Umbilical coords equal safe XY; umbilical still on placeholder `15,15`; `disable_docking` or `homing_override: False` with virtual Z; `wrap_probe_calibrate: False` (intentional policy note — stock paper test leaves probe mounted); `travel_speed` > `[printer] max_velocity`; `clearance_z` below \|probe z_offset\| + pad |

**Not** errors: dock outside the **printable bed** (frame docks are normal). Absolute reachability uses machine limits from `stepper_x` / `stepper_y`. Path checks use the same attach/detach waypoint planners as motion (release = dock + detach, clear = release − approach).

**`disable_docking: True`:** path/vector/staging errors still apply. Geometry must stay load-valid so re-enabling docking does not surprise you; only attach/dock *motion* is skipped at runtime.

## Dock geometry (optional)

| Option | Default | Description |
|--------|---------|-------------|
| `dock_z` | *omit* | Absolute dock Z. **Omit** for gantry/frame mounts |
| `approach_z`, `detach_z` | `0` | Z components of approach/detach |
| `approach2_x/y/z` | `0` | Intermediate approach (side docks / Euclid-style) |

### Coordinate frame (dock / approach / park / umbilical / safe XY)

All dock geometry and staging waypoints (`dock_*`, `approach_*`, `park_*`, `umbilical_*`, `safe_xy_*`) are in the **toolhead / machine frame** (same as `toolhead.get_position()`). Moves use `toolhead.manual_move`, which does **not** pass through G-code transforms such as `[skew_correction]`.

That is intentional: the physical dock does not move when a skew profile loads. Old macro suites used `G0`/`G1` and therefore applied skew to dock targets (upstream issue #287). Calibrate dock and staging XY from toolhead position, not from skewed gcode coordinates.

### Servo docks / extra entry gap

Increase `approach_x` / `approach_y` (and optionally `approach2_*`) so the entry staging point sits far enough for the servo arm to deploy before the final attach move.

## Features (how each changes the flow)

| Option | Default | Flow impact |
|--------|---------|-------------|
| `homing_override` | `True` | Plugin owns `G28` (XY order, Z dock/attach policy). Conflicts with `[safe_z_home]` / `[homing_override]`. **Off:** stock G28; you must attach before virtual Z yourself. |
| `auto_attach` | `True` | **Gate** for session hooks (`start_probe_session` / `end_probe_session`) and wraps for `BED_MESH_CALIBRATE`, `PROBE_ACCURACY`, QGL / Z_TILT / SCREWS. **G28** attach/dock is owned by the homing plan when `homing_override: True` (session auto-dock is suppressed during stock virtual-Z G28). **Off:** no session hooks/wraps; use `ATTACH_PROBE` / `DETACH_PROBE` (flow F6). Bare `PROBE` will not auto-dock. |
| `wrap_probe_calibrate` | `True` | Wrap `PROBE_CALIBRATE`: stage XY → attach → probe → **dock** → nozzle paper test (stock ManualProbe UI). **Independent of `auto_attach`**. **Off:** stock calibrate only (unsafe for Klicky if probe stays mounted). |
| `show_ui_macros` | `True` | Register empty printer objects `gcode_macro ATTACH_PROBE` / `DETACH_PROBE` / `PROBE_CALIBRATE` / `PROBE_ACCURACY` so Mainsail/Fluidd show dashboard buttons under those names. Does **not** change G-code handlers (still Python `register_command` / stock wraps). Set `False` to omit. Skipped if a real `[gcode_macro …]` object already exists. Buttons have no param form (`MOVE`, `X`/`Y`, `RESTORE`, …); console still accepts params. |
| `dock_before_z_home` | `True` | Physical Z: dock **before** Z home (F4). |
| `disable_docking` | `False` | Skip all attach/dock motion (debug). Breaks virtual-Z attach if you still need the probe. |
| `log_level` | `info` | Logging ladder: `warning` \| `info` \| `verbose` \| `debug`. Default **`info`**: short ready line only. `verbose` adds geometry/features dumps and attach/dock progress. `debug` adds plan/trace. `warning` is quiet (warnings/errors only). Legacy `verbose`/`debug` booleans still map if `log_level` is omitted (`debug: True` → `debug`; `verbose: True` → `verbose`; `verbose: False` → `info`). |
| `adaptive_mesh` | `False` | Default `BED_MESH_CALIBRATE` adaptive when `ADAPTIVE` omitted |

### Adaptive mesh policy

| Caller | `adaptive_mesh` | Result |
|--------|-----------------|--------|
| `ADAPTIVE=1` | any | Adaptive; margin = caller `ADAPTIVE_MARGIN` or **`[bed_mesh] adaptive_margin`** (stock) |
| `ADAPTIVE=0` | any | Full mesh |
| no `ADAPTIVE` | `True` | Inject **only** `ADAPTIVE=1` (margin stays stock) |
| no `ADAPTIVE` | `False` | Pass-through |

Requires `[bed_mesh]`. Margin is **not** a `[klicky_probe]` option — set it under stock config:

```ini
[bed_mesh]
adaptive_margin: 5   # stock default is 0; optional gcode ADAPTIVE_MARGIN overrides
```

When `adaptive_mesh: True`, **`[exclude_object]` is required** at config load (Klipper would otherwise soft-fallback to a full mesh). Also enable Label/Exclude Objects in the slicer and call mesh during print start after objects are defined. Without labeled objects at mesh time, stock Klipper still uses a full mesh.

**Migration:** if you previously had `adaptive_margin` under `[klicky_probe]`, move that value to `[bed_mesh]` and delete the klicky key (unused keys error at config load).

### Klipper version

`[klicky_probe]` requires **Klipper ≥ v0.13.0** (probe session API). The plugin reads `software_version` at connect and **fails config** if the version is too old or unparseable.

### Probe section caveats

- **Do not** put Klicky dock XY moves in `[probe] activate_gcode` / `deactivate_gcode`. Klipper errors if the toolhead moves during those scripts. Docking is owned by `[klicky_probe]`.
- Optional: `deactivate_on_each_sample: False` if you use other activate scripts — Klicky docking does not require it.

## Motion / safety (optional overrides)

| Option | Derived default |
|--------|-----------------|
| `travel_speed` | `[printer] max_velocity` (required there — no invented fallback) |
| `move_accel` | `[printer] max_accel` around attach/detach (same rule) |
| `attach_speed` | `50` |
| `detach_speed` | `75` |
| `z_speed` | `20` |
| `clearance_z` | at least `25`, or based on probe z_offset |
| `z_hop_when_unhomed` | `True` (set `False` for free-falling beds). Unhomed hop runs **at most once** until Z is successfully homed — stacking hops would re-zero Z at each new height and walk out of the intended Z envelope (G28 + attach clearance + retries / failed re-home). |
| `bed_min_x` / `bed_min_y` | `stepper_x/y.position_min` (Klipper default `0` if omitted) |
| `bed_max_x` / `bed_max_y` | `stepper_x/y.position_max` (**required** in stepper config) |
| `z_home_x` / `z_home_y` | bed center − probe x/y_offset (toolhead XY for Z home **after** attach; Klipper probes at current XY) |
| `endstop_backoff_x/y` | `10` |
| `home_first` | `auto` (`auto` \| `x` \| `y`) |
| `dock_retries` | `0` |
| `reseat_before_z_home` | `True` — virtual Z: if probe already “attached”, dock then re-attach before home |

## Dock path (umbilical / safe XY / safe_dock_travel)

| Option | Default | Description |
|--------|---------|-------------|
| `safe_dock_travel` | `True` | L-path staging to dock entry (avoids diagonal crash into dock) |
| `safe_xy_before_dock` | `True` | On **detach** only, move to `safe_xy_x`/`safe_xy_y` before dock approach (avoids sweeping nozzle clean / purge brush with probe mounted) |
| `safe_xy_x` / `safe_xy_y` | bed center | Omit → center of `bed_min/max` |
| `umbilical` | `False` | If true, move to `(umbilical_x, umbilical_y, clearance_z)` before safe XY / dock entry (both attach and detach) |
| `umbilical_x` / `umbilical_y` | `15` / `15` | Toolhead XY for that early waypoint; set a real free point on your machine (`15,15` is only a placeholder default) |

### Path order

Attach and detach always raise Z to `clearance_z` first. Optional staging then runs in this order (each step is independent — no config conflict):

```
clearance_z
  → umbilical (if on)              # early fixed XY — cable / corner routing
  → safe_xy (if on; detach only)   # mid staging — avoid nozzle clean with probe on head
  → L-path to entry (safe_dock_travel, default on)
  → attach/detach body
```

| Option | Default | Role | When to enable |
|--------|---------|------|----------------|
| `umbilical` | off | Early fixed XY at `clearance_z` | Probe/toolhead **cable** snags if you go straight from the print area; need a corner/front waypoint first |
| `safe_xy_before_dock` | on | Mid staging on **detach** (omit coords → bed center) | **Nozzle clean** / purge brush / wipe on the path while the probe is mounted |
| `safe_dock_travel` | on | Final axis-aligned path into dock entry | Keep on unless you intentionally want legacy **diagonal** entry |

They do **not** replace each other: umbilical is cable routing, safe XY is obstacle clearance with probe on, L-path is final dock geometry. If you would set umbilical and safe XY to the **same** point, enable only one — a double move is wasteful.

### Safe XY before dock (when to use)

On **detach**, horizontal travel toward the dock can cross a **nozzle cleaner**, purge brush, or similar fixed obstacle and knock the probe off the mount. Safe XY staging runs only on detach; attach travels empty and skips it.

| Situation | Recommendation |
|-----------|----------------|
| Cleaner / brush / wipe on the path from print area → dock | Keep **`safe_xy_before_dock: True`** (default). Omit `safe_xy_x`/`safe_xy_y` for bed center, or set both explicitly. |
| Bed center is still not clear | Set custom `safe_xy_x` / `safe_xy_y` clear of the obstacle. |
| Open bed, no fixed XY obstacles, want shortest path | `safe_xy_before_dock: False` |
| Already using `umbilical` | Both OK if the points differ; order is umbilical → safe XY (detach) → dock entry |

### Umbilical (when to use)

When `umbilical: True`, attach/detach first move to `(umbilical_x, umbilical_y)` at `clearance_z` and `travel_speed`, then continue with safe XY (detach) and dock entry. Defaults `15,15` are **not** machine-specific — pick a free corner that keeps the cable clear.

| Situation | Recommendation |
|-----------|----------------|
| Cable/umbilical pulls or snags near a rear/side dock | `umbilical: True` + set `umbilical_x` / `umbilical_y` to a free corner |
| Only need to avoid nozzle clean / brush | Keep `safe_xy_before_dock`; leave **`umbilical: False`** (default) |
| Would set umbilical coords equal to safe XY | Use **one** only |
| Open path, no cable issue | Leave `umbilical: False` |

## Probe staging (accuracy / calibrate)

Defaults use the same **formula** as default `z_home_*` (bed center − probe offsets), but each pair is **independent** — overriding `z_home_x/y` does not move accuracy or calibrate targets.

| Option | Default | Description |
|--------|---------|-------------|
| `probe_accuracy_move` | `True` | When the `PROBE_ACCURACY` wrap runs (`auto_attach`), move to a target toolhead XY before stock samples. `False` = stock “probe here” (still attaches/docks). Override per call with `MOVE=0` / `MOVE=1`. |
| `probe_accuracy_x` / `probe_accuracy_y` | derived bed center − probe offsets | Set only if accuracy should use a different point than derived center. Runtime: `PROBE_ACCURACY X=… Y=…`. |
| `probe_calibrate_move` | `True` | When `wrap_probe_calibrate`, stage toolhead XY before the automatic probe sample. Then **dock**, then nozzle paper test. `MOVE=0` / `MOVE=1` override per call. Stage + post-dock XY use `travel_speed`; Z uses `z_speed`. Paper ManualProbe starts at toolhead Z after the sample + 5 mm (stock lift), not `clearance_z`. Probe descent still uses Klipper `[probe] speed`. |
| `probe_calibrate_x` / `probe_calibrate_y` | derived bed center − probe offsets | Independent of `z_home_*` and `probe_accuracy_*` overrides. Runtime: `PROBE_CALIBRATE X=… Y=…`. |

## Optional behaviors

| Option | Description |
|--------|-------------|
| `park_after` + `park_x/y/z` | Park after attach/dock/home (`park_z` omit = keep Z) |
| `dock_servo` + `servo_name` + angles + `servo_delay_ms` | Servo-deployed dock |

## User gcode hooks

Optional G-code under `[klicky_probe]` runs at lifecycle points so you can customize per machine (status LEDs, beeps, display, extra macros, …). Omit any key you do not need.

### Side-effect hooks (soft-fail)

Missing hook = no-op. If a hook **raises** (unknown command, macro error, …), Klicky logs a warning, prints `klicky: hook <name> failed: …` to the console, and **continues** the core path. Soft-fail is for UI / non-critical extras — do **not** put dock-critical motion here (use `dock_servo` / approach geometry for that).

| Option | When it runs |
|--------|----------------|
| `pre_attach_gcode` / `post_attach_gcode` | Around attach dock body (after servo deploy / after attach motion) |
| `pre_detach_gcode` / `post_detach_gcode` | Around detach dock body |
| `pre_homing_gcode` / `post_homing_gcode` | Start / end of plugin `G28` (`homing_override`). Also fires on internal Z rehome inside `Z_TILT_ADJUST` (nested under leveling hooks) |
| `pre_leveling_gcode` / `post_leveling_gcode` | After attach, before stock op / after exit, for QGL, `SCREWS_TILT_CALCULATE`, `Z_TILT_ADJUST` |
| `pre_meshing_gcode` / `post_meshing_gcode` | Same lifecycle for `BED_MESH_CALIBRATE` |
| `pre_probe_calibrate_gcode` / `post_probe_calibrate_gcode` | Start of Klicky `PROBE_CALIBRATE`; post once on paper ACCEPT/ABORT or on error if paper UI never started |
| `pre_probe_accuracy_gcode` / `post_probe_accuracy_gcode` | Same lifecycle for `PROBE_ACCURACY` |

**Wrapped ops** (mesh / leveling / accuracy) share one order: **attach → pre_* → stock work → dock/exit → post_***. Pre runs after attach so the probe is already mounted. Post always runs even if dock-on-exit fails.

Nested attach during calibrate still runs attach hooks. For a long op (e.g. paper test), put “in progress” UI on outer hooks (`pre_probe_calibrate_gcode`, …) rather than only on `post_attach_gcode`.

### Axis home replacement (hard-fail)

| Option | When it runs |
|--------|----------------|
| `home_x_gcode` / `home_y_gcode` | Replaces stock `G28 X` / `G28 Y` when set (sensorless, etc.) |

These are **not** soft-fail: a failure aborts that axis home. Omit both keys to use stock homing.

### Example

Wire your own macros (names are yours — call whatever you already use on the printer):

```ini
[klicky_probe]
pre_attach_gcode:
  STATUS_BUSY
post_attach_gcode:
  STATUS_READY
pre_detach_gcode:
  STATUS_BUSY
post_detach_gcode:
  STATUS_READY
pre_homing_gcode:
  STATUS_HOMING
post_homing_gcode:
  STATUS_READY
pre_leveling_gcode:
  STATUS_LEVELING
post_leveling_gcode:
  STATUS_READY
pre_meshing_gcode:
  STATUS_MESHING
post_meshing_gcode:
  STATUS_READY
pre_probe_calibrate_gcode:
  STATUS_CALIBRATING_Z
post_probe_calibrate_gcode:
  STATUS_READY
# pre_probe_accuracy_gcode: / post_probe_accuracy_gcode: optional
```

## Meaning map from old macros (reference only — not compatible)

| Old variable | New option |
|--------------|------------|
| `docklocation_*` | `dock_*` |
| `attachmove_*` | `approach_*` |
| `dockmove_*` | `detach_*` |
| `attachmove2_*` | `approach2_*` |
| `safe_z` | `clearance_z` |
| `z_endstop_*` | `z_home_*` |
| `variable_adaptive_mesh` | `adaptive_mesh` |

There is **no** compatibility with `Attach_Probe` macro names or `klicky-variables.cfg`.

See [gcodes.md](gcodes.md) for flows (F1–F7) and override params.
