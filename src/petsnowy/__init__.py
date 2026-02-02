"""Petsnowy — Async Python library for local control of PetSnowy devices."""

from .const import DPS, DeviceStatus, Fault, Notification
from .device import PetSnowy
from .exceptions import CommandError, ConnectionError, DeviceFaultError, PetSnowyError
from .feeder import (
    Feeder,
    FeederDPS,
    FeederState,
    FoodStatus,
    MealSchedule,
    Weekday,
    decode_meal_plan,
    encode_meal_plan,
)
from .fountain import Fountain, FountainDPS, FountainState, WorkMode
from .models import DeviceState
from .purifier import Purifier, PurifierDPS, PurifierFault, PurifierMode, PurifierState

__all__ = [
    # Litterbox (original)
    "PetSnowy",
    "DeviceState",
    "DPS",
    "DeviceStatus",
    "Fault",
    "Notification",
    # Water Fountain
    "Fountain",
    "FountainState",
    "FountainDPS",
    "WorkMode",
    # Air Purifier
    "Purifier",
    "PurifierState",
    "PurifierDPS",
    "PurifierMode",
    "PurifierFault",
    # Pet Feeder
    "Feeder",
    "FeederState",
    "FeederDPS",
    "FoodStatus",
    "MealSchedule",
    "Weekday",
    "decode_meal_plan",
    "encode_meal_plan",
    # Exceptions
    "PetSnowyError",
    "ConnectionError",
    "DeviceFaultError",
    "CommandError",
]
