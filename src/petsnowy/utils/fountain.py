"""Utility functions for PetSnowy Water Fountain (PS-010)."""

from __future__ import annotations

import asyncio

from ..fountain import Fountain, FountainState
from .common import connect_device


async def get_status() -> FountainState:
    """Connect to the water fountain and return its current state."""
    async with connect_device("fountain") as dev:
        assert isinstance(dev, Fountain)
        return await dev.get_state()


def print_status(state: FountainState) -> None:
    """Print a human-readable summary of fountain state."""
    print("=== PetSnowy Water Fountain Status ===")
    print()
    print(f"  Power:              {'ON' if state.switch else 'OFF'}")
    print(f"  Work mode:          {state.work_mode.value}")
    print(f"  Filter remaining:   {state.filter_days} days")
    print(f"  Pump clean in:      {state.pump_time} days")
    print(f"  Light:              {'ON' if state.light else 'OFF'}")
    print(f"  Filter reminder:    {state.filter_life} days")


async def set_light(enabled: bool) -> None:
    """Turn the fountain indicator light on or off."""
    async with connect_device("fountain") as dev:
        assert isinstance(dev, Fountain)
        await dev.set_light(enabled)


if __name__ == "__main__":
    state = asyncio.run(get_status())
    print_status(state)
