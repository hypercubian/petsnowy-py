"""CLI for quick PetSnowy device commands.

Usage:
    python -m petsnowy status                           Litterbox status (default)
    python -m petsnowy clean                            Litterbox clean cycle
    python -m petsnowy monitor                          Litterbox event stream

    python -m petsnowy --device fountain status          Fountain status
    python -m petsnowy --device fountain set-work-mode night
    python -m petsnowy --device fountain reset-filter

    python -m petsnowy --device purifier status          Purifier status
    python -m petsnowy --device purifier set-mode auto
    python -m petsnowy --device purifier set-speed 3

    python -m petsnowy --device feeder status             Feeder status
    python -m petsnowy --device feeder feed 5

Credentials are read from devices.json (tinytuya wizard output) or env vars:
    PETSNOWY_DEVICE_ID, PETSNOWY_ADDRESS, PETSNOWY_LOCAL_KEY
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, cast

from .base import BasePetDevice
from .const import DPS, Fault, Notification
from .device import PetSnowy
from .feeder import Feeder
from .fountain import Fountain
from .purifier import Purifier, PurifierFault

# -- Device registry -----------------------------------------------------------

DEVICE_REGISTRY: dict[str, dict[str, Any]] = {
    "litterbox": {
        "class": PetSnowy,
        "product_ids": {"bdfimkssp9ews36b"},
        "categories": {"msp"},
        "default_version": 3.4,
    },
    "fountain": {
        "class": Fountain,
        "product_ids": {"6atwtbtrc6xszdem"},
        "categories": {"cwysj"},
        "default_version": 3.3,
    },
    "purifier": {
        "class": Purifier,
        "product_ids": {"tlqmw4ej2ym37kcv"},
        "categories": {"kj"},
        "default_version": 3.4,
    },
    "feeder": {
        "class": Feeder,
        "product_ids": {"xamrfcvbiz64but3"},
        "categories": {"cwwsq"},
        "default_version": 3.3,
    },
}


def _device_type_from_json(dev_entry: dict[str, Any]) -> str | None:
    """Match a devices.json entry to a device type name."""
    pid = dev_entry.get("product_id", "")
    cat = dev_entry.get("category", "")
    for name, info in DEVICE_REGISTRY.items():
        if pid in info["product_ids"] or cat in info["categories"]:
            return name
    return None


# -- Credential resolution -----------------------------------------------------


def _find_credentials(
    device_type: str = "litterbox",
) -> tuple[str, str, str, float, str]:
    """Resolve device credentials, returning (id, address, key, version, type).

    Checks env vars first, then searches devices.json.
    """
    device_id = os.environ.get("PETSNOWY_DEVICE_ID")
    address = os.environ.get("PETSNOWY_ADDRESS")
    local_key = os.environ.get("PETSNOWY_LOCAL_KEY")
    version = float(os.environ.get("PETSNOWY_VERSION", "0"))

    if device_id and address and local_key:
        if version == 0:
            version = DEVICE_REGISTRY[device_type]["default_version"]
        return device_id, address, local_key, version, device_type

    # Search for devices.json
    candidates = [
        Path.cwd() / "devices.json",
        Path(__file__).resolve().parent.parent.parent / "devices.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        with open(path) as f:
            devices = json.load(f)
        for dev in devices:
            matched_type = _device_type_from_json(dev)
            if matched_type == device_type:
                return (
                    dev["id"],
                    dev.get("ip", ""),
                    dev["key"],
                    float(
                        dev.get(
                            "version", DEVICE_REGISTRY[device_type]["default_version"]
                        )
                    ),
                    device_type,
                )

    print(f"Error: No {device_type} credentials found.", file=sys.stderr)
    print(
        "Set PETSNOWY_DEVICE_ID, PETSNOWY_ADDRESS, PETSNOWY_LOCAL_KEY env vars",
        file=sys.stderr,
    )
    print(
        "or run 'python -m tinytuya wizard' to generate devices.json", file=sys.stderr
    )
    sys.exit(1)


def _connect(device_type: str = "litterbox") -> BasePetDevice:
    device_id, address, local_key, version, dtype = _find_credentials(device_type)
    cls = DEVICE_REGISTRY[dtype]["class"]
    return cls(device_id, address, local_key, version=version)


def _parse_bool(value: str) -> bool:
    if value.lower() in ("on", "true", "1", "yes"):
        return True
    if value.lower() in ("off", "false", "0", "no"):
        return False
    print(f"Error: expected on/off, got '{value}'", file=sys.stderr)
    sys.exit(1)


# -- Litterbox commands --------------------------------------------------------


async def cmd_litterbox_status(device_type: str) -> None:
    async with _connect(device_type) as dev:
        dev = cast(PetSnowy, dev)
        state = await dev.get_state()
        print("=== PetSnowy Snow+ Status ===")
        print()
        print(f"  Status:             {state.status.value}")
        print(f"  Auto-clean:         {'ON' if state.auto_clean else 'OFF'}")
        print(f"  Clean delay:        {state.delay_clean_time} min")
        print(f"  Cat weight:         {state.cat_weight} g")
        print(f"  Excretions today:   {state.excretion_count_today}")
        print(f"  Excretion time:     {state.excretion_duration_today} s")
        print(f"  Sleep mode:         {'ON' if state.sleep_mode else 'OFF'}")
        print(f"  Light:              {'ON' if state.light else 'OFF'}")
        print(f"  Child lock:         {'LOCKED' if state.child_locked else 'UNLOCKED'}")
        print(f"  Auto-deodorize:     {'ON' if state.auto_deodorize else 'OFF'}")
        print(f"  Scheduled deodorize: {'ON' if state.scheduled_deodorize else 'OFF'}")
        print(f"  Scheduled clean:    {'ON' if state.scheduled_clean else 'OFF'}")
        print(f"  Filter remaining:   {state.filter_days_remaining} days")

        if state.notifications:
            print("\n  Notifications:")
            for notif in Notification:
                if notif and notif in state.notifications:
                    print(f"    - {notif.name}")

        if state.faults:
            print("\n  FAULTS:")
            for fault in Fault:
                if fault and fault in state.faults:
                    print(f"    - {fault.name}")
        else:
            print("\n  Faults:             None")


async def cmd_button(device_type: str, name: str, method: str) -> None:
    async with _connect(device_type) as dev:
        await getattr(dev, method)()
        print(f"{name} triggered.")


async def cmd_setting(device_type: str, name: str, method: str, value: object) -> None:
    async with _connect(device_type) as dev:
        await getattr(dev, method)(value)
        print(f"{name} set to {value}.")


async def cmd_monitor(device_type: str) -> None:
    DPS_NAMES = {
        str(DPS.SWITCH): "switch",
        str(DPS.AUTO_CLEAN): "auto_clean",
        str(DPS.DELAY_CLEAN_TIME): "delay_clean_time",
        str(DPS.CAT_WEIGHT): "cat_weight",
        str(DPS.EXCRETION_TIMES_DAY): "excretion_count",
        str(DPS.EXCRETION_TIME_DAY): "excretion_time",
        str(DPS.MANUAL_CLEAN): "manual_clean",
        str(DPS.SLEEP): "sleep_mode",
        str(DPS.LIGHT): "light",
        str(DPS.DEODORIZATION): "deodorize",
        str(DPS.NOTIFICATION): "notification",
        str(DPS.FAULT): "fault",
        str(DPS.STATUS): "status",
        str(DPS.FILTER_DAYS): "filter_days",
        str(DPS.LOCK): "lock (inverted)",
        str(DPS.AUTO_DEODORIZE): "auto_deodorize",
        str(DPS.EMPTY): "empty_litter",
        str(DPS.PAUSE): "pause",
        str(DPS.CONTINUE): "resume",
    }

    async with _connect(device_type) as dev:
        print(f"Connected to {device_type}.")
        print("Monitoring for events (Ctrl+C to stop)...\n")

        count = 0
        async for update in dev.monitor():
            count += 1
            print(f"--- Update #{count} ---")
            for key, value in update.items():
                name = DPS_NAMES.get(key, f"dps_{key}")
                if key == str(DPS.NOTIFICATION) and isinstance(value, int):
                    notif_flags = Notification(value)
                    active = [n.name for n in Notification if n and n in notif_flags]
                    print(f"  {name}: {active or 'none'}")
                elif key == str(DPS.FAULT) and isinstance(value, int):
                    fault_flags = Fault(value)
                    active = [ft.name for ft in Fault if ft and ft in fault_flags]
                    print(f"  {name}: {active or 'none'}")
                else:
                    print(f"  {name}: {value}")
            print()


# -- Fountain commands ---------------------------------------------------------


async def cmd_fountain_status(device_type: str) -> None:
    async with _connect(device_type) as dev:
        dev = cast(Fountain, dev)
        state = await dev.get_state()
        print("=== PetSnowy Water Fountain Status ===")
        print()
        print(f"  Power:              {'ON' if state.switch else 'OFF'}")
        print(f"  Work mode:          {state.work_mode.value}")
        print(f"  Filter remaining:   {state.filter_days} days")
        print(f"  Pump clean in:      {state.pump_time} days")
        print(f"  Filter reminder:    {state.filter_life} days")


# -- Purifier commands ---------------------------------------------------------


async def cmd_purifier_status(device_type: str) -> None:
    async with _connect(device_type) as dev:
        dev = cast(Purifier, dev)
        state = await dev.get_state()
        print("=== PetSnowy Air Purifier Status ===")
        print()
        print(f"  Power:              {'ON' if state.switch else 'OFF'}")
        print(f"  Mode:               {state.mode.value}")
        print(f"  Fan speed:          {state.speed}")
        print(f"  Ionizer:            {'ON' if state.anion else 'OFF'}")
        print(f"  TVOC:               {state.tvoc} ug/m3")
        print(f"  Filter remaining:   {state.filter_days} days")
        print(f"  Countdown:          {state.countdown_set}")
        print(f"  Countdown left:     {state.countdown_left} min")

        if state.faults:
            print("\n  FAULTS:")
            for flag in PurifierFault:
                if flag and flag in state.faults:
                    print(f"    - {flag.name}")
        else:
            print("\n  Faults:             None")


# -- Feeder commands -----------------------------------------------------------


async def cmd_feeder_status(device_type: str) -> None:
    async with _connect(device_type) as dev:
        dev = cast(Feeder, dev)
        state = await dev.get_state()
        print("=== PetSnowy Pet Feeder Status ===")
        print()
        print(f"  Food level:         {state.food_status.value}")


# -- Command dispatch ----------------------------------------------------------


async def _cmd_power(device_type: str, name: str, method: str) -> None:
    """Power on/off helper for devices with turn_on/turn_off (no args)."""
    async with _connect(device_type) as dev:
        await getattr(dev, method)()
        print(f"{name}.")


def _build_litterbox_commands() -> dict[str, Any]:
    return {
        "status": lambda args, dt: cmd_litterbox_status(dt),
        "clean": lambda args, dt: cmd_button(dt, "Clean cycle", "clean"),
        "deodorize": lambda args, dt: cmd_button(dt, "Deodorization", "deodorize"),
        "pause": lambda args, dt: cmd_button(dt, "Pause", "pause"),
        "resume": lambda args, dt: cmd_button(dt, "Resume", "resume"),
        "empty": lambda args, dt: cmd_button(dt, "Empty litter", "empty_litter"),
        "cancel-empty": lambda args, dt: cmd_button(dt, "Cancel empty", "cancel_empty"),
        "reset-filter": lambda args, dt: cmd_button(dt, "Filter reset", "reset_filter"),
        "calibrate-weight": lambda args, dt: cmd_button(
            dt, "Weight calibration", "calibrate_weight"
        ),
        "light": lambda args, dt: cmd_setting(
            dt, "Light", "set_light", _parse_bool(args[0])
        ),
        "auto-clean": lambda args, dt: cmd_setting(
            dt, "Auto-clean", "set_auto_clean", _parse_bool(args[0])
        ),
        "clean-delay": lambda args, dt: cmd_setting(
            dt, "Clean delay", "set_clean_delay", int(args[0])
        ),
        "sleep": lambda args, dt: cmd_setting(
            dt, "Sleep mode", "set_sleep_mode", _parse_bool(args[0])
        ),
        "child-lock": lambda args, dt: cmd_setting(
            dt, "Child lock", "set_child_lock", _parse_bool(args[0])
        ),
        "auto-deodorize": lambda args, dt: cmd_setting(
            dt, "Auto-deodorize", "set_auto_deodorize", _parse_bool(args[0])
        ),
        "scheduled-deodorize": lambda args, dt: cmd_setting(
            dt, "Scheduled deodorize", "set_scheduled_deodorize", _parse_bool(args[0])
        ),
        "scheduled-clean": lambda args, dt: cmd_setting(
            dt, "Scheduled clean", "set_scheduled_clean", _parse_bool(args[0])
        ),
        "monitor": lambda args, dt: cmd_monitor(dt),
    }


def _build_fountain_commands() -> dict[str, Any]:
    return {
        "status": lambda args, dt: cmd_fountain_status(dt),
        "on": lambda args, dt: _cmd_power(dt, "Powered on", "turn_on"),
        "off": lambda args, dt: _cmd_power(dt, "Powered off", "turn_off"),
        "set-work-mode": lambda args, dt: cmd_setting(
            dt, "Work mode", "set_work_mode", args[0]
        ),
        "reset-filter": lambda args, dt: cmd_button(dt, "Filter reset", "reset_filter"),
        "reset-pump": lambda args, dt: cmd_button(dt, "Pump reset", "reset_pump"),
        "set-filter-reminder": lambda args, dt: cmd_setting(
            dt, "Filter reminder", "set_filter_reminder", int(args[0])
        ),
        "monitor": lambda args, dt: cmd_monitor(dt),
    }


def _build_purifier_commands() -> dict[str, Any]:
    return {
        "status": lambda args, dt: cmd_purifier_status(dt),
        "on": lambda args, dt: _cmd_power(dt, "Powered on", "turn_on"),
        "off": lambda args, dt: _cmd_power(dt, "Powered off", "turn_off"),
        "set-mode": lambda args, dt: cmd_setting(dt, "Mode", "set_mode", args[0]),
        "set-speed": lambda args, dt: cmd_setting(
            dt, "Fan speed", "set_speed", args[0]
        ),
        "anion": lambda args, dt: cmd_setting(
            dt, "Ionizer", "set_anion", _parse_bool(args[0])
        ),
        "set-countdown": lambda args, dt: cmd_setting(
            dt, "Countdown", "set_countdown", args[0]
        ),
        "monitor": lambda args, dt: cmd_monitor(dt),
    }


def _build_feeder_commands() -> dict[str, Any]:
    return {
        "status": lambda args, dt: cmd_feeder_status(dt),
        "feed": lambda args, dt: cmd_setting(dt, "Feed", "feed", int(args[0])),
        "quick-feed": lambda args, dt: cmd_button(dt, "Quick feed", "quick_feed"),
        "monitor": lambda args, dt: cmd_monitor(dt),
    }


DEVICE_COMMANDS: dict[str, dict[str, Any]] = {
    "litterbox": _build_litterbox_commands(),
    "fountain": _build_fountain_commands(),
    "purifier": _build_purifier_commands(),
    "feeder": _build_feeder_commands(),
}


# -- Help text -----------------------------------------------------------------

HELP_TEXTS: dict[str, str] = {
    "litterbox": """\
Litterbox commands:
  status                  Show device state
  clean                   Start manual clean cycle
  deodorize               Start deodorization
  pause                   Pause current operation
  resume                  Resume paused operation
  empty                   Start emptying litter
  cancel-empty            Cancel litter emptying
  reset-filter            Reset filter life counter
  calibrate-weight        Calibrate weight sensor
  light on|off            Toggle indicator light
  auto-clean on|off       Toggle automatic cleaning
  clean-delay <minutes>   Set auto-clean delay (2-60, even)
  sleep on|off            Toggle sleep mode
  child-lock on|off       Toggle child/pet lock
  auto-deodorize on|off   Toggle auto deodorization
  scheduled-deodorize on|off  Toggle scheduled deodorization
  scheduled-clean on|off  Toggle scheduled cleaning
  monitor                 Stream live events""",
    "fountain": """\
Fountain commands:
  status                        Show fountain state
  on / off                      Power on/off
  set-work-mode normal|night    Set operating mode
  reset-filter                  Reset filter counter
  reset-pump                    Reset pump counter
  set-filter-reminder <days>    Set filter reminder (0-90)
  monitor                       Stream live events""",
    "purifier": """\
Purifier commands:
  status                                Show purifier state
  on / off                              Power on/off
  set-mode auto|sleep                   Set operating mode
  set-speed 1-6                         Set fan speed
  anion on|off                          Toggle ionizer
  set-countdown cancel|1h|2h|3h|4h|5h   Set auto-off timer
  monitor                               Stream live events""",
    "feeder": """\
Feeder commands:
  status              Show feeder state
  feed <portions>     Dispense food (1-20 cups)
  quick-feed          Dispense 1 portion
  monitor             Stream live events""",
}


def _print_help(device_type: str | None = None) -> None:
    print("Usage: python -m petsnowy [--device <type>] <command> [args]")
    print()
    print("Device types: litterbox (default), fountain, purifier, feeder")
    print()
    if device_type and device_type in HELP_TEXTS:
        print(HELP_TEXTS[device_type])
    else:
        for _dt, text in HELP_TEXTS.items():
            print(text)
            print()


def main() -> None:
    argv = sys.argv[1:]

    # Parse --device flag
    device_type = "litterbox"
    if len(argv) >= 2 and argv[0] == "--device":
        device_type = argv[1].lower()
        argv = argv[2:]
        if device_type not in DEVICE_COMMANDS:
            print(f"Unknown device type: {device_type}", file=sys.stderr)
            print(f"Valid types: {', '.join(DEVICE_COMMANDS)}", file=sys.stderr)
            sys.exit(1)

    if not argv or argv[0] in ("-h", "--help", "help"):
        _print_help(device_type)
        return

    cmd = argv[0]
    args = argv[1:]
    commands = DEVICE_COMMANDS[device_type]

    if cmd not in commands:
        print(f"Unknown {device_type} command: {cmd}", file=sys.stderr)
        print(
            f"Run 'python -m petsnowy --device {device_type} help' for usage",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        asyncio.run(commands[cmd](args, device_type))
    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
