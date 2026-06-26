# DeFi Alpha Scanner

Detects leveraged-loop and funding-carry opportunities across on-chain lending
and perpetuals markets, ranks them with a transparent multi-factor scorer, and
surfaces a confidence score driven by **real collected signals** (deployment
age, audit history, observation persistence) rather than hardcoded heuristics.

- **Backend**: FastAPI + SQLAlchemy (async) + Alembic + TimescaleDB. Background
  collectors pull Aave V3 reserves over RPC and Hyperliquid funding rates over
  REST; new `ProtocolAuditCollector` (DefiLlama) and `ProtocolAgeCollector`
  (on-chain `get_code` binary search) feed the confidence engine.
- **Frontend**: Next.js 16 + TypeScript + Tailwind. A single page-level fetch
  feeds the hero, leaderboard, and filterable feed — the three used to triple-
  fetch the same endpoint on mount.

## What it filters out

The ranker is intentionally conservative about what counts as an opportunity:

- **Carry opps without a borrow leg.** A perp asset with no matching lending
  market is dropped before scoring — a 0% synthetic borrow cost would overstate
  `net_carry` against opps that pay a real borrow rate.
- **Loops with an inverted nominal spread.** When `deposit_apy < borrow_apy`,
  the only thing producing positive `effective_yield` is leverage amplifying an
  inverted pre-leverage edge. Mathematically profitable, economically not —
  filtered before scoring. Floor is `DEFI_LOOP_MIN_NOMINAL_SPREAD` (default
  `0.0` = require non-inverted rates; raise to demand a thicker pre-leverage
  margin for rate drift, gas, and fees).

## Quickstart (local)

Requires Docker + an Ethereum mainnet RPC URL (the Aave collector needs it).

```bash
cp .env.example .env       # if present; otherwise create .env
# Minimal .env:
#   DEFI_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/<your-key>
./run.sh
```

`docker compose up` boots:

| Service     | Port | Notes                                            |
|-------------|------|--------------------------------------------------|
| TimescaleDB | 5432 | `defi:defi` / `defi_scanner`; hypertables on `observed_at` |
| backend     | 8000 | Runs Alembic migrations on startup, then uvicorn |
| frontend    | 3000 | Next.js (dev mode) pointing at `localhost:8000`  |

Open http://localhost:3000.

## Configuration

All settings are env vars (prefix `DEFI_`), defined in `backend/app/config.py`.
Notable overrides:

| Var | Default | Purpose |
|-----|---------|---------|
| `DEFI_RPC_URL` | `https://eth.llamarpc.com` | Ethereum RPC for Aave + protocol-age binary search |
| `DEFI_LLAMA_PROTOCOLS_URL` | `https://api.llama.fi/protocols` | DefiLlama /protocols list (audit presence + contract address) |
| `DEFI_PROTOCOL_METADATA_INTERVAL_SECONDS` | `3600` | How often audit/age collectors refresh |
| `DEFI_LOOP_MIN_NOMINAL_SPREAD` | `0.0` | Pre-leverage `(deposit − borrow)` floor for loops (percentage points) |
| `DEFI_VOLATILITY_WINDOW` | `20` | Snapshots used for STDDEV + depth factor |
| `RANKER_WEIGHTS` | JSON | Per-metric weights for the scorer |

## Architecture

```
backend/
  app/
    api/routes.py          # GET /opportunities, /looping, /funding, /history, …
    calculations/
      looping.py           # recursive deposit→borrow→deposit simulator
      carry.py             # net_carry = spot + funding − borrow − fees
      ranker.py            # min-max normalize, weighted score, rank
      rating.py            # confidence from real signals (age/audit/persistence/depth)
      history_agg.py       # batched per-market today/yesterday/7d/30d aggregates
    collectors/
      aave.py              # Aave V3 on-chain reserve reader (web3.py)
      hyperliquid.py       # Hyperliquid perp funding REST adapter
      lending.py / funding.py  # persist snapshots + trigger calcs
      protocol_metadata.py # audit presence (DefiLlama) + deployment age (RPC)
    models/                # SQLAlchemy ORM (Protocol, Market, *Snapshot, *Calculation)
    schemas/responses.py   # Pydantic v2 response models
  alembic/                 # 001 initial + 002 protocol metadata
  tests/                   # 168 tests: pytest + pytest-asyncio

frontend/
  src/
    app/page.tsx           # OpportunitiesProvider wraps hero + leaderboard + feed
    components/            # terminal-hero, rating-leaderboard, opportunity-feed, detail
    lib/
      api.ts               # typed fetch wrapper + Loop/Carry opp types
      capital-context.tsx  # localStorage-backed capital simulation
      opportunities-context.tsx  # single shared /opportunities fetch
```

### Confidence: real signals, not a static allowlist

Each opportunity carries four real inputs (collected, not hardcoded):

| Signal | Source | Stubbed when… |
|--------|--------|---------------|
| `_protocol_age_days` | `ProtocolAgeCollector` (`get_code` binary search on the deployment block) | deployment unknown (non-EVM chain, no configured RPC) |
| `_audit_count` | `ProtocolAuditCollector` (DefiLlama `/protocols` audit presence) | no audits found |
| `_persistence_days` | `_history_depth_map` (distinct observation days, last 30d) | `< DEFI` persistence floor (7 days) |
| `_history_points` | `_history_depth_map` (snapshot count, last 30d) | drives the depth factor `min(1, n / 20)` |

Each stubbed signal costs `0.15` of completeness (floored at `0.4`); `confidence = 100 × completeness × depth`.

### Ranker + rating

`ranker.py` min-max normalizes seven metrics across the current batch and
applies `RANKER_WEIGHTS`. `rating.py` then min-max normalizes the scorer's
output to a 0-100 rating, assigns `🥇🥈🥉`, and computes confidence. For
`type=all`, `rerate_combined` re-scales loops and carries on one shared scale
so medals don't collide across types.

## Development

```bash
# backend
cd backend && source .venv/bin/activate
pytest                       # 168 passing
ruff check app              # clean

# frontend
cd frontend
npx tsc --noEmit            # clean
npm run lint                # clean
npm run build              # builds
```

## Branch policy

`main` is protected: direct pushes are rejected. All changes land via pull
request. Branch protection was applied with:

```bash
gh api -X PUT repos/:owner/:repo/branches/main/protection \
  -F required_pull_request_reviews.dismiss_stale_reviews=true \
  -F required_pull_request_reviews.required_approving_review_count=0 \
  -f required_status_checks=null \
  -F enforce_admins=true \
  -F restrictions=null
```

`required_approving_review_count=0` keeps solo self-merge possible — gate is
"PR-reviewed," not "peer-reviewed."

## Project layout / tasks

Detailed design notes and review history live under `tasks/`. The full review
report for this pass is at `tasks/feat-defi-alpha-scanner/review-report.md`.