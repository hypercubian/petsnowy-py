"""In-memory fake of the tinytuya LAN protocol, for deterministic tests.

``FakeTuyaNetwork`` replaces ``tinytuya.Device`` (see the ``fake_tuya`` fixture in
``tests/conftest.py``). Every layer above tinytuya (device classes, monitor loop,
registry, CLI) then runs for real against simulated devices that:

- answer ``status()`` with their DPS state, or with tinytuya-shaped error payloads
  when unreachable, addressed wrongly, or given the wrong local key or version;
- apply ``set_value()`` writes, auto-reset momentary buttons, and can reject DPS;
- react to writes the way the firmware does (e.g. a clean press sets ``cleaning``);
- feed ``receive()`` from an event queue that tests push to, including dropped
  connections and raised errors, so ``monitor()`` and its reconnect path are covered.
"""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Final

# tinytuya error codes/messages (tinytuya.core.error_codes) the library sees.
ERR_UNREACHABLE: Final = {"Error": "Network Error: Device Unreachable", "Err": "905"}
ERR_KEY_OR_VERSION: Final = {"Error": "Check device key or version", "Err": "914"}

_DROP: Final = object()
_IDLE_POLL_SECONDS: Final = 0.01

Reaction = Callable[["FakeDevice", Any], Mapping[str, Any]]


@dataclass
class FakeDevice:
    """Simulated device state, shared by every client connection to it."""

    device_id: str
    address: str
    local_key: str
    version: float
    dps: dict[str, Any]
    momentary: frozenset[str] = frozenset()
    reactions: dict[str, Reaction] = field(default_factory=dict)
    reachable: bool = True
    rejected: set[str] = field(default_factory=set)
    writes: list[tuple[str, Any]] = field(default_factory=list)
    heartbeats: int = 0
    connections: int = 0
    closes: int = 0
    # I/O on a closed client: real tinytuya silently opens a new socket for it.
    io_after_close: int = 0
    # How long an idle receive() blocks (tinytuya's default socket timeout is 5 s).
    receive_timeout: float = _IDLE_POLL_SECONDS
    _events: queue.Queue[object] = field(default_factory=queue.Queue)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    # -- Test controls -------------------------------------------------------------

    def push(self, update: Mapping[str, Any]) -> None:
        """Queue a device-initiated DPS update for the next ``receive()``."""
        self._events.put(dict(update))

    def drop_connection(self) -> None:
        """Make the next ``receive()`` report a dropped socket, as tinytuya does."""
        self._events.put(_DROP)

    def fail_receive(self, exc: BaseException) -> None:
        """Make the next ``receive()`` raise ``exc``."""
        self._events.put(exc)

    def written(self, dps_id: int) -> list[Any]:
        """Return every value written to ``dps_id``, oldest first."""
        return [value for key, value in self.writes if key == str(dps_id)]

    # -- Protocol behaviour (called by FakeTuyaClient) -----------------------------

    def apply_write(self, dps_id: str, value: Any) -> dict[str, Any]:
        with self._lock:
            self.writes.append((dps_id, value))
            changed = {dps_id: value}
            if dps_id not in self.momentary:
                self.dps[dps_id] = value
            reaction = self.reactions.get(dps_id)
            if reaction is not None:
                effects = dict(reaction(self, value))
                self.dps.update(effects)
                changed.update(effects)
        if reaction is not None:
            self._events.put(effects)
        return changed

    def next_event(self) -> dict[str, Any] | None:
        try:
            event = self._events.get(timeout=self.receive_timeout)
        except queue.Empty:
            return None  # what tinytuya returns when the receive timeout expires
        if event is _DROP:
            return dict(ERR_UNREACHABLE)
        if isinstance(event, BaseException):
            raise event
        assert isinstance(event, dict)
        with self._lock:
            self.dps.update(event)
        return {"dps": event}


class FakeTuyaClient:
    """Drop-in for one ``tinytuya.Device`` connection."""

    def __init__(
        self,
        network: FakeTuyaNetwork,
        dev_id: str,
        address: str | None = None,
        local_key: str = "",
        version: float = 3.1,
        **_kwargs: Any,
    ) -> None:
        self._network = network
        self._dev_id = dev_id
        self._address = address
        self._local_key = local_key
        self._version = float(version)
        self.persistent = False
        self.closed = False
        network.clients.append(self)

    def _device(self) -> FakeDevice | None:
        device = self._network.devices.get(self._dev_id)
        if device is None or not device.reachable or device.address != self._address:
            return None
        return device

    def _session(self) -> tuple[FakeDevice | None, dict[str, Any] | None]:
        if self.closed:
            known = self._network.devices.get(self._dev_id)
            if known is not None:
                known.io_after_close += 1
        device = self._device()
        if device is None:
            return None, dict(ERR_UNREACHABLE)
        if device.local_key != self._local_key or device.version != self._version:
            return None, dict(ERR_KEY_OR_VERSION)
        return device, None

    def set_socketPersistent(self, persist: bool) -> None:  # noqa: N802 - tinytuya API
        self.persistent = persist

    def status(self) -> dict[str, Any]:
        device, error = self._session()
        if device is None:
            assert error is not None
            return error
        device.connections += 1
        return {"devId": device.device_id, "dps": dict(device.dps)}

    def set_value(self, index: int | str, value: Any) -> dict[str, Any]:
        device, error = self._session()
        if device is None:
            assert error is not None
            return error
        dps_id = str(index)
        if dps_id in device.rejected:
            return {"Error": "Device rejected the command", "Err": "900"}
        return {"devId": device.device_id, "dps": device.apply_write(dps_id, value)}

    def receive(self) -> dict[str, Any] | None:
        device, error = self._session()
        if device is None:
            return error
        return device.next_event()

    def heartbeat(self) -> None:
        device, _ = self._session()
        if device is not None:
            device.heartbeats += 1

    def close(self) -> None:
        self.closed = True
        device = self._network.devices.get(self._dev_id)
        if device is not None:
            device.closes += 1


@dataclass
class FakeTuyaNetwork:
    """A LAN of fake devices.

    Call an instance as you would ``tinytuya.Device``.
    """

    devices: dict[str, FakeDevice] = field(default_factory=dict)
    clients: list[FakeTuyaClient] = field(default_factory=list)

    def __call__(self, dev_id: str, *args: Any, **kwargs: Any) -> FakeTuyaClient:
        return FakeTuyaClient(self, dev_id, *args, **kwargs)

    def add(self, device: FakeDevice) -> FakeDevice:
        self.devices[device.device_id] = device
        return device


# -- Device profiles ---------------------------------------------------------------
# DPS ids mirror src/petsnowy/{const,fountain,purifier,feeder}.py. Values are shaped
# like real firmware reports (purifier values from a captured snapshot).


def _sets_status(status: str) -> Reaction:
    return lambda _device, _value: {"24": status}


def litterbox(**overrides: Any) -> FakeDevice:
    dps: dict[str, Any] = {
        "1": True,
        "4": True,
        "5": 10,
        "7": 2,
        "8": 95,
        "10": False,
        "16": True,
        "21": 0,
        "22": 0,
        "24": "standby",
        "102": 21,
        "104": True,  # inverted: true = unlocked
        "107": True,
        "116": "112C005A",  # 0x112C = 4396 g, 0x005A = 90 s
        "117": False,
        "118": True,
    }
    return _profile(
        "fake-litterbox",
        "192.0.2.10",
        3.4,
        dps,
        momentary={"9", "17", "101", "109", "110", "111", "112", "115"},
        reactions={"9": _sets_status("cleaning"), "17": _sets_status("deodorization")},
        overrides=overrides,
    )


def fountain(**overrides: Any) -> FakeDevice:
    dps = {"1": True, "2": "normal", "3": 42, "4": 5, "7": 30, "102": True}
    return _profile("fake-fountain", "192.0.2.11", 3.3, dps, {"5", "6"}, {}, overrides)


def purifier(**overrides: Any) -> FakeDevice:
    dps = {
        "1": True,
        "3": "auto",
        "4": "5",
        "6": True,
        "14": 7,
        "16": 0,
        "18": "cancel",
        "19": 0,
        "22": 0,
    }
    return _profile("fake-purifier", "192.0.2.12", 3.4, dps, set(), {}, overrides)


def feeder(**overrides: Any) -> FakeDevice:
    dps = {"3": 1, "6": "enough", "13": 0}
    return _profile("fake-feeder", "192.0.2.13", 3.3, dps, {"24"}, {}, overrides)


def _profile(
    device_id: str,
    address: str,
    version: float,
    dps: dict[str, Any],
    momentary: Iterable[str],
    reactions: dict[str, Reaction],
    overrides: Mapping[str, Any],
) -> FakeDevice:
    fields: dict[str, Any] = {
        "device_id": device_id,
        "address": address,
        "local_key": f"{device_id}-key",
        "version": version,
        "dps": dps,
        "momentary": frozenset(momentary),
        "reactions": reactions,
    }
    fields.update(overrides)
    return FakeDevice(**fields)
