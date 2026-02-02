"""Stream real-time DPS updates from a PetSnowy device."""

import asyncio
import os
import signal
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from petsnowy import Fault, Notification, PetSnowy  # noqa: E402
from petsnowy.const import DPS  # noqa: E402

DEVICE_ID = os.environ.get("PETSNOWY_DEVICE_ID", "your_device_id")
ADDRESS = os.environ.get("PETSNOWY_ADDRESS", "192.168.1.100")
LOCAL_KEY = os.environ.get("PETSNOWY_LOCAL_KEY", "your_local_key")

# Human-readable names for common DPS IDs
DPS_NAMES = {
    str(DPS.SWITCH): "switch",
    str(DPS.AUTO_CLEAN): "auto_clean",
    str(DPS.DELAY_CLEAN_TIME): "delay_clean_time",
    str(DPS.CAT_WEIGHT): "cat_weight",
    str(DPS.EXCRETION_TIMES_DAY): "excretion_count",
    str(DPS.EXCRETION_TIME_DAY): "excretion_time",
    str(DPS.MANUAL_CLEAN): "manual_clean",
    str(DPS.SLEEP): "sleep_mode",
    str(DPS.LIGHT): "light",
    str(DPS.DEODORIZATION): "deodorize",
    str(DPS.NOTIFICATION): "notification",
    str(DPS.FAULT): "fault",
    str(DPS.STATUS): "status",
    str(DPS.FILTER_DAYS): "filter_days",
    str(DPS.LOCK): "lock (inverted)",
    str(DPS.AUTO_DEODORIZE): "auto_deodorize",
    str(DPS.EMPTY): "empty_litter",
    str(DPS.PAUSE): "pause",
    str(DPS.CONTINUE): "resume",
}


def decode_update(dps: dict[str, object]) -> None:
    """Print a human-readable interpretation of a DPS update."""
    for key, value in dps.items():
        name = DPS_NAMES.get(key, f"dps_{key}")

        if key == str(DPS.NOTIFICATION) and isinstance(value, int):
            notif_flags = Notification(value)
            active = [n.name for n in Notification if n and n in notif_flags]
            print(f"  {name}: {active or 'none'}")
        elif key == str(DPS.FAULT) and isinstance(value, int):
            fault_flags = Fault(value)
            active = [ft.name for ft in Fault if ft and ft in fault_flags]
            print(f"  {name}: {active or 'none'}")
        else:
            print(f"  {name}: {value}")


async def main() -> None:
    stop = asyncio.Event()

    # Handle Ctrl+C gracefully
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

    print("Connecting to PetSnowy...")
    async with PetSnowy(DEVICE_ID, ADDRESS, LOCAL_KEY) as dev:
        # Print initial state
        state = await dev.get_state()
        print(f"Connected. Status: {state.status.value}")
        print("Monitoring for events (Ctrl+C to stop)...\n")

        update_count = 0
        async for update in dev.monitor():
            if stop.is_set():
                break

            update_count += 1
            print(f"--- Update #{update_count} ---")
            decode_update(update)
            print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
