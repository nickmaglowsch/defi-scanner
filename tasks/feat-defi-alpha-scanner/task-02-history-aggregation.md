# Task 02: Yield History Aggregation (Today / Yesterday / 7D / 30D)

## Objective
Provide per-market yield aggregates (today, yesterday, 7-day avg, 30-day avg) computed from raw snapshot history, so every opportunity can show whether its current yield is exceptional (PRD #4).

## Context
**Quick Context:**
- There is **no stored history of computed effective_yield / net_carry / spread** — those are derived per-request. Aggregates must be computed from the raw fields in `lending_snapshots` (deposit_apy, borrow_apy) and `funding_snapshots` (annualized_funding) keyed by `market_id + observed_at`.
- `routes.py:_volatility_map()` is the existing pattern for a batched windowed aggregate over snapshot tables — follow it (single SQL over many market_ids, no N+1).

## Requirements
- Add the helper in a **new file `backend/app/calculations/history_agg.py`** (NOT in `routes.py` — task-04 edits `routes.py` heavily and must not collide with this task). Given an `AsyncSession`, a set of market_ids, and a snapshot table/field, it returns per-market aggregates: `today` (most recent value), `yesterday` (value ~24h prior, nearest snapshot), `avg_7d`, `avg_30d`.
- Batched: one (or few) SQL queries for all requested market_ids — do not query per market.
- Return shape: `{market_id: {"today": float|None, "yesterday": float|None, "avg_7d": float|None, "avg_30d": float|None}}`. Missing data → None for that bucket (do not fabricate).
- Aggregate the **input yield field** appropriate to the opportunity type (loops: `deposit_apy`; carry: `annualized_funding`). Keep it generic enough that the field/table is a parameter.
- "today"/"yesterday" buckets relative to the latest `observed_at` for that market (not wall-clock midnight) — DeFi data is sparse; nearest-snapshot semantics avoid empty buckets. Document this with a `# ponytail:` comment.

## Existing Code References
- `backend/app/api/routes.py:_volatility_map` (~lines 676-700) — batched windowed-aggregate SQL pattern to mirror.
- `backend/app/models/lending_snapshot.py`, `backend/app/models/funding_snapshot.py` — column names + `observed_at` index.

## Implementation Details
- Prefer a single SQL with conditional aggregates (FILTER / CASE WHEN on `observed_at >= now() - interval`) over multiple round-trips.
- Use `func.now()` / interval math in SQL, or compute cutoff datetimes in Python and pass as params (matches the `_volatility_map` text() style).
- This helper is consumed by task-04 (wires aggregates into the API response) — keep it importable and side-effect free besides the DB read.

## TDD Mode

This task uses Test-Driven Development. Write tests BEFORE implementation.

### Test Specifications
- **Test file**: `backend/tests/test_history_agg.py` (new)
- **Test framework**: pytest + pytest-asyncio
- **Test command**: `cd backend && pytest tests/test_history_agg.py`

### Tests to Write
1. **basic aggregates**: seed a market with snapshots across the last 30 days; assert today/yesterday/avg_7d/avg_30d match hand-computed expectations.
2. **sparse / missing buckets**: a market with only 1 recent snapshot → today set, yesterday/7d/30d either None or computed-from-available per the documented semantics (assert the chosen behavior explicitly).
3. **multiple markets batched**: two markets in one call → correct per-market separation, results don't bleed across markets.
4. **empty input**: empty market_id set → empty dict, no SQL error.

### TDD Process
1. Write the tests above — they should FAIL (RED)
2. Implement the minimum code to make them pass (GREEN)
3. Run the full test suite to check for regressions
4. Refactor if needed while keeping tests green

### Mocking Discipline
- Mock only at the **system boundary**. Use the **real test DB / session fixture** from `backend/tests/conftest.py` — do NOT mock the database or the session; an in-memory/real DB is what makes these aggregates trustworthy.
- Do NOT mock the code under test or the SQLAlchemy session it calls through.
- Seed real rows via the test fixtures rather than stubbing query results.

## Acceptance Criteria
- [ ] Helper returns `{market_id: {today, yesterday, avg_7d, avg_30d}}` for a batch of market_ids in ≤ a small constant number of queries (no per-market query)
- [ ] Aggregates match hand-computed values on seeded data
- [ ] Markets with sparse history return None (not fabricated values) for unavailable buckets, per documented semantics
- [ ] Empty input returns empty dict without error
- [ ] Existing backend test suite still passes (`cd backend && pytest`)

## Dependencies
- Depends on: None
- Blocks: 04
