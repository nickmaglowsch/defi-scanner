# Task 01 — Database Migrations

## Objective

Evolve the database schema to support multi-chain markets, reward APY, cross-protocol calculations, and strategy-specific risk penalties.

## Context

The current schema assumes one chain per protocol, no reward yield, and only Loop/Carry calculations. The planning decisions require adding `chain` to `Market`, `reward_apy` to `LendingSnapshot`, a new `CrossProtocolCalculation` table, and penalty storage on calculation rows.

## Requirements

1. Add a nullable `chain` column to the `markets` table and the `Market` model.
2. Add a nullable `reward_apy` column to `lending_snapshots` and the `LendingSnapshot` model.
3. Create a new `cross_protocol_calculations` table and SQLAlchemy model with:
   - `id` UUID PK
   - `deposit_market_id` (UUID, FK to markets.id)
   - `borrow_market_id` (UUID, FK to markets.id)
   - `calc_version` string default `cross-protocol-v1`
   - `deposit_apy`, `borrow_apy`, `net_spread`, `leverage`, `risk_score`
   - `created_at` timestamp
   - Any strategy-specific penalty fields as nullable floats
4. Add a nullable JSONB `penalty_breakdown` column to `loop_calculations`, `carry_calculations`, and `cross_protocol_calculations` to store strategy-specific penalty components.
5. Create an Alembic migration file that applies these changes idempotently.
6. Update `app/models/__init__.py` to export the new model.

## Target Files

- `backend/app/models/market.py`
- `backend/app/models/lending_snapshot.py`
- `backend/alembic/versions/003_expand_opportunity_universe.py` (new)
- `backend/app/models/cross_protocol_calculation.py` (new)
- `backend/app/models/__init__.py`
- `backend/app/models/loop_calculation.py`
- `backend/app/models/carry_calculation.py`

## Dependencies

None.

## TDD Mode

Yes.

- Write a migration test that creates the tables via Alembic `upgrade`, then assert columns exist and foreign keys are correct.
- Write model import/attribute tests before adding fields.

## Acceptance Criteria

1. `alembic upgrade head` succeeds on a fresh database.
2. `pytest backend/tests/test_migrations.py` (new) passes.
3. All existing tests still pass.
4. `Market`, `LendingSnapshot`, and `CrossProtocolCalculation` expose the new fields.

## Notes

- `chain` is added to `Market`, not `Protocol`, per planning decision Q1-B.
- `reward_apy` is top-level; token details remain in `raw_payload`, per Q3-C.
- Penalty fields are kept generic via `penalty_breakdown` JSONB so the ranker can add metrics without further migrations.
