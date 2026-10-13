"""Utility functions for PetSnowy Snow+ litterbox (PS-001)."""

from __future__ import annotations

import asyncio
from typing import cast

from ..const import Fault, Notification
from ..device import PetSnowy
from ..models import DeviceState
from .common import connect_device, format_flags


async def get_status() -> DeviceState:
    """Connect to the litterbox and return its current state."""
    async with connect_device("litterbox") as dev:
        return await cast(PetSnowy, dev).get_state()


def format_status(state: DeviceState) -> str:
    """Return a human-readable summary of litterbox state."""

    def on_off(flag: bool) -> str:
        return "ON" if flag else "OFF"

    lines = [
        "=== PetSnowy Snow+ Status ===",
        "",
        f"  Status:             {state.status.value}",
        f"  Cat present:        {'YES' if state.cat_present else 'NO'}",
        f"  Auto-clean:         {on_off(state.auto_clean)}",
        f"  Clean delay:        {state.delay_clean_time} min",
        f"  Cat weight:         {state.cat_weight} g",
        f"  Excretions today:   {state.excretion_count_today}",
        f"  Excretion time:     {state.excretion_duration_today} s",
        f"  Sleep mode:         {on_off(state.sleep_mode)}",
        f"  Light:              {on_off(state.light)}",
        f"  Child lock:         {'LOCKED' if state.child_locked else 'UNLOCKED'}",
        f"  Auto-deodorize:     {on_off(state.auto_deodorize)}",
        f"  Scheduled deodorize: {on_off(state.scheduled_deodorize)}",
        f"  Scheduled clean:    {on_off(state.scheduled_clean)}",
        f"  Filter remaining:   {state.filter_days_remaining} days",
    ]
    if state.notifications:
        lines.append("")
        lines.extend(
            format_flags(
                "Notifications", "Notifications", state.notifications, Notification
            )
        )
    lines.append("")
    lines.extend(format_flags("FAULTS", "Faults", state.faults, Fault))
    return "\n".join(lines)


def print_status(state: DeviceState) -> None:
    """Print a human-readable summary of litterbox state."""
    print(format_status(state))


if __name__ == "__main__":
    print_status(asyncio.run(get_status()))
