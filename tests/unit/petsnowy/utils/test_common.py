from __future__ import annotations

from petsnowy.const import DPS, Fault, Notification
from petsnowy.fountain import FountainDPS
from petsnowy.utils.common import flag_names, format_flags, format_update


def test_flag_names_lists_set_single_bit_members() -> None:
    assert flag_names(Fault.DRAWER | Fault.TOP_COVER, Fault) == ["TOP_COVER", "DRAWER"]
    assert flag_names(Fault.NONE, Fault) == []


def test_format_flags_empty_and_active() -> None:
    assert format_flags("FAULTS", "Faults", Fault.NONE, Fault) == [
        "  Faults:             None"
    ]
    assert format_flags("FAULTS", "Faults", Fault.DRAWER, Fault) == [
        "  FAULTS:",
        "    - DRAWER",
    ]


def test_format_update_expands_litterbox_bitmasks() -> None:
    update = {
        str(DPS.STATUS): "cleaning",
        str(DPS.NOTIFICATION): int(Notification.AUTO_CLEAN_DONE),
        str(DPS.FAULT): 0,
        "250": 1,
    }
    assert format_update(update, DPS) == [
        "  status: cleaning",
        "  notification: ['AUTO_CLEAN_DONE']",
        "  fault: none",
        "  dps_250: 1",
    ]


def test_format_update_uses_the_devices_own_names() -> None:
    # DPS 4 is pump_time on the fountain but auto_clean on the litterbox.
    assert format_update({"4": 3}, FountainDPS) == ["  pump_time: 3"]
    assert format_update({"4": True}, DPS) == ["  auto_clean: True"]
