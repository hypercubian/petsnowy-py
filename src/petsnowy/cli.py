"""CLI for quick PetSnowy device commands.

Usage:
    petsnowy status                           Litterbox status (default device)
    petsnowy clean                            Litterbox clean cycle
    petsnowy monitor                          Litterbox event stream

    petsnowy --device fountain status         Fountain status
    petsnowy --device fountain set-work-mode night
    petsnowy --device purifier set-speed 3
    petsnowy --device feeder feed 5

Credentials are read from env vars (PETSNOWY_DEVICE_ID, PETSNOWY_ADDRESS,
PETSNOWY_LOCAL_KEY, optional PETSNOWY_VERSION) or devices.json (tinytuya wizard
output). Exit codes: 0 success, 1 device or connection error, 2 usage error.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import cast

from .base import BasePetDevice
from .device import PetSnowy
from .exceptions import PetSnowyError
from .feeder import Feeder
from .fountain import Fountain, WorkMode
from .purifier import Purifier, PurifierMode
from .registry import DEVICE_SPECS, create_device, resolve_credentials
from .utils import feeder as feeder_utils
from .utils import fountain as fountain_utils
from .utils import litterbox as litterbox_utils
from .utils import purifier as purifier_utils
from .utils.common import format_update

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2

DEFAULT_DEVICE = "litterbox"

Action = Callable[[BasePetDevice, str], Awaitable[None]]


class UsageError(ValueError):
    """The command line is malformed; reported with exit code 2."""


# -- Argument parsers -------------------------------------------------------------


def parse_bool(value: str) -> bool:
    lowered = value.lower()
    if lowered in ("on", "true", "1", "yes"):
        return True
    if lowered in ("off", "false", "0", "no"):
        return False
    raise UsageError(f"expected on/off, got '{value}'")


def parse_int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        raise UsageError(f"expected a whole number, got '{value}'") from None


def choice(*allowed: str) -> Callable[[str], str]:
    """Return a parser accepting only ``allowed`` (case-insensitive)."""

    def _parse(value: str) -> str:
        if value.lower() not in allowed:
            raise UsageError(f"expected one of {'|'.join(allowed)}, got '{value}'")
        return value.lower()

    return _parse


# -- Command table ----------------------------------------------------------------


@dataclass(frozen=True)
class Command:
    """One CLI command: a device method call, or a custom ``action``.

    Exactly one of ``method`` and ``action`` is set. With ``parse`` the command takes a
    single argument, converted before connecting so bad input never reaches a device.
    """

    summary: str
    method: str | None = None
    done: str = ""
    parse: Callable[[str], object] | None = None
    metavar: str = ""
    action: Action | None = None

    @property
    def nargs(self) -> int:
        return 1 if self.parse is not None else 0


def _button(method: str, label: str, summary: str) -> Command:
    return Command(summary, method=method, done=f"{label} triggered.")


def _setting(
    method: str, label: str, summary: str, parse: Callable[[str], object], metavar: str
) -> Command:
    return Command(summary, method=method, done=label, parse=parse, metavar=metavar)


def _toggle(method: str, label: str, summary: str) -> Command:
    return _setting(method, label, summary, parse_bool, "on|off")


async def _litterbox_status(dev: BasePetDevice, _device_type: str) -> None:
    state = await cast(PetSnowy, dev).get_state()
    print(litterbox_utils.format_status(state))


async def _fountain_status(dev: BasePetDevice, _device_type: str) -> None:
    state = await cast(Fountain, dev).get_state()
    print(fountain_utils.format_status(state))


async def _purifier_status(dev: BasePetDevice, _device_type: str) -> None:
    state = await cast(Purifier, dev).get_state()
    print(purifier_utils.format_status(state))


async def _feeder_status(dev: BasePetDevice, _device_type: str) -> None:
    state = await cast(Feeder, dev).get_state()
    print(feeder_utils.format_status(state))


async def _monitor(dev: BasePetDevice, device_type: str) -> None:
    print(f"Connected to {device_type}.")
    print("Monitoring for events (Ctrl+C to stop)...\n")
    dps_cls = DEVICE_SPECS[device_type].dps
    count = 0
    async for update in dev.monitor():
        count += 1
        print(f"--- Update #{count} ---")
        print("\n".join(format_update(update, dps_cls)))
        print()


_MONITOR = Command("Stream live events", action=_monitor)
_POWER_ON = Command("Power on", method="turn_on", done="Powered on.")
_POWER_OFF = Command("Power off", method="turn_off", done="Powered off.")

LITTERBOX_COMMANDS: dict[str, Command] = {
    "status": Command("Show device state", action=_litterbox_status),
    "clean": _button("clean", "Clean cycle", "Start manual clean cycle"),
    "deodorize": _button("deodorize", "Deodorization", "Start deodorization"),
    "pause": _button("pause", "Pause", "Pause current operation"),
    "resume": _button("resume", "Resume", "Resume paused operation"),
    "empty": _button("empty_litter", "Empty litter", "Start emptying litter"),
    "cancel-empty": _button("cancel_empty", "Cancel empty", "Cancel litter emptying"),
    "reset-filter": _button("reset_filter", "Filter reset", "Reset filter life"),
    "calibrate-weight": _button(
        "calibrate_weight", "Weight calibration", "Calibrate weight sensor"
    ),
    "light": _toggle("set_light", "Light", "Toggle indicator light"),
    "auto-clean": _toggle("set_auto_clean", "Auto-clean", "Toggle automatic cleaning"),
    "clean-delay": _setting(
        "set_clean_delay",
        "Clean delay",
        "Set auto-clean delay (2-60, even)",
        parse_int,
        "<minutes>",
    ),
    "sleep": _toggle("set_sleep_mode", "Sleep mode", "Toggle sleep mode"),
    "child-lock": _toggle("set_child_lock", "Child lock", "Toggle child/pet lock"),
    "auto-deodorize": _toggle(
        "set_auto_deodorize", "Auto-deodorize", "Toggle auto deodorization"
    ),
    "scheduled-deodorize": _toggle(
        "set_scheduled_deodorize",
        "Scheduled deodorize",
        "Toggle scheduled deodorization",
    ),
    "scheduled-clean": _toggle(
        "set_scheduled_clean", "Scheduled clean", "Toggle scheduled cleaning"
    ),
    "monitor": _MONITOR,
}

FOUNTAIN_COMMANDS: dict[str, Command] = {
    "status": Command("Show fountain state", action=_fountain_status),
    "on": _POWER_ON,
    "off": _POWER_OFF,
    "set-work-mode": _setting(
        "set_work_mode",
        "Work mode",
        "Set operating mode",
        choice(*(m.value for m in WorkMode)),
        "|".join(m.value for m in WorkMode),
    ),
    "reset-filter": _button("reset_filter", "Filter reset", "Reset filter counter"),
    "reset-pump": _button("reset_pump", "Pump reset", "Reset pump counter"),
    "set-filter-reminder": _setting(
        "set_filter_reminder",
        "Filter reminder",
        "Set filter reminder (0-90)",
        parse_int,
        "<days>",
    ),
    "light": _toggle("set_light", "Light", "Toggle indicator light"),
    "monitor": _MONITOR,
}

_COUNTDOWNS = ("cancel", "1h", "2h", "3h", "4h", "5h")
_SPEEDS = ("1", "2", "3", "4", "5", "6")

PURIFIER_COMMANDS: dict[str, Command] = {
    "status": Command("Show purifier state", action=_purifier_status),
    "on": _POWER_ON,
    "off": _POWER_OFF,
    "set-mode": _setting(
        "set_mode",
        "Mode",
        "Set operating mode",
        choice(*(m.value for m in PurifierMode)),
        "|".join(m.value for m in PurifierMode),
    ),
    "set-speed": _setting(
        "set_speed", "Fan speed", "Set fan speed", choice(*_SPEEDS), "1-6"
    ),
    "anion": _toggle("set_anion", "Ionizer", "Toggle ionizer"),
    "set-countdown": _setting(
        "set_countdown",
        "Countdown",
        "Set auto-off timer",
        choice(*_COUNTDOWNS),
        "|".join(_COUNTDOWNS),
    ),
    "monitor": _MONITOR,
}

FEEDER_COMMANDS: dict[str, Command] = {
    "status": Command("Show feeder state", action=_feeder_status),
    "feed": _setting(
        "feed", "Feed", "Dispense food (1-20 portions)", parse_int, "<portions>"
    ),
    "quick-feed": _button("quick_feed", "Quick feed", "Dispense 1 portion"),
    "monitor": _MONITOR,
}

DEVICE_COMMANDS: dict[str, dict[str, Command]] = {
    "litterbox": LITTERBOX_COMMANDS,
    "fountain": FOUNTAIN_COMMANDS,
    "purifier": PURIFIER_COMMANDS,
    "feeder": FEEDER_COMMANDS,
}


# -- Help -------------------------------------------------------------------------


def format_device_help(device_type: str) -> str:
    rows = [
        (f"{name} {cmd.metavar}".rstrip(), cmd.summary)
        for name, cmd in DEVICE_COMMANDS[device_type].items()
    ]
    width = max(len(usage) for usage, _ in rows) + 2
    lines = [f"{device_type.capitalize()} commands:"]
    lines.extend(f"  {usage:<{width}}{summary}" for usage, summary in rows)
    return "\n".join(lines)


def format_help(device_type: str | None = None) -> str:
    """Return CLI help for one device type, or for every type when None."""
    header = [
        "Usage: petsnowy [--device <type>] <command> [args]",
        "",
        f"Device types: {', '.join(DEVICE_COMMANDS)} (default: {DEFAULT_DEVICE})",
        "",
    ]
    types = [device_type] if device_type else list(DEVICE_COMMANDS)
    return "\n".join(header) + "\n" + "\n\n".join(map(format_device_help, types))


# -- Parse, run, report -----------------------------------------------------------


@dataclass(frozen=True)
class Invocation:
    """A parsed command line.

    ``command`` is None when help was requested.
    """

    device_type: str
    explicit_device: bool
    command: str | None
    value: object = None


def parse_args(argv: Sequence[str]) -> Invocation:
    """Parse ``[--device TYPE] COMMAND [ARG]`` into an Invocation.

    Raises:
        UsageError: Unknown device or command, or a missing or invalid argument.
    """
    args = list(argv)
    device_type, explicit = DEFAULT_DEVICE, False
    if args and (args[0] == "--device" or args[0].startswith("--device=")):
        flag = args.pop(0)
        if "=" in flag:
            device_type = flag.split("=", 1)[1]
        elif args:
            device_type = args.pop(0)
        else:
            raise UsageError("--device needs a value")
        device_type, explicit = device_type.lower(), True
        if device_type not in DEVICE_COMMANDS:
            raise UsageError(
                f"Unknown device type: {device_type}. "
                f"Valid types: {', '.join(DEVICE_COMMANDS)}"
            )

    if not args or args[0] in ("-h", "--help", "help"):
        return Invocation(device_type, explicit, None)

    name, rest = args[0], args[1:]
    command = DEVICE_COMMANDS[device_type].get(name)
    if command is None:
        raise UsageError(
            f"Unknown {device_type} command: {name}. "
            f"Run 'petsnowy --device {device_type} help' for usage"
        )
    if len(rest) != command.nargs:
        usage = f"{name} {command.metavar}".rstrip()
        raise UsageError(f"Usage: petsnowy --device {device_type} {usage}")
    value = command.parse(rest[0]) if command.parse is not None else None
    return Invocation(device_type, explicit, name, value)


async def run(invocation: Invocation) -> None:
    """Connect to the device and execute a parsed (non-help) invocation."""
    if invocation.command is None:
        raise UsageError("no command given")
    command = DEVICE_COMMANDS[invocation.device_type][invocation.command]
    creds = resolve_credentials(invocation.device_type)
    async with create_device(invocation.device_type, creds) as dev:
        if command.action is not None:
            await command.action(dev, invocation.device_type)
            return
        method = getattr(dev, str(command.method))
        if command.parse is None:
            await method()
            print(command.done)
        else:
            try:
                await method(invocation.value)
            except ValueError as exc:  # the device method's own range check
                raise UsageError(str(exc)) from exc
            print(f"{command.done} set to {invocation.value}.")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return the process exit code."""
    try:
        invocation = parse_args(sys.argv[1:] if argv is None else argv)
    except UsageError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    if invocation.command is None:
        print(
            format_help(invocation.device_type if invocation.explicit_device else None)
        )
        return EXIT_OK

    try:
        asyncio.run(run(invocation))
    except KeyboardInterrupt:
        print("\nStopped.")
    except UsageError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except PetSnowyError as exc:  # includes ConfigError for malformed credentials
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except Exception as exc:  # last-resort boundary: report, never traceback
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_OK
