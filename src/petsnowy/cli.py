"""CLI for quick PetSnowy commands.

Usage:
    python -m petsnowy status
    python -m petsnowy clean
    python -m petsnowy deodorize
    python -m petsnowy pause
    python -m petsnowy resume
    python -m petsnowy empty
    python -m petsnowy cancel-empty
    python -m petsnowy reset-filter
    python -m petsnowy calibrate-weight
    python -m petsnowy light on|off
    python -m petsnowy auto-clean on|off
    python -m petsnowy clean-delay <minutes>
    python -m petsnowy sleep on|off
    python -m petsnowy child-lock on|off
    python -m petsnowy auto-deodorize on|off
    python -m petsnowy monitor

Credentials are read from devices.json (tinytuya wizard output) or env vars:
    PETSNOWY_DEVICE_ID, PETSNOWY_ADDRESS, PETSNOWY_LOCAL_KEY
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from .const import DPS, Fault, Notification
from .device import PetSnowy


def _find_credentials() -> tuple[str, str, str, float]:
    """Resolve device credentials from env vars or devices.json."""
    device_id = os.environ.get("PETSNOWY_DEVICE_ID")
    address = os.environ.get("PETSNOWY_ADDRESS")
    local_key = os.environ.get("PETSNOWY_LOCAL_KEY")
    version = float(os.environ.get("PETSNOWY_VERSION", "3.4"))

    if device_id and address and local_key:
        return device_id, address, local_key, version

    # Search for devices.json
    candidates = [
        Path.cwd() / "devices.json",
        Path(__file__).resolve().parent.parent.parent / "devices.json",
    ]
    for path in candidates:
        if path.exists():
            with open(path) as f:
                devices = json.load(f)
            for dev in devices:
                if dev.get("product_id") == "bdfimkssp9ews36b" or dev.get("category") == "msp":
                    name = dev.get("name", "").lower()
                    if "litter" in name or "clean" in name or dev.get("product_id") == "bdfimkssp9ews36b":
                        return (
                            dev["id"],
                            dev.get("ip", ""),
                            dev["key"],
                            float(dev.get("version", "3.4")),
                        )

    print("Error: No credentials found.", file=sys.stderr)
    print("Set PETSNOWY_DEVICE_ID, PETSNOWY_ADDRESS, PETSNOWY_LOCAL_KEY env vars", file=sys.stderr)
    print("or run 'python -m tinytuya wizard' to generate devices.json", file=sys.stderr)
    sys.exit(1)


def _connect() -> PetSnowy:
    device_id, address, local_key, version = _find_credentials()
    return PetSnowy(device_id, address, local_key, version=version)


def _parse_bool(value: str) -> bool:
    if value.lower() in ("on", "true", "1", "yes"):
        return True
    if value.lower() in ("off", "false", "0", "no"):
        return False
    print(f"Error: expected on/off, got '{value}'", file=sys.stderr)
    sys.exit(1)


async def cmd_status() -> None:
    async with _connect() as dev:
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
        print(f"  Filter remaining:   {state.filter_days_remaining} days")

        if state.notifications:
            print(f"\n  Notifications:")
            for flag in Notification:
                if flag and flag in state.notifications:
                    print(f"    - {flag.name}")

        if state.faults:
            print(f"\n  FAULTS:")
            for flag in Fault:
                if flag and flag in state.faults:
                    print(f"    - {flag.name}")
        else:
            print(f"\n  Faults:             None")


async def cmd_button(name: str, method: str) -> None:
    async with _connect() as dev:
        await getattr(dev, method)()
        print(f"{name} triggered.")
        await asyncio.sleep(1)
        state = await dev.get_state()
        print(f"Status: {state.status.value}")


async def cmd_setting(name: str, method: str, value: object) -> None:
    async with _connect() as dev:
        await getattr(dev, method)(value)
        print(f"{name} set to {value}.")


async def cmd_monitor() -> None:
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

    async with _connect() as dev:
        state = await dev.get_state()
        print(f"Connected. Status: {state.status.value}")
        print("Monitoring for events (Ctrl+C to stop)...\n")

        count = 0
        async for update in dev.monitor():
            count += 1
            print(f"--- Update #{count} ---")
            for key, value in update.items():
                name = DPS_NAMES.get(key, f"dps_{key}")
                if key == str(DPS.NOTIFICATION) and isinstance(value, int):
                    flags = Notification(value)
                    active = [f.name for f in Notification if f and f in flags]
                    print(f"  {name}: {active or 'none'}")
                elif key == str(DPS.FAULT) and isinstance(value, int):
                    flags = Fault(value)
                    active = [f.name for f in Fault if f and f in flags]
                    print(f"  {name}: {active or 'none'}")
                else:
                    print(f"  {name}: {value}")
            print()


COMMANDS = {
    "status": lambda args: cmd_status(),
    "clean": lambda args: cmd_button("Clean cycle", "clean"),
    "deodorize": lambda args: cmd_button("Deodorization", "deodorize"),
    "pause": lambda args: cmd_button("Pause", "pause"),
    "resume": lambda args: cmd_button("Resume", "resume"),
    "empty": lambda args: cmd_button("Empty litter", "empty_litter"),
    "cancel-empty": lambda args: cmd_button("Cancel empty", "cancel_empty"),
    "reset-filter": lambda args: cmd_button("Filter reset", "reset_filter"),
    "calibrate-weight": lambda args: cmd_button("Weight calibration", "calibrate_weight"),
    "light": lambda args: cmd_setting("Light", "set_light", _parse_bool(args[0])),
    "auto-clean": lambda args: cmd_setting("Auto-clean", "set_auto_clean", _parse_bool(args[0])),
    "clean-delay": lambda args: cmd_setting("Clean delay", "set_clean_delay", int(args[0])),
    "sleep": lambda args: cmd_setting("Sleep mode", "set_sleep_mode", _parse_bool(args[0])),
    "child-lock": lambda args: cmd_setting("Child lock", "set_child_lock", _parse_bool(args[0])),
    "auto-deodorize": lambda args: cmd_setting("Auto-deodorize", "set_auto_deodorize", _parse_bool(args[0])),
    "monitor": lambda args: cmd_monitor(),
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print("Usage: python -m petsnowy <command> [args]")
        print()
        print("Commands:")
        print("  status                  Show device state")
        print("  clean                   Start manual clean cycle")
        print("  deodorize               Start deodorization")
        print("  pause                   Pause current operation")
        print("  resume                  Resume paused operation")
        print("  empty                   Start emptying litter")
        print("  cancel-empty            Cancel litter emptying")
        print("  reset-filter            Reset filter life counter")
        print("  calibrate-weight        Calibrate weight sensor")
        print("  light on|off            Toggle indicator light")
        print("  auto-clean on|off       Toggle automatic cleaning")
        print("  clean-delay <minutes>   Set auto-clean delay (2-60, even)")
        print("  sleep on|off            Toggle sleep mode")
        print("  child-lock on|off       Toggle child/pet lock")
        print("  auto-deodorize on|off   Toggle auto deodorization")
        print("  monitor                 Stream live events")
        return

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd not in COMMANDS:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print(f"Run 'python -m petsnowy help' for usage", file=sys.stderr)
        sys.exit(1)

    try:
        asyncio.run(COMMANDS[cmd](args))
    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
