"""The CLI driven through ``main()`` against the fake Tuya network."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from petsnowy.cli import main
from petsnowy.const import DPS
from petsnowy.purifier import PurifierDPS
from tests import fake_tuya as profiles
from tests.fake_tuya import FakeDevice

UseDevice = Callable[[FakeDevice], FakeDevice]


def test_litterbox_status(
    use_device: UseDevice, capsys: pytest.CaptureFixture[str]
) -> None:
    use_device(profiles.litterbox())

    assert main(["status"]) == 0
    out = capsys.readouterr().out
    assert "=== PetSnowy Snow+ Status ===" in out
    assert "Cat weight:         4396 g" in out
    assert "Faults:             None" in out


@pytest.mark.parametrize(
    ("factory", "device_type", "heading"),
    [
        (profiles.fountain, "fountain", "Water Fountain Status"),
        (profiles.purifier, "purifier", "Air Purifier Status"),
        (profiles.feeder, "feeder", "Pet Feeder Status"),
    ],
)
def test_status_for_each_device(
    use_device: UseDevice,
    capsys: pytest.CaptureFixture[str],
    factory: Callable[[], FakeDevice],
    device_type: str,
    heading: str,
) -> None:
    use_device(factory())

    assert main(["--device", device_type, "status"]) == 0
    assert heading in capsys.readouterr().out


def test_button_command(
    use_device: UseDevice, capsys: pytest.CaptureFixture[str]
) -> None:
    device = use_device(profiles.litterbox())

    assert main(["clean"]) == 0
    assert capsys.readouterr().out.strip() == "Clean cycle triggered."
    assert device.written(DPS.MANUAL_CLEAN) == [True]


def test_setting_command(
    use_device: UseDevice, capsys: pytest.CaptureFixture[str]
) -> None:
    device = use_device(profiles.purifier())

    assert main(["--device", "purifier", "set-speed", "4"]) == 0
    assert capsys.readouterr().out.strip() == "Fan speed set to 4."
    assert device.written(PurifierDPS.SPEED) == ["4"]


def test_power_command(
    use_device: UseDevice, capsys: pytest.CaptureFixture[str]
) -> None:
    device = use_device(profiles.fountain())

    assert main(["--device", "fountain", "off"]) == 0
    assert capsys.readouterr().out.strip() == "Powered off."
    assert device.dps["1"] is False


def test_invalid_argument_never_reaches_the_device(
    use_device: UseDevice, capsys: pytest.CaptureFixture[str]
) -> None:
    device = use_device(profiles.litterbox())

    assert main(["light", "dim"]) == 2
    assert "expected on/off" in capsys.readouterr().err
    assert device.writes == []


def test_device_side_range_check_is_a_usage_error(
    use_device: UseDevice, capsys: pytest.CaptureFixture[str]
) -> None:
    use_device(profiles.litterbox())

    assert main(["clean-delay", "7"]) == 2
    assert "even number between 2 and 60" in capsys.readouterr().err


def test_unreachable_device_exits_1(
    use_device: UseDevice, capsys: pytest.CaptureFixture[str]
) -> None:
    use_device(profiles.litterbox(reachable=False))

    assert main(["status"]) == 1
    assert "Device Unreachable" in capsys.readouterr().err


def test_wrong_local_key_exits_1(
    use_device: UseDevice,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    use_device(profiles.feeder())
    monkeypatch.setenv("PETSNOWY_LOCAL_KEY", "rotated-key")

    assert main(["--device", "feeder", "status"]) == 1
    assert "Check device key or version" in capsys.readouterr().err


def test_monitor_prints_named_updates_until_connection_is_lost(
    use_device: UseDevice, capsys: pytest.CaptureFixture[str]
) -> None:
    device = use_device(profiles.fountain())
    device.push({"2": "night", "4": 3})
    device.push({"250": "x"})
    device.drop_connection()
    device.push({"1": False})  # unreachable after the drop, so never delivered

    original = device.next_event

    def _next_event() -> dict[str, object] | None:
        event = original()
        if event is not None and "Error" in event:
            device.reachable = False  # reconnect will fail
        return event

    device.next_event = _next_event  # type: ignore[method-assign]

    assert main(["--device", "fountain", "monitor"]) == 1
    captured = capsys.readouterr()
    assert "--- Update #1 ---\n  work_mode: night\n  pump_time: 3" in captured.out
    assert "--- Update #2 ---\n  dps_250: x" in captured.out
    assert "Update #3" not in captured.out
    assert "Monitor reconnect failed" in captured.err


@pytest.mark.parametrize(
    ("contents", "message"),
    [
        ('[{"id": ', "is not valid JSON"),
        ('{"id": "x"}', "must be a JSON list of device objects"),
    ],
)
def test_malformed_devices_json_exits_1(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    contents: str,
    message: str,
) -> None:
    path = tmp_path / "devices.json"
    path.write_text(contents, encoding="utf-8")
    monkeypatch.setenv("PETSNOWY_DEVICES_JSON", str(path))

    assert main(["status"]) == 1
    err = capsys.readouterr().err
    assert message in err
    assert "devices.json" in err


def test_bad_version_env_var_exits_1(
    use_device: UseDevice,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    use_device(profiles.litterbox())
    monkeypatch.setenv("PETSNOWY_VERSION", "abc")

    assert main(["status"]) == 1
    assert "PETSNOWY_VERSION must be a number" in capsys.readouterr().err
