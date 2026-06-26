---
name: defi-alpha-scanner-build
description: Completed build of the DeFi Alpha Scanner decision engine feature (11 tasks, 6 waves). Records key implementation decisions and risks for future work on this feature.
metadata:
  type: project
---

Feature `feat/defi-alpha-scanner` completed 2026-06-26. All 11 tasks executed in 6 waves, 0 failures, 0 retries.

**Key decisions:**
- Backend test suite (`cd backend && pytest`) requires Docker Postgres — the conftest `db_session` fixture creates asyncpg engine inside the fixture body to avoid event-loop binding errors.
- `history_agg.py::get_yield_history` uses format-string for table/field identifiers (safe: internal callers only, not user input). Marked `# ponytail:`.
- `rate_opportunities` in `rating.py` **mutates and re-sorts** the input list by rating before assigning medals — Task 04 wiring is already aware.
- `_history_points` for rating confidence is a binary proxy (1 if avg_30d non-null, else 0) — a richer count would need a separate COUNT(*) SQL call.
- `sort=liquidity` in the API falls back to score ordering — real liquidity sort deferred until `available_liquidity` is on the response model.
- `page.tsx` is now a `"use client"` component (holds `selectedOpp` state for the detail overlay). If SSR of the page shell matters later, extract the state+overlay into a separate client wrapper.
- `funding-chart.tsx` was deleted by Task 10 — the landing page's funding rate section no longer exists; the feed is the replacement.
- `loop-table.tsx` and `carry-table.tsx` were deleted by Task 09.

**Why:** Transform the scanner from a data explorer to a Bloomberg-style decision engine with rating engine, history context, capital simulator, and unified feed.

**How to apply:** When extending this feature, be aware of the mutations in `rate_opportunities`, the binary history_points proxy, and that page.tsx being a client component may affect SSR if the architecture needs to change.
