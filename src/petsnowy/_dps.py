"""Tolerant readers for raw Tuya DPS dicts (string keys, loosely typed values)."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from enum import Enum
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

E = TypeVar("E", bound=Enum)


def dps_bool(dps: Mapping[str, Any], key: int, default: bool = False) -> bool:
    value = dps.get(str(key))
    return bool(value) if value is not None else default


def dps_int(dps: Mapping[str, Any], key: int, default: int = 0) -> int:
    """Return DPS ``key`` as an int, or ``default`` when missing or non-numeric.

    A single malformed value from firmware must not make the whole state snapshot
    unreadable, so bad values are logged and replaced rather than raised.
    """
    value = dps.get(str(key))
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        logger.warning("DPS %s: expected an int, got %r", key, value)
        return default


def dps_str(dps: Mapping[str, Any], key: int, default: str = "") -> str:
    value = dps.get(str(key))
    return str(value) if value is not None else default


def dps_enum(dps: Mapping[str, Any], key: int, enum_cls: type[E], default: E) -> E:
    """Return DPS ``key`` as a member of ``enum_cls``, or ``default`` if unknown."""
    value = dps.get(str(key))
    if value is None:
        return default
    try:
        return enum_cls(value)
    except ValueError:
        logger.warning("DPS %s: unknown %s value %r", key, enum_cls.__name__, value)
        return default


def dps_names(dps_cls: type) -> dict[str, str]:
    """Map DPS id strings to lower-case names from a ``*DPS`` constants class."""
    return {
        str(value): name.lower()
        for name, value in vars(dps_cls).items()
        if name.isupper() and isinstance(value, int)
    }
