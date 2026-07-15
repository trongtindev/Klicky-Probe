# Klicky Probe — Klipper extra for magnetic dockable probes
#
# Copyright (C) 2026 Klicky Probe contributors
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Install: copy/symlink this package to klippy/extras/klicky_probe/
# Config section: [klicky_probe]

from __future__ import annotations

import logging

from . import errors as E
from .command_wrappers import CommandWrappers
from .defaults import (
    PrinterSnapshot,
    resolve_settings,
    validate_homing_conflicts,
)
from .dock_executor import DockExecutor
from .homing_executor import HomingExecutor
from .homing_plan import HomingRequest
from .klipper_version import MIN_KLIPPER_VERSION, check_min_klipper_version
from .probe_lifecycle import ProbeLifecycle
from .probe_session import SessionCounters
from .probe_state import ProbeState


def _config_has(config, name):
    """Return True if option is present in this config section."""
    try:
        return config.fileconfig.has_option(config.get_name(), name)
    except Exception:
        return False


class KlickyProbe:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")
        self.config = config
        self.reactor = self.printer.get_reactor()

        self._user = self._parse_user_config(config)
        self.settings = None
        self.state = ProbeState()
        self._toolhead = None
        self._probe = None
        self._orig_g28 = None
        self._orig_bed_mesh = None
        self._wrapped = {}
        self._session = SessionCounters()
        self._gcode_templates = {}
        self._skew_frame_logged = False

        self.dock = DockExecutor(self)
        self.lifecycle = ProbeLifecycle(self)
        self.homing = HomingExecutor(self)
        self.wrappers = CommandWrappers(self)

        for name in (
            "pre_attach_gcode",
            "post_attach_gcode",
            "pre_detach_gcode",
            "post_detach_gcode",
            "home_x_gcode",
            "home_y_gcode",
        ):
            if _config_has(config, name):
                try:
                    self._gcode_templates[name] = config.gettemplate(name)
                except Exception:
                    self._gcode_templates[name] = config.get(name)

        self.printer.register_event_handler("klippy:connect", self._handle_connect)
        self.printer.register_event_handler("klippy:ready", self._handle_ready)

        self.gcode.register_command(
            "ATTACH_PROBE", self.cmd_ATTACH_PROBE, desc=self.cmd_ATTACH_PROBE_help
        )
        self.gcode.register_command(
            "DETACH_PROBE", self.cmd_DETACH_PROBE, desc=self.cmd_DETACH_PROBE_help
        )
        self.gcode.register_command(
            "LOCK_PROBE", self.cmd_LOCK_PROBE, desc=self.cmd_LOCK_PROBE_help
        )
        self.gcode.register_command(
            "UNLOCK_PROBE", self.cmd_UNLOCK_PROBE, desc=self.cmd_UNLOCK_PROBE_help
        )
        self.gcode.register_command(
            "GET_PROBE_STATUS",
            self.cmd_GET_PROBE_STATUS,
            desc=self.cmd_GET_PROBE_STATUS_help,
        )
        self.gcode.register_command(
            "ENSURE_PROBE_DOCKED",
            self.cmd_ENSURE_PROBE_DOCKED,
            desc=self.cmd_ENSURE_PROBE_DOCKED_help,
        )

    def _parse_user_config(self, config):
        user = {
            "dock_x": config.getfloat("dock_x"),
            "dock_y": config.getfloat("dock_y"),
            "approach_x": config.getfloat("approach_x"),
            "approach_y": config.getfloat("approach_y"),
            "detach_x": config.getfloat("detach_x"),
            "detach_y": config.getfloat("detach_y"),
        }

        optional_floats = (
            "dock_z", "approach_z", "detach_z",
            "approach2_x", "approach2_y", "approach2_z",
            "adaptive_margin", "clearance_z",
            "travel_speed", "attach_speed", "detach_speed", "z_speed", "move_accel",
            "bed_min_x", "bed_min_y", "bed_max_x", "bed_max_y", "z_home_x", "z_home_y",
            "endstop_backoff_x", "endstop_backoff_y",
            "park_x", "park_y", "park_z",
            "umbilical_x", "umbilical_y",
            "servo_deploy_angle", "servo_retract_angle", "servo_delay_ms",
        )
        for name in optional_floats:
            if _config_has(config, name):
                user[name] = config.getfloat(name)

        optional_bools = (
            "homing_override", "auto_attach", "wrap_probe_calibrate",
            "dock_before_z_home", "disable_docking", "verbose", "debug",
            "adaptive_mesh", "z_hop_when_unhomed", "park_after",
            "umbilical", "dock_servo", "safe_dock_travel", "reseat_before_z_home",
        )
        for name in optional_bools:
            if _config_has(config, name):
                user[name] = config.getboolean(name)

        if _config_has(config, "home_first"):
            user["home_first"] = config.get("home_first")
        if _config_has(config, "servo_name"):
            user["servo_name"] = config.get("servo_name")
        if _config_has(config, "dock_retries"):
            user["dock_retries"] = config.getint("dock_retries")
        return user

    def _build_printer_snapshot(self) -> PrinterSnapshot:
        printer = self.printer
        configfile = printer.lookup_object("configfile")
        status = configfile.get_status(self.reactor.monotonic())
        settings = status.get("settings", {})

        def sect(name):
            return settings.get(name, {}) or {}

        sx, sy, sz = sect("stepper_x"), sect("stepper_y"), sect("stepper_z")
        probe, pr = sect("probe"), sect("printer")
        endstop = str(sz.get("endstop_pin", ""))
        return PrinterSnapshot(
            stepper_x_position_max=float(sx.get("position_max", 300)),
            stepper_y_position_max=float(sy.get("position_max", 300)),
            stepper_x_position_min=float(sx.get("position_min", 0)),
            stepper_y_position_min=float(sy.get("position_min", 0)),
            probe_x_offset=float(probe.get("x_offset", 0)),
            probe_y_offset=float(probe.get("y_offset", 0)),
            probe_z_offset=float(probe.get("z_offset", 0)),
            probe_speed=float(probe.get("speed", 5)),
            max_velocity=float(pr.get("max_velocity", 300)),
            max_accel=float(pr.get("max_accel", 3000)),
            z_virtual_endstop="z_virtual_endstop" in endstop,
            has_bed_mesh=printer.lookup_object("bed_mesh", None) is not None,
            has_exclude_object=printer.lookup_object("exclude_object", None) is not None,
            has_safe_z_home=printer.lookup_object("safe_z_home", None) is not None,
            has_homing_override=printer.lookup_object("homing_override", None) is not None,
        )

    def _handle_connect(self):
        ver = self.printer.get_start_args().get("software_version", "?")
        ver_reason = check_min_klipper_version(ver)
        if ver_reason == "too_old":
            raise self.printer.config_error(
                E.klipper_version_too_old(found=ver, required=MIN_KLIPPER_VERSION)
            )
        if ver_reason == "unparseable":
            raise self.printer.config_error(
                E.klipper_version_unparseable(
                    found=ver, required=MIN_KLIPPER_VERSION
                )
            )

        probe = self.printer.lookup_object("probe", None)
        if probe is None:
            raise self.printer.config_error(E.probe_section_required())
        self._probe = probe

        snap = self._build_printer_snapshot()
        try:
            self.settings = resolve_settings(self._user, snap)
        except ValueError as e:
            raise self.printer.config_error(str(e))

        err = validate_homing_conflicts(self.settings, snap)
        if err:
            raise self.printer.config_error(err)

        if self.settings.adaptive_mesh and not snap.has_bed_mesh:
            raise self.printer.config_error(E.adaptive_needs_bed_mesh())
        if self.settings.adaptive_mesh and not snap.has_exclude_object:
            raise self.printer.config_error(E.adaptive_needs_exclude_object())
        if self.settings.auto_attach and not hasattr(probe, "start_probe_session"):
            raise self.printer.config_error(E.session_api_required())

        if self.settings.debug or self.settings.verbose:
            self._log(
                "resolved: dock=(%.3f,%.3f,%s) clearance_z=%.2f travel=%.1f "
                "bed_max=(%.1f,%.1f) z_home=(%.1f,%.1f) adaptive_mesh=%s"
                % (
                    self.settings.dock_x, self.settings.dock_y, self.settings.dock_z,
                    self.settings.clearance_z, self.settings.travel_speed,
                    self.settings.bed_max_x, self.settings.bed_max_y,
                    self.settings.z_home_x, self.settings.z_home_y,
                    self.settings.adaptive_mesh,
                )
            )

    def _handle_ready(self):
        self._toolhead = self.printer.lookup_object("toolhead")
        s = self.settings
        if s is None:
            return

        if s.homing_override:
            self._orig_g28 = self.gcode.register_command("G28", None)
            self.gcode.register_command("G28", self.cmd_G28)

        # auto_attach is the single gate for all automatic attach/dock wraps
        # (session hooks, mesh, leveling, accuracy). wrap_probe_calibrate is
        # independent (paper-test ergonomics).
        if s.auto_attach:
            self.wrappers.install_probe_session_hooks()
            self.wrappers.wrap_leveling_commands()
            if self.printer.lookup_object("bed_mesh", None) is not None:
                self.wrappers.wrap_bed_mesh_calibrate()
            self.wrappers.wrap_probe_accuracy()

        if s.wrap_probe_calibrate:
            self.wrappers.wrap_probe_calibrate()

        self._maybe_log_skew_frame()

    def _maybe_log_skew_frame(self):
        """Document toolhead-frame dock policy when skew is active (#287)."""
        if self._skew_frame_logged:
            return
        skew = self.printer.lookup_object("skew_correction", None)
        if skew is None:
            return
        try:
            st = skew.get_status(self.reactor.monotonic())
            name = (st or {}).get("current_profile_name") or ""
        except Exception:
            name = ""
        if not name:
            return
        self._skew_frame_logged = True
        self._log(
            "skew profile '%s' active; dock/approach coords use toolhead "
            "(machine) frame — toolhead.manual_move bypasses gcode skew"
            % name
        )

    def _log(self, msg):
        logging.info("klicky_probe: %s", msg)
        if self.settings and self.settings.verbose:
            try:
                self.gcode.respond_info("klicky: %s" % msg)
            except Exception:
                pass

    def _debug(self, msg):
        if self.settings and self.settings.debug:
            logging.info("klicky_probe debug: %s", msg)
            try:
                self.gcode.respond_info("klicky debug: %s" % msg)
            except Exception:
                pass

    def _run_template(self, name):
        tmpl = self._gcode_templates.get(name)
        if tmpl is None:
            return
        if hasattr(tmpl, "run_gcode_from_command"):
            tmpl.run_gcode_from_command()
        elif isinstance(tmpl, str):
            self.gcode.run_script_from_command(tmpl)

    def _xy_homed(self) -> bool:
        th = self._toolhead or self.printer.lookup_object("toolhead")
        homed = th.get_status(self.reactor.monotonic()).get("homed_axes", "")
        return "x" in homed and "y" in homed

    def _query_probe_triggered(self) -> bool:
        """
        Return True if the probe switch reports triggered (typically docked).

        Uses QUERY_PROBE then probe.get_status()['last_query']. Fail closed.
        """
        self.gcode.run_script_from_command("QUERY_PROBE")
        probe = self._probe
        try:
            st = probe.get_status(self.reactor.monotonic())
            if isinstance(st, dict) and "last_query" in st:
                return bool(st["last_query"])
        except Exception:
            pass
        if probe is not None and hasattr(probe, "last_query"):
            return bool(probe.last_query)
        raise self.gcode.error(E.probe_query_unavailable())

    def _status_led(self, name):
        try:
            self.gcode.run_script_from_command("STATUS_%s" % name.upper())
        except Exception:
            pass

    def _check_over_bed(self):
        s = self.settings
        pos = self._toolhead.get_position()
        margin = 50.0
        if (
            pos[0] > s.bed_max_x + margin
            or pos[1] > s.bed_max_y + margin
            or pos[0] < s.bed_min_x - margin
            or pos[1] < s.bed_min_y - margin
        ):
            raise self.gcode.error(
                E.outside_bed(s.bed_min_x, s.bed_max_x, s.bed_min_y, s.bed_max_y)
            )

    # --- public attach/detach (used by cmds and wrappers) ---

    def attach_probe(self, restore=False, require_fresh=False):
        self.lifecycle.attach_probe(restore=restore, require_fresh=require_fresh)

    def detach_probe(self, restore=False, force=False):
        self.lifecycle.detach_probe(restore=restore, force=force)

    cmd_ATTACH_PROBE_help = "Attach the Klicky probe from the dock"

    def cmd_ATTACH_PROBE(self, gcmd):
        self.attach_probe(restore=bool(gcmd.get_int("RESTORE", 0)))

    cmd_DETACH_PROBE_help = "Detach/dock the Klicky probe"

    def cmd_DETACH_PROBE(self, gcmd):
        self.detach_probe(restore=bool(gcmd.get_int("RESTORE", 0)))

    cmd_LOCK_PROBE_help = "Lock probe so DETACH_PROBE is ignored until unlock"

    def cmd_LOCK_PROBE(self, gcmd):
        self.state.lock()
        self._log("probe locked")

    cmd_UNLOCK_PROBE_help = "Unlock probe attach state"

    def cmd_UNLOCK_PROBE(self, gcmd):
        self.state.unlock()
        self._log("probe unlocked")

    cmd_GET_PROBE_STATUS_help = "Report Klicky probe attach/lock state"

    def cmd_GET_PROBE_STATUS(self, gcmd):
        try:
            triggered = self._query_probe_triggered()
            self.state.set_from_query(triggered)
        except Exception:
            gcmd.respond_info(E.probe_query_stale_warning())
        gcmd.respond_info(
            E.probe_status_report(
                self.state.attach_state.value,
                self.state.locked,
                self._session.session_depth,
                self._session.hold_depth,
            )
        )

    cmd_ENSURE_PROBE_DOCKED_help = (
        "Query probe and dock if attached (print-start / recovery; #230)"
    )

    def cmd_ENSURE_PROBE_DOCKED(self, gcmd):
        self.lifecycle.ensure_probe_docked(gcmd)

    def cmd_G28(self, gcmd):
        params = gcmd.get_command_parameters()
        raw = {}
        for axis in ("X", "Y", "Z"):
            if axis in params or axis.lower() in params:
                raw[axis] = True
        for k, v in params.items():
            if str(k).upper() in ("PROBE_LOCK", "DOCK"):
                raw[k] = v
        req = HomingRequest.from_params(raw)
        self.homing.execute(req)

    def get_status(self, eventtime):
        return {
            "probe_state": self.state.attach_state.value,
            "locked": self.state.locked,
            "session_depth": self._session.session_depth,
            "hold_depth": self._session.hold_depth,
        }


def load_config(config):
    return KlickyProbe(config)
