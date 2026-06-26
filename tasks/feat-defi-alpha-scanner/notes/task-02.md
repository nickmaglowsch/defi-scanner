# Task 02: Database Schema & Migrations

- **Decisions**: 
  - Used string UUIDs (`String(36)`) as primary keys rather than native `UUID` type — simpler application-side generation, no driver-specific UUID handling.
  - Snapshot tables use composite PK `(id, observed_at)` with no unique constraint on `id` alone — required by TimescaleDB (partition column must be in all unique indexes). FK references from calculation tables (`loop_calculations.lending_snapshot_id`, `carry_calculations.funding_snapshot_id`, `carry_calculations.lending_snapshot_id`) are soft references (plain columns, no DB-level FK). UUIDs guarantee uniqueness at the application level. This is the standard pattern seen in TimescaleDB projects with hypertables that have child-table references.
  - Alembic `env.py` constructs sync URL by replacing `+asyncpg` with `+psycopg2` — matching the existing config approach, no need for a separate sync database URL configuration.
  - Unitended side effect: the `Func` import from sqlalchemy was not used in lending_snapshot.py and funding_snapshot.py — kept `import` to match the `func` call on `server_default` for other models, but removed on snapshots (no `func.now()` col needed).

- **Deviations**: 
  - FK constraints removed from `loop_calculations.lending_snapshot_id` and `carry_calculations.funding_snapshot_id` (and `carry_calculations.lending_snapshot_id`) — technically a deviation from the PRD which shows FK arrows, but necessary for TimescaleDB compatibility. The PRD arrows are logical references, not necessarily DB-level constraints.
  - `alembic revision --autogenerate` not possible without a live DB; wrote migration manually from model definitions.

- **Trade-offs**: 
  - Could have used a separate unique index on `id` + dropped/re-added it around hypertable creation, but that's fragile and non-transactional. Soft FKs are simpler and sufficient for a read-only scanner.
  - Models verified import-time and with ruff; no test files exist yet (tests are task-03+).

- **Risks**: 
  - If anyone adds a DB-level FK from a child table to `lending_snapshots.id` or `funding_snapshots.id`, it will fail because there's no unique constraint on `id` alone. The `id` column is only unique within the composite PK. Documentation in migration comments covers this.
  - The `server_default` for `risk_score` is the string `'0'` — SQLAlchemy will type-coerce but reviewers should be aware this is intentional (matches the model).
