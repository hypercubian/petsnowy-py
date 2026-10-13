from __future__ import annotations

import pytest

from petsnowy.cli import (
    DEVICE_COMMANDS,
    Invocation,
    UsageError,
    choice,
    format_help,
    main,
    parse_args,
    parse_bool,
    parse_int,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("on", True), ("TRUE", True), ("yes", True), ("off", False), ("0", False)],
)
def test_parse_bool(raw: str, expected: bool) -> None:
    assert parse_bool(raw) is expected


def test_parse_bool_rejects_other_words() -> None:
    with pytest.raises(UsageError, match="expected on/off"):
        parse_bool("maybe")


def test_parse_int() -> None:
    assert parse_int("12") == 12
    with pytest.raises(UsageError, match="whole number"):
        parse_int("1.5")


def test_choice_is_case_insensitive() -> None:
    parse = choice("auto", "sleep")
    assert parse("AUTO") == "auto"
    with pytest.raises(UsageError, match="auto|sleep"):
        parse("turbo")


def test_parse_args_defaults_to_litterbox() -> None:
    assert parse_args(["clean"]) == Invocation("litterbox", False, "clean")


@pytest.mark.parametrize("flag", [["--device", "Fountain"], ["--device=fountain"]])
def test_parse_args_device_flag_forms(flag: list[str]) -> None:
    inv = parse_args([*flag, "set-filter-reminder", "30"])
    assert inv == Invocation("fountain", True, "set-filter-reminder", 30)


@pytest.mark.parametrize("argv", [[], ["help"], ["-h"], ["--help"]])
def test_parse_args_help_has_no_command(argv: list[str]) -> None:
    assert parse_args(argv).command is None


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["--device"], "--device needs a value"),
        (["--device", "toaster", "status"], "Unknown device type: toaster"),
        (["dance"], "Unknown litterbox command: dance"),
        (["clean-delay"], "clean-delay <minutes>"),
        (["clean", "now"], "Usage: petsnowy --device litterbox clean"),
        (["light", "dim"], "expected on/off"),
        (["--device", "purifier", "set-speed", "9"], "expected one of 1|2|3|4|5|6"),
    ],
)
def test_parse_args_usage_errors(argv: list[str], message: str) -> None:
    with pytest.raises(UsageError, match=message.replace("|", r"\|")):
        parse_args(argv)


def test_every_command_has_exactly_one_of_method_or_action() -> None:
    for commands in DEVICE_COMMANDS.values():
        for name, cmd in commands.items():
            assert (cmd.method is None) != (cmd.action is None), name


def test_format_help_for_one_device_lists_only_its_commands() -> None:
    text = format_help("feeder")
    assert "Feeder commands:" in text
    assert "feed <portions>" in text
    assert "Litterbox commands:" not in text


def test_format_help_for_all_devices() -> None:
    text = format_help()
    for device_type in DEVICE_COMMANDS:
        assert f"{device_type.capitalize()} commands:" in text


def test_main_usage_error_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["dance"]) == 2
    assert "Unknown litterbox command" in capsys.readouterr().err


def test_main_help_exits_0(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--device", "purifier"]) == 0
    assert "Purifier commands:" in capsys.readouterr().out
