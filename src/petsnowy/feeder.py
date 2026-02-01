"""Async device interface for PetSnowy Pet Feeder (PS-020)."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from enum import IntFlag, StrEnum
from typing import Any

from .base import BasePetDevice


class FeederDPS:
    """Tuya Data Point IDs for PetSnowy Pet Feeder (PS-020).

    Product ID: xamrfcvbiz64but3
    Category: cwwsq
    Version: 3.3
    """

    MEAL_PLAN = 1           # raw bytes, scheduled feeding plan
    MANUAL_FEED = 3         # int 1-20, manual feed portions (cups)
    STATUS = 6              # "enough", "insufficient"
    COVER_STATE = 13        # int, lid open/closed
    FACTORY_RESET = 24      # momentary button


class FoodStatus(StrEnum):
    """Food level status (DPS 6)."""

    ENOUGH = "enough"
    INSUFFICIENT = "insufficient"


class Weekday(IntFlag):
    """Weekday bitmask for meal plan schedules. Bit 6=Mon, bit 0=Sun."""

    MON = 1 << 6
    TUE = 1 << 5
    WED = 1 << 4
    THU = 1 << 3
    FRI = 1 << 2
    SAT = 1 << 1
    SUN = 1 << 0
    WEEKDAYS = MON | TUE | WED | THU | FRI
    WEEKEND = SAT | SUN
    EVERY_DAY = MON | TUE | WED | THU | FRI | SAT | SUN


@dataclass(frozen=True)
class MealSchedule:
    """A single scheduled feeding entry (5 bytes in Tuya raw format).

    Encoding per Tuya cwwsq standard:
        byte 0: weekday bitmask (bit6=Mon .. bit0=Sun, 1=active)
        byte 1: hour (0-23)
        byte 2: minute (0-59)
        byte 3: portions (1-20)
        byte 4: enabled (0=off, 1=on)
    """

    days: Weekday
    hour: int
    minute: int
    portions: int
    enabled: bool

    def to_bytes(self) -> bytes:
        """Encode this schedule entry to 5 raw bytes."""
        return bytes([
            int(self.days) & 0x7F,
            self.hour,
            self.minute,
            self.portions,
            1 if self.enabled else 0,
        ])

    @classmethod
    def from_bytes(cls, data: bytes) -> MealSchedule:
        """Decode a 5-byte schedule entry."""
        if len(data) != 5:
            raise ValueError(f"Expected 5 bytes, got {len(data)}")
        return cls(
            days=Weekday(data[0] & 0x7F),
            hour=data[1],
            minute=data[2],
            portions=data[3],
            enabled=bool(data[4]),
        )

    @property
    def time_str(self) -> str:
        """Format time as HH:MM."""
        return f"{self.hour:02d}:{self.minute:02d}"

    @property
    def days_str(self) -> str:
        """Format active days as abbreviated names."""
        names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        flags = [Weekday.MON, Weekday.TUE, Weekday.WED, Weekday.THU,
                 Weekday.FRI, Weekday.SAT, Weekday.SUN]
        active = [n for n, f in zip(names, flags) if f in self.days]
        if len(active) == 7:
            return "Every day"
        if active == ["Mon", "Tue", "Wed", "Thu", "Fri"]:
            return "Weekdays"
        if active == ["Sat", "Sun"]:
            return "Weekends"
        return ", ".join(active) if active else "None"

    def __str__(self) -> str:
        state = "ON" if self.enabled else "OFF"
        return f"{self.time_str} | {self.days_str} | {self.portions} portions | {state}"


def encode_meal_plan(schedules: list[MealSchedule]) -> str:
    """Encode a list of meal schedules to a base64 string for DPS 1.

    Args:
        schedules: Up to 10 feeding schedule entries.

    Returns:
        Base64-encoded string suitable for writing to DPS 1.
    """
    if len(schedules) > 10:
        raise ValueError("Maximum 10 feeding schedules supported")
    raw = b"".join(s.to_bytes() for s in schedules)
    return base64.b64encode(raw).decode("ascii")


def decode_meal_plan(data: str | bytes) -> list[MealSchedule]:
    """Decode a meal plan from base64 string or raw bytes.

    Args:
        data: Base64-encoded string or raw bytes from DPS 1.

    Returns:
        List of MealSchedule entries.
    """
    if isinstance(data, str):
        raw = base64.b64decode(data)
    else:
        raw = data
    if len(raw) % 5 != 0:
        raise ValueError(f"Meal plan data length {len(raw)} is not a multiple of 5")
    return [MealSchedule.from_bytes(raw[i:i + 5]) for i in range(0, len(raw), 5)]


@dataclass(frozen=True)
class FeederState:
    """Parsed snapshot of Pet Feeder data points."""

    food_status: FoodStatus
    cover_closed: bool
    raw_dps: dict[str, Any]

    @classmethod
    def from_dps(cls, dps: dict[str, Any]) -> FeederState:
        """Build a FeederState from a raw DPS dict (string keys)."""
        status_raw = dps.get(str(FeederDPS.STATUS), "enough")
        try:
            food_status = FoodStatus(status_raw)
        except ValueError:
            food_status = FoodStatus.ENOUGH

        cover_raw = dps.get(str(FeederDPS.COVER_STATE))
        cover_closed = cover_raw == 0 if cover_raw is not None else True

        return cls(
            food_status=food_status,
            cover_closed=cover_closed,
            raw_dps=dict(dps),
        )


class Feeder(BasePetDevice):
    """Async interface to a PetSnowy Pet Feeder (PS-020).

    Usage::

        async with Feeder("device_id", "192.168.1.103", "local_key", version=3.3) as dev:
            state = await dev.get_state()
            print(state.food_status)
            await dev.feed(5)
    """

    def __init__(
        self,
        device_id: str,
        address: str,
        local_key: str,
        version: float = 3.3,
    ) -> None:
        super().__init__(device_id, address, local_key, version=version)

    # -- State reading ---------------------------------------------------------

    async def get_state(self) -> FeederState:
        """Read and parse the full feeder state."""
        dps = await self.get_raw_dps()
        return FeederState.from_dps(dps)

    # -- Commands --------------------------------------------------------------

    async def feed(self, portions: int = 1) -> None:
        """Dispense food manually.

        Args:
            portions: Number of portions to dispense (1-20 cups).
        """
        if not (1 <= portions <= 20):
            raise ValueError("portions must be between 1 and 20")
        await self._set_dps(FeederDPS.MANUAL_FEED, portions)

    async def quick_feed(self) -> None:
        """Dispense a single portion of food."""
        await self.feed(1)

    async def set_meal_plan(self, schedules: list[MealSchedule]) -> None:
        """Write a feeding schedule to the device.

        Args:
            schedules: Up to 10 MealSchedule entries. The device stores
                these locally and executes them even when offline.
        """
        payload = encode_meal_plan(schedules)
        await self._set_dps(FeederDPS.MEAL_PLAN, payload)
