"""Async device interface for PetSnowy Water Fountain (PS-010)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .base import BasePetDevice


class FountainDPS:
    """Tuya Data Point IDs for PetSnowy Water Fountain (PS-010).

    Product ID: 6atwtbtrc6xszdem
    Category: cwysj
    Version: 3.3
    """

    SWITCH = 1
    WORK_MODE = 2           # "normal", "night"
    FILTER_DAYS = 3         # 0-90, read-only
    PUMP_TIME = 4           # pump cleaning days remaining (0-7), read-only
    FILTER_RESET = 5        # momentary button
    PUMP_RESET = 6          # momentary button
    FILTER_LIFE = 7         # filter replacement reminder period (0-90 days)
    LIGHT = 102             # indicator light on/off


class WorkMode(StrEnum):
    """Fountain operating mode (DPS 2)."""

    NORMAL = "normal"
    NIGHT = "night"


@dataclass(frozen=True)
class FountainState:
    """Parsed snapshot of Water Fountain data points."""

    switch: bool
    work_mode: WorkMode
    filter_days: int
    pump_time: int
    filter_life: int
    light: bool
    raw_dps: dict[str, Any]

    @classmethod
    def from_dps(cls, dps: dict[str, Any]) -> FountainState:
        """Build a FountainState from a raw DPS dict (string keys)."""
        def _bool(key: int, default: bool = False) -> bool:
            v = dps.get(str(key))
            return bool(v) if v is not None else default

        def _int(key: int, default: int = 0) -> int:
            v = dps.get(str(key))
            return int(v) if v is not None else default

        mode_raw = dps.get(str(FountainDPS.WORK_MODE), "normal")
        try:
            work_mode = WorkMode(mode_raw)
        except ValueError:
            work_mode = WorkMode.NORMAL

        return cls(
            switch=_bool(FountainDPS.SWITCH),
            work_mode=work_mode,
            filter_days=_int(FountainDPS.FILTER_DAYS),
            pump_time=_int(FountainDPS.PUMP_TIME),
            filter_life=_int(FountainDPS.FILTER_LIFE),
            light=_bool(FountainDPS.LIGHT),
            raw_dps=dict(dps),
        )


class Fountain(BasePetDevice):
    """Async interface to a PetSnowy Water Fountain (PS-010).

    Usage::

        async with Fountain("device_id", "192.168.1.101", "local_key", version=3.3) as dev:
            state = await dev.get_state()
            print(state.work_mode, state.filter_days)
            await dev.set_work_mode(WorkMode.NIGHT)
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

    async def get_state(self) -> FountainState:
        """Read and parse the full fountain state."""
        dps = await self.get_raw_dps()
        return FountainState.from_dps(dps)

    # -- Power -----------------------------------------------------------------

    async def turn_on(self) -> None:
        """Turn the fountain on."""
        await self._set_dps(FountainDPS.SWITCH, True)

    async def turn_off(self) -> None:
        """Turn the fountain off."""
        await self._set_dps(FountainDPS.SWITCH, False)

    # -- Commands (momentary buttons) ------------------------------------------

    async def reset_filter(self) -> None:
        """Reset the filter days counter."""
        await self._send_button(FountainDPS.FILTER_RESET)

    async def reset_pump(self) -> None:
        """Reset the pump cleaning counter."""
        await self._send_button(FountainDPS.PUMP_RESET)

    # -- Settings --------------------------------------------------------------

    async def set_work_mode(self, mode: str | WorkMode) -> None:
        """Set the fountain operating mode ('normal' or 'night')."""
        await self._set_dps(FountainDPS.WORK_MODE, str(WorkMode(mode)))

    async def set_filter_reminder(self, days: int) -> None:
        """Set the filter replacement reminder period (0-90 days)."""
        if not (0 <= days <= 90):
            raise ValueError("filter_reminder must be between 0 and 90")
        await self._set_dps(FountainDPS.FILTER_LIFE, days)

    async def set_light(self, enabled: bool) -> None:
        """Turn the indicator light on or off."""
        await self._set_dps(FountainDPS.LIGHT, enabled)
