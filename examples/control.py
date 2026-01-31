"""Send commands to a PetSnowy device."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from petsnowy import PetSnowy

DEVICE_ID = os.environ.get("PETSNOWY_DEVICE_ID", "your_device_id")
ADDRESS = os.environ.get("PETSNOWY_ADDRESS", "192.168.1.100")
LOCAL_KEY = os.environ.get("PETSNOWY_LOCAL_KEY", "your_local_key")


async def main() -> None:
    async with PetSnowy(DEVICE_ID, ADDRESS, LOCAL_KEY) as dev:
        state = await dev.get_state()
        print(f"Current status: {state.status.value}")

        # Toggle the light
        new_light = not state.light
        print(f"Toggling light to {'ON' if new_light else 'OFF'}...")
        await dev.set_light(new_light)

        # Read back to confirm
        state = await dev.get_state()
        print(f"Light is now: {'ON' if state.light else 'OFF'}")

        # Uncomment to trigger other commands:
        # await dev.deodorize()           # Start deodorization
        # await dev.clean()               # Start manual clean
        # await dev.set_auto_clean(True)  # Enable auto-clean
        # await dev.set_clean_delay(10)   # 10 min delay before auto-clean
        # await dev.set_child_lock(True)  # Lock buttons
        # await dev.empty_litter()        # Dump waste bin
        # await dev.pause()               # Pause current operation
        # await dev.resume()              # Resume paused operation


if __name__ == "__main__":
    asyncio.run(main())
