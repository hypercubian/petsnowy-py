"""Read and display the current PetSnowy device state."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from petsnowy import PetSnowy, Fault, Notification

# Replace with your actual credentials
DEVICE_ID = os.environ.get("PETSNOWY_DEVICE_ID", "your_device_id")
ADDRESS = os.environ.get("PETSNOWY_ADDRESS", "192.168.1.100")
LOCAL_KEY = os.environ.get("PETSNOWY_LOCAL_KEY", "your_local_key")


async def main() -> None:
    async with PetSnowy(DEVICE_ID, ADDRESS, LOCAL_KEY) as dev:
        state = await dev.get_state()

        print("=== PetSnowy Snow+ Status ===\n")
        print(f"  Status:             {state.status.value}")
        print(f"  Switch:             {'ON' if state.switch else 'OFF'}")
        print(f"  Auto-clean:         {'ON' if state.auto_clean else 'OFF'}")
        print(f"  Clean delay:        {state.delay_clean_time} min")
        print(f"  Cat weight:         {state.cat_weight} g")
        print(f"  Excretions today:   {state.excretion_count_today}")
        print(f"  Excretion time:     {state.excretion_duration_today} s")
        print(f"  Sleep mode:         {'ON' if state.sleep_mode else 'OFF'}")
        print(f"  Light:              {'ON' if state.light else 'OFF'}")
        print(f"  Child lock:         {'LOCKED' if state.child_locked else 'UNLOCKED'}")
        print(f"  Auto-deodorize:     {'ON' if state.auto_deodorize else 'OFF'}")
        print(f"  Filter remaining:   {state.filter_days_remaining} days")

        # Decode notifications
        if state.notifications:
            print(f"\n  Notifications:")
            for flag in Notification:
                if flag and flag in state.notifications:
                    print(f"    - {flag.name}")

        # Decode faults
        if state.faults:
            print(f"\n  FAULTS:")
            for flag in Fault:
                if flag and flag in state.faults:
                    print(f"    - {flag.name}")
        else:
            print(f"\n  Faults:             None")

        print(f"\n  Raw DPS: {state.raw_dps}")


if __name__ == "__main__":
    asyncio.run(main())
