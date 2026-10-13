"""The per-device ``format_status`` helpers in petsnowy.utils."""

from __future__ import annotations

import pytest

from petsnowy.feeder import FeederState
from petsnowy.fountain import FountainState
from petsnowy.models import DeviceState
from petsnowy.purifier import PurifierState
from petsnowy.utils import feeder, fountain, litterbox, purifier


def test_litterbox_status() -> None:
    text = litterbox.format_status(
        DeviceState.from_dps(
            {"24": "pet_into", "116": "112C005A", "104": False, "21": 1, "22": 4}
        )
    )
    assert "Status:             pet_into" in text
    assert "Cat present:        YES" in text
    assert "Cat weight:         4396 g" in text
    assert "Child lock:         LOCKED" in text
    assert "    - MANUAL_CLEAN_DONE" in text
    assert "    - DRAWER_FULL" in text


def test_litterbox_status_without_faults_or_notifications() -> None:
    text = litterbox.format_status(DeviceState.from_dps({}))
    assert "Notifications" not in text
    assert text.endswith("  Faults:             None")


def test_fountain_status() -> None:
    text = fountain.format_status(FountainState.from_dps({"2": "night", "102": True}))
    assert "Work mode:          night" in text
    assert "Light:              ON" in text


def test_purifier_status_lists_faults() -> None:
    text = purifier.format_status(PurifierState.from_dps({"22": 4}))
    assert "    - FAN_ERR" in text


@pytest.mark.parametrize(("cover", "word"), [(0, "closed"), (1, "open")])
def test_feeder_status(cover: int, word: str) -> None:
    text = feeder.format_status(FeederState.from_dps({"13": cover}))
    assert f"Cover:              {word}" in text


def test_print_status_writes_format_status(capsys: pytest.CaptureFixture[str]) -> None:
    state = FountainState.from_dps({})
    fountain.print_status(state)
    assert capsys.readouterr().out == fountain.format_status(state) + "\n"
