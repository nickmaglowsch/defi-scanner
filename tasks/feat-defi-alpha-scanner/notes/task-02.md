# Task 02: Yield History Aggregation (Today / Yesterday / 7D / 30D)

- **Decisions**:
  1. Single SQL with five CTEs (`latest`, `snaps`, `today_cte`, `yesterday_cte`, `agg_cte`) — one round-trip for any number of market_ids. Mirrors `_volatility_map`'s `text()` + `ANY(:market_ids)` pattern.
  2. "yesterday" uses a ±12h window around `(latest - 24h)` to avoid counting today's snapshot as yesterday. Documented with `# ponytail:` comment per task requirement.
  3. `avg_7d` uses `AVG(...) FILTER (WHERE age <= INTERVAL '7 days')` — Postgres conditional aggregate, no subquery.
  4. `db_session` fixture creates the engine inside the fixture body (not at module level). asyncpg requires the engine to be created on the same event loop as the test; module-level creation binds to the import-time loop and causes `attached to a different loop` errors.

- **Deviations**: Added a 5th test (`test_funding_snapshots_annualized_funding`) beyond the 4 specified, to verify the generic `table`/`field` params work for funding snapshots.

- **Trade-offs**: Format-string for `table`/`field` identifiers instead of parameterized quoting — safe because callers are internal route code (not user input). Documented with `# ponytail:` comment.

- **Risks**: The `db_session` fixture requires the real Postgres DB to be running (via Docker). If the DB is unavailable, these 5 tests will fail with a connection error rather than a meaningful message.
