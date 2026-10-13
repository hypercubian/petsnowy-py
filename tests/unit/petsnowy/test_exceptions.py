from __future__ import annotations

from petsnowy.const import Fault
from petsnowy.exceptions import (
    CommandError,
    ConnectionError,
    CredentialsNotFoundError,
    DeviceFaultError,
    PetSnowyError,
)


def test_all_errors_share_the_library_base() -> None:
    for exc in (CommandError, ConnectionError, CredentialsNotFoundError):
        assert issubclass(exc, PetSnowyError)


def test_device_fault_error_carries_faults() -> None:
    err = DeviceFaultError(Fault.DRAWER | Fault.CAT_STUCK)
    assert err.faults == Fault.DRAWER | Fault.CAT_STUCK
    assert "DRAWER" in str(err)
