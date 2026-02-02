"""Utility functions for PetSnowy Pet Feeder (PS-020)."""

from __future__ import annotations

import asyncio
from typing import cast

from ..feeder import Feeder, FeederState, MealSchedule, decode_meal_plan
from .common import cloud_get_dps, connect_device


async def get_status() -> FeederState:
    """Connect to the pet feeder and return its current state."""
    async with connect_device("feeder") as dev:
        dev = cast(Feeder, dev)
        return await dev.get_state()


def print_status(state: FeederState) -> None:
    """Print a human-readable summary of feeder state."""
    print("=== PetSnowy Pet Feeder Status ===")
    print()
    print(f"  Food level:         {state.food_status.value}")
    print(f"  Cover:              {'closed' if state.cover_closed else 'open'}")


async def dump_raw_dps() -> dict[str, object]:
    """Connect to the feeder and return the full raw DPS dict for discovery."""
    async with connect_device("feeder") as dev:
        dev = cast(Feeder, dev)
        return await dev.get_raw_dps()


def get_schedule() -> list[MealSchedule]:
    """Read the current feeding schedule from the Tuya cloud.

    The meal_plan (DPS 1) is a raw-type data point that the local protocol doesn't
    include in status responses. The cloud API returns it as a base64 string.

    Requires tinytuya.json with cloud API credentials.
    """
    dps = cloud_get_dps("feeder")
    raw = dps.get("meal_plan")
    if not raw:
        return []
    return decode_meal_plan(raw)


async def set_schedule(schedules: list[MealSchedule]) -> None:
    """Write a feeding schedule to the feeder over the local network.

    Example::

        await set_schedule([
            MealSchedule(Weekday.EVERY_DAY, 8, 0, 2, True),
            MealSchedule(Weekday.EVERY_DAY, 18, 0, 2, True),
        ])
    """
    async with connect_device("feeder") as dev:
        dev = cast(Feeder, dev)
        await dev.set_meal_plan(schedules)


def print_schedule(schedules: list[MealSchedule]) -> None:
    """Print a human-readable feeding schedule, all slots."""
    active = [s for s in schedules if s.enabled]
    disabled = [s for s in schedules if not s.enabled]

    print("=== Feeding Schedule ===")
    print()
    if not schedules:
        print("  No schedules configured.")
        return

    if active:
        print(f"  Active ({len(active)}):")
        for s in active:
            print(f"    {s.time_str}  {s.days_str:<12}  {s.portions} portions")
    else:
        print("  Active: none")

    if disabled:
        print()
        print(f"  Disabled ({len(disabled)}):")
        for s in disabled:
            print(f"    {s.time_str}  {s.days_str:<12}  {s.portions} portions")


if __name__ == "__main__":
    state = asyncio.run(get_status())
    print_status(state)
    print()
    schedules = get_schedule()
    print_schedule(schedules)
