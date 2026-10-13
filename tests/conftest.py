"""Shared fixtures: the fake Tuya network and credential isolation."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from petsnowy import base
from petsnowy import testing as profiles
from petsnowy.registry import (
    ENV_ADDRESS,
    ENV_DEVICE_ID,
    ENV_DEVICES_JSON,
    ENV_LOCAL_KEY,
    ENV_VERSION,
)
from petsnowy.testing import FakeDevice, FakeTuyaNetwork

_TIERS = ("unit", "integration", "functional", "e2e")
# Never created: points devices.json lookups away from the real repo-root file.
_NO_DEVICES_JSON = Path(__file__).parent / "no-such-dir" / "devices.json"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark every test with its tier, taken from its directory under tests/."""
    for item in items:
        parts = Path(str(item.path)).parts
        for tier in _TIERS:
            if tier in parts:
                item.add_marker(getattr(pytest.mark, tier))
                break


@pytest.fixture(autouse=True)
def _isolate_credentials(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keep tests away from real devices.json files and PETSNOWY_* variables."""
    if request.node.get_closest_marker("e2e") is not None:
        return
    for name in (ENV_DEVICE_ID, ENV_ADDRESS, ENV_LOCAL_KEY, ENV_VERSION):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(ENV_DEVICES_JSON, str(_NO_DEVICES_JSON))


@pytest.fixture
def fake_tuya(monkeypatch: pytest.MonkeyPatch) -> FakeTuyaNetwork:
    """Replace ``tinytuya.Device`` with an empty fake network."""
    network = FakeTuyaNetwork()
    monkeypatch.setattr(base.tinytuya, "Device", network)
    return network


@pytest.fixture
def use_device(
    fake_tuya: FakeTuyaNetwork, monkeypatch: pytest.MonkeyPatch
) -> Callable[[FakeDevice], FakeDevice]:
    """Return a function that adds a device and points PETSNOWY_* env vars at it."""

    def _use(device: FakeDevice) -> FakeDevice:
        fake_tuya.add(device)
        monkeypatch.setenv(ENV_DEVICE_ID, device.device_id)
        monkeypatch.setenv(ENV_ADDRESS, device.address)
        monkeypatch.setenv(ENV_LOCAL_KEY, device.local_key)
        monkeypatch.setenv(ENV_VERSION, str(device.version))
        return device

    return _use


@pytest.fixture
def litterbox(fake_tuya: FakeTuyaNetwork) -> FakeDevice:
    return fake_tuya.add(profiles.litterbox())


@pytest.fixture
def fountain(fake_tuya: FakeTuyaNetwork) -> FakeDevice:
    return fake_tuya.add(profiles.fountain())


@pytest.fixture
def purifier(fake_tuya: FakeTuyaNetwork) -> FakeDevice:
    return fake_tuya.add(profiles.purifier())


@pytest.fixture
def feeder(fake_tuya: FakeTuyaNetwork) -> FakeDevice:
    return fake_tuya.add(profiles.feeder())
