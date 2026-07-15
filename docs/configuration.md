# Configuration reference

Section name: **`[klicky_probe]`**

Rule: **if you do not set an option, it is derived from existing Klipper config** (printer max velocity/accel, stepper bed size, probe offsets, etc.). Declaring a key overrides the default.

## Required

| Option | Description |
|--------|-------------|
| `dock_x`, `dock_y` | Toolhead XY at the dock |
| `approach_x`, `approach_y` | Relative approach vector for attach |
| `detach_x`, `detach_y` | Relative slide to release magnets when docking |

## Dock geometry (optional)

| Option | Default | Description |
|--------|---------|-------------|
| `dock_z` | *omit* | Absolute dock Z. **Omit** for gantry/frame mounts |
| `approach_z`, `detach_z` | `0` | Z components of approach/detach |
| `approach2_x/y/z` | `0` | Intermediate approach (side docks / Euclid-style) |

## Features (how each changes the flow)

| Option | Default | Flow impact |
|--------|---------|-------------|
| `homing_override` | `True` | Plugin owns `G28` (XY order, Z dock/attach policy). Conflicts with `[safe_z_home]` / `[homing_override]`. **Off:** stock G28; you must attach before virtual Z yourself. |
| `auto_attach` | `True` | **Gate** for session hooks (`start_probe_session` / `end_probe_session`) and wraps for `BED_MESH_CALIBRATE`, `PROBE_ACCURACY`, QGL / Z_TILT / SCREWS. **G28** attach/dock is owned by the homing plan when `homing_override: True` (session auto-dock is suppressed during stock virtual-Z G28). **Off:** no session hooks/wraps; use `ATTACH_PROBE` / `DETACH_PROBE` (flow F6). Bare `PROBE` will not auto-dock. |
| `wrap_probe_calibrate` | `True` | Wrap `PROBE_CALIBRATE` (attach + leave for paper test). **Independent of `auto_attach`** (paper-test ergonomics). **Off:** stock calibrate only. |
| `dock_before_z_home` | `True` | Physical Z: dock **before** Z home (F4). |
| `disable_docking` | `False` | Skip all attach/dock motion (debug). Breaks virtual-Z attach if you still need the probe. |
| `verbose` / `debug` | `True` / `False` | Logging |
| `adaptive_mesh` | `False` | Default `BED_MESH_CALIBRATE` adaptive when `ADAPTIVE` omitted |
| `adaptive_margin` | `5` | Default margin (mm) for adaptive mesh |

### Adaptive mesh policy

| Caller | `adaptive_mesh` | Result |
|--------|-----------------|--------|
| `ADAPTIVE=1` | any | Adaptive; margin = caller or `adaptive_margin` |
| `ADAPTIVE=0` | any | Full mesh |
| no `ADAPTIVE` | `True` | Inject `ADAPTIVE=1` + margin |
| no `ADAPTIVE` | `False` | Pass-through |

Requires `[bed_mesh]`. When `adaptive_mesh: True`, **`[exclude_object]` is required** at config load (Klipper would otherwise soft-fallback to a full mesh). Also enable Label/Exclude Objects in the slicer and call mesh during print start after objects are defined. Without labeled objects at mesh time, stock Klipper still uses a full mesh.

### Klipper version

`[klicky_probe]` requires **Klipper ≥ v0.13.0** (probe session API). The plugin reads `software_version` at connect and **fails config** if the version is too old or unparseable.

### Probe section caveats

- **Do not** put Klicky dock XY moves in `[probe] activate_gcode` / `deactivate_gcode`. Klipper errors if the toolhead moves during those scripts. Docking is owned by `[klicky_probe]`.
- Optional: `deactivate_on_each_sample: False` if you use other activate scripts — Klicky docking does not require it.

## Motion / safety (optional overrides)

| Option | Derived default |
|--------|-----------------|
| `travel_speed` | `min(printer.max_velocity, 200)` |
| `move_accel` | `printer.max_accel` (around attach/detach) |
| `attach_speed` | `50` |
| `detach_speed` | `75` |
| `z_speed` | `20` |
| `clearance_z` | at least `25`, or based on probe z_offset |
| `z_hop_when_unhomed` | `True` (set `False` for free-falling beds). Unhomed hop runs **at most once** until Z is successfully homed — stacking hops would re-zero Z at each new height and walk out of the intended Z envelope (G28 + attach clearance + retries / failed re-home). |
| `bed_min_x` / `bed_min_y` | `stepper_x/y.position_min` |
| `bed_max_x` / `bed_max_y` | `stepper_x/y.position_max` |
| `z_home_x` / `z_home_y` | bed center − probe x/y_offset (toolhead XY for Z home **after** attach; Klipper probes at current XY) |
| `endstop_backoff_x/y` | `10` |
| `home_first` | `auto` (`auto` \| `x` \| `y`) |
| `dock_retries` | `0` |
| `safe_dock_travel` | `True` — L-path staging to dock entry (avoids diagonal crash into dock) |
| `reseat_before_z_home` | `True` — virtual Z: if probe already “attached”, dock then re-attach before home |

### Coordinate frame (dock / approach / park)

All dock geometry is in the **toolhead / machine frame** (same as `toolhead.get_position()`). Moves use `toolhead.manual_move`, which does **not** pass through G-code transforms such as `[skew_correction]`.

That is intentional: the physical dock does not move when a skew profile loads. Old macro suites used `G0`/`G1` and therefore applied skew to dock targets (upstream issue #287). Calibrate `dock_*` / `approach_*` from toolhead position, not from skewed gcode coordinates.

### Servo docks / extra entry gap

Increase `approach_x` / `approach_y` (and optionally `approach2_*`) so the entry staging point sits far enough for the servo arm to deploy before the final attach move.

## Optional behaviors

| Option | Description |
|--------|-------------|
| `park_after` + `park_x/y/z` | Park after attach/dock/home (`park_z` omit = keep Z) |
| `umbilical` + `umbilical_x/y` | Extra path before dock moves |
| `dock_servo` + `servo_name` + angles + `servo_delay_ms` | Servo-deployed dock |
| `pre_attach_gcode` / `post_attach_gcode` / `pre_detach_gcode` / `post_detach_gcode` | Custom snippets |
| `home_x_gcode` / `home_y_gcode` | Custom axis homing (sensorless, etc.) |

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
