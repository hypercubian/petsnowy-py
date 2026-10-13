"""BasePetDevice against the in-memory fake: connection and error paths."""

from __future__ import annotations

import pytest

from petsnowy.base import BasePetDevice
from petsnowy.exceptions import CommandError, ConnectionError
from tests.fake_tuya import FakeDevice, FakeTuyaNetwork


def _base(device: FakeDevice, **overrides: object) -> BasePetDevice:
    args: dict[str, object] = {
        "device_id": device.device_id,
        "address": device.address,
        "local_key": device.local_key,
        "version": device.version,
    }
    args.update(overrides)
    return BasePetDevice(**args)  # type: ignore[arg-type]


async def test_connect_reads_status_and_enables_persistent_socket(
    fake_tuya: FakeTuyaNetwork, litterbox: FakeDevice
) -> None:
    async with _base(litterbox) as dev:
        assert await dev.get_raw_dps() == litterbox.dps
    assert fake_tuya.clients[0].persistent is True
    assert litterbox.closes == 1


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"local_key": "wrong"}, "Check device key or version"),
        ({"version": 3.3}, "Check device key or version"),
        ({"address": "192.0.2.99"}, "Device Unreachable"),
    ],
)
async def test_connect_failures_raise_connection_error(
    litterbox: FakeDevice, overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(ConnectionError, match=message):
        await _base(litterbox, **overrides).connect()


async def test_calls_before_connect_raise() -> None:
    dev = BasePetDevice("d", "a", "k")
    with pytest.raises(ConnectionError, match="Not connected"):
        await dev.get_raw_dps()


async def test_rejected_write_raises_command_error(litterbox: FakeDevice) -> None:
    litterbox.rejected.add("16")
    async with _base(litterbox) as dev:
        with pytest.raises(CommandError, match="DPS 16=False"):
            await dev._set_dps(16, False)


async def test_status_read_after_device_goes_offline(litterbox: FakeDevice) -> None:
    async with _base(litterbox) as dev:
        litterbox.reachable = False
        with pytest.raises(ConnectionError, match="Failed to read status"):
            await dev.get_raw_dps()


async def test_disconnect_swallows_close_errors(
    fake_tuya: FakeTuyaNetwork, litterbox: FakeDevice, monkeypatch: pytest.MonkeyPatch
) -> None:
    dev = _base(litterbox)
    await dev.connect()

    def _boom() -> None:
        raise OSError("socket already closed")

    monkeypatch.setattr(fake_tuya.clients[0], "close", _boom)
    await dev.disconnect()
    await dev.disconnect()  # idempotent
