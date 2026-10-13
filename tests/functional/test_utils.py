"""The petsnowy.utils helpers, resolved through devices.json to fake devices."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from petsnowy.feeder import FeederDPS, MealSchedule, Weekday, encode_meal_plan
from petsnowy.fountain import FountainDPS, WorkMode
from petsnowy.purifier import PurifierDPS
from petsnowy.utils import common, feeder, fountain, litterbox, purifier
from tests import fake_tuya as profiles
from tests.fake_tuya import FakeDevice, FakeTuyaNetwork

CATEGORIES = {
    "fake-litterbox": "msp",
    "fake-fountain": "cwysj",
    "fake-purifier": "kj",
    "fake-feeder": "cwwsq",
}


@pytest.fixture
def lan(
    fake_tuya: FakeTuyaNetwork, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> dict[str, FakeDevice]:
    """All four fake devices, listed in a devices.json the utils will find."""
    devices = {
        d.device_id: fake_tuya.add(d)
        for d in (
            profiles.litterbox(),
            profiles.fountain(),
            profiles.purifier(),
            profiles.feeder(),
        )
    }
    entries = [
        {
            "id": d.device_id,
            "key": d.local_key,
            "ip": d.address,
            "version": str(d.version),
            "category": CATEGORIES[d.device_id],
        }
        for d in devices.values()
    ]
    path = tmp_path / "devices.json"
    path.write_text(json.dumps(entries), encoding="utf-8")
    monkeypatch.setenv("PETSNOWY_DEVICES_JSON", str(path))
    return devices


async def test_get_status_for_each_device(lan: dict[str, FakeDevice]) -> None:
    assert (await litterbox.get_status()).cat_weight == 4396
    assert (await fountain.get_status()).work_mode is WorkMode.NORMAL
    assert (await purifier.get_status()).speed == "5"
    assert (await feeder.get_status()).cover_closed is True


async def test_setters(lan: dict[str, FakeDevice]) -> None:
    await fountain.set_light(False)
    await purifier.set_speed("3")

    assert lan["fake-fountain"].written(FountainDPS.LIGHT) == [False]
    assert lan["fake-purifier"].written(PurifierDPS.SPEED) == ["3"]


async def test_feeder_schedule_write_and_raw_dump(lan: dict[str, FakeDevice]) -> None:
    plan = [MealSchedule(Weekday.WEEKEND, 9, 0, 1, True)]

    await feeder.set_schedule(plan)

    assert lan["fake-feeder"].written(FeederDPS.MEAL_PLAN) == [encode_meal_plan(plan)]
    assert (await feeder.dump_raw_dps())["6"] == "enough"


def test_get_schedule_decodes_the_cloud_meal_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = [MealSchedule(Weekday.EVERY_DAY, 8, 0, 2, True)]
    monkeypatch.setattr(
        feeder, "cloud_get_dps", lambda _t: {"meal_plan": encode_meal_plan(plan)}
    )
    assert feeder.get_schedule() == plan

    monkeypatch.setattr(feeder, "cloud_get_dps", lambda _t: {})
    assert feeder.get_schedule() == []


def test_print_schedule(capsys: pytest.CaptureFixture[str]) -> None:
    feeder.print_schedule(
        [
            MealSchedule(Weekday.EVERY_DAY, 8, 0, 2, True),
            MealSchedule(Weekday.WEEKEND, 18, 0, 1, False),
        ]
    )
    out = capsys.readouterr().out
    assert "Active (1):\n    08:00  Every day     2 portions" in out
    assert "Disabled (1):\n    18:00  Weekends      1 portions" in out

    feeder.print_schedule([])
    assert "No schedules configured." in capsys.readouterr().out


class _Cloud:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response

    def getstatus(self, device_id: str) -> dict[str, object]:
        assert device_id == "fake-feeder"
        return self.response


def test_cloud_get_dps(
    lan: dict[str, FakeDevice], monkeypatch: pytest.MonkeyPatch
) -> None:
    ok = {"success": True, "result": [{"code": "status", "value": "enough"}]}
    monkeypatch.setattr(common, "cloud_client", lambda: _Cloud(ok))
    assert common.cloud_get_dps("feeder") == {"status": "enough"}

    monkeypatch.setattr(common, "cloud_client", lambda: _Cloud({"success": False}))
    with pytest.raises(RuntimeError, match="Cloud API error"):
        common.cloud_get_dps("feeder")
