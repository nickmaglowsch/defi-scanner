# Task 02: Database Schema & Flyway Migration → Alembic Migration

## Objective
Define SQLAlchemy ORM models for all 7 tables (`protocols`, `markets`, `lending_snapshots`, `funding_snapshots`, `loop_calculations`, `carry_calculations`, `alerts`), initialize Alembic, and create the first migration that enables the TimescaleDB extension and creates hypertables on the two snapshot tables.

## Context
All subsequent tasks depend on these models for database I/O. The schema must match the table definitions in `updated-prd.md` "Database Schema" section exactly. TimescaleDB hypertables require raw SQL in the migration (`CREATE EXTENSION`, `SELECT create_hypertable()`). SQLAlchemy models use standard ORM patterns — the hypertable aspect is invisible to the ORM (it's just a table with a time index to SQLAlchemy).

**Quick Context**: Alembic uses a sync engine (psycopg2 or asyncpg with sync wrapper) for DDL even though the app uses async SQLAlchemy. The `env.py` reads `DATABASE_URL` from `app.config`.

## Target Files
- `backend/app/models/__init__.py` (re-export all models)
- `backend/app/models/protocol.py`
- `backend/app/models/market.py`
- `backend/app/models/lending_snapshot.py`
- `backend/app/models/funding_snapshot.py`
- `backend/app/models/loop_calculation.py`
- `backend/app/models/carry_calculation.py`
- `backend/app/models/alert.py`
- `backend/alembic.ini`
- `backend/alembic/env.py`
- `backend/alembic/script.py.mako`
- `backend/alembic/versions/001_initial.py`

## Dependencies
- task-01 (needs `config.py` for DATABASE_URL, `db/session.py` for engine pattern)

## Steps
1. Add `psycopg2-binary` to `pyproject.toml` dev dependencies (Alembic needs a sync driver for DDL) — `uv add --dev psycopg2-binary`.
2. Write SQLAlchemy models (one file each, all use `declarative_base` from `app.db.session`):
   - **Protocol**: `id` (UUID PK, default `uuid4`), `name` (String, unique, nullable=False), `type` (String, nullable=False), `chain` (String), `risk_score` (Float, default 0), `created_at` (TIMESTAMPTZ, server_default `now()`).
   - **Market**: `id` (UUID PK), `protocol_id` (UUID FK → protocols.id), `asset` (String, nullable=False), `market_type` (String, nullable=False), `created_at` (TIMESTAMPTZ).
   - **LendingSnapshot**: `id` (UUID PK), `market_id` (UUID FK → markets.id), `observed_at` (TIMESTAMPTZ, nullable=False, index), all numeric fields per schema, `raw_payload` (JSONB, nullable). Unique constraint on `(market_id, observed_at)`.
   - **FundingSnapshot**: Same pattern as LendingSnapshot with funding-specific numeric fields + `raw_payload` JSONB. Unique constraint on `(market_id, observed_at)`.
   - **LoopCalculation**: All fields per schema, `calc_version` (String, default `"loop-v1"`), FK to `lending_snapshots.id`, `created_at`.
   - **CarryCalculation**: All fields per schema, `calc_version` (String, default `"carry-v1"`), FK to `funding_snapshots.id`, nullable FK to `lending_snapshots.id`, `created_at`.
   - **Alert**: All fields per schema, `fired_at` (TIMESTAMPTZ, server_default `now()`).
   - Use `from app.models import *` in `__init__.py` so Alembic auto-discovers all models via `Base.metadata`.
3. Ensure the shared declarative `Base` lives in `backend/app/db/session.py` (from task-01). If not already there, add it:
   ```python
   from sqlalchemy.orm import DeclarativeBase
   class Base(DeclarativeBase):
       pass
   ```
   All models import from `app.db.session import Base`.
4. Run `alembic init alembic` from `backend/`. Update `alembic.ini`: set `sqlalchemy.url` to read from env (or leave placeholder — `env.py` will override).
5. Rewrite `backend/alembic/env.py`:
   - Import `Base` from `app.db.session` and all models from `app.models` (so `Base.metadata` is populated).
   - Import `config.Settings` and use `settings.DATABASE_URL` with the sync driver: replace `+asyncpg` with `+psycopg2` (or construct a separate sync URL from config parts).
   - Set `target_metadata = Base.metadata`.
   - Configure both `run_migrations_online` (standard) and allow offline mode.
6. Generate initial migration: `alembic revision --autogenerate -m "initial"`. Verify the generated migration creates all 7 tables with correct columns.
7. Edit the migration file (`001_initial.py`) after the table creation DDL — add raw SQL in `upgrade()`:
   ```python
   op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
   op.execute("SELECT create_hypertable('lending_snapshots', 'observed_at', if_not_exists => TRUE)")
   op.execute("SELECT create_hypertable('funding_snapshots', 'observed_at', if_not_exists => TRUE)")
   ```
   And in `downgrade()`: drop hypertables then tables (or just drop tables — TimescaleDB handles cleanup).
8. Set `backend/PYTHONPATH` or adjust `env.py` so `from app.config import Settings` works. Simplest: add `sys.path.insert(0, ...)` in env.py.
9. Run `alembic upgrade head` against the Docker timescaledb to verify migration succeeds.
10. Add `ruff` format/lint pass on all new files.

## Acceptance Criteria
- [ ] `alembic upgrade head` succeeds against Docker timescaledb — all 7 tables exist
- [ ] `\dx` in psql shows `timescaledb` extension installed
- [ ] `SELECT * FROM timescaledb_information.hypertables` shows `lending_snapshots` and `funding_snapshots`
- [ ] `alembic downgrade -1` successfully drops hypertables and tables; re-upgrade works
- [ ] All models importable: `from app.models import Protocol, Market, LendingSnapshot, FundingSnapshot, LoopCalculation, CarryCalculation, Alert`
- [ ] `raw_payload` column is JSONB type on both snapshot tables
- [ ] `ruff check` passes on all files
