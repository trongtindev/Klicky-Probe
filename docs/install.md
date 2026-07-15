# Install Klicky Probe plugin

## Requirements

- **Klipper ≥ v0.13.0** with probe session API (`probe.start_probe_session` / `end_probe_session`) — checked at load (not the removed `multi_probe_begin`/`end` API)
- Existing `[probe]` section in `printer.cfg`
- Moonraker optional (for update manager)

## Quick install

```bash
cd ~
git clone https://github.com/trongtindev/Klicky-Probe.git
cd Klicky-Probe
./plugin/install.sh
```

The install script:

1. Symlinks `plugin/klicky_probe` into `$KLIPPER_PATH/klippy/extras/klicky_probe` (default `~/klipper`)
2. Registers `[update_manager klicky_probe]` in `moonraker.conf` when found. A section is **managed** only when the installer marker comment sits immediately above it (blank lines allowed). Managed sections get path/origin rewritten to the current clone; sections without that adjacent marker are treated as hand-edited and left alone
3. Restarts Klipper when the service is active; restarts Moonraker only when the conf was just modified

Non-default paths:

```bash
export KLIPPER_PATH=/home/pi/klipper
./plugin/install.sh
# or:
./plugin/install.sh -k /home/pi/klipper
./plugin/install.sh /home/pi/klipper

# Custom moonraker.conf:
./plugin/install.sh -m ~/printer_data/config/moonraker.conf
```

### Installer flags

```text
Usage: install.sh [-k KLIPPER_PATH] [-m MOONRAKER_CONF] [-u] [-h] [KLIPPER_PATH]

  -k PATH   Klipper root (default: $KLIPPER_PATH or ~/klipper)
  -m PATH   moonraker.conf path (default: auto-detect)
  -u        Uninstall (extras link + Moonraker update_manager section)
  -h        Help
```

Moonraker conf is searched in order: `$MOONRAKER_CONF` / `-m`, then:

- `~/printer_data/config/moonraker.conf`
- `~/klipper_config/moonraker.conf`
- `~/moonraker.conf`

If no conf is found, install still succeeds; add the update block manually (below).

## printer.cfg

1. Remove old macro includes (`klicky-probe.cfg`, etc.).
2. If using plugin homing, **remove** `[safe_z_home]` and any `[homing_override]`.
3. Add a `[klicky_probe]` section (see [configuration.md](configuration.md) and `config/sample-klicky.cfg`).
4. Keep your stock `[probe]` pin/offsets/samples. **Do not** put dock XY motion in `activate_gcode`.

```ini
[include sample-klicky.cfg]
# or paste [klicky_probe] directly
```

Optional for unhomed Z hop:

```ini
[force_move]
enable_force_move: True
```

## After install — learn the flows

Default: each mesh/level/probe op **attaches then docks**.

Multi-step without thrash:

```gcode
G28 PROBE_LOCK=1
BED_MESH_CALIBRATE PROBE_LOCK=1
UNLOCK_PROBE
DETACH_PROBE
```

Full override guide and flows **F1–F7**: [gcodes.md](gcodes.md).

## Moonraker update manager

`./plugin/install.sh` adds this automatically when it finds `moonraker.conf`.

Manual fallback — copy the block from `plugin/moonraker.snippet.conf` into `moonraker.conf`, adjusting `path` and `origin` to your clone, then restart Moonraker.

## Adaptive bed mesh

1. Configure `[bed_mesh]` as usual (set `adaptive_margin` there if you want a non-zero margin — stock default is `0`).
2. Add `[exclude_object]`.
3. Enable Label Objects / Exclude Objects in the slicer.
4. Set `adaptive_mesh: True` in `[klicky_probe]` (optional; injects `ADAPTIVE=1` only) or call:

```gcode
BED_MESH_CALIBRATE ADAPTIVE=1
# optional runtime override:
# BED_MESH_CALIBRATE ADAPTIVE=1 ADAPTIVE_MARGIN=5
```

Run mesh during print start after objects are defined.

## Uninstall

```bash
./plugin/install.sh -u
# optional path overrides:
./plugin/install.sh -u -k /path/to/klipper -m /path/to/moonraker.conf
```

This removes:

- `$KLIPPER_PATH/klippy/extras/klicky_probe` (symlink or copy)
- `[update_manager klicky_probe]` from `moonraker.conf` (when present)

Then remove `[klicky_probe]` from `printer.cfg` and restart if services were not restarted.

```bash
# manual fallback if needed:
rm -rf ~/klipper/klippy/extras/klicky_probe
sudo systemctl restart klipper
```

## Development tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -q
```
