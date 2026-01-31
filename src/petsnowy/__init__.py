"""petsnowy — Async Python library for local control of PetSnowy Snow+ litterbox."""

from .const import DPS, DeviceStatus, Fault, Notification
from .device import PetSnowy
from .exceptions import CommandError, ConnectionError, DeviceFaultError, PetSnowyError
from .models import DeviceState

__all__ = [
    "PetSnowy",
    "DeviceState",
    "DPS",
    "DeviceStatus",
    "Fault",
    "Notification",
    "PetSnowyError",
    "ConnectionError",
    "DeviceFaultError",
    "CommandError",
]
