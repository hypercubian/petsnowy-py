from __future__ import annotations

from typing import Any

import pytest

from petsnowy.const import DeviceStatus, Fault, Notification
from petsnowy.models import DeviceState


def test_from_empty_dps_uses_defaults() -> None:
    state = DeviceState.from_dps({})

    assert state.status is DeviceStatus.STANDBY
    assert state.delay_clean_time == 10
    assert state.cat_weight == 0
    assert state.faults == Fault.NONE
    assert state.notifications == Notification.NONE
    assert state.child_locked is False
    assert state.raw_dps == {}


@pytest.mark.parametrize(("lock_dps", "locked"), [(False, True), (True, False)])
def test_child_lock_is_inverted(lock_dps: bool, locked: bool) -> None:
    assert DeviceState.from_dps({"104": lock_dps}).child_locked is locked


def test_cat_weight_falls_back_to_toilet_record() -> None:
    state = DeviceState.from_dps({"116": "112C005A"})
    assert state.cat_weight == 0x112C


def test_cat_weight_prefers_dps_6_when_reported() -> None:
    assert DeviceState.from_dps({"6": 3900, "116": "112C005A"}).cat_weight == 3900


@pytest.mark.parametrize("record", ["", "12", "zzzz0000", 12345, None])
def test_unparseable_toilet_record_gives_zero_weight(record: Any) -> None:
    assert DeviceState.from_dps({"116": record}).cat_weight == 0


def test_bitmasks_decode() -> None:
    state = DeviceState.from_dps({"21": 0b11, "22": 0b100})

    assert Notification.MANUAL_CLEAN_DONE in state.notifications
    assert Notification.AUTO_CLEAN_DONE in state.notifications
    assert state.faults == Fault.DRAWER_FULL


@pytest.mark.parametrize(
    ("status", "present"), [("pet_into", True), ("standby", False), ("unknown", False)]
)
def test_cat_present_follows_pet_into_status(status: str, present: bool) -> None:
    assert DeviceState.from_dps({"24": status}).cat_present is present


def test_raw_dps_is_a_copy() -> None:
    raw = {"1": True}
    state = DeviceState.from_dps(raw)
    raw["1"] = False
    assert state.raw_dps == {"1": True}
