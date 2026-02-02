"""Utility functions for PetSnowy Air Purifier."""

from __future__ import annotations

import asyncio
from typing import cast

from ..purifier import Purifier, PurifierFault, PurifierState
from .common import connect_device


async def get_status() -> PurifierState:
    """Connect to the air purifier and return its current state."""
    async with connect_device("purifier") as dev:
        dev = cast(Purifier, dev)
        return await dev.get_state()


def print_status(state: PurifierState) -> None:
    """Print a human-readable summary of purifier state."""
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
        for fault in PurifierFault:
            if fault and fault in state.faults:
                print(f"    - {fault.name}")
    else:
        print("\n  Faults:             None")


async def set_speed(level: str) -> None:
    """Set the purifier fan speed ('1' through '6')."""
    async with connect_device("purifier") as dev:
        dev = cast(Purifier, dev)
        await dev.set_speed(level)


if __name__ == "__main__":
    state = asyncio.run(get_status())
    print_status(state)
