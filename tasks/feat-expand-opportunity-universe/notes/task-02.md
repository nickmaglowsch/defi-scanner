# Task 02 — Protocol Registry Config + Loader — Implementation Notes

## What changed

- `backend/app/protocols/registry.yaml` (new)
  - Human-editable YAML registry with `version` and a `registry` list.
  - Entries for every required protocol: Aave V3 (Ethereum, Base, Arbitrum, Optimism, Polygon), Morpho, Spark, Euler, Fluid, Moonwell, Compound, Silo, Hyperliquid, GMX, Drift, Vertex, dYdX.
  - Placeholder entries for stable lending, staking (Lido, Rocket Pool), restaking (EigenLayer, ether.fi), and Pendle.
  - Unknown contract addresses are zeroed / empty with inline `ponytail:` comments explaining the blocker.

- `backend/app/protocols/registry.py` (new)
  - `RegistryEntry` and `Registry` frozen dataclasses.
  - `load_registry(path=None)` parses YAML, validates required fields, and returns typed objects.
  - `get_protocol_entries(registry, protocol, chain=None)` filters by display name or slug, optionally by chain.
  - `RegistryValidationError` raised with a clear message on malformed entries.
  - Reads `DEFI_PROTOCOL_REGISTRY_PATH` from settings when no path is supplied.

- `backend/app/protocols/__init__.py` (new)
  - Re-exports the public registry API.

- `backend/app/config.py`
  - Added `DEFI_PROTOCOL_REGISTRY_PATH: str = ""` setting so tests and forks can override the registry location.

- `backend/pyproject.toml` / `backend/uv.lock`
  - Added `pyyaml>=6.0` as a direct dependency and refreshed the lockfile.

- `backend/tests/test_protocol_registry.py` (new)
  - TDD tests: fixture-based registry parsing, default-path loading, filter helpers, validation errors, and acceptance-criteria coverage checks.

## Test results

- `pytest backend/tests/test_protocol_registry.py` — 18 passed.
- Focused broader run (`test_protocol_registry`, `test_ranker`, `test_rating`, `test_looping`, `test_carry`, `test_api`, `test_aave_adapter`, `test_hyperliquid_adapter`, `test_protocol_metadata`) — 167 passed.

## Blockers / follow-ups

- Several protocol/chain entries use placeholder addresses (`0x0000...` or empty strings) marked with `ponytail:` comments. These need real contract/endpoint research before collectors can fetch live data for those deployments.
- Full suite has pre-existing failures in `test_history_agg.py` and `test_migrations.py` (missing `chain` column, `reward_apy`, `penalty_breakdown`, `cross_protocol_calculations` table). These are unrelated to this task; the new registry code does not touch those models or migrations.
