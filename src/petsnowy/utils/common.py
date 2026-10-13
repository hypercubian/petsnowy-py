"""Shared utility helpers across PetSnowy devices."""

from __future__ import annotations

import json
from collections.abc import Mapping
from enum import IntFlag
from typing import Any

import tinytuya

from .._dps import dps_names
from ..base import BasePetDevice
from ..const import DPS, Fault, Notification
from ..registry import (
    create_device,
    credentials_from_devices_json,
    default_search_paths,
)


def find_device_in_json(device_type: str) -> tuple[str, str, str, float]:
    """Find device credentials from devices.json by device type name.

    Searches cwd and project root for devices.json, matches by product_id
    or category.

    Returns:
        (device_id, ip_address, local_key, version)

    Raises:
        FileNotFoundError: No devices.json found.
        KeyError: No matching device entry for the requested type.
    """
    creds = credentials_from_devices_json(device_type)
    return creds.device_id, creds.address, creds.local_key, creds.version


def connect_device(device_type: str) -> BasePetDevice:
    """Create a device instance from devices.json credentials.

    Returns an unconnected device — use as async context manager::

        async with connect_device("purifier") as dev:
            ...
    """
    return create_device(device_type, credentials_from_devices_json(device_type))


def cloud_client() -> tinytuya.Cloud:
    """Create a tinytuya Cloud client from tinytuya.json credentials.

    Searches cwd and project root for tinytuya.json.

    Raises:
        FileNotFoundError: No tinytuya.json found.
    """
    for path in default_search_paths("tinytuya.json"):
        if not path.is_file():
            continue
        creds = json.loads(path.read_text(encoding="utf-8"))
        return tinytuya.Cloud(
            apiRegion=creds["apiRegion"],
            apiKey=creds["apiKey"],
            apiSecret=creds["apiSecret"],
            apiDeviceID=creds.get("apiDeviceID", ""),
        )
    raise FileNotFoundError("No tinytuya.json found for cloud API access")


def cloud_get_dps(device_type: str) -> dict[str, Any]:
    """Fetch device status via Tuya cloud API.

    Returns a dict mapping code names to values, e.g.
    ``{"meal_plan": "fwYA...", "status": "enough"}``.

    Useful for reading raw-type DPS (like meal_plan) that the local
    protocol doesn't return in status queries.
    """
    device_id, *_ = find_device_in_json(device_type)
    cloud = cloud_client()
    result = cloud.getstatus(device_id)
    if not result.get("success"):
        raise RuntimeError(f"Cloud API error: {result}")
    return {item["code"]: item["value"] for item in result.get("result", [])}


def flag_names(value: IntFlag, flag_cls: type[IntFlag]) -> list[str]:
    """Return the names of the single-bit members of ``flag_cls`` set in ``value``."""
    return [str(flag.name) for flag in flag_cls if flag and flag in value]


def format_flags(
    active_title: str, empty_title: str, value: IntFlag, flag_cls: type[IntFlag]
) -> list[str]:
    """Return status lines listing the set flags, or a single 'None' line."""
    names = flag_names(value, flag_cls)
    if not names:
        return [f"  {empty_title + ':':<20}None"]
    return [f"  {active_title}:", *(f"    - {name}" for name in names)]


def format_update(update: Mapping[str, Any], dps_cls: type) -> list[str]:
    """Return one ``name: value`` line per DPS in a monitor update.

    Names come from ``dps_cls`` (the device's ``*DPS`` constants). Litterbox
    notification and fault bitmasks are expanded to flag names.
    """
    names = dps_names(dps_cls)
    bitmasks: dict[str, type[IntFlag]] = (
        {str(DPS.NOTIFICATION): Notification, str(DPS.FAULT): Fault}
        if dps_cls is DPS
        else {}
    )
    lines = []
    for key, value in update.items():
        name = names.get(key, f"dps_{key}")
        flag_cls = bitmasks.get(key)
        if flag_cls is not None and isinstance(value, int):
            value = flag_names(flag_cls(value), flag_cls) or "none"
        lines.append(f"  {name}: {value}")
    return lines
