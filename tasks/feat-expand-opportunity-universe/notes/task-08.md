# Task 08: Generic Opportunity Schema and API Refactor

- **Decisions**: Made `LoopOpportunityOut` and `CarryOpportunityOut` subclasses of `OpportunityOut` in Python (not just aliases) so any code importing them still gets a valid Pydantic model. In TypeScript, made them type aliases (`= OpportunityOut`) — simpler and sufficient since TS structural typing means the union collapses cleanly.

- **Decisions**: `rerate_combined` was left completely unchanged. It accesses `.score`, `.rating`, `.rating_label`, `.medal` — all present on `OpportunityOut`. No surgery needed there.

- **Decisions**: Strategy-specific fields (loop: deposit_apy, effective_yield, leverage, etc.; carry: funding_yield, net_carry, borrow_cost, etc.) are now in `strategy_details: dict`. The common headline yield is surfaced as `net_apy` (effective_yield for loop, net_carry for carry) so callers don't have to dig into `strategy_details` for the single most important number.

- **Decisions**: Frontend components that accessed `opp.effective_yield` / `opp.net_carry` directly (opportunity-card, home-cards, opportunity-detail) were updated to use `opp.strategy_details.effective_yield` / `opp.strategy_details.net_carry`. Components that only used `oppYield(opp)` or `isLoop(opp)` needed only import updates — those helpers were already abstracted.

- **Deviations**: The `/looping` endpoint still has `-> list[LoopOpportunityOut]` type annotation (FastAPI uses this for schema generation), but now returns `OpportunityOut` instances (which are valid `LoopOpportunityOut` since it's a subclass). Functionally identical; kept for OpenAPI doc continuity.

- **Trade-offs**: Considered making `strategy_details` typed as `LoopDetails | CarryDetails` discriminated union in TS. Rejected — the whole point of `strategy_details: dict` is extensibility without schema changes. A `Record<string, number | null>` is the right call here.

- **Risks**: `strategy_details` values are `number | null` from the backend but typed as `Record<string, number | null>` in TS. `fmtPct` in the frontend accepts `number | null | undefined` so the optional-chaining access (`d?.effective_yield`) is safe. No runtime risk, but reviewers should note that `Number(d.leverage)` casts in components are defensive (values from `strategy_details` come as `number | null`, not string).
