"""Guide and helper for extracting Tuya device credentials.

Run this script for step-by-step instructions on how to obtain the device_id, local_key,
and IP address needed to control your PetSnowy.
"""

import json
from pathlib import Path


def print_guide() -> None:
    print(
        """
=== PetSnowy Tuya Credential Setup ===

You need three values to control your PetSnowy locally:
  1. Device ID   — unique identifier for your litterbox
  2. Local Key   — encryption key for LAN communication
  3. IP Address   — your device's local network address

--- Step 1: Install tinytuya ---

    pip install tinytuya

--- Step 2: Discover your device on the network ---

    python -m tinytuya scan

  This will show devices on your LAN, including IP and Device ID.
  Note: the Local Key will show as blank until you complete Step 5.

--- Step 3: Create a Tuya IoT Developer account ---

  1. Go to https://iot.tuya.com and create an account
  2. Create a new Cloud Project (any name, e.g. "PetSnowy Control")
  3. Select your data center region (should match your PetSnowy app region)
  4. Subscribe to these APIs in the project:
     - IoT Core
     - Smart Home Basic Service
     - Authorization Token Management

--- Step 4: Link your PetSnowy app account ---

  In the Tuya IoT Platform:
  1. Go to Cloud > Development > your project
  2. Click the "Devices" tab
  3. Click "Link Tuya App Account"
  4. Open the PetSnowy app on your phone
  5. Go to Me > Settings and scan the QR code shown on the Tuya platform

--- Step 5: Run the tinytuya wizard ---

    python -m tinytuya wizard

  When prompted, enter:
  - API Key (Access ID) from your Tuya Cloud project
  - API Secret from your Tuya Cloud project
  - Your device ID (from Step 2 scan)
  - Your data center region

  This generates a devices.json file with your Local Key.

--- Step 6: Use your credentials ---

  Once you have all three values, use them like this:

    from petsnowy import PetSnowy

    async with PetSnowy(
        device_id="your_device_id",
        address="192.168.1.xxx",
        local_key="your_local_key",
    ) as dev:
        state = await dev.get_state()
        print(state)
"""
    )


def check_devices_json() -> None:
    """Look for an existing devices.json from tinytuya wizard."""
    candidates = [
        Path("devices.json"),
        Path.home() / "devices.json",
    ]
    for path in candidates:
        if path.exists():
            print(f"\nFound {path}! Extracting PetSnowy credentials...\n")
            with open(path) as f:
                devices = json.load(f)
            for dev in devices:
                name = dev.get("name", "").lower()
                category = dev.get("category", "")
                # PetSnowy devices are in the msp (smart pet) category
                if "petsnowy" in name or "snow" in name or category == "msp":
                    print(f"  Device:    {dev.get('name')}")
                    print(f"  Device ID: {dev.get('id')}")
                    print(f"  Local Key: {dev.get('key')}")
                    print(f"  IP:        {dev.get('ip', 'run tinytuya scan to find')}")
                    print(f"  Version:   {dev.get('version', '3.4')}")
                    return
            print("  No PetSnowy device found in devices.json.")
            print(
                "  Make sure your PetSnowy app account is linked"
                " in the Tuya IoT Platform."
            )
            return
    print("\nNo devices.json found. Follow the guide above to generate one.")


if __name__ == "__main__":
    print_guide()
    check_devices_json()
