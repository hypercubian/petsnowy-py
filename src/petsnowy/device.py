"""Async device interface for PetSnowy Snow+ litterbox."""

from __future__ import annotations

from .base import BasePetDevice
from .const import DPS
from .models import DeviceState


class PetSnowy(BasePetDevice):
    """Async interface to a PetSnowy Snow+ (PS-001) on the local network.

    Uses tinytuya for Tuya protocol communication. All blocking I/O is
    offloaded to a thread via ``asyncio.to_thread()``.

    Usage::

        async with PetSnowy("device_id", "192.168.1.100", "local_key") as dev:
            state = await dev.get_state()
            print(state.status, state.cat_weight)
            await dev.deodorize()
    """

    # -- State reading ---------------------------------------------------------

    async def get_state(self) -> DeviceState:
        """Read and parse the full device state."""
        dps = await self.get_raw_dps()
        return DeviceState.from_dps(dps)

    # -- Commands (momentary buttons) ------------------------------------------

    async def clean(self) -> None:
        """Start a manual cleaning cycle."""
        await self._send_button(DPS.MANUAL_CLEAN)

    async def deodorize(self) -> None:
        """Start a manual deodorization cycle."""
        await self._send_button(DPS.DEODORIZATION)

    async def empty_litter(self) -> None:
        """Start emptying / changing cat litter."""
        await self._send_button(DPS.EMPTY)

    async def cancel_empty(self) -> None:
        """Cancel an in-progress litter emptying."""
        await self._send_button(DPS.EMPTY_CANCEL)

    async def pause(self) -> None:
        """Pause the current operation."""
        await self._send_button(DPS.PAUSE)

    async def resume(self) -> None:
        """Resume a paused operation."""
        await self._send_button(DPS.CONTINUE)

    async def reset_filter(self) -> None:
        """Reset the deodorizer filter life counter."""
        await self._send_button(DPS.FILTER_RESET)

    async def calibrate_weight(self) -> None:
        """Calibrate the weight sensor (ball reset)."""
        await self._send_button(DPS.BALL_RESET)

    # -- Settings (toggles) ----------------------------------------------------

    async def set_auto_clean(self, enabled: bool) -> None:
        """Enable or disable automatic cleaning after cat use."""
        await self._set_dps(DPS.AUTO_CLEAN, enabled)

    async def set_clean_delay(self, minutes: int) -> None:
        """Set the delay before auto-clean starts (2-60, even numbers only)."""
        if not (2 <= minutes <= 60) or minutes % 2 != 0:
            raise ValueError("clean_delay must be an even number between 2 and 60")
        await self._set_dps(DPS.DELAY_CLEAN_TIME, minutes)

    async def set_sleep_mode(self, enabled: bool) -> None:
        """Enable or disable sleep / do-not-disturb mode."""
        await self._set_dps(DPS.SLEEP, enabled)

    async def set_light(self, enabled: bool) -> None:
        """Turn the indicator light on or off."""
        await self._set_dps(DPS.LIGHT, enabled)

    async def set_child_lock(self, locked: bool) -> None:
        """Enable or disable the child/pet safety lock.

        Handles the DPS inversion: DPS 104 false=locked, true=unlocked.
        """
        await self._set_dps(DPS.LOCK, not locked)

    async def set_auto_deodorize(self, enabled: bool) -> None:
        """Enable or disable automatic deodorization."""
        await self._set_dps(DPS.AUTO_DEODORIZE, enabled)

    async def set_scheduled_deodorize(self, enabled: bool) -> None:
        """Enable or disable scheduled periodic deodorization."""
        await self._set_dps(DPS.SCHEDULED_DEODORIZE, enabled)

    async def set_scheduled_clean(self, enabled: bool) -> None:
        """Enable or disable scheduled periodic cleaning."""
        await self._set_dps(DPS.SCHEDULED_CLEAN, enabled)
