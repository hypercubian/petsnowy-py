from __future__ import annotations

from petsnowy.fountain import FountainState, WorkMode


def test_from_dps_parses_all_fields() -> None:
    state = FountainState.from_dps(
        {"1": True, "2": "night", "3": 42, "4": 5, "7": 30, "102": False}
    )

    assert state.switch is True
    assert state.work_mode is WorkMode.NIGHT
    assert state.filter_days == 42
    assert state.pump_time == 5
    assert state.filter_life == 30
    assert state.light is False


def test_unknown_work_mode_falls_back_to_normal() -> None:
    assert FountainState.from_dps({"2": "turbo"}).work_mode is WorkMode.NORMAL
