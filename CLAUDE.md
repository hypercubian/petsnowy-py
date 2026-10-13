# CLAUDE.md

`petsnowy` (repo `petsnowy-py`): async library and CLI for local-network control of
PetSnowy devices (litterbox, fountain, purifier, feeder) over the Tuya protocol via
tinytuya. Follows hypercubian-qa-platinum-standards.

## Common commands

```bash
poetry install --with dev
poetry run pre-commit install            # installs pre-commit AND pre-push hooks
poetry run pytest                        # unit + integration + functional (e2e deselected)
PETSNOWY_E2E=1 poetry run pytest -m e2e  # read-only, real devices on the LAN
poetry run pre-commit run --all-files
poetry run mypy src
poetry run pylint --errors-only src/petsnowy
poetry run bandit -r src/petsnowy -c pyproject.toml
```

On Windows sandboxes where the system temp dir is not writable, add
`--basetemp=<writable dir>` to pytest.

## Architecture

```
cli.py ──> registry.py ──> device classes ──> base.py ──> tinytuya.Device (LAN)
  │            │                (device.py, fountain.py, purifier.py, feeder.py)
  └──> utils/<device>.py (format_status, get_status, ...) ──> utils/common.py
```

- `base.BasePetDevice`: connection lifecycle, `_set_dps`, `_send_button`, `monitor()`.
  All blocking tinytuya I/O runs in threads (`asyncio.to_thread` / executor).
- `<device>State.from_dps`: pure parsers built on the tolerant readers in `_dps.py`.
- `registry.py`: the single table of device types (`DEVICE_SPECS`) and credential
  resolution: `PETSNOWY_*` env vars, then `devices.json` (`PETSNOWY_DEVICES_JSON`
  overrides the search path).
- `cli.py`: parse (`parse_args`), run one invocation (`run`), map errors to exit codes
  (0 ok, 1 device/connection error, 2 usage error). Commands are a declarative table.

## Tests

- Four tiers under `tests/{unit,integration,functional,e2e}`. `tests/conftest.py`
  marks each test by its directory and blocks real credentials for non-e2e tests.
- `petsnowy.testing` (in `src/`, shipped so ha-petsnowy reuses it) is the mock harness: a fake `tinytuya.Device` network with
  per-device DPS state, key/version/reachability checks, momentary buttons, firmware
  reactions and a monitor event queue. Use the `fake_tuya`, `use_device` and
  per-device fixtures. Do not mock the device classes themselves.
- BDD lives in `tests/functional/features/` with steps in `step_definitions/`.

## Conventions specific to this repo

- `ConnectionError` in `petsnowy.exceptions` deliberately shadows the builtin. It is
  public API.
- DPS 104 (child lock) is inverted on the device: false = locked.
- Cat weight comes from DPS 116 (toilet record, hex), not DPS 6.
- `print()` is allowed only in `cli.py` and `utils/` (the interactive helpers).
  Everything else logs.
- Secrets (`devices.json`, `tinytuya.json`, captures) are gitignored. Never commit
  them.

## PetSnowy Utilities Pattern

- When the user asks a PetSnowy-related question or task in any session, implement it as a function in the appropriate per-device utility module:
  - Litterbox: `src/petsnowy/utils/litterbox.py`
  - Fountain: `src/petsnowy/utils/fountain.py`
  - Purifier: `src/petsnowy/utils/purifier.py`
  - Feeder: `src/petsnowy/utils/feeder.py`
- Reuse existing functions in the relevant module before creating new ones
- Each function should be self-contained, documented, and use the corresponding device class (`PetSnowy`, `Fountain`, `Purifier`, `Feeder`)
- For cross-device or shared helpers, use `src/petsnowy/utils/common.py`
