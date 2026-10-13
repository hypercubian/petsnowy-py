"""Utility functions for PetSnowy Water Fountain (PS-010)."""

from __future__ import annotations

import asyncio
from typing import cast

from ..fountain import Fountain, FountainState
from .common import connect_device


async def get_status() -> FountainState:
    """Connect to the water fountain and return its current state."""
    async with connect_device("fountain") as dev:
        dev = cast(Fountain, dev)
        return await dev.get_state()


def format_status(state: FountainState) -> str:
    """Return a human-readable summary of fountain state."""
    return "\n".join(
        [
            "=== PetSnowy Water Fountain Status ===",
            "",
            f"  Power:              {'ON' if state.switch else 'OFF'}",
            f"  Work mode:          {state.work_mode.value}",
            f"  Filter remaining:   {state.filter_days} days",
            f"  Pump clean in:      {state.pump_time} days",
            f"  Light:              {'ON' if state.light else 'OFF'}",
            f"  Filter reminder:    {state.filter_life} days",
        ]
    )


def print_status(state: FountainState) -> None:
    """Print a human-readable summary of fountain state."""
    print(format_status(state))


async def set_light(enabled: bool) -> None:
    """Turn the fountain indicator light on or off."""
    async with connect_device("fountain") as dev:
        dev = cast(Fountain, dev)
        await dev.set_light(enabled)


if __name__ == "__main__":
    state = asyncio.run(get_status())
    print_status(state)
