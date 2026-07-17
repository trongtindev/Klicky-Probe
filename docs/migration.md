# Migrate from legacy Klicky macros

This guide is for printers that used the **old Klipper macro suite** (`klicky-variables.cfg`, `klicky-probe.cfg`, `Attach_Probe`, …). **Klicky Probe Plugin** is a Python Klipper extra (`[klicky_probe]`). It is **not** drop-in compatible with those macros.

Hardware (Klicky / KlickyNG / Unklicky) stays the same. Only the software integration changes.

## 1. Remove the macro suite

1. Delete or comment out every include of legacy Klicky software, for example:
   - `klicky-variables.cfg`
   - `klicky-probe.cfg` / `klicky-macros.cfg`
   - printer- or distro-specific Klicky includes (e.g. RatOS `config/z-probe/klicky/…` if you used that path)
2. If you will use plugin `homing_override: True` (default), remove:
   - `[safe_z_home]`
   - any custom `[homing_override]` for Klicky
3. In `[probe]`, remove dock/attach **XY motion** from `activate_gcode` / `deactivate_gcode`. Klipper forbids toolhead moves there; docking is owned by the plugin.

Keep your stock `[probe]` pin, offsets, and samples.

## 2. Install the plugin

Follow [install.md](install.md): clone this repo, run `./plugin/install.sh`, then add a `[klicky_probe]` section (see `config/sample-klicky.cfg` and [configuration.md](configuration.md)).

## 3. Map geometry variables

| Old macro / variable | Plugin option |
|----------------------|---------------|
| `docklocation_*` | `dock_*` |
| `attachmove_*` | `approach_*` |
| `dockmove_*` | `detach_*` |
| `attachmove2_*` | `approach2_*` |
| `safe_z` | `clearance_z` |
| `z_endstop_*` | `z_home_*` |
| `variable_adaptive_mesh` | `adaptive_mesh` |

Dock, approach, park, umbilical, and safe XY are **toolhead / machine** coordinates (not skewed G-code frame). Calibrate from toolhead position.

## 4. Commands and flows

| Legacy idea | Plugin |
|-------------|--------|
| `Attach_Probe` / `Dock_Probe` macros | `ATTACH_PROBE` / `DETACH_PROBE` |
| Custom start macros that call attach/dock | Prefer wraps + params; see [gcodes.md](gcodes.md) |
| Stay attached across steps | `PROBE_LOCK=1` or `LOCK_PROBE` |
| Dock after one op only | default attach → work → dock |
| Skip dock for one command | `DOCK=0` |

Full flows **F1–F7** and param rules: [gcodes.md](gcodes.md). Do not re-add macro names as the integration API.

## 5. Homing and mesh

| Topic | Plugin behavior |
|-------|-----------------|
| Virtual Z (`probe:z_virtual_endstop`) | With `homing_override: True`, the plugin owns G28 attach/dock for Z |
| Physical Z endstop | Dock before Z home when `dock_before_z_home: True` (default) |
| Adaptive mesh | `adaptive_mesh` under `[klicky_probe]`; **margin** is stock `[bed_mesh] adaptive_margin` (not a klicky key) |

Option details: [configuration.md](configuration.md).

Already on this plugin and only need a new clone path / remote? See [install.md — Existing clone](install.md#existing-clone-repo-rename).
