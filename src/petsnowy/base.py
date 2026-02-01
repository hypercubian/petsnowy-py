"""Base device class with shared connection, DPS, and monitoring logic."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

import tinytuya

from .exceptions import CommandError, ConnectionError

logger = logging.getLogger(__name__)


class BasePetDevice:
    """Base async interface for PetSnowy Tuya devices on the local network.

    Provides connection lifecycle, DPS read/write helpers, and an event
    monitoring async generator. Subclasses add device-specific commands
    and state parsing.
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
        result = await asyncio.to_thread(dev.status)
        if result is None or "Error" in result:
            msg = result.get("Error", "Unknown error") if result else "No response"
            raise ConnectionError(f"Failed to connect to {self._address}: {msg}")
        self._dev = dev
        logger.info("Connected to %s at %s", type(self).__name__, self._address)

    async def disconnect(self) -> None:
        """Close the device connection."""
        if self._dev is not None:
            try:
                await asyncio.to_thread(self._dev.close)
            except Exception:
                pass
            self._dev = None
            logger.info("Disconnected from %s", type(self).__name__)

    async def __aenter__(self) -> BasePetDevice:
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

    # -- Event monitoring ------------------------------------------------------

    async def monitor(self) -> AsyncIterator[dict[str, Any]]:
        """Async generator that yields DPS update dicts as they arrive.

        Maintains a persistent connection with heartbeats. Automatically
        reconnects on transient errors.
        """
        dev = self._ensure_connected()
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        stop = asyncio.Event()

        def _receive_loop() -> None:
            loop = asyncio.get_event_loop()
            while not stop.is_set():
                try:
                    data = dev.receive()
                except Exception as exc:
                    logger.warning("Monitor receive error: %s", exc)
                    loop.call_soon_threadsafe(queue.put_nowait, None)
                    return

                if data and "dps" in data:
                    dps = data["dps"]
                    loop.call_soon_threadsafe(queue.put_nowait, dps)
                elif data is None or data == {}:
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
                    logger.info("Monitor: connection lost, reconnecting...")
                    try:
                        await self.disconnect()
                        await self.connect()
                        dev = self._ensure_connected()
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
            try:
                await asyncio.wait_for(asyncio.wrap_future(task), timeout=2.0)
            except (asyncio.TimeoutError, Exception):
                pass
