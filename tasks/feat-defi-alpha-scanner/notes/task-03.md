# Task 03: Opportunity Rating Engine

- **Decisions**: `rate_opportunities` sorts `scored` in-place by rating before assigning medals. This mutates the input list (same behavior as `score_opportunities` in ranker.py which also mutates in-place). Task-04 wiring should be aware the list order changes after calling this.
- **Deviations**: None — formulas, thresholds, and constants match the PRD exactly.
- **Trade-offs**: `PROTOCOL_METADATA` hardcodes 5 known protocols. An unknown protocol gets 2 extra stub penalties (age + audit unknown), matching the PRD's "treat as unknown" rule. Adding protocols later is a one-liner edit to the dict.
- **Risks**: The test for `test_confidence_penalises_more_stubbed_inputs` depends on `"aave"` being in `PROTOCOL_METADATA` with `age_known=True, audit_known=True`. If that entry is removed or changed, the test will break.
