"""Base device class with shared connection, DPS, and monitoring logic."""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import AsyncIterator, Callable
from typing import Any, Self

import tinytuya

from .exceptions import CommandError, ConnectionError

logger = logging.getLogger(__name__)


class BasePetDevice:
    """Base async interface for PetSnowy Tuya devices on the local network.

    Provides connection lifecycle, DPS read/write helpers, and an event monitoring async
    generator. Subclasses add device-specific commands and state parsing.
    """

    # Seconds monitor() waits for its receive thread on exit. The thread may outlive
    # it while blocked in receive(); it exits without further I/O once unblocked.
    MONITOR_STOP_TIMEOUT = 2.0

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
        # Last known value of every DPS on this connection. See get_raw_dps().
        self._dps_cache: dict[str, Any] = {}

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
        self._dps_cache = {}
        self._merge_dps(result)
        logger.info("Connected to %s at %s", type(self).__name__, self._address)

    async def disconnect(self) -> None:
        """Close the device connection."""
        if self._dev is not None:
            try:
                await asyncio.to_thread(self._dev.close)
            except Exception as exc:  # the socket is discarded either way
                logger.debug("Ignoring error while closing %s: %s", self._address, exc)
            self._dev = None
            logger.info("Disconnected from %s", type(self).__name__)

    async def __aenter__(self) -> Self:
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
            raise CommandError(
                f"Failed to set DPS {dps_id}={value!r}: {result['Error']}"
            )

    async def _send_button(self, dps_id: int) -> None:
        """Send a momentary button press (set True, device auto-resets)."""
        await self._set_dps(dps_id, True)

    # -- State reading ---------------------------------------------------------

    async def get_raw_dps(self) -> dict[str, Any]:
        """Return the last known value of every DPS, refreshed from the device.

        On a persistent socket, tinytuya's status() returns whichever frame arrives
        next. That can be an unsolicited push carrying only the DPS that just changed
        (from the app, the device buttons, or a set). Merging into a per-connection
        cache stops those partial frames from resetting every other DPS to its default,
        which showed up as switches flipping off until the next poll.
        """
        dev = self._ensure_connected()
        result = await asyncio.to_thread(dev.status)
        if result is None or "Error" in result:
            msg = result.get("Error", "Unknown") if result else "No response"
            raise ConnectionError(f"Failed to read status: {msg}")
        self._merge_dps(result)
        return dict(self._dps_cache)

    def _merge_dps(self, result: dict[str, Any]) -> None:
        dps = result.get("dps", {})
        if not isinstance(dps, dict):
            raise ConnectionError(f"Malformed status response: {result!r}")
        self._dps_cache.update(dps)

    # -- Event monitoring ------------------------------------------------------

    async def monitor(self) -> AsyncIterator[dict[str, Any]]:
        """Async generator that yields DPS update dicts as they arrive.

        Maintains a persistent connection with heartbeats. Automatically reconnects on
        transient errors.
        """
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        # threading.Event, not asyncio.Event: it is read from the executor thread.
        stop = threading.Event()
        # Captured here because the executor thread has no event loop of its own;
        # asyncio.get_event_loop() there raises RuntimeError.
        loop = asyncio.get_running_loop()

        def emit(item: dict[str, Any] | None) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, item)

        def start() -> asyncio.Future[None]:
            dev = self._ensure_connected()
            return loop.run_in_executor(None, _receive_loop, dev, stop, emit)

        task = start()
        try:
            while True:
                item = await queue.get()
                if item is not None:
                    self._dps_cache.update(item)
                    yield item
                    continue
                logger.info("Monitor: connection lost, reconnecting...")
                try:
                    await self.disconnect()
                    await self.connect()
                except Exception as exc:
                    logger.error("Monitor: reconnect failed: %s", exc)
                    raise ConnectionError(f"Monitor reconnect failed: {exc}") from exc
                task = start()
        finally:
            stop.set()
            try:
                await asyncio.wait_for(task, timeout=self.MONITOR_STOP_TIMEOUT)
            except Exception as exc:  # shutdown must not mask the caller's exit
                logger.debug("Monitor receive thread did not stop cleanly: %s", exc)


def _receive_loop(
    dev: tinytuya.Device,
    stop: threading.Event,
    emit: Callable[[dict[str, Any] | None], None],
) -> None:
    """Thread body for monitor(): emit DPS updates, then None once the link is lost.

    Re-checks ``stop`` after every blocking call: receive() can outlast the caller's
    stop and disconnect, and any further I/O would make tinytuya open a new socket.
    """
    while not stop.is_set():
        try:
            data = dev.receive()
        except Exception as exc:
            if not stop.is_set():
                logger.warning("Monitor receive error: %s", exc)
                emit(None)
            return
        if stop.is_set():
            return
        if data and "Error" in data:
            # tinytuya reports a dropped socket as an error payload rather than
            # raising; without this branch the loop spins forever.
            logger.warning("Monitor receive error: %s", data["Error"])
            emit(None)
            return
        if data and "dps" in data:
            emit(data["dps"])
        elif not data:
            try:
                dev.heartbeat()
            except Exception:
                emit(None)
                return
