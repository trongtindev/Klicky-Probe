# Klicky Probe

Magnetic microswitch probe for CoreXY and similar printers — **hardware** in [Klicky-Probe-Files](https://github.com/trongtindev/Klicky-Probe-Files) plus a **Klipper Python plugin** for attach/dock, homing, leveling, and adaptive bed mesh.

## Software (current)

The supported integration is the **`[klicky_probe]`** Klipper extra under [`plugin/`](plugin/).

- Requires **Klipper ≥ v0.13.0** (checked at load)
- One config section; defaults from `[printer]` / steppers / `[probe]`
- **`auto_attach`**: attach/dock around Klipper **probe sessions** (`start_probe_session` / `end_probe_session`)
- First-class wraps: **G28**, mesh, QGL / Z-tilt / screws, `PROBE_CALIBRATE`, `PROBE_ACCURACY` — not every Klipper probe consumer (see [docs/gcodes.md](docs/gcodes.md) scope)
- Safe default: **dock after each probe op**; override with `PROBE_LOCK` / `DOCK` for multi-step macros
- Adaptive bed mesh via native `ADAPTIVE` / `ADAPTIVE_MARGIN`
- Pure-logic unit tests (`pytest`)

### Probe lifecycle (short)

```text
default:     attach → work → dock
PROBE_LOCK:  attach → work → stay on (until UNLOCK + DETACH)
DOCK=0:      attach → work → stay on (next op may dock)
```

**F1 — one command (default, safe)**

```gcode
BED_MESH_CALIBRATE
# attaches, meshes, docks — no params
```

**F2 — multi-step without dock thrash**

```gcode
G28 PROBE_LOCK=1
BED_MESH_CALIBRATE PROBE_LOCK=1
UNLOCK_PROBE
DETACH_PROBE
```

| Want | Do |
|------|-----|
| Keep probe across steps | `PROBE_LOCK=1` or `LOCK_PROBE` |
| This command only, no dock | `DOCK=0` |
| Force dock | `DOCK=1` or `UNLOCK_PROBE` + `DETACH_PROBE` |
| Full manual | `auto_attach: False` + `ATTACH_PROBE` / `DETACH_PROBE` (no auto session/mesh/level wraps) |

Details, flows F1–F7, and **supported vs unsupported scope**: **[docs/gcodes.md](docs/gcodes.md)**.

### Install

```bash
git clone https://github.com/trongtindev/Klicky-Probe.git
cd Klicky-Probe
./plugin/install.sh
```

Then add `[klicky_probe]` to `printer.cfg` (see [`config/sample-klicky.cfg`](config/sample-klicky.cfg)).

**Docs:** [Install](docs/install.md) · [Configuration](docs/configuration.md) · [G-codes & flows](docs/gcodes.md)

### Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -q
```

### Minimal config sketch

```ini
[probe]
pin: ^YOUR_PIN
x_offset: 0
y_offset: 25
z_offset: 0
# Do NOT put dock XY moves in activate_gcode (Klipper forbids toolhead motion there)

[klicky_probe]
dock_x: 0
dock_y: 300
approach_x: 30
approach_y: 0
detach_x: 0
detach_y: 40
homing_override: True
auto_attach: True
adaptive_mesh: False
```

Remove old Klicky **macro** includes and, if `homing_override: True`, remove `[safe_z_home]` / `[homing_override]`.

## Hardware & history

STLs, CAD, printer guides, photos, and usermods live under [`files/`](https://github.com/trongtindev/Klicky-Probe-Files) (separate repo so this plugin clone stays small).

| Path | Contents |
|------|----------|
| [`files/probes/`](https://github.com/trongtindev/Klicky-Probe-Files/tree/main/probes) | Klicky / KlickyNG / Unklicky assembly |
| [`files/printers/`](https://github.com/trongtindev/Klicky-Probe-Files/tree/main/printers) | Voron, V-Core, Switchwire, … |
| [`files/usermods/`](https://github.com/trongtindev/Klicky-Probe-Files/tree/main/usermods) | Community mounts |
| [`files/photos/`](https://github.com/trongtindev/Klicky-Probe-Files/tree/main/photos) | Shared photos / media |
| [`files/CAD/`](https://github.com/trongtindev/Klicky-Probe-Files/tree/main/CAD) | STEP / CAD exports |

Software for Klipper is the **plugin** under [`plugin/`](plugin/) (see [docs/](docs/)). Older Klipper **macro** suites are not shipped here and are **not** compatible with this plugin (new option names and G-codes).

## License

GPL-3.0 — see [LICENSE](LICENSE).

## Credits

Original Klicky hardware and macros: JosAr and many contributors (Mental, Garrettwp, richardjm, Voron community, Annex Quickdraw lineage, and others). See [Klicky-Probe-Files](https://github.com/trongtindev/Klicky-Probe-Files) docs for full attribution.
