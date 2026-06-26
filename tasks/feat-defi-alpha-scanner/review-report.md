# Code Review Report — DeFi Alpha Scanner: Re-Review of Auto-Fixes (uncommitted on commit 668e045)

## Summary
All three findings from the prior review are **RESOLVED** and the fixes address the root causes, not symptoms. The slug normalization is applied at the boundary on both backend and frontend; the cross-batch rerate is a single shared-scale pass that leaves the route's sort keys untouched; the leaderboard client re-sort removal is sound under a verified monotonicity argument. Full backend suite is green (144 passed), TypeScript typecheck clean. No new Critical or Important issues in the changed lines. **Ship.**

## Prior Findings — Resolution Status

| # | Prior finding | Status | Verification |
|---|---------------|--------|--------------|
| Critical | Protocol display-name vs slug mismatch (confidence understated + dead Aave deep link) | ✅ RESOLVED | `_protocol_slug()` + `protocolLink` slug split; regression test drives real `"Aave V3"` → confidence 85 |
| Important #1 | Cross-batch rating/medal collision in `type=all` | ✅ RESOLVED | `rerate_combined()` one shared scale + unique global top-3 medals; called in `get_opportunities` before sort/limit |
| Important #2 | Limit-before-client-sort in leaderboard | ✅ RESOLVED | Redundant client re-sort removed; monotonicity argument holds (rating is strictly monotonic in score) |
| Minor | Stale page-header subtitle / unused `_volatility_penalty` | ◻️ Not in scope of this pass | Carried forward (Minor, non-blocking) |

## Fix Verification Detail

### Critical — slug mismatch (RESOLVED, root-cause)
- `backend/app/calculations/rating.py:44-51`: `_protocol_slug(name)` returns lowercased first token; empty/blank → `""`. `_confidence` (line 73) now does `PROTOCOL_METADATA.get(_protocol_slug(protocol), {})`. `"Aave V3"` → `"aave"` → `{age_known, audit_known}` true, only persistence stubbed → completeness 0.85, depth 1.0 at `_history_points=20` → confidence 85. Confirmed by `test_confidence_resolves_display_name_to_slug` (asserts `pytest.approx(85.0)` from the REAL display name — exactly the value-selection gap that let the bug pass 141 tests before).
- `frontend/src/lib/protocol-links.ts:11`: `name.toLowerCase().split(" ")[0]` → `"Aave V3"` resolves to `"aave"` key → deep link renders. Same normalization on both sides, so backend protocol names and frontend keys agree.
- This is the boundary normalization the prior report recommended, not a per-caller patch. Both symptoms route through the single slug helper.

### Important #1 — `rerate_combined` (RESOLVED, no sort regression)
- `backend/app/calculations/rating.py:129-149`: rerates every merged object on one min-max scale over `.score`, resets `.medal=None`, then assigns 🥇🥈🥉 to the global top-3 by rating. Leaves `.confidence` untouched (correct — confidence is per-opportunity, not batch-relative).
- `backend/app/api/routes.py:126-127`: invoked only when `type == "all"`, before sort/limit.
- **Sort-interaction check (all five options):** `rerate_combined` mutates only `.rating`, `.rating_label`, `.medal`. The route's `_sort_key` (lines 130-136) keys on `.score`, `.risk_score`, `.confidence`, `.sharpe`, `.score` (liquidity proxy) — none of which rerate touches. So return/risk/confidence/sharpe/liquidity ordering is identical with or without the rerate. No mis-ordering introduced.
- **Mutation safety:** the route does not read `.rating`/`.medal` after `rerate_combined` except to serialize the response model; `.rank` is left stale but is never used for `type=all` ordering or display (frontend uses positional index, not `.rank`). `.score` is a non-nullable `float` on both response models, so `min/max`/subtraction in rerate cannot hit `None`.
- Covered by `test_rerate_combined_shared_scale_and_unique_medals` (top→100, bottom→0, exactly one of each medal, gold on highest score) and `test_rerate_combined_empty_is_noop`.

### Important #2 — leaderboard re-sort removal (RESOLVED, monotonicity verified)
- `frontend/src/components/rating-leaderboard.tsx:35-46`: client `[...data].sort(by rating)` removed; `getOpportunities({ sort: "return", limit: 10 }).then(setOpps)`.
- Monotonicity argument holds: for `type=all` the API runs `rerate_combined` (rating = strictly monotonic min-max of `.score`) and returns results sorted `sort="return"` == `.score` desc == rating desc. So the server-side top-`limit` is already the correct top-rated set, in rating order — the client re-sort was redundant and the truncation now precedes the same ordering the display wants. Edge note: ties in score get equal rating; relative order within a tie is arbitrary but rating-equivalent, so display correctness is preserved.
- No orphaned imports left by the removal (diff removes inline logic only; all imports still used). TypeScript typecheck passes.
- `terminal-hero.tsx` (`sort:"return", limit:8`) never had a client re-sort; it benefits from the same server-side rerate and is now coherent.

## Issues Found

### Critical
None.

### Important
None in the changed lines.

### Minor (carried forward / informational)
- **`frontend/src/app/page.tsx`** (unchanged this pass): stale header subtitle ("Mempool monitoring · …") still unrelated to the loop/carry scanner. Non-blocking.
- **`backend/app/api/routes.py:803-805`** (unchanged this pass): `_volatility_penalty` single-market wrapper still appears unused. Possible dead code; non-blocking.
- **Out-of-scope changes present in working tree** (not part of the three documented fixes, but included in the uncommitted diff): `backend/app/collectors/aave.py` + `test_aave_adapter.py` (Aave V3 `ReserveDataLegacy` ABI layout correction — field order/count now matches the on-chain struct, `_ReserveData` unpack indices and tests updated consistently, 35/35 aave+rating tests pass) and `docker-compose.yml` (`NEXT_PUBLIC_API_URL` → `http://localhost:8000`, correct because `NEXT_PUBLIC_*` is inlined into the browser bundle and must be host-reachable). Both are coherent and test-covered; flagged only so the reviewer/committer is aware they ride along with this fix batch.

## What Looks Good
- Single-boundary normalization for the slug fix — backend and frontend split identically, so the two symptoms share one fix point. No sibling caller left broken.
- The new regression test exercises the real production value (`"Aave V3"`), closing the exact blind spot that hid the original bug.
- `rerate_combined` is deliberately scoped: it touches only the batch-relative fields and leaves per-opportunity `confidence` and all sort keys alone, so it cannot perturb any sort ordering.
- Comments on both fixes state intent (slug mapping rationale, why `confidence` is untouched, why the client re-sort is unnecessary) without over-explaining.
- Aave ABI fix is rigorous: the comment names the exact struct-layout hazard (offset misreads if field order/count diverge) and the tests pin the new positional decode.

## Test Coverage

| Area | Tests Exist | Coverage Notes |
|------|-------------|----------------|
| Rating slug resolution | Yes | `test_confidence_resolves_display_name_to_slug` uses real `"Aave V3"`, asserts confidence 85 — closes prior gap |
| `rerate_combined` | Yes | Shared-scale (100/0 bounds), unique medals, gold-on-top, empty no-op |
| Aave ABI decode | Yes | Both tests rebuilt to new positional struct; assert decoded fields |
| API routes (`type=all` rerate path) | Yes (existing) | `test_api.py` 20 passed; rerate runs through the route |

**Test Coverage Assessment**: The +3 new tests target precisely the prior defects, including the value-selection gap. Assertions are specific (formula outputs, medal multiset, scale bounds) — not existence-only.

## Test Execution

| Check | Result | Details |
|-------|--------|---------|
| Test command discovered | Yes (`pytest`) | `backend/pyproject.toml`; ran via `backend/.venv` |
| Backend suite run | Passed (144/144) | First full run showed 4 transient `ConnectionRefusedError` in `test_history_agg.py`; re-ran in isolation and full suite → all green. DB-connection flake, not a code regression (history_agg.py unchanged) |
| Rating + Aave subset | Passed (35/35) | Confirms the changed modules directly |
| API routes | Passed (20/20) | `type=all` rerate path exercised |
| Frontend typecheck | Passed | `tsc --noEmit` exit 0 |
| TDD evidence | Yes | Regression tests added RED→GREEN for each fix |

**Test Execution Assessment**: Green. The lone wobble was a transient Postgres connection refusal under full-suite load that cleared on re-run; not attributable to these edits.

## Recommendations
1. Ship the three fixes — root causes resolved, no regressions, tests pin the formerly-uncaught paths.
2. Decide explicitly whether the bundled Aave ABI + docker-compose changes belong in this commit or a separate one; they are correct but were not part of the documented fix scope.
3. (Backlog, Minor) Update the stale `page.tsx` subtitle and remove `_volatility_penalty` if confirmed dead.

**Verdict: SHIP.**
