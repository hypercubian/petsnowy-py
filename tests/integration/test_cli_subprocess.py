"""The CLI as a real subprocess: entry point wiring, exit codes, stderr."""

from __future__ import annotations

import os
import subprocess  # nosec B404 - runs this package's own CLI
import sys
from pathlib import Path

import pytest


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("PETSNOWY_")}
    # Points at a file that does not exist, so a real devices.json is never used.
    env["PETSNOWY_DEVICES_JSON"] = str(cwd / "devices.json")
    return subprocess.run(  # nosec B603 - fixed argv, no shell
        [sys.executable, "-m", "petsnowy", *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd,
        env=env,
        timeout=60,
    )


def test_help_exits_0(tmp_path: Path) -> None:
    result = _run("--help", cwd=tmp_path)

    assert result.returncode == 0
    assert "Usage: petsnowy" in result.stdout
    assert "Feeder commands:" in result.stdout


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("dance",), "Unknown litterbox command: dance"),
        (("--device", "toaster", "status"), "Unknown device type: toaster"),
        (("clean-delay",), "clean-delay <minutes>"),
    ],
)
def test_usage_errors_exit_2(
    tmp_path: Path, args: tuple[str, ...], message: str
) -> None:
    result = _run(*args, cwd=tmp_path)

    assert result.returncode == 2
    assert message in result.stderr


def test_missing_credentials_exit_1(tmp_path: Path) -> None:
    result = _run("status", cwd=tmp_path)

    assert result.returncode == 1
    assert "No litterbox credentials found" in result.stderr
    assert "Traceback" not in result.stderr
