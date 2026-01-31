"""Async device interface for PetSnowy Snow+ litterbox."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import tinytuya

from .const import DPS, DeviceStatus, Fault, Notification
from .exceptions import CommandError, ConnectionError
from .models import DeviceState

logger = logging.getLogger(__name__)

_HEARTBEAT_INTERVAL = 9  # seconds between heartbeats in monitor loop
_RECEIVE_TIMEOUT = 12    # seconds to wait for a message before retrying


class PetSnowy:
    """Async interface to a PetSnowy Snow+ (PS-001) on the local network.

    Uses tinytuya for Tuya protocol communication. All blocking I/O is
    offloaded to a thread via ``asyncio.to_thread()``.

    Usage::

        async with PetSnowy("device_id", "192.168.1.100", "local_key") as dev:
            state = await dev.get_state()
            print(state.status, state.cat_weight)
            await dev.deodorize()
    """

    def __init__(
        self,
        device_id: str,
        address: str,
        local_key: str,
        version: float = 3.4,
    ) -> None:
        self._device_id = device_id
        self._address = address
        self._local_key = local_key
        self._version = version
        self._dev: tinytuya.Device | None = None

    # -- Connection lifecycle --------------------------------------------------

    async def connect(self) -> None:
        """Open a persistent connection to the device."""
        dev = tinytuya.Device(
            self._device_id,
            self._address,
            self._local_key,
            version=self._version,
        )
        dev.set_socketPersistent(True)
        # Issue an initial status request to validate the connection
        result = await asyncio.to_thread(dev.status)
        if result is None or "Error" in result:
            msg = result.get("Error", "Unknown error") if result else "No response"
            raise ConnectionError(f"Failed to connect to {self._address}: {msg}")
        self._dev = dev
        logger.info("Connected to PetSnowy at %s", self._address)

    async def disconnect(self) -> None:
        """Close the device connection."""
        if self._dev is not None:
            try:
                await asyncio.to_thread(self._dev.close)
            except Exception:
                pass
            self._dev = None
            logger.info("Disconnected from PetSnowy")

    async def __aenter__(self) -> PetSnowy:
        await self.connect()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.disconnect()

    # -- Internal helpers ------------------------------------------------------

    def _ensure_connected(self) -> tinytuya.Device:
        if self._dev is None:
            raise ConnectionError("Not connected. Call connect() first.")
        return self._dev

    async def _set_dps(self, dps_id: int, value: Any) -> None:
        """Set a single DPS value on the device."""
        dev = self._ensure_connected()
        result = await asyncio.to_thread(dev.set_value, dps_id, value)
        if result and "Error" in result:
            raise CommandError(f"Failed to set DPS {dps_id}={value!r}: {result['Error']}")

    async def _send_button(self, dps_id: int) -> None:
        """Send a momentary button press (set True, device auto-resets)."""
        await self._set_dps(dps_id, True)

    # -- State reading ---------------------------------------------------------

    async def get_raw_dps(self) -> dict[str, Any]:
        """Return the raw DPS dict from the device."""
        dev = self._ensure_connected()
        result = await asyncio.to_thread(dev.status)
        if result is None or "Error" in result:
            msg = result.get("Error", "Unknown") if result else "No response"
            raise ConnectionError(f"Failed to read status: {msg}")
        return result.get("dps", {})

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

    # -- Event monitoring ------------------------------------------------------

    async def monitor(self) -> AsyncIterator[dict[str, Any]]:
        """Async generator that yields DPS update dicts as they arrive.

        Maintains a persistent connection with heartbeats. Automatically
        reconnects on transient errors. Yields each DPS update as a dict
        (same format as ``get_raw_dps()``).

        Usage::

            async for update in dev.monitor():
                print("DPS changed:", update)
        """
        dev = self._ensure_connected()
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        stop = asyncio.Event()

        def _receive_loop() -> None:
            """Blocking loop that runs in a thread, pushing updates to the queue."""
            loop = asyncio.get_event_loop()
            while not stop.is_set():
                try:
                    data = dev.receive()
                except Exception as exc:
                    logger.warning("Monitor receive error: %s", exc)
                    # Signal the async side to handle reconnection
                    loop.call_soon_threadsafe(queue.put_nowait, None)
                    return

                if data and "dps" in data:
                    dps = data["dps"]
                    loop.call_soon_threadsafe(queue.put_nowait, dps)
                elif data is None or data == {}:
                    # Timeout / no data — send heartbeat
                    try:
                        dev.heartbeat()
                    except Exception:
                        loop.call_soon_threadsafe(queue.put_nowait, None)
                        return

        task = asyncio.get_event_loop().run_in_executor(None, _receive_loop)
        try:
            while True:
                item = await queue.get()
                if item is None:
                    # Connection lost — attempt reconnect
                    logger.info("Monitor: connection lost, reconnecting...")
                    try:
                        await self.disconnect()
                        await self.connect()
                        dev = self._ensure_connected()
                        # Restart the receive loop
                        task = asyncio.get_event_loop().run_in_executor(
                            None, _receive_loop
                        )
                    except Exception as exc:
                        logger.error("Monitor: reconnect failed: %s", exc)
                        raise ConnectionError(f"Monitor reconnect failed: {exc}") from exc
                    continue
                yield item
        finally:
            stop.set()
            # Give the thread a moment to notice the stop flag
            try:
                await asyncio.wait_for(asyncio.wrap_future(task), timeout=2.0)
            except (asyncio.TimeoutError, Exception):
                pass
