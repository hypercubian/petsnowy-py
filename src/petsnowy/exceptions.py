"""Custom exceptions for the petsnowy library."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .const import Fault


class PetSnowyError(Exception):
    """Base exception for all petsnowy errors."""


class ConnectionError(PetSnowyError):
    """Device is unreachable or connection failed."""


class DeviceFaultError(PetSnowyError):
    """Device is reporting one or more hardware faults."""

    def __init__(self, faults: Fault) -> None:
        self.faults = faults
        super().__init__(f"Device fault(s): {faults!r}")


class CommandError(PetSnowyError):
    """A command was rejected or failed to execute."""
