# petsnowy-py

Async Python library and CLI for local-network control of PetSnowy pet devices over
the Tuya protocol (via [tinytuya](https://github.com/jasonacox/tinytuya)). No cloud
round-trip is needed for day-to-day control.

| Device | Model | Class | Tuya protocol |
|--------|-------|-------|---------------|
| Snow+ self-cleaning litterbox | PS-001 | `PetSnowy` | 3.4 |
| Water fountain | PS-010 | `Fountain` | 3.3 |
| Air purifier | n/a | `Purifier` | 3.4 |
| Pet feeder | PS-020 | `Feeder` | 3.3 |

## Install

```bash
poetry add git+https://github.com/hypercubian/petsnowy-py.git@v0.2.0
```

This installs the `petsnowy` console script (also runnable as `python -m petsnowy`):

```text
petsnowy [--device litterbox|fountain|purifier|feeder] <command> [args]
petsnowy --device fountain help
```

## Configuration

Each device needs its Tuya device id, LAN address and local key. The CLI resolves
them in this order:

1. Environment variables `PETSNOWY_DEVICE_ID`, `PETSNOWY_ADDRESS`,
   `PETSNOWY_LOCAL_KEY`, plus an optional `PETSNOWY_VERSION`.
2. A `devices.json` file (tinytuya wizard output) in the current directory or the
   repository root. Each entry is matched to a device type by `product_id` or
   `category`.

Generate `devices.json` with `python -m tinytuya wizard`
(`docs/examples/credentials.py` walks through it). Cloud-only reads, such as the
feeder meal plan, also need the wizard's `tinytuya.json`. Both files contain
secrets and are gitignored. Never commit them.

## Usage

Library:

```python
import asyncio

from petsnowy import PetSnowy


async def main() -> None:
    async with PetSnowy("device_id", "192.168.1.100", "local_key") as dev:
        state = await dev.get_state()
        print(state.status, state.cat_weight, state.cat_present)
        await dev.deodorize()

        async for update in dev.monitor():  # live DPS updates, auto-reconnects
            print(update)


asyncio.run(main())
```

CLI:

```bash
petsnowy status                              # litterbox (default device)
petsnowy clean
petsnowy clean-delay 10
petsnowy monitor
petsnowy --device fountain set-work-mode night
petsnowy --device purifier set-speed 3
petsnowy --device feeder feed 2
```

The exit code is 0 on success, 1 on a device or connection error, and 2 on a usage
error. More runnable scripts are in `docs/examples/`.

## Development

```bash
poetry install --with dev
poetry run pre-commit install        # installs pre-commit AND pre-push hooks
poetry run pytest                    # unit + integration + functional
```

| Tier | Path | Runs against |
|------|------|--------------|
| unit | `tests/unit/` | Pure parsers, encoders, CLI helpers |
| integration | `tests/integration/` | Real `devices.json` on disk, CLI subprocess |
| functional | `tests/functional/` | Public API and CLI against the fake-Tuya harness (incl. BDD) |
| e2e | `tests/e2e/` | A real device on the LAN, read-only. `PETSNOWY_E2E=1 poetry run pytest -m e2e` |

`petsnowy.testing` (shipped with the package) holds the mock harness: an in-memory stand-in for
`tinytuya.Device` that keeps per-device DPS state, applies writes, resets momentary
buttons and replays monitor events. The `fake_tuya` fixture patches it in at the
`tinytuya` boundary, so every layer above it runs for real.

Lint and type-check as CI does:

```bash
poetry run pre-commit run --all-files
poetry run mypy src
poetry run pylint --errors-only src/petsnowy
poetry run bandit -r src/petsnowy -c pyproject.toml
```

The project follows
[hypercubian-qa-platinum-standards](https://github.com/hypercubian/hypercubian-qa-platinum-standards).

## License

MIT. See [LICENSE](LICENSE).
