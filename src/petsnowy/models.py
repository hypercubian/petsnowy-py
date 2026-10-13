"""Data models for PetSnowy device state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ._dps import dps_bool, dps_enum, dps_int
from .const import DPS, DeviceStatus, Fault, Notification


@dataclass(frozen=True)
class DeviceState:
    """Parsed snapshot of all PetSnowy device data points.

    Constructed via ``DeviceState.from_dps(raw_dict)`` which handles
    type coercion, missing keys, and the inverted child-lock DPS.
    """

    switch: bool
    auto_clean: bool
    delay_clean_time: int
    cat_weight: int
    excretion_count_today: int
    excretion_duration_today: int
    sleep_mode: bool
    light: bool
    notifications: Notification
    faults: Fault
    status: DeviceStatus
    filter_days_remaining: int
    child_locked: bool
    auto_deodorize: bool
    scheduled_deodorize: bool
    scheduled_clean: bool
    raw_dps: dict[str, Any]

    @property
    def cat_present(self) -> bool:
        """Return True if a cat is currently in the litter box."""
        return self.status == DeviceStatus.PET_INTO

    @classmethod
    def from_dps(cls, dps: dict[str, Any]) -> DeviceState:
        """Build a DeviceState from a raw DPS dict (string keys)."""

        def _bool(key: int) -> bool:
            return dps_bool(dps, key)

        def _int(key: int, default: int = 0) -> int:
            return dps_int(dps, key, default)

        # DPS 104 (lock) is inverted: false=locked, true=unlocked
        lock_raw = dps.get(str(DPS.LOCK))
        child_locked = not lock_raw if lock_raw is not None else False

        status = dps_enum(dps, DPS.STATUS, DeviceStatus, DeviceStatus.STANDBY)

        # DPS 6 (cat_weight) is not reported by the device. Weight is
        # encoded in DPS 116 (toilet_record) as a 4-byte hex string:
        # bytes 0-1 = weight in grams (big-endian), bytes 2-3 = duration in seconds.
        cat_weight = _int(DPS.CAT_WEIGHT) or _toilet_record_weight(
            dps.get(str(DPS.TOILET_RECORD))
        )

        return cls(
            switch=_bool(DPS.SWITCH),
            auto_clean=_bool(DPS.AUTO_CLEAN),
            delay_clean_time=_int(DPS.DELAY_CLEAN_TIME, 10),
            cat_weight=cat_weight,
            excretion_count_today=_int(DPS.EXCRETION_TIMES_DAY),
            excretion_duration_today=_int(DPS.EXCRETION_TIME_DAY),
            sleep_mode=_bool(DPS.SLEEP),
            light=_bool(DPS.LIGHT),
            notifications=Notification(_int(DPS.NOTIFICATION)),
            faults=Fault(_int(DPS.FAULT)),
            status=status,
            filter_days_remaining=_int(DPS.FILTER_DAYS),
            child_locked=child_locked,
            auto_deodorize=_bool(DPS.AUTO_DEODORIZE),
            scheduled_deodorize=_bool(DPS.SCHEDULED_DEODORIZE),
            scheduled_clean=_bool(DPS.SCHEDULED_CLEAN),
            raw_dps=dict(dps),
        )


def _toilet_record_weight(record: object) -> int:
    """Return the cat weight in grams from a DPS 116 hex record, or 0 if unparseable."""
    if not isinstance(record, str) or len(record) < 4:
        return 0
    try:
        return int(record[:4], 16)
    except ValueError:
        return 0
