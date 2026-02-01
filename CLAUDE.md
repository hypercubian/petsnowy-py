## PetSnowy Utilities Pattern

- When the user asks a PetSnowy-related question or task in any session, implement it as a function in the appropriate per-device utility module:
  - Litterbox: `src/petsnowy/utils/litterbox.py`
  - Fountain: `src/petsnowy/utils/fountain.py`
  - Purifier: `src/petsnowy/utils/purifier.py`
  - Feeder: `src/petsnowy/utils/feeder.py`
- Reuse existing functions in the relevant module before creating new ones
- Each function should be self-contained, documented, and use the corresponding device class (`PetSnowy`, `Fountain`, `Purifier`, `Feeder`)
- For cross-device or shared helpers, use `src/petsnowy/utils/common.py`
