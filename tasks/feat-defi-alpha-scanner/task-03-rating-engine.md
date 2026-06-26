# Task 03: Opportunity Rating Engine (pure function)

## Objective
Build the killer Rating Engine: a pure function that turns scored opportunities into a 0-100 rating, a label (Excellent/Very Good/Good/Fair/Avoid), an approximate Sharpe, and a confidence %, plus the stubbed protocols-metadata source it relies on.

## Context
**Quick Context:**
- Layers on top of `score_opportunities()` output (task-01 adds `breakdown`/`weights`; this engine reads each opp's `score`).
- Protocol **age**, **audit history**, **persistence** are NOT collected — use a static stubbed metadata map keyed by protocol name. `Protocol.created_at` is row-insert time and MUST NOT be used as launch date.
- Exact formulas are specified in `updated-prd.md` ("Rating Engine — exact formulas", "Sharpe"). Follow them precisely so UI labels are deterministic.

## Requirements
- New module `backend/app/calculations/rating.py`, pure (no I/O).
- **Static stubbed metadata**: a module-level dict `PROTOCOL_METADATA` keyed by lowercase protocol name → `{"age_known": bool, "audit_known": bool}` (or similar). For protocols not in the map, treat age/audit as unknown (stubbed). Mark with a `# ponytail:` comment noting it's a placeholder until a real collector exists.
- **`rate_opportunities(scored: list[dict]) -> list[dict]`**: given the ranker output, for each opp compute and attach:
  - `rating` (0-100, RELATIVE min-max of `score` across the batch ×100; batch range 0 → all 100).
  - `rating_label` (Excellent ≥85, Very Good ≥70, Good ≥55, Fair ≥40, Avoid <40).
  - `confidence` (0-100) = `base(100) × completeness_factor × depth_factor`, where completeness subtracts 0.15 per stubbed input (age, audit, persistence; floor 0.4) and `depth_factor = min(1.0, n / N)` with `n` = history points available for that opp and `N` = volatility window (default 20). Persistence is always stubbed for now → counts as one stubbed input.
  - `medal`: 🥇/🥈/🥉 for the top 3 by rating, else None.
- Inputs the engine needs per opp that aren't already on the dict (history point count `n`, protocol name) must be passed in — define the expected input keys clearly (e.g. opp carries `_protocol`, `_history_points`). The wiring task (task-04) populates them.
- Pure and deterministic; no DB, no clock, no randomness.

## Existing Code References
- `backend/app/calculations/ranker.py` — upstream producer; `rate_opportunities` consumes its output.
- `backend/tests/test_ranker.py` — test style + factory pattern to mirror.
- `tasks/feat-defi-alpha-scanner/updated-prd.md` — authoritative formulas/thresholds.

## Implementation Details
- Min-max over `score`: `rating = 0..100`; if `max==min`, all `rating=100`.
- Confidence example to verify against: 3 stubbed inputs + n=4, N=20 → completeness 0.55 × depth 0.2 × 100 ≈ 11. Mature/all-stubbed (n≥20) → ≈55.
- Keep label thresholds and penalty constants as module-level named constants so they're easy to tune.

## TDD Mode

This task uses Test-Driven Development. Write tests BEFORE implementation.

### Test Specifications
- **Test file**: `backend/tests/test_rating.py` (new)
- **Test framework**: pytest + pytest-asyncio
- **Test command**: `cd backend && pytest tests/test_rating.py`

### Tests to Write
1. **relative rating scale**: batch of opps with distinct scores → top gets rating 100, bottom gets 0, monotonic in between.
2. **all-equal batch**: identical scores → all rating 100 (no divide-by-zero).
3. **label thresholds**: ratings 90/72/56/41/30 map to Excellent/Very Good/Good/Fair/Avoid respectively (test boundary values 85/70/55/40).
4. **confidence penalises stubbed inputs**: opp with 3 stubbed inputs has lower confidence than one with fewer (when depth equal).
5. **confidence penalises thin history**: same stubbed inputs, n=4 vs n=20 → thin history reads materially lower confidence; assert the ~11 vs ~55 ballpark from the PRD.
6. **medals**: top 3 by rating get 🥇🥈🥉, 4th gets None.

### TDD Process
1. Write the tests above — they should FAIL (RED)
2. Implement the minimum code to make them pass (GREEN)
3. Run the full test suite to check for regressions
4. Refactor if needed while keeping tests green

### Mocking Discipline
- Mock only at the **system boundary**. `rate_opportunities` is pure — test directly with real dicts, no mocks.
- Do NOT mock the code under test or internal modules.

## Acceptance Criteria
- [ ] `rate_opportunities` attaches `rating`, `rating_label`, `confidence`, `medal` per the PRD formulas
- [ ] Rating is relative min-max ×100; all-equal batch yields 100 with no error
- [ ] Labels match thresholds (85/70/55/40 boundaries)
- [ ] Confidence drops with more stubbed inputs AND with thinner history; matches the documented ~11 / ~55 examples
- [ ] Top 3 by rating receive 🥇🥈🥉, others None
- [ ] Function is pure (no DB/clock/random); existing backend suite still passes

## Dependencies
- Depends on: 01
- Blocks: 04
