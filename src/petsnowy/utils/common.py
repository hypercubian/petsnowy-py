"""Shared utility helpers across PetSnowy devices."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import tinytuya

from ..base import BasePetDevice
from ..device import PetSnowy
from ..feeder import Feeder
from ..fountain import Fountain
from ..purifier import Purifier

DEVICE_REGISTRY: dict[str, dict[str, Any]] = {
    "litterbox": {
        "class": PetSnowy,
        "product_ids": {"bdfimkssp9ews36b"},
        "categories": {"msp"},
        "default_version": 3.4,
    },
    "fountain": {
        "class": Fountain,
        "product_ids": {"6atwtbtrc6xszdem"},
        "categories": {"cwysj"},
        "default_version": 3.3,
    },
    "purifier": {
        "class": Purifier,
        "product_ids": {"tlqmw4ej2ym37kcv"},
        "categories": {"kj"},
        "default_version": 3.4,
    },
    "feeder": {
        "class": Feeder,
        "product_ids": {"xamrfcvbiz64but3"},
        "categories": {"cwwsq"},
        "default_version": 3.3,
    },
}


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
    candidates = [
        Path.cwd() / "devices.json",
        Path(__file__).resolve().parent.parent.parent.parent / "devices.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        with open(path) as f:
            devices = json.load(f)
        info = DEVICE_REGISTRY[device_type]
        for dev in devices:
            pid = dev.get("product_id", "")
            cat = dev.get("category", "")
            if pid in info["product_ids"] or cat in info["categories"]:
                return (
                    dev["id"],
                    dev.get("ip", ""),
                    dev["key"],
                    float(dev.get("version", info["default_version"])),
                )
    raise KeyError(f"No {device_type} device found in devices.json")


def connect_device(device_type: str) -> BasePetDevice:
    """Create a device instance from devices.json credentials.

    Returns an unconnected device — use as async context manager::

        async with connect_device("purifier") as dev:
            ...
    """
    device_id, address, local_key, version = find_device_in_json(device_type)
    cls = DEVICE_REGISTRY[device_type]["class"]
    return cls(device_id, address, local_key, version=version)


def cloud_client() -> tinytuya.Cloud:
    """Create a tinytuya Cloud client from tinytuya.json credentials.

    Searches cwd and project root for tinytuya.json.

    Raises:
        FileNotFoundError: No tinytuya.json found.
    """
    candidates = [
        Path.cwd() / "tinytuya.json",
        Path(__file__).resolve().parent.parent.parent.parent / "tinytuya.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        with open(path) as f:
            creds = json.load(f)
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
