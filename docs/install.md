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

The install script symlinks `plugin/klicky_probe` into `$KLIPPER_PATH/klippy/extras/klicky_probe` (default `~/klipper`) and restarts Klipper when possible.

Non-default Klipper location:

```bash
export KLIPPER_PATH=/home/pi/klipper
./plugin/install.sh
# or:
./plugin/install.sh /home/pi/klipper
```

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

Copy the block from `plugin/moonraker.snippet.conf` into `moonraker.conf`, adjusting `path` and `origin` to your clone.

## Adaptive bed mesh

1. Configure `[bed_mesh]` as usual.
2. Add `[exclude_object]`.
3. Enable Label Objects / Exclude Objects in the slicer.
4. Set `adaptive_mesh: True` (optional) or call:

```gcode
BED_MESH_CALIBRATE ADAPTIVE=1 ADAPTIVE_MARGIN=5
```

Run mesh during print start after objects are defined.

## Uninstall

```bash
rm -rf ~/klipper/klippy/extras/klicky_probe
# remove [klicky_probe] from printer.cfg
sudo systemctl restart klipper
```

## Development tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -q
```
