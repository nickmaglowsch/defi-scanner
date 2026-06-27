# Task 01 — Database Migrations — Implementation Notes

## What changed

- `backend/app/models/market.py`
  - Added nullable `chain` column to the `Market` model.
- `backend/app/models/lending_snapshot.py`
  - Added nullable `reward_apy` column to the `LendingSnapshot` model.
- `backend/app/models/cross_protocol_calculation.py` (new)
  - New `CrossProtocolCalculation` model with FKs to `markets.id`, metric fields, and `penalty_breakdown` JSONB.
- `backend/app/models/loop_calculation.py`
  - Added nullable `penalty_breakdown` JSONB column.
- `backend/app/models/carry_calculation.py`
  - Added nullable `penalty_breakdown` JSONB column.
- `backend/app/models/__init__.py`
  - Exports `CrossProtocolCalculation`.
- `backend/alembic/versions/003_expand_opportunity_universe.py` (new)
  - Idempotent-by-alembic migration applying all schema changes.
- `backend/tests/test_migrations.py` (new)
  - Model attribute tests and migration schema tests against a fresh test database.

## Test results

- `pytest backend/tests/test_migrations.py` — 9 passed.
- `pytest backend/tests` — 195 passed (after running `alembic upgrade head` on the dev database).
- `alembic upgrade head` succeeds on a fresh database (verified by the migration test fixture).

## Decisions

- Added `chain` to `Market` instead of `Protocol` per planning decision Q1-B.
- Stored reward yield as a top-level `reward_apy` float on `LendingSnapshot`; token details remain in `raw_payload` per Q3-C.
- Kept penalties generic via a single `penalty_breakdown` JSONB column on `loop_calculations`, `carry_calculations`, and `cross_protocol_calculations` so the ranker can add metrics without further migrations.
- Used a dedicated throwaway test database for migration tests to avoid touching the developer database.

## Deviations

- Skipped adding individual nullable float penalty fields on `cross_protocol_calculations`; requirement 3 mentioned them but the project note explicitly says penalties are generic via JSONB. The JSONB column covers all strategy-specific penalty components.

## Trade-offs

- JSONB penalty storage trades direct column queryability for flexibility and zero future migration churn as penalty metrics evolve.
- Creating and dropping a fresh database per migration test module adds overhead but guarantees isolation and accurately tests `alembic upgrade head` on a clean schema.

## Risks

- Existing tests now require the developer database to be migrated to head before passing; `alembic upgrade head` is part of the local test workflow.
- Migration tests assume the `defi` PostgreSQL user has `CREATEDB`; if that privilege is revoked, the test fixture will fail.
