# Updated PRD — Expand Opportunity Universe

## Goal

Transform the DeFi Alpha Scanner from a narrow Aave + Hyperliquid engine into a market-wide opportunity engine that monitors thousands of lending markets, perpetual exchanges, and cross-protocol spreads across multiple chains. When complete, "No opportunities found" will be a meaningful signal because it reflects a broad scan rather than a handful of protocols.

## Decisions from Planning

The following decisions are locked in for this build:

1. **Multi-chain identity:** `Market` gains a `chain` column. One `Protocol` row per protocol; markets disambiguate by chain.
2. **Configuration:** Protocol/chain/asset mappings live in a committed `backend/app/protocols/registry.yaml` plus a small Python loader.
3. **Reward emissions:** `LendingSnapshot` gains an optional `reward_apy` column. Token-level reward metadata stays in `raw_payload`.
4. **Funding normalization:** Each funding adapter is responsible for converting exchange-specific values into `funding_rate`, `funding_interval_hours`, and `annualized_funding` before returning.
5. **Opportunity schema:** A single generic `OpportunityOut` response model with a `strategy_type` discriminator replaces the separate `Loop/Carry` schemas.
6. **Cross-protocol opportunities:** A new `CrossProtocolCalculation` table persists calculated cross-market spreads, keyed by two market IDs.
7. **Historical context:** Percentile / historical-rank fields are computed on-demand from existing snapshot history, not pre-materialized.
8. **Staking/restaking/Pendle:** Implemented as dedicated `LendingProvider` adapters that produce markets with distinct `market_type` values (`staking`, `restaking`, `pendle`).
9. **Collector concurrency:** Adapters run concurrently; each adapter processes its own markets sequentially unless profiling shows otherwise.
10. **Risk scoring:** The ranker gains strategy-specific penalty metrics (e.g. `cross_protocol_penalty`, `slashing_penalty`).
11. **Frontend migration:** Big-bang refactor to the generic `OpportunityOut` type across `api.ts`, context, cards, hero, leaderboard, and feed.
12. **Testability:** Adapters accept injectable HTTP/Web3 clients; tests mock responses rather than hitting live services.

## Scope — In This Build

### Chains
- Ethereum (primary)
- Base
- Arbitrum
- Optimism
- Polygon
- Sonic (best-effort; may fall back to null chain if RPC/data unavailable)

### Lending Protocols
- Aave V3 (refactored for registry/multi-chain)
- Morpho
- Spark
- Euler
- Fluid
- Moonwell
- Compound
- Silo

### Assets
- USDC, USDT, DAI, USDS
- ETH, WETH, wstETH
- cbBTC, WBTC
- ezETH, rsETH (staking/restaking)

### Perpetual / Funding Exchanges
- Hyperliquid (existing)
- GMX
- Drift
- Vertex
- dYdX

### Strategy Types
- Loop (existing leveraged loop)
- Carry (existing funding-carry)
- Stable Lending (simple deposit)
- Staking (liquid staking: wstETH, ezETH, rsETH)
- Restaking (EigenLayer ecosystem)
- Pendle (fixed-yield / implied yield)
- Cross-Protocol Spread (deposit on one protocol, borrow on another)

## Scope — Future / Out of Scope

- Berachain support (noted for future; no RPC/registry entries in this build)
- Automated trade execution or position monitoring
- Options-based strategies
- Real-time websocket streaming for funding rates
- A full admin UI for registry editing
- On-chain position simulation beyond the existing loop simulator

## Open Questions

1. **Data source priorities:** Some protocols have both RPC and subgraph/API options. The implementation tasks default to the simplest reliable public source per protocol; if a source is unavailable we stub the adapter with a clear `NotImplementedError`/`ponytail` comment rather than block the build.
2. **Reward APY accuracy:** Reward emissions are volatile and may require a follow-up task to source token prices for USD-denominated reward yield. This build stores the protocol-reported reward APY as a scalar.
3. **Sonic data availability:** If public RPC/contract data for Sonic is not readily available during implementation, Sonic will be listed in the registry as a future entry and excluded from active collection.

## Success Criteria

1. `GET /api/v1/opportunities` returns opportunities with `strategy_type` covering at least Loop, Carry, Stable Lending, and Cross-Protocol.
2. At least three new lending protocols and three new funding exchanges are wired into the collector runner.
3. The frontend renders all returned opportunities through the generic `OpportunityOut` schema without type errors.
4. All 168+ existing backend tests pass, plus new tests for registry loader, adapters, and generic schema routes.
5. `docker compose up` still boots the stack with no manual migration steps beyond Alembic.
