from __future__ import annotations

from pathlib import Path

import pytest

from petsnowy.device import PetSnowy
from petsnowy.exceptions import ConfigError, CredentialsNotFoundError
from petsnowy.fountain import Fountain
from petsnowy.registry import (
    DeviceCredentials,
    create_device,
    credentials_from_entries,
    credentials_from_env,
    device_type_for,
    devices_json_paths,
    resolve_credentials,
)

ENTRIES = [
    {"id": "f1", "key": "kf", "ip": "10.0.0.2", "category": "cwysj", "version": ""},
    {"id": "l1", "key": "kl", "ip": "10.0.0.1", "product_id": "bdfimkssp9ews36b"},
]


@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        ({"product_id": "bdfimkssp9ews36b"}, "litterbox"),
        ({"category": "cwwsq"}, "feeder"),
        ({"product_id": "tlqmw4ej2ym37kcv"}, "purifier"),
        ({"category": "dj", "product_id": "bulb"}, None),
    ],
)
def test_device_type_for(entry: dict[str, str], expected: str | None) -> None:
    assert device_type_for(entry) == expected


def test_credentials_from_entries_matches_type_and_defaults_blank_version() -> None:
    assert credentials_from_entries("fountain", ENTRIES) == DeviceCredentials(
        "f1", "10.0.0.2", "kf", 3.3
    )
    assert credentials_from_entries("litterbox", ENTRIES) == DeviceCredentials(
        "l1", "10.0.0.1", "kl", 3.4
    )
    assert credentials_from_entries("feeder", ENTRIES) is None


def test_credentials_from_env_requires_all_three_values() -> None:
    env = {"PETSNOWY_DEVICE_ID": "d", "PETSNOWY_ADDRESS": "a"}
    assert credentials_from_env("litterbox", env) is None


@pytest.mark.parametrize(("version", "expected"), [("", 3.3), ("0", 3.3), ("3.5", 3.5)])
def test_credentials_from_env_version(version: str, expected: float) -> None:
    env = {
        "PETSNOWY_DEVICE_ID": "d",
        "PETSNOWY_ADDRESS": "a",
        "PETSNOWY_LOCAL_KEY": "k",
        "PETSNOWY_VERSION": version,
    }
    assert credentials_from_env("feeder", env) == DeviceCredentials(
        "d", "a", "k", expected
    )


def test_devices_json_paths_honours_override() -> None:
    paths = devices_json_paths({"PETSNOWY_DEVICES_JSON": "/tmp/x.json"})
    assert paths == [Path("/tmp/x.json")]


def test_devices_json_paths_default_searches_cwd_first() -> None:
    paths = devices_json_paths({})
    assert paths[0] == Path.cwd() / "devices.json"
    assert len(paths) == 2


@pytest.mark.parametrize(
    ("device_type", "cls"), [("litterbox", PetSnowy), ("fountain", Fountain)]
)
def test_create_device_builds_the_registered_class(device_type: str, cls: type) -> None:
    dev = create_device(device_type, DeviceCredentials("d", "a", "k", 3.3))
    assert isinstance(dev, cls)


def test_bad_version_raises_config_error_that_is_also_a_value_error() -> None:
    env = {
        "PETSNOWY_DEVICE_ID": "d",
        "PETSNOWY_ADDRESS": "a",
        "PETSNOWY_LOCAL_KEY": "k",
        "PETSNOWY_VERSION": "v3",
    }
    with pytest.raises(ConfigError, match="must be a number") as info:
        credentials_from_env("litterbox", env)
    assert isinstance(info.value, ValueError)


def test_resolve_credentials_uses_the_given_environ_for_devices_json() -> None:
    env = {"PETSNOWY_DEVICES_JSON": "/nonexistent/devices.json"}
    with pytest.raises(CredentialsNotFoundError) as info:
        resolve_credentials("feeder", environ=env)
    assert "nonexistent" in str(info.value.__cause__)
