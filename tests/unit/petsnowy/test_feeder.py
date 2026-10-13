from __future__ import annotations

import base64

import pytest

from petsnowy.feeder import (
    FeederState,
    FoodStatus,
    MealSchedule,
    Weekday,
    decode_meal_plan,
    encode_meal_plan,
)

BREAKFAST = MealSchedule(Weekday.EVERY_DAY, 8, 0, 2, True)
DINNER = MealSchedule(Weekday.WEEKDAYS, 18, 30, 3, False)


def test_meal_schedule_byte_layout() -> None:
    assert BREAKFAST.to_bytes() == bytes([0x7F, 8, 0, 2, 1])
    assert DINNER.to_bytes() == bytes([0b1111100, 18, 30, 3, 0])


def test_meal_schedule_round_trips() -> None:
    assert MealSchedule.from_bytes(DINNER.to_bytes()) == DINNER


def test_from_bytes_rejects_wrong_length() -> None:
    with pytest.raises(ValueError, match="Expected 5 bytes"):
        MealSchedule.from_bytes(b"\x00\x01")


@pytest.mark.parametrize(
    ("days", "text"),
    [
        (Weekday.EVERY_DAY, "Every day"),
        (Weekday.WEEKDAYS, "Weekdays"),
        (Weekday.WEEKEND, "Weekends"),
        (Weekday.MON | Weekday.WED, "Mon, Wed"),
        (Weekday(0), "None"),
    ],
)
def test_days_str(days: Weekday, text: str) -> None:
    assert MealSchedule(days, 7, 5, 1, True).days_str == text


def test_str_summary() -> None:
    assert str(DINNER) == "18:30 | Weekdays | 3 portions | OFF"


def test_meal_plan_encode_decode_round_trip() -> None:
    encoded = encode_meal_plan([BREAKFAST, DINNER])

    assert base64.b64decode(encoded) == BREAKFAST.to_bytes() + DINNER.to_bytes()
    assert decode_meal_plan(encoded) == [BREAKFAST, DINNER]
    assert decode_meal_plan(base64.b64decode(encoded)) == [BREAKFAST, DINNER]


def test_encode_rejects_more_than_ten_schedules() -> None:
    with pytest.raises(ValueError, match="Maximum 10"):
        encode_meal_plan([BREAKFAST] * 11)


def test_decode_rejects_partial_entries() -> None:
    with pytest.raises(ValueError, match="not a multiple of 5"):
        decode_meal_plan(b"\x00" * 7)


@pytest.mark.parametrize(
    ("dps", "status", "closed"),
    [
        ({}, FoodStatus.ENOUGH, True),
        ({"6": "insufficient", "13": 1}, FoodStatus.INSUFFICIENT, False),
        ({"6": "??", "13": 0}, FoodStatus.ENOUGH, True),
    ],
)
def test_feeder_state(dps: dict[str, object], status: FoodStatus, closed: bool) -> None:
    state = FeederState.from_dps(dps)
    assert state.food_status is status
    assert state.cover_closed is closed
