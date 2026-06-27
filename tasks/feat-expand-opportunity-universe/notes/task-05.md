# Task 05: New Lending Adapters Batch 2 (Fluid, Moonwell, Compound, Silo)

- **Decisions**:
  - Fluid: Used `https://api.fluid.instadapp.io/v2/{chainId}/vaults` (verified live, returns 119 vaults on mainnet). Rates are in basis points (157 → 1.57%), collateralFactor and liquidationThreshold are also in bps (8500 → 85%). TVL is computed as `totalSupply_tokens * supplyToken.price` since the API includes USD prices. Asset named `supplySymbol/borrowSymbol` (e.g. ETH/USDC) matching Morpho's collateral/loan convention.
  - Moonwell: Used `https://api.moonwell.fi/v1/markets?chainId={chainId}` (verified live, 20 markets on Base). APYs are already percent, USD amounts are already USD — no conversion needed. `collateralFactor` is a 0–1 ratio multiplied by 100 for `ltv_pct`. Deprecated markets are filtered out.
  - Compound: Raised `NotImplementedError`. The V2 API was shut down April 2023. V3 (Comet) has no official public REST API. COMP reward_apy (required by the task) can only be read via the on-chain `CometRewards` contract. Documented upgrade path in the ponytail comment.
  - Silo: Raised `NotImplementedError`. `app.silo.finance` is a Next.js SPA with no stable public REST API. TheGraph subgraph exists but requires a paid API key. Documented the SiloLens contract as the RPC upgrade path.

- **Deviations**:
  - Registry YAML still lists Fluid/Moonwell with `data_source: rpc` and placeholder `pool_address`. The adapters use REST APIs instead and accept `pool_address` as the API base URL override. The YAML was not changed (out of scope for this task) — the adapters fall back to the hardcoded default URL when pool_address is a zero-address.
  - Fluid `available_liquidity` is expressed in supply-token units (collateral), not USD. Computing in borrow-token liquidity would require the borrow token price which the API provides but adds complexity. This is noted with a ponytail comment.

- **Trade-offs**:
  - Fluid utilization: computed as `totalBorrow_raw / totalSupply_raw` from the vault's raw token amounts. This gives per-vault utilization in supply-token-equivalent terms. An alternative using USD values would require cross-multiplying by token prices — skipped as the raw ratio is the standard Compound-style utilization metric.
  - Moonwell `liquidation_threshold_pct` is set equal to `ltv_pct` because the API only exposes `collateralFactor`. The ponytail comment documents this.

- **Risks**:
  - Fluid API (`api.fluid.instadapp.io`) is undocumented/unofficial. If Instadapp restructures the URL scheme (e.g. chain ID path segment changes), the adapter breaks silently. Monitor for 404s.
  - Moonwell API returns APYs that include reward components in `totalSupplyApr`/`totalBorrowApr` but we use `baseSupplyApy`/`baseBorrowApy` (base rate only). This is intentional — reward APY is inconsistently included in total figures and we expose `reward_apy: 0.0` as a placeholder until a separate rewards endpoint is identified.
