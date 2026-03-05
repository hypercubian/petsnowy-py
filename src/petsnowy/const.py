"""DPS ID constants, enums, and bitmask definitions for PetSnowy Snow+."""

from enum import IntFlag, StrEnum


class DPS:
    """Tuya Data Point IDs for PetSnowy Snow+ (PS-001).

    Product ID: bdfimkssp9ews36b
    Source: tuya-local PR #2806 (petsnowy_snowplus_catlitter.yaml)
    """

    SWITCH = 1
    AUTO_CLEAN = 4
    DELAY_CLEAN_TIME = 5  # 2-60 minutes, step 2
    CAT_WEIGHT = 6  # grams, read-only
    EXCRETION_TIMES_DAY = 7  # 0-60, read-only
    EXCRETION_TIME_DAY = 8  # 0-1800 seconds, read-only
    MANUAL_CLEAN = 9  # momentary button
    SLEEP = 10
    LIGHT = 16
    DEODORIZATION = 17  # momentary button
    NOTIFICATION = 21  # bitmask, read-only
    FAULT = 22  # bitmask, read-only
    FACTORY_RESET = 23
    STATUS = 24  # enum string, read-only
    FILTER_RESET = 101  # momentary button
    FILTER_DAYS = 102  # read-only
    AVERAGE_TIMES = 103  # read-only
    LOCK = 104  # INVERTED: false=locked, true=unlocked
    PERIODIC_CLEANING = 105  # raw bytes
    SLEEP_TIME = 106  # string, sleep schedule
    AUTO_DEODORIZE = 107
    PERIODIC_DEODORIZE = 108  # raw/string, schedule
    EMPTY = 109  # momentary button
    PAUSE = 110  # momentary button
    CONTINUE = 111  # momentary button
    BALL_RESET = 112  # momentary button (weight calibration)
    CLEANED_COMPLETE = 113  # read-only
    RESET_COMPLETE = 114  # read-only
    EMPTY_CANCEL = 115  # momentary button
    TOILET_RECORD = 116  # string, read-only
    T_D_SW = 117  # unknown
    T_CLEASW = 118  # unknown


class DeviceStatus(StrEnum):
    """Device operating state (DPS 24)."""

    STANDBY = "standby"
    CLEANING = "cleaning"
    DEODORIZATION = "deodorization"
    SLEEP = "sleep"
    PET_INTO = "pet_into"


class Notification(IntFlag):
    """Event notification bitmask (DPS 21).

    Multiple flags can be set.
    """

    NONE = 0
    MANUAL_CLEAN_DONE = 1 << 0
    AUTO_CLEAN_DONE = 1 << 1
    TIMED_CLEAN_DONE = 1 << 2
    MANUAL_CLEAN_CANCELED = 1 << 3
    MANUAL_DEODORIZE_DONE = 1 << 4
    AUTO_DEODORIZE_DONE = 1 << 5
    TIMED_DEODORIZE_DONE = 1 << 6
    EMPTY_LITTER_DONE = 1 << 7
    WEIGHT_RESET = 1 << 8
    SELF_CHECK_OK = 1 << 9
    BUTTON_LOCKED = 1 << 10
    BUTTON_UNLOCKED = 1 << 11
    LIGHT_ON = 1 << 12
    LIGHT_OFF = 1 << 13
    PAUSE_CLEANING = 1 << 14
    SLEEP_ON = 1 << 15
    SLEEP_OFF = 1 << 16
    CANCEL_EMPTY = 1 << 17
    CHANGE_LITTER = 1 << 18


class Fault(IntFlag):
    """Device fault bitmask (DPS 22).

    Value of 0 means no faults.
    """

    NONE = 0
    TOP_COVER = 1 << 0
    DRAWER = 1 << 1
    DRAWER_FULL = 1 << 2
    CAT_STUCK = 1 << 3
    CHECK_FAULT = 1 << 4
    CAT_STAYED_LONG = 1 << 5
    TROUBLE_REMOVAL = 1 << 6
