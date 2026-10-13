from __future__ import annotations

import logging

import pytest

from petsnowy._dps import dps_bool, dps_enum, dps_int, dps_names, dps_str
from petsnowy.const import DPS, DeviceStatus


@pytest.mark.parametrize(
    ("raw", "expected"), [({"1": True}, True), ({"1": 0}, False), ({}, False)]
)
def test_dps_bool(raw: dict[str, object], expected: bool) -> None:
    assert dps_bool(raw, 1) is expected


def test_dps_bool_default_applies_only_when_missing() -> None:
    assert dps_bool({}, 1, default=True) is True
    assert dps_bool({"1": False}, 1, default=True) is False


@pytest.mark.parametrize(("raw", "expected"), [("12", 12), (7, 7), (None, 3)])
def test_dps_int_coerces_or_defaults(raw: object, expected: int) -> None:
    dps = {} if raw is None else {"5": raw}
    assert dps_int(dps, 5, default=3) == expected


def test_dps_int_logs_and_defaults_on_malformed_value(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        assert dps_int({"5": "abc"}, 5, default=9) == 9
    assert "expected an int" in caplog.text


def test_dps_str() -> None:
    assert dps_str({"4": 5}, 4) == "5"
    assert dps_str({}, 4, "1") == "1"


def test_dps_enum_known_unknown_and_missing(caplog: pytest.LogCaptureFixture) -> None:
    assert (
        dps_enum({"24": "cleaning"}, 24, DeviceStatus, DeviceStatus.STANDBY)
        is DeviceStatus.CLEANING
    )
    assert dps_enum({}, 24, DeviceStatus, DeviceStatus.SLEEP) is DeviceStatus.SLEEP
    with caplog.at_level(logging.WARNING):
        assert (
            dps_enum({"24": "warp"}, 24, DeviceStatus, DeviceStatus.STANDBY)
            is DeviceStatus.STANDBY
        )
    assert "unknown DeviceStatus value 'warp'" in caplog.text


def test_dps_names_maps_ids_to_lowercase_constant_names() -> None:
    names = dps_names(DPS)
    assert names["9"] == "manual_clean"
    assert names["104"] == "lock"
    assert all(name.islower() for name in names.values())
