"""Step definitions for features/litterbox.feature (fake Tuya network)."""

from __future__ import annotations

import shlex
from collections.abc import Callable
from dataclasses import dataclass

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from petsnowy.cli import main
from petsnowy.const import DPS
from petsnowy.models import DeviceState
from tests import fake_tuya as profiles
from tests.fake_tuya import FakeDevice

pytestmark = pytest.mark.bdd

scenarios("../features/litterbox.feature")


@dataclass
class CliResult:
    code: int
    out: str
    err: str


@given("a reachable litterbox in standby", target_fixture="device")
def _litterbox(use_device: Callable[[FakeDevice], FakeDevice]) -> FakeDevice:
    return use_device(profiles.litterbox())


@given("the cat has stepped into the litterbox")
def _cat_steps_in(device: FakeDevice) -> None:
    device.dps["24"] = "pet_into"


@when(parsers.parse('I run "{command}"'), target_fixture="result")
def _run(command: str, capsys: pytest.CaptureFixture[str]) -> CliResult:
    argv = shlex.split(command)[1:]  # drop the program name
    code = main(argv)
    captured = capsys.readouterr()
    return CliResult(code, captured.out, captured.err)


@then(parsers.parse('the command succeeds with "{text}"'))
def _succeeds(result: CliResult, text: str) -> None:
    assert result.code == 0, result.err
    assert text in result.out


@then(parsers.parse('the command fails with exit code {code:d} mentioning "{text}"'))
def _fails(result: CliResult, code: int, text: str) -> None:
    assert result.code == code
    assert text.replace("\\|", "|") in result.err


@then(parsers.parse('the litterbox reports status "{status}"'))
def _status(device: FakeDevice, status: str) -> None:
    assert DeviceState.from_dps(device.dps).status.value == status


@then("data point 104 was written as false")
def _lock_written(device: FakeDevice) -> None:
    assert device.written(DPS.LOCK) == [False]


@then("the litterbox reports its buttons locked")
def _locked(device: FakeDevice) -> None:
    assert DeviceState.from_dps(device.dps).child_locked is True


@then("nothing was written to the litterbox")
def _no_writes(device: FakeDevice) -> None:
    assert device.writes == []
