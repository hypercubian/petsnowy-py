"""Public device API driven end to end against the fake Tuya network."""

from __future__ import annotations

import asyncio
import base64
from collections.abc import AsyncIterator

import pytest

from petsnowy import (
    DPS,
    ConnectionError,
    DeviceStatus,
    Feeder,
    FeederDPS,
    Fountain,
    FountainDPS,
    MealSchedule,
    PetSnowy,
    Purifier,
    PurifierDPS,
    PurifierMode,
    Weekday,
    WorkMode,
)
from tests.fake_tuya import FakeDevice

# -- Litterbox ---------------------------------------------------------------------


async def test_litterbox_state_reflects_device(litterbox: FakeDevice) -> None:
    async with PetSnowy(
        litterbox.device_id, litterbox.address, litterbox.local_key
    ) as dev:
        state = await dev.get_state()

    assert state.status is DeviceStatus.STANDBY
    assert state.cat_weight == 4396
    assert state.child_locked is False
    assert state.scheduled_clean is True


async def test_clean_press_is_momentary_and_starts_cleaning(
    litterbox: FakeDevice,
) -> None:
    async with PetSnowy(
        litterbox.device_id, litterbox.address, litterbox.local_key
    ) as dev:
        await dev.clean()
        state = await dev.get_state()

    assert litterbox.written(DPS.MANUAL_CLEAN) == [True]
    assert str(DPS.MANUAL_CLEAN) not in litterbox.dps  # auto-reset, never stored
    assert state.status is DeviceStatus.CLEANING


@pytest.mark.parametrize(
    ("method", "dps_id"),
    [
        ("deodorize", DPS.DEODORIZATION),
        ("empty_litter", DPS.EMPTY),
        ("cancel_empty", DPS.EMPTY_CANCEL),
        ("pause", DPS.PAUSE),
        ("resume", DPS.CONTINUE),
        ("reset_filter", DPS.FILTER_RESET),
        ("calibrate_weight", DPS.BALL_RESET),
    ],
)
async def test_litterbox_buttons(
    litterbox: FakeDevice, method: str, dps_id: int
) -> None:
    async with PetSnowy(
        litterbox.device_id, litterbox.address, litterbox.local_key
    ) as dev:
        await getattr(dev, method)()
    assert litterbox.written(dps_id) == [True]


@pytest.mark.parametrize(
    ("method", "dps_id"),
    [
        ("set_auto_clean", DPS.AUTO_CLEAN),
        ("set_sleep_mode", DPS.SLEEP),
        ("set_light", DPS.LIGHT),
        ("set_auto_deodorize", DPS.AUTO_DEODORIZE),
        ("set_scheduled_deodorize", DPS.SCHEDULED_DEODORIZE),
        ("set_scheduled_clean", DPS.SCHEDULED_CLEAN),
    ],
)
async def test_litterbox_toggles(
    litterbox: FakeDevice, method: str, dps_id: int
) -> None:
    async with PetSnowy(
        litterbox.device_id, litterbox.address, litterbox.local_key
    ) as dev:
        await getattr(dev, method)(False)
    assert litterbox.dps[str(dps_id)] is False


async def test_child_lock_writes_inverted_value(litterbox: FakeDevice) -> None:
    async with PetSnowy(
        litterbox.device_id, litterbox.address, litterbox.local_key
    ) as dev:
        await dev.set_child_lock(True)
        assert (await dev.get_state()).child_locked is True

    assert litterbox.written(DPS.LOCK) == [False]


@pytest.mark.parametrize("minutes", [1, 3, 62])
async def test_clean_delay_rejects_invalid_values_without_writing(
    litterbox: FakeDevice, minutes: int
) -> None:
    async with PetSnowy(
        litterbox.device_id, litterbox.address, litterbox.local_key
    ) as dev:
        with pytest.raises(ValueError, match="even number between 2 and 60"):
            await dev.set_clean_delay(minutes)
        await dev.set_clean_delay(20)
    assert litterbox.written(DPS.DELAY_CLEAN_TIME) == [20]


# -- Monitor -----------------------------------------------------------------------


async def _take(
    stream: AsyncIterator[dict[str, object]], n: int
) -> list[dict[str, object]]:
    out = []
    async for update in stream:
        out.append(update)
        if len(out) == n:
            break
    return out


async def test_monitor_yields_device_events(litterbox: FakeDevice) -> None:
    async with PetSnowy(
        litterbox.device_id, litterbox.address, litterbox.local_key
    ) as dev:
        litterbox.push({"24": "pet_into"})
        litterbox.push({"24": "wait_clean", "116": "11F80050"})
        updates = await asyncio.wait_for(_take(dev.monitor(), 2), timeout=5)

    assert updates == [{"24": "pet_into"}, {"24": "wait_clean", "116": "11F80050"}]


async def test_monitor_reconnects_after_dropped_socket(litterbox: FakeDevice) -> None:
    async with PetSnowy(
        litterbox.device_id, litterbox.address, litterbox.local_key
    ) as dev:
        litterbox.push({"24": "cleaning"})
        litterbox.drop_connection()
        litterbox.push({"24": "standby"})
        updates = await asyncio.wait_for(_take(dev.monitor(), 2), timeout=5)

    assert updates == [{"24": "cleaning"}, {"24": "standby"}]
    assert litterbox.connections == 2  # initial connect + one reconnect


async def test_monitor_reconnects_after_receive_exception(
    litterbox: FakeDevice,
) -> None:
    async with PetSnowy(
        litterbox.device_id, litterbox.address, litterbox.local_key
    ) as dev:
        litterbox.fail_receive(OSError("connection reset"))
        litterbox.push({"21": 2})
        updates = await asyncio.wait_for(_take(dev.monitor(), 1), timeout=5)

    assert updates == [{"21": 2}]


async def test_monitor_raises_when_reconnect_fails(litterbox: FakeDevice) -> None:
    async with PetSnowy(
        litterbox.device_id, litterbox.address, litterbox.local_key
    ) as dev:
        litterbox.reachable = False
        with pytest.raises(ConnectionError, match="Monitor reconnect failed"):
            await asyncio.wait_for(_take(dev.monitor(), 1), timeout=5)


# -- Fountain, purifier, feeder ------------------------------------------------------


async def test_fountain_controls(fountain: FakeDevice) -> None:
    async with Fountain(
        fountain.device_id, fountain.address, fountain.local_key
    ) as dev:
        await dev.set_work_mode("night")
        await dev.turn_off()
        await dev.reset_pump()
        await dev.set_filter_reminder(60)
        with pytest.raises(ValueError):
            await dev.set_filter_reminder(91)
        state = await dev.get_state()

    assert state.work_mode is WorkMode.NIGHT
    assert state.switch is False
    assert state.filter_life == 60
    assert fountain.written(FountainDPS.PUMP_RESET) == [True]


async def test_purifier_controls(purifier: FakeDevice) -> None:
    async with Purifier(
        purifier.device_id, purifier.address, purifier.local_key
    ) as dev:
        await dev.set_mode(PurifierMode.SLEEP)
        await dev.set_speed("2")
        await dev.set_countdown("3h")
        await dev.set_anion(False)
        with pytest.raises(ValueError):
            await dev.set_speed("7")
        with pytest.raises(ValueError):
            await dev.set_countdown("6h")
        state = await dev.get_state()

    assert (state.mode, state.speed, state.countdown_set) == (
        PurifierMode.SLEEP,
        "2",
        "3h",
    )
    assert state.anion is False
    assert purifier.written(PurifierDPS.SPEED) == ["2"]


async def test_feeder_feeds_and_writes_meal_plan(feeder: FakeDevice) -> None:
    plan = [MealSchedule(Weekday.EVERY_DAY, 7, 30, 2, True)]
    async with Feeder(feeder.device_id, feeder.address, feeder.local_key) as dev:
        await dev.feed(3)
        await dev.quick_feed()
        await dev.set_meal_plan(plan)
        with pytest.raises(ValueError, match="between 1 and 20"):
            await dev.feed(21)

    assert feeder.written(FeederDPS.MANUAL_FEED) == [3, 1]
    (encoded,) = feeder.written(FeederDPS.MEAL_PLAN)
    assert base64.b64decode(encoded) == bytes([0x7F, 7, 30, 2, 1])


async def test_monitor_stop_does_no_io_after_disconnect(
    litterbox: FakeDevice, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Real receive() blocks for seconds; stop must not heartbeat once it returns,
    # or tinytuya would reopen the socket the caller just closed.
    litterbox.receive_timeout = 0.3
    monkeypatch.setattr(PetSnowy, "MONITOR_STOP_TIMEOUT", 0.01)
    async with PetSnowy(
        litterbox.device_id, litterbox.address, litterbox.local_key
    ) as dev:
        litterbox.push({"24": "pet_into"})
        await asyncio.wait_for(_take(dev.monitor(), 1), timeout=5)
    await asyncio.sleep(0.6)  # let the blocked receive() return

    assert litterbox.closes == 1
    assert litterbox.io_after_close == 0
