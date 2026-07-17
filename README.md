# Klicky Probe Plugin

Klipper **Python plugin** for Klicky / KlickyNG / Unklicky magnetic probes (attach/dock, homing, leveling, adaptive bed mesh). Hardware STLs and printer guides live in [Klicky-Probe-Files](https://github.com/trongtindev/Klicky-Probe-Files).

## Software

The supported integration is the **`[klicky_probe]`** Klipper extra under [`plugin/`](plugin/).

- Requires **Klipper ≥ v0.13.0** (checked at load)
- One config section; defaults from `[printer]` / steppers / `[probe]`
- **`auto_attach`**: attach/dock around Klipper **probe sessions** (`start_probe_session` / `end_probe_session`) for mesh / probe ops
- **G28** (homing plan): owns virtual-Z attach-before / dock-after; session auto-dock suppressed during stock G28 Z
- First-class wraps: **G28**, mesh, QGL / Z-tilt / screws, `PROBE_CALIBRATE`, `PROBE_ACCURACY` — not every Klipper probe consumer (see [docs/gcodes.md](docs/gcodes.md) scope)
- Safe default: **dock after each probe op**; override with `PROBE_LOCK` / `DOCK` for multi-step macros
- Adaptive bed mesh via native `ADAPTIVE` / `ADAPTIVE_MARGIN` (margin from `[bed_mesh]`, not `[klicky_probe]`)
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
git clone https://github.com/trongtindev/klicky-probe-plugin.git
cd klicky-probe-plugin
./plugin/install.sh
```

Registers the plugin in Klipper extras and adds a Moonraker update-manager section when `moonraker.conf` is found. Uninstall: `./plugin/install.sh -u`.

Then add `[klicky_probe]` to `printer.cfg` (see [`config/sample-klicky.cfg`](config/sample-klicky.cfg)).

Coming from legacy macros? **[docs/migration.md](docs/migration.md)**.

**Docs:** [Install](docs/install.md) · [Migration](docs/migration.md) · [Configuration](docs/configuration.md) · [G-codes & flows](docs/gcodes.md)

### Tests

```bash
pip install -e ".[dev]"
ruff check plugin tests
pytest tests/ -q
```

### Minimal config sketch

Same geometry and feature gates as [`config/sample-klicky.cfg`](config/sample-klicky.cfg) (comment/uncomment the rest there).

```ini
[probe]
pin: ^YOUR_PIN
x_offset: 0
y_offset: 25
z_offset: 0
# Do NOT put dock XY moves in activate_gcode (Klipper forbids toolhead motion there)

[klicky_probe]
dock_x: 40
dock_y: 300
approach_x: 0
approach_y: 30
detach_x: -40
detach_y: 0
homing_override: True
auto_attach: True
wrap_probe_calibrate: True
# adaptive_mesh: True   # optional; needs [bed_mesh] + [exclude_object]
```

If `homing_override: True`, remove `[safe_z_home]` / `[homing_override]`. Legacy macro cleanup: [docs/migration.md](docs/migration.md).

## Hardware

STLs, CAD, printer guides, photos, and usermods: [Klicky-Probe-Files](https://github.com/trongtindev/Klicky-Probe-Files) (separate repo so this plugin clone stays small). A `files/` tree may also exist in this clone for local development.

| Path | Contents |
|------|----------|
| [`files/probes/`](https://github.com/trongtindev/Klicky-Probe-Files/tree/main/probes) | Klicky / KlickyNG / Unklicky assembly |
| [`files/printers/`](https://github.com/trongtindev/Klicky-Probe-Files/tree/main/printers) | Voron, V-Core, Switchwire, … |
| [`files/usermods/`](https://github.com/trongtindev/Klicky-Probe-Files/tree/main/usermods) | Community mounts |
| [`files/photos/`](https://github.com/trongtindev/Klicky-Probe-Files/tree/main/photos) | Shared photos / media |
| [`files/CAD/`](https://github.com/trongtindev/Klicky-Probe-Files/tree/main/CAD) | STEP / CAD exports |

## License

GPL-3.0 — see [LICENSE](LICENSE).

## Credits

Original Klicky hardware and macros: JosAr and many contributors (Mental, Garrettwp, richardjm, Voron community, Annex Quickdraw lineage, and others). See [Klicky-Probe-Files](https://github.com/trongtindev/Klicky-Probe-Files) docs for full attribution.
