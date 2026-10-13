"""Read-only smoke test against real devices on the LAN.

Opt in with ``PETSNOWY_E2E=1 poetry run pytest -m e2e``. Credentials come from
devices.json (PETSNOWY_DEVICES_JSON or the default search paths), not PETSNOWY_*
env vars, which describe a single device. Device types not listed there are
skipped. Nothing is written to any device.
"""

from __future__ import annotations

import os

import pytest

from petsnowy.registry import DEVICE_SPECS, create_device, credentials_from_devices_json

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("PETSNOWY_E2E") != "1",
        reason="set PETSNOWY_E2E=1 to run against real devices",
    ),
]


@pytest.mark.parametrize("device_type", list(DEVICE_SPECS))
async def test_reads_state(device_type: str) -> None:
    try:
        creds = credentials_from_devices_json(device_type)
    except (FileNotFoundError, KeyError):
        pytest.skip(f"no {device_type} entry in devices.json")

    async with create_device(device_type, creds) as dev:
        state = await dev.get_state()  # type: ignore[attr-defined]

    assert state.raw_dps, f"{device_type} returned no data points"
