# Planning Questions — Expand Opportunity Universe

## Codebase Summary

Explored the full stack. Findings that shape this PRD:

**Backend**
- `app/collectors/base.py` defines two tiny protocols: `LendingProvider.fetch_reserves()` and `FundingProvider.fetch_funding_rates()`. Returning a normalized `list[dict]` is already the pattern.
- `LendingSnapshot` has the fields the PRD asks for (deposit_apy, borrow_apy, utilization, available_liquidity, total_supplied, total_borrowed, tvl) plus `raw_payload` JSONB. It does **not** have `ltv`, `liquidation_threshold`, `reserve_factor`, or `reward_emissions` — those live inside `raw_payload.configuration` for Aave.
- `Market` is `(protocol_id, asset, market_type)` with no chain column. `Protocol` has `chain` but it is a single string per protocol; multi-chain protocols like Aave V3 on Base/Arbitrum would need multiple Protocol rows or a chain-per-market model.
- `FundingSnapshot` stores perp funding rates for Hyperliquid only. No exchange identifier, no normalized funding interval beyond the adapter.
- Opportunities are currently two hardcoded types: `LoopOpportunityOut` and `CarryOpportunityOut`. The API `GET /opportunities` merges them with `rerate_combined()`.
- Calculations are persisted: `LoopCalculation` and `CarryCalculation`. Cross-protocol opportunities would need a new calculation table.
- The collector runner in `app/collectors/__init__.py` manually wires one Aave lending collector and one Hyperliquid funding collector. New adapters must be wired here.
- Confidence/rating already depends on real signals (`deployed_at`, `audit_count`, persistence, depth). Adding many new protocols will initially produce low-confidence scores until metadata collectors fill them in.
- Tests: 168 backend tests; API tests mock execute-call ordering tightly. Adding new strategy types or response fields will require updating mocks.

**Frontend**
- `frontend/AGENTS.md` warns this is a customized Next.js; docs must be read at implementation time after `npm install`.
- Types in `src/lib/api.ts` mirror the backend schemas exactly. `LoopOpportunityOut` / `CarryOpportunityOut` are discriminated by `isLoop()` checking `effective_yield`.
- `opportunity-feed.tsx` filters by `all | loop | carry` only. Cards, hero, and leaderboard assume every opp is either Loop or Carry.
- No existing frontend test harness.

---

## Questions

### Q1: Multi-chain identity model
**Context:** The PRD wants Ethereum, Base, Arbitrum, Optimism, Polygon, Sonic, and future Berachain. Today `Protocol.chain` is a single string and `Market` has no chain column. A protocol like Aave V3 exists on multiple chains; Morpho, Spark, etc. are also multi-chain. We must decide how to represent `(protocol, chain, asset)` uniquely.
**Question:** Which identity model should we use?
- **A) One Protocol row per (protocol, chain) pair.** Aave V3 Ethereum and Aave V3 Base become two Protocol rows (`Aave V3 Ethereum`, `Aave V3 Base`). Market stays `(protocol_id, asset, market_type)`. Minimal schema change, but the protocol name becomes a display string that embeds chain.
- **B) Add `chain` to Market.** Keep one Protocol row per protocol (e.g. `Aave V3`). Market becomes `(protocol_id, chain, asset, market_type)`. Clean separation but requires a migration and updates to every query that groups/joins by protocol.
- **C) Add `chain` to both Protocol and Market.** Protocol has a canonical/default chain; Market overrides it. More flexible but more places to keep consistent.
**Recommended:** **B** — add `chain` to `Market`. It models reality cleanly and avoids polluting protocol names.

### Q2: Asset / contract configuration format
**Context:** Aave assets are currently configured as a single env string `AAVE_ASSETS=SYM:0xAddr,...` on Ethereum mainnet. Expanding to many protocols, chains, and assets makes this unwieldy. Pool addresses, asset addresses, and chain RPCs all need configuration.
**Question:** How should per-protocol, per-chain configuration be stored?
- **A) Extend env vars.** `MORPHO_ETHEREUM_ASSETS=...`, `MORPHO_BASE_ASSETS=...`, `SPARK_POOL_ADDRESS=...`, etc. Simplest for the current code but explodes into dozens of env vars.
- **B) Static JSON/YAML registry committed in the repo.** A file like `backend/app/protocols/registry.yaml` lists each protocol, chain, pool address, assets, and optional RPC overrides. Loaded at startup. Easier to review and extend.
- **C) Database-seeded registry.** Protocol/chain/asset mappings live in the DB and are edited via an admin endpoint or migration. More operational overhead; overkill until we need runtime reconfiguration.
**Recommended:** **B** — a committed registry file. It keeps the expansion visible, reviewable, and version-controlled without inventing an admin UI.

### Q3: Reward emissions field
**Context:** The PRD asks to collect reward emissions where applicable (e.g. Compound COMP, Aave incentives, Morpho rewards). Lending adapters today return deposit_apy/borrow_apy as the nominal protocol APY.
**Question:** How should reward emissions be captured?
- **A) Add `reward_apy` / `reward_token` columns to `LendingSnapshot`.** Explicit schema fields; easy to query and rank. Requires a migration and adapter updates.
- **B) Keep rewards inside `raw_payload` only.** No schema change; adapters put reward info in the JSONB blob. Ranker would ignore them unless later extracted.
- **C) Add `reward_apy` as an optional top-level field but keep token details in `raw_payload`.** Middle ground: the aggregate reward yield is queryable, details stay flexible.
**Recommended:** **C** — it lets the ranker include reward yield without over-normalizing token metadata.

### Q4: Normalized funding rate contract
**Context:** Hyperliquid funds hourly; GMX, Drift, Vertex, and dYdX have different funding intervals and sign conventions. To compare funding yields across exchanges, we need a normalized `annualized_funding` and clear `funding_interval_hours`.
**Question:** What is the contract for `FundingProvider` adapters?
- **A) Adapters return raw exchange values; `FundingCollector` normalizes.** Adapters return exchange-specific fields; a shared normalizer converts to `annualized_funding` and `funding_interval_hours`. Centralizes logic but couples adapters to one normalization model.
- **B) Each adapter normalizes itself before returning.** Adapters must output `funding_rate`, `funding_interval_hours`, `annualized_funding` using exchange-specific math. Simpler collector, but each adapter author must know the convention.
- **C) Both: adapter returns exchange-specific raw plus a normalized block; collector stores both.** More complete but duplicates data.
**Recommended:** **B** — adapters normalize. The existing `FundingCollector` already expects normalized keys; keeping that contract minimizes churn.

### Q5: New strategy types vs. unified opportunity schema
**Context:** The PRD adds Stable Lending, Staking, Restaking, Pendle, and Cross-Protocol opportunities. Today the API returns a union of `LoopOpportunityOut | CarryOpportunityOut` and the frontend discriminates on `effective_yield`.
**Question:** How should new strategy types be exposed?
- **A) Extend the existing union with new Pydantic schemas.** Add `StableLendOpportunityOut`, `StakeOpportunityOut`, `RestakeOpportunityOut`, `PendleOpportunityOut`, `CrossProtocolOpportunityOut`. Strong typing; frontend must handle each variant. Most verbose.
- **B) Introduce a single generic `OpportunityOut` with a `strategy_type` discriminator and strategy-specific sub-fields.** One schema, one frontend type, fewer mocks to update. Loses some compile-time field guarantees.
- **C) Keep Loop/Carry as first-class and add only Cross-Protocol as a new type; fold Stable Lending into Loop with leverage=1; fold Staking/Restaking/Pendle into a generic "Yield" type.** Smaller surface but hides strategic distinctions.
**Recommended:** **B** — a single generic `OpportunityOut` with a discriminator. It scales to future strategy types without multiplying schemas and matches the frontend's current union helpers.

### Q6: Cross-protocol opportunities storage
**Context:** Cross-protocol opportunities (e.g. deposit on Aave, borrow on Morpho) require two market references and a computed spread. They do not map to a single snapshot.
**Question:** How should cross-protocol opportunities be represented?
- **A) Compute on-the-fly in the API route.** Query latest lending snapshots across all protocols, build pairs, calculate spreads, and return them without persisting. Simplest first version; no new table.
- **B) Persist a new `CrossProtocolCalculation` table.** Similar to `LoopCalculation`/`CarryCalculation`, keyed by two market IDs. Enables history, alerts, and reranking without recomputing. Requires a migration and a calculation trigger.
- **C) Materialized view / batch job.** A periodic job writes cross-protocol pairs into a table. Good for thousands of markets but adds infrastructure.
**Recommended:** **B** — persist cross-protocol calculations. It reuses the existing snapshot-triggered calculation pattern and gives us history for anomaly detection later.

### Q7: Historical context / anomaly detection scope
**Context:** The PRD wants signals like "highest lending spread in 90 days" and "funding rate in 99th percentile". The backend already has `get_yield_history()` for today/yesterday/7d/30d averages and `_history_depth_map()` for counts.
**Question:** How far do we go with historical context in this build?
- **A) Extend response models with percentile/rank fields only.** Add `percentile_90d` and `historical_rank` to opportunity outputs; compute them on-demand from existing snapshot history. No new storage.
- **B) Add a `market_anomalies` table / materialized aggregates.** Pre-compute percentiles, min/max, and rolling windows. Better performance for thousands of markets but adds a migration and refresh logic.
- **C) Ship history sparklines in the UI first, defer anomaly scores.** Frontend shows 90-day charts; percentile badges come later. Minimal backend work.
**Recommended:** **A** — compute percentile/rank on-demand from existing history. It satisfies the PRD signal without new storage, and we can materialize later if performance becomes an issue.

### Q8: Staking / Restaking / Pendle data sources
**Context:** These assets (wstETH, ezETH, rsETH, Pendle PT/YT) often have yields available from dedicated APIs (Lido, Rocket Pool, EigenLayer, Pendle) rather than generic lending pools.
**Question:** How do we integrate these?
- **A) Add dedicated providers that implement `LendingProvider`.** Each returns a normalized `deposit_apy`/`tvl` and is collected by the existing `LendingCollector`. Reuses the pipeline; market_type can be `staking`/`restaking`/`pendle`.
- **B) Create a separate `YieldProvider` protocol and collector.** New protocol distinct from `LendingProvider`/`FundingProvider`. Cleaner semantically but adds a new snapshot table and collector loop.
- **C) Fetch from a single aggregated source (e.g. DefiLlama yields API).** One adapter covers many categories. Fastest to expand but less control over freshness and field coverage.
**Recommended:** **A** — implement as `LendingProvider` variants with a distinct `market_type`. It reuses the current snapshot/ranking pipeline while preserving semantic identity.

### Q9: Collector concurrency and resilience
**Context:** The PRD targets "thousands of markets." The current Aave adapter fetches reserves sequentially and the runner schedules one task per collector. Adding many protocols/chains will make collection slow and increases partial-failure risk.
**Question:** How should collection scale?
- **A) Keep sequential per-adapter but run adapters concurrently.** Each adapter still processes its own markets sequentially, but all adapters run in parallel tasks. Simplest next step.
- **B) Parallelize within each adapter.** Use `asyncio.gather` across markets/chains inside each adapter. Higher RPC/API pressure; requires careful rate-limiting.
- **C) Move collection out of the FastAPI process to a separate worker / cron.** Best long-term but introduces job infrastructure (Celery, temporal, etc.).
**Recommended:** **A** — concurrent adapters, sequential within each adapter. It is the smallest change that meaningfully scales, and we can parallelize internally later where profiling shows it matters.

### Q10: Risk scoring for new opportunity types
**Context:** The current ranker uses `yield_score`, `liquidity_score`, `tvl_score`, `stability_score`, `utilization_penalty`, `volatility_penalty`, `protocol_risk`. New strategies like restaking and cross-protocol carry different risk dimensions (slashing, bridge risk, oracle mismatch, smart-contract stack).
**Question:** How do we handle risk for new strategies?
- **A) Reuse the existing 7-metric ranker; map new risks into the existing `protocol_risk`/`volatility_penalty` buckets.** Minimal change but lossy.
- **B) Add strategy-specific penalty metrics to the ranker.** E.g. `cross_protocol_penalty`, `slashing_penalty`. Keeps scoring transparent but requires weights update and frontend breakdown support.
- **C) Add a generic `risk_tags` field with qualitative flags.** Less precise but surfaces the risk dimensions without redesigning the numeric ranker.
**Recommended:** **B** — add explicit penalty metrics for new risk dimensions. The frontend already shows a score breakdown; new metrics map naturally to it.

### Q11: Frontend type migration strategy
**Context:** Switching to a generic `OpportunityOut` or adding several new strategy schemas will break `src/lib/api.ts`, `opportunity-feed.tsx`, `opportunity-card.tsx`, `terminal-hero.tsx`, and `rating-leaderboard.tsx`.
**Question:** How should the frontend migrate?
- **A) Big-bang refactor to a generic `OpportunityOut` with `strategy_type`.** Update all components in one pass. Cleanest result but higher risk of regressions.
- **B) Incremental: keep Loop/Carry as-is, add new types alongside.** Existing components keep working; new strategy cards are added separately. More files, more duplication, lower risk.
- **C) Introduce a shared `Opportunity` interface that both old and new types satisfy.** Wrap old types at the API layer. Adds a compatibility layer but smooths transition.
**Recommended:** **A** — big-bang refactor to a generic `OpportunityOut`. The current codebase is small enough that a single consistent model is cheaper than maintaining two.

### Q12: Data source fallback / testability
**Context:** Many new adapters will rely on external RPCs, subgraphs, and REST APIs. Live data is flaky, and tests should not require real network calls.
**Question:** How do we keep adapters testable?
- **A) Inject an HTTP/Web3 client into each adapter and provide fixtures that mock responses.** Existing `HyperliquidAdapter` already accepts an `httpx.AsyncClient`; extend this pattern to all adapters.
- **B) Wrap external calls behind a thin `DataSource` abstraction with a fake implementation.** Adds a layer but makes tests entirely deterministic without touching real clients.
- **C) Record real API responses as JSON fixtures and replay them in tests.** Good for regression but fixtures go stale quickly.
**Recommended:** **A** — inject clients and mock responses. It is the pattern already in place and keeps tests fast and deterministic.
