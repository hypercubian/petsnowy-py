"""Credential resolution against real devices.json / tinytuya.json files on disk."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from petsnowy.exceptions import CredentialsNotFoundError
from petsnowy.fountain import Fountain
from petsnowy.registry import (
    DeviceCredentials,
    credentials_from_devices_json,
    resolve_credentials,
)
from petsnowy.utils import common

FOUNTAIN_ENTRY = {
    "id": "fake-fountain",
    "key": "fake-fountain-key",
    "ip": "192.0.2.11",
    "category": "cwysj",
    "version": "3.3",
}


def _write(path: Path, payload: Any) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_reads_first_file_with_a_match(tmp_path: Path) -> None:
    empty = _write(tmp_path / "a.json", [])
    full = _write(tmp_path / "b.json", [FOUNTAIN_ENTRY])

    creds = credentials_from_devices_json("fountain", [empty, full])

    assert creds == DeviceCredentials(
        "fake-fountain", "192.0.2.11", "fake-fountain-key", 3.3
    )


def test_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="No devices.json found"):
        credentials_from_devices_json("fountain", [tmp_path / "nope.json"])


def test_no_matching_entry_raises_key_error(tmp_path: Path) -> None:
    path = _write(tmp_path / "devices.json", [FOUNTAIN_ENTRY])
    with pytest.raises(KeyError, match="No feeder device"):
        credentials_from_devices_json("feeder", [path])


def test_env_override_points_lookups_at_one_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _write(tmp_path / "custom.json", [FOUNTAIN_ENTRY])
    monkeypatch.setenv("PETSNOWY_DEVICES_JSON", str(path))

    assert resolve_credentials("fountain").device_id == "fake-fountain"
    assert isinstance(common.connect_device("fountain"), Fountain)
    assert common.find_device_in_json("fountain")[0] == "fake-fountain"


def test_env_vars_win_over_devices_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(
        "PETSNOWY_DEVICES_JSON", str(_write(tmp_path / "d.json", [FOUNTAIN_ENTRY]))
    )
    monkeypatch.setenv("PETSNOWY_DEVICE_ID", "from-env")
    monkeypatch.setenv("PETSNOWY_ADDRESS", "192.0.2.50")
    monkeypatch.setenv("PETSNOWY_LOCAL_KEY", "env-key")

    assert resolve_credentials("fountain").device_id == "from-env"


def test_resolve_wraps_lookup_failures() -> None:
    with pytest.raises(CredentialsNotFoundError, match="No purifier credentials"):
        resolve_credentials("purifier")


class _FakeCloud:
    def __init__(self, **kwargs: str) -> None:
        self.kwargs = kwargs


def test_cloud_client_reads_tinytuya_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    creds = {
        "apiRegion": "eu",
        "apiKey": "fake-api-key",  # pragma: allowlist secret
        "apiSecret": "fake-secret",  # pragma: allowlist secret
    }
    _write(tmp_path / "tinytuya.json", creds)
    monkeypatch.setattr(common, "default_search_paths", lambda name: [tmp_path / name])
    monkeypatch.setattr(common.tinytuya, "Cloud", _FakeCloud)

    client = common.cloud_client()

    assert isinstance(client, _FakeCloud)
    assert client.kwargs == {**creds, "apiDeviceID": ""}


def test_cloud_client_without_tinytuya_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(common, "default_search_paths", lambda name: [tmp_path / name])
    with pytest.raises(FileNotFoundError, match="tinytuya.json"):
        common.cloud_client()
