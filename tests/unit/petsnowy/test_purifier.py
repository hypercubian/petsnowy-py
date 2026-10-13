from __future__ import annotations

from petsnowy.purifier import PurifierFault, PurifierMode, PurifierState


def test_from_dps_parses_captured_snapshot() -> None:
    state = PurifierState.from_dps(
        {"1": True, "3": "auto", "4": "5", "6": True, "14": 7, "16": 0, "18": "cancel"}
    )

    assert state.mode is PurifierMode.AUTO
    assert state.speed == "5"
    assert state.anion is True
    assert state.tvoc == 7
    assert state.countdown_set == "cancel"
    assert state.faults == PurifierFault.NONE


def test_defaults_when_dps_missing() -> None:
    state = PurifierState.from_dps({})

    assert state.mode is PurifierMode.AUTO
    assert state.speed == "1"
    assert state.countdown_set == "cancel"


def test_fault_bitmask() -> None:
    faults = PurifierState.from_dps({"22": 0b1010}).faults
    assert faults == PurifierFault.TOPPLE_OVER | PurifierFault.FILTER_NO
