"""Async device interface for PetSnowy Air Purifier."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntFlag, StrEnum
from typing import Any

from .base import BasePetDevice


class PurifierDPS:
    """Tuya Data Point IDs for PetSnowy Air Purifier.

    Product ID: tlqmw4ej2ym37kcv
    Category: kj
    Version: 3.4
    """

    SWITCH = 1
    MODE = 3  # "auto", "sleep"
    SPEED = 4  # "1"-"6"
    ANION = 6  # ionizer on/off
    TVOC = 14  # 0-1000 ug/m3, read-only
    FILTER_DAYS = 16  # 0-1000, read-only
    COUNTDOWN_SET = 18  # "cancel","1h","2h","3h","4h","5h"
    COUNTDOWN_LEFT = 19  # 0-600 min, read-only
    FAULT = 22  # bitmap, read-only


class PurifierMode(StrEnum):
    """Purifier operating mode (DPS 3)."""

    AUTO = "auto"
    SLEEP = "sleep"


class PurifierFault(IntFlag):
    """Purifier fault bitmask (DPS 22)."""

    NONE = 0
    HALL = 1 << 0
    TOPPLE_OVER = 1 << 1
    FAN_ERR = 1 << 2
    FILTER_NO = 1 << 3


@dataclass(frozen=True)
class PurifierState:
    """Parsed snapshot of Air Purifier data points."""

    switch: bool
    mode: PurifierMode
    speed: str
    anion: bool
    tvoc: int
    filter_days: int
    countdown_set: str
    countdown_left: int
    faults: PurifierFault
    raw_dps: dict[str, Any]

    @classmethod
    def from_dps(cls, dps: dict[str, Any]) -> PurifierState:
        """Build a PurifierState from a raw DPS dict (string keys)."""

        def _bool(key: int, default: bool = False) -> bool:
            v = dps.get(str(key))
            return bool(v) if v is not None else default

        def _int(key: int, default: int = 0) -> int:
            v = dps.get(str(key))
            return int(v) if v is not None else default

        def _str(key: int, default: str = "") -> str:
            v = dps.get(str(key))
            return str(v) if v is not None else default

        mode_raw = dps.get(str(PurifierDPS.MODE), "auto")
        try:
            mode = PurifierMode(mode_raw)
        except ValueError:
            mode = PurifierMode.AUTO

        return cls(
            switch=_bool(PurifierDPS.SWITCH),
            mode=mode,
            speed=_str(PurifierDPS.SPEED, "1"),
            anion=_bool(PurifierDPS.ANION),
            tvoc=_int(PurifierDPS.TVOC),
            filter_days=_int(PurifierDPS.FILTER_DAYS),
            countdown_set=_str(PurifierDPS.COUNTDOWN_SET, "cancel"),
            countdown_left=_int(PurifierDPS.COUNTDOWN_LEFT),
            faults=PurifierFault(_int(PurifierDPS.FAULT)),
            raw_dps=dict(dps),
        )


class Purifier(BasePetDevice):
    """Async interface to a PetSnowy Air Purifier.

    Usage::

        async with Purifier("device_id", "192.168.1.102", "local_key") as dev:
            state = await dev.get_state()
            print(state.mode, state.tvoc)
            await dev.set_mode(PurifierMode.AUTO)
    """

    # -- State reading ---------------------------------------------------------

    async def get_state(self) -> PurifierState:
        """Read and parse the full purifier state."""
        dps = await self.get_raw_dps()
        return PurifierState.from_dps(dps)

    # -- Power -----------------------------------------------------------------

    async def turn_on(self) -> None:
        """Turn the purifier on."""
        await self._set_dps(PurifierDPS.SWITCH, True)

    async def turn_off(self) -> None:
        """Turn the purifier off."""
        await self._set_dps(PurifierDPS.SWITCH, False)

    # -- Settings --------------------------------------------------------------

    async def set_mode(self, mode: str | PurifierMode) -> None:
        """Set the purifier mode ('auto' or 'sleep')."""
        await self._set_dps(PurifierDPS.MODE, str(PurifierMode(mode)))

    async def set_speed(self, level: str) -> None:
        """Set the fan speed ('1' through '6')."""
        if level not in ("1", "2", "3", "4", "5", "6"):
            raise ValueError("speed must be '1' through '6'")
        await self._set_dps(PurifierDPS.SPEED, level)

    async def set_anion(self, enabled: bool) -> None:
        """Enable or disable the ionizer."""
        await self._set_dps(PurifierDPS.ANION, enabled)

    async def set_countdown(self, setting: str) -> None:
        """Set the auto-off countdown ('cancel','1h','2h','3h','4h','5h')."""
        valid = ("cancel", "1h", "2h", "3h", "4h", "5h")
        if setting not in valid:
            raise ValueError(f"countdown must be one of {valid}")
        await self._set_dps(PurifierDPS.COUNTDOWN_SET, setting)
