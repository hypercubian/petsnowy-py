"""Supported device types and credential resolution (env vars, then devices.json)."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .base import BasePetDevice
from .const import DPS
from .device import PetSnowy
from .exceptions import ConfigError, CredentialsNotFoundError
from .feeder import Feeder, FeederDPS
from .fountain import Fountain, FountainDPS
from .purifier import Purifier, PurifierDPS

ENV_DEVICE_ID = "PETSNOWY_DEVICE_ID"
ENV_ADDRESS = "PETSNOWY_ADDRESS"
ENV_LOCAL_KEY = "PETSNOWY_LOCAL_KEY"
ENV_VERSION = "PETSNOWY_VERSION"
ENV_DEVICES_JSON = "PETSNOWY_DEVICES_JSON"


@dataclass(frozen=True)
class DeviceSpec:
    """How to recognise and construct one PetSnowy device type."""

    cls: type[BasePetDevice]
    dps: type
    product_ids: frozenset[str]
    categories: frozenset[str]
    default_version: float


@dataclass(frozen=True)
class DeviceCredentials:
    device_id: str
    address: str
    local_key: str
    version: float


DEVICE_SPECS: dict[str, DeviceSpec] = {
    "litterbox": DeviceSpec(
        PetSnowy, DPS, frozenset({"bdfimkssp9ews36b"}), frozenset({"msp"}), 3.4
    ),
    "fountain": DeviceSpec(
        Fountain,
        FountainDPS,
        frozenset({"6atwtbtrc6xszdem"}),
        frozenset({"cwysj"}),
        3.3,
    ),
    "purifier": DeviceSpec(
        Purifier, PurifierDPS, frozenset({"tlqmw4ej2ym37kcv"}), frozenset({"kj"}), 3.4
    ),
    "feeder": DeviceSpec(
        Feeder, FeederDPS, frozenset({"xamrfcvbiz64but3"}), frozenset({"cwwsq"}), 3.3
    ),
}


def default_search_paths(filename: str) -> list[Path]:
    """Return the current directory and the source checkout root for ``filename``."""
    return [Path.cwd() / filename, Path(__file__).resolve().parents[2] / filename]


def devices_json_paths(environ: Mapping[str, str] | None = None) -> list[Path]:
    """Return ``$PETSNOWY_DEVICES_JSON`` alone if set, else the default search paths."""
    override = (os.environ if environ is None else environ).get(ENV_DEVICES_JSON)
    if override:
        return [Path(override).expanduser()]
    return default_search_paths("devices.json")


def device_type_for(entry: Mapping[str, Any]) -> str | None:
    """Match a devices.json entry to a device type name by product id or category."""
    pid = entry.get("product_id", "")
    cat = entry.get("category", "")
    for name, spec in DEVICE_SPECS.items():
        if pid in spec.product_ids or cat in spec.categories:
            return name
    return None


def credentials_from_env(
    device_type: str, environ: Mapping[str, str]
) -> DeviceCredentials | None:
    """Return credentials from ``PETSNOWY_*`` variables, or None if any is missing."""
    device_id = environ.get(ENV_DEVICE_ID)
    address = environ.get(ENV_ADDRESS)
    local_key = environ.get(ENV_LOCAL_KEY)
    if not (device_id and address and local_key):
        return None
    raw_version = environ.get(ENV_VERSION) or "0"
    try:
        version = float(raw_version) or DEVICE_SPECS[device_type].default_version
    except ValueError:
        raise ConfigError(
            f"{ENV_VERSION} must be a number, got {raw_version!r}"
        ) from None
    return DeviceCredentials(device_id, address, local_key, version)


def credentials_from_entries(
    device_type: str, entries: Iterable[Mapping[str, Any]]
) -> DeviceCredentials | None:
    """Return credentials for the first entry matching ``device_type``."""
    default_version = DEVICE_SPECS[device_type].default_version
    for entry in entries:
        if device_type_for(entry) == device_type:
            return DeviceCredentials(
                device_id=entry["id"],
                address=entry.get("ip", ""),
                local_key=entry["key"],
                version=float(entry.get("version") or default_version),
            )
    return None


def credentials_from_devices_json(
    device_type: str, search_paths: Sequence[Path] | None = None
) -> DeviceCredentials:
    """Find ``device_type`` credentials in the first devices.json that has them.

    ``search_paths`` defaults to :func:`devices_json_paths`.

    Raises:
        FileNotFoundError: No devices.json exists on any search path.
        KeyError: devices.json exists but has no entry for ``device_type``.
        ConfigError: A devices.json is not a JSON list of device objects.
    """
    paths = list(devices_json_paths() if search_paths is None else search_paths)
    existing = [p for p in paths if p.is_file()]
    if not existing:
        raise FileNotFoundError(f"No devices.json found (searched {paths})")
    for path in existing:
        creds = credentials_from_entries(device_type, _load_entries(path))
        if creds is not None:
            return creds
    raise KeyError(f"No {device_type} device found in devices.json")


def _load_entries(path: Path) -> list[dict[str, Any]]:
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ConfigError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(entries, list) or not all(isinstance(e, dict) for e in entries):
        raise ConfigError(f"{path} must be a JSON list of device objects")
    return [e for e in entries if "id" in e and "key" in e]


def resolve_credentials(
    device_type: str,
    environ: Mapping[str, str] | None = None,
    search_paths: Sequence[Path] | None = None,
) -> DeviceCredentials:
    """Resolve credentials from ``PETSNOWY_*`` env vars, then devices.json.

    Raises:
        CredentialsNotFoundError: Neither source has credentials for the device.
    """
    env = os.environ if environ is None else environ
    creds = credentials_from_env(device_type, env)
    if creds is not None:
        return creds
    paths = devices_json_paths(env) if search_paths is None else search_paths
    try:
        return credentials_from_devices_json(device_type, paths)
    except (FileNotFoundError, KeyError) as exc:
        raise CredentialsNotFoundError(
            f"No {device_type} credentials found. Set {ENV_DEVICE_ID}, "
            f"{ENV_ADDRESS} and {ENV_LOCAL_KEY}, or run "
            "'python -m tinytuya wizard' to generate devices.json."
        ) from exc


def create_device(device_type: str, creds: DeviceCredentials) -> BasePetDevice:
    """Return an unconnected device instance of ``device_type``."""
    return DEVICE_SPECS[device_type].cls(
        creds.device_id, creds.address, creds.local_key, version=creds.version
    )
