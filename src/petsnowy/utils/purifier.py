"""Utility functions for PetSnowy Air Purifier."""

from __future__ import annotations

import asyncio
from typing import cast

from ..purifier import Purifier, PurifierFault, PurifierState
from .common import connect_device, format_flags


async def get_status() -> PurifierState:
    """Connect to the air purifier and return its current state."""
    async with connect_device("purifier") as dev:
        dev = cast(Purifier, dev)
        return await dev.get_state()


def format_status(state: PurifierState) -> str:
    """Return a human-readable summary of purifier state."""
    lines = [
        "=== PetSnowy Air Purifier Status ===",
        "",
        f"  Power:              {'ON' if state.switch else 'OFF'}",
        f"  Mode:               {state.mode.value}",
        f"  Fan speed:          {state.speed}",
        f"  Ionizer:            {'ON' if state.anion else 'OFF'}",
        f"  TVOC:               {state.tvoc} ug/m3",
        f"  Filter remaining:   {state.filter_days} days",
        f"  Countdown:          {state.countdown_set}",
        f"  Countdown left:     {state.countdown_left} min",
        "",
    ]
    lines.extend(format_flags("FAULTS", "Faults", state.faults, PurifierFault))
    return "\n".join(lines)


def print_status(state: PurifierState) -> None:
    """Print a human-readable summary of purifier state."""
    print(format_status(state))


async def set_speed(level: str) -> None:
    """Set the purifier fan speed ('1' through '6')."""
    async with connect_device("purifier") as dev:
        dev = cast(Purifier, dev)
        await dev.set_speed(level)


if __name__ == "__main__":
    state = asyncio.run(get_status())
    print_status(state)
