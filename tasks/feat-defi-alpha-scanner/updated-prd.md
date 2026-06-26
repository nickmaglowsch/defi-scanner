# Updated PRD — DeFi Alpha Scanner (MVP Vertical Slice)

## Scope

A read-only intelligence platform scanning DeFi lending protocols and perpetual exchanges for yield opportunities. This MVP vertical slice delivers the full architecture shape end-to-end: data collection → normalized storage → calculation engine → REST API → dashboard. Only one lending adapter (Aave V3, on-chain via web3.py) and one funding adapter (Hyperliquid, REST via httpx). Architecture is provider-pluggable — adding Morpho, Spark, GMX, Drift, Vertex later is a single interface implementation each.

## Tech Stack (Python Pivot)

| Layer | Technology | Notes |
|-------|-----------|-------|
| Backend | Python 3.12, FastAPI, Uvicorn | Replaces Java/Spring Boot |
| ORM | SQLAlchemy 2.0 (async) + asyncpg | Async throughout |
| Migrations | Alembic | Sync engine for DDL |
| Aave data | web3.py + Ethereum RPC | On-chain `getReserveData()` per reserve |
| Hyperliquid data | httpx (async HTTP) | `api.hyperliquid.xyz/info` |
| Telegram alerts | httpx | POST to Telegram Bot API |
| Frontend | Next.js 15, TypeScript, Tailwind, shadcn/ui, TanStack Table, Recharts | App Router |
| Package mgmt | uv (backend, pyproject.toml), npm (frontend) | |
| Lint/format | ruff + black | ruff does both; mypy optional, off by default |
| Database | PostgreSQL 16 + TimescaleDB | `timescale/timescaledb:pg16` Docker image |
| Dev orchestration | Docker Compose | root `docker-compose.yml`: timescaledb + backend + frontend |
| Tests | pytest + pytest-asyncio | TDD for calculations; mock adapters for collector tests |

## Architecture

```
┌───────────┐    ┌───────────┐
│ Aave V3   │    │Hyperliquid│
│ (on-chain)│    │  (REST)   │
└─────┬─────┘    └─────┬─────┘
      │ web3.py        │ httpx
      ▼                ▼
┌─────────────────────────────────┐
│         Collectors              │
│  AaveV3Adapter  HyperliquidAdapter│
│  (implements LendingProvider /  │
│   FundingProvider protocols)    │
└──────────────┬──────────────────┘
               │ SQLAlchemy async
               ▼
┌─────────────────────────────────┐
│   PostgreSQL + TimescaleDB      │
│   lending_snapshots (hypertable)│
│   funding_snapshots (hypertable)│
│   loop_calculations             │
│   carry_calculations            │
│   protocols, markets, alerts    │
└──────────────┬──────────────────┘
               │
      ┌────────┴────────┐
      ▼                 ▼
┌───────────┐    ┌──────────────┐
│Calculation│    │   REST API   │
│ Engine    │    │ 6 endpoints  │
│ looping   │    │ FastAPI      │
│ carry     │    │ routes       │
│ ranker    │    └──────┬───────┘
└───────────┘           │ JSON
                        ▼
               ┌────────────────┐
               │ Next.js Dashboard│
               │ Home cards      │
               │ Loop table      │
               │ Carry table     │
               │ Funding chart   │
               └────────────────┘

┌───────────┐
│Alerts Engine│──► Telegram webhook (real)
│              │──► Email/Discord/Slack (stub → log)
└──────────────┘
```

## Monorepo Layout

```
defi-scanner/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app, lifespan, CORS
│   │   ├── config.py            # pydantic-settings, env vars
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   └── session.py       # async engine + session factory
│   │   ├── models/              # SQLAlchemy ORM models
│   │   │   ├── __init__.py
│   │   │   ├── protocol.py
│   │   │   ├── market.py
│   │   │   ├── lending_snapshot.py
│   │   │   ├── funding_snapshot.py
│   │   │   ├── loop_calculation.py
│   │   │   ├── carry_calculation.py
│   │   │   └── alert.py
│   │   ├── schemas/             # Pydantic response models
│   │   │   ├── __init__.py
│   │   │   └── responses.py
│   │   ├── collectors/          # External data adapters
│   │   │   ├── __init__.py
│   │   │   ├── base.py          # LendingProvider, FundingProvider protocols
│   │   │   ├── aave.py          # Aave V3 on-chain adapter
│   │   │   ├── hyperliquid.py   # Hyperliquid REST adapter
│   │   │   ├── lending.py       # Lending collector service (orchestrates adapters)
│   │   │   └── funding.py       # Funding collector service
│   │   ├── calculations/        # Pure deterministic math
│   │   │   ├── __init__.py
│   │   │   ├── looping.py       # Leveraged looping simulator
│   │   │   ├── carry.py         # Carry trade calculator
│   │   │   └── ranker.py        # Opportunity scoring + ranking
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── routes.py        # All 6 endpoints (ponytail: single file)
│   │   └── alerts/
│   │       ├── __init__.py
│   │       ├── engine.py        # Threshold evaluation, alert firing
│   │       └── channels.py      # Telegram (real) + stub Email/Discord/Slack
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 001_initial.py
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_aave_adapter.py
│   │   ├── test_hyperliquid_adapter.py
│   │   ├── test_looping.py
│   │   ├── test_carry.py
│   │   ├── test_ranker.py
│   │   ├── test_api.py
│   │   └── test_alerts.py
│   ├── pyproject.toml
│   └── uv.lock
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   └── page.tsx
│   │   ├── components/
│   │   │   ├── home-cards.tsx
│   │   │   ├── loop-table.tsx
│   │   │   ├── carry-table.tsx
│   │   │   └── funding-chart.tsx
│   │   └── lib/
│   │       └── api.ts
│   ├── package.json
│   ├── tailwind.config.ts
│   └── tsconfig.json
├── docker-compose.yml
└── .gitignore
```

## Database Schema

### protocols
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| name | VARCHAR UNIQUE | e.g. "Aave V3", "Hyperliquid" |
| type | VARCHAR | 'lending' or 'derivatives' |
| chain | VARCHAR | e.g. "ethereum" |
| risk_score | FLOAT | hardcoded protocol risk (0-10) |
| created_at | TIMESTAMPTZ | |

### markets
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| protocol_id | UUID FK → protocols | |
| asset | VARCHAR | e.g. "USDC" |
| market_type | VARCHAR | 'lending' or 'perp' |
| created_at | TIMESTAMPTZ | |

### lending_snapshots (TimescaleDB hypertable on `observed_at`)
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| market_id | UUID FK → markets | |
| observed_at | TIMESTAMPTZ NOT NULL | hypertable partition key |
| deposit_apy | FLOAT | % annualized |
| borrow_apy | FLOAT | % annualized |
| utilization | FLOAT | borrow / supply ratio |
| available_liquidity | FLOAT | |
| total_supplied | FLOAT | |
| total_borrowed | FLOAT | |
| tvl | FLOAT | |
| raw_payload | JSONB | full on-chain response for recalc |

### funding_snapshots (TimescaleDB hypertable on `observed_at`)
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| market_id | UUID FK → markets | |
| observed_at | TIMESTAMPTZ NOT NULL | hypertable partition key |
| funding_rate | FLOAT | raw decimal per interval |
| funding_interval_hours | FLOAT | e.g. 1 for Hyperliquid |
| annualized_funding | FLOAT | computed: rate * 8760 / interval |
| open_interest | FLOAT | |
| volume_24h | FLOAT | |
| long_short_ratio | FLOAT | |
| mark_price | FLOAT | |
| index_price | FLOAT | |
| raw_payload | JSONB | full REST response for recalc |

### loop_calculations
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| lending_snapshot_id | UUID FK → lending_snapshots | |
| calc_version | VARCHAR | "loop-v1" |
| created_at | TIMESTAMPTZ | |
| input_capital | FLOAT | |
| input_target_ltv | FLOAT | |
| input_safety_buffer | FLOAT | |
| input_max_loops | INT | |
| deposited_capital | FLOAT | output |
| borrowed_capital | FLOAT | output |
| net_apy | FLOAT | output |
| effective_yield | FLOAT | output |
| leverage | FLOAT | output |
| safety_margin | FLOAT | output |
| liquidation_distance | FLOAT | output |
| risk_score | FLOAT | output |

### carry_calculations
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| funding_snapshot_id | UUID FK → funding_snapshots | |
| lending_snapshot_id | UUID FK → lending_snapshots (nullable) | |
| calc_version | VARCHAR | "carry-v1" |
| created_at | TIMESTAMPTZ | |
| spot_yield | FLOAT | |
| funding_yield | FLOAT | |
| borrow_cost | FLOAT | |
| trading_fees | FLOAT | |
| net_carry | FLOAT | output |
| risk_score | FLOAT | output |
| expected_annual_return | FLOAT | output |

### alerts
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| alert_type | VARCHAR | 'loop_yield', 'funding_rate', 'net_carry', 'borrow_apy' |
| threshold_value | FLOAT | |
| triggered_value | FLOAT | |
| market_id | UUID FK → markets | |
| snapshot_id | UUID | (nullable, whichever triggered) |
| channel | VARCHAR | 'telegram','email','discord','slack' |
| status | VARCHAR | 'fired', 'acknowledged' |
| fired_at | TIMESTAMPTZ | |
| raw_message | TEXT | |

## REST API Endpoints

All under `/api/v1/`. No auth. CORS allows frontend origin (env-configurable).

| Method | Path | Description | Query Params |
|--------|------|-------------|-------------|
| GET | `/opportunities` | Ranked opportunities (all types) | `type=loop|carry`, `asset`, `protocol`, `min_yield`, `min_liquidity`, `limit` |
| GET | `/looping` | Loop opportunities (from loop_calculations) | `asset`, `protocol`, `min_yield`, `min_liquidity`, `limit` |
| GET | `/funding` | Latest funding rates | `asset`, `protocol`, `limit` |
| GET | `/history` | Historical snapshots/charts | `type=funding|lending`, `market_id`, `from`, `to`, `limit` |
| GET | `/protocols` | List protocols | none |
| GET | `/assets` | List assets | none |

## Calculation Engine

### Looping Simulator (calc_version: "loop-v1")
Pure function. Inputs: deposit_apy, borrow_apy, max_ltv, liquidation_threshold, initial_capital, target_ltv, safety_buffer, max_loops. Simulates recursive deposit→borrow→deposit cycle. Outputs match `loop_calculations` columns above.

### Carry Calculator (calc_version: "carry-v1")
Pure function. Inputs: spot_yield, funding_yield, borrow_cost, trading_fees. Output: net_carry = funding_yield + spot_yield - borrow_cost - trading_fees. Risk score from volatility proxy.

### Opportunity Ranker (configurable weights)
Score = Σ(weight_i × normalized_metric_i). Metrics: yield_score, liquidity_score, tvl_score, stability_score, utilization_penalty, volatility_penalty, protocol_risk. Volatility = STDDEV of last 20 funding snapshots per market (neutral/zero during bootstrap <20 snapshots). Weights configurable via env or config dict.

## Alert Engine

Evaluates thresholds against latest snapshots + calculations on each collector cycle:
- Loop Yield > X% → fire
- Funding Rate > X% → fire
- Net Carry > X% → fire
- Borrow APY < X% → fire

Channels: Telegram webhook (real impl via httpx POST to Bot API), Email/Discord/Slack (stub: log message, return silently).

## Collectors

Run on an asyncio loop with configurable interval in the FastAPI lifespan. Each cycle:
1. Query external source (web3.py for Aave, httpx for Hyperliquid)
2. Retry up to 3 times with exponential backoff (1s, 2s, 4s) on failure
3. On exhaustion: log error, skip cycle
4. On success: parse raw response, upsert protocol/market, insert snapshot with raw_payload

## Decisions Log

| # | Decision | Rationale |
|---|----------|-----------|
| Q1 | Flat root monorepo: `backend/` + `frontend/` | No monorepo tooling needed; builds are independent |
| Q2 | Python 3.12 + FastAPI (pivot from Java/Spring Boot) | User directive; uv for deps, ruff for lint |
| Q3 | npm for frontend | Ships with Node.js, sufficient for single package |
| Q4 | Aave V3 on-chain via web3.py | User directive; requires RPC, ABI, RAY conversion |
| Q5 | TimescaleDB extension (Docker image) | Hypertables for time-series snapshots; fallback to plain PG if extension absent |
| Q6 | Retry + skip resilience | 3 retries with backoff; log and skip on exhaustion |
| Q7 | No API auth | Read-only public data; CORS to frontend origin only |
| Q8 | httpx for REST calls | Async, modern; web3.py for on-chain |
| Q9 | Volatility = STDDEV of own funding snapshots | Zero-cost, improves over time; neutral until ≥20 snapshots |
| Q10 | TDD for calculation logic | Test-first for looping, carry, ranker; test-after for adapters/API |
| — | `raw_payload` JSONB column on snapshots | Single table, simpler than separate raw tables; full recalc-ability preserved |
| — | All 6 API routes in single `routes.py` | Ponytail: one file, thin DB queries; split later if file exceeds ~300 lines |
| — | `asyncio` loop in FastAPI lifespan for collectors | No extra scheduler dependency; APScheduler added later if needed |

## Out of Scope (architecture seams preserved)

- Morpho, Spark, GMX, Drift, Vertex collector implementations — interfaces exist (`LendingProvider`, `FundingProvider`); adding = one file each
- Email/Discord/Slack real delivery — stub channels that log; Telegram is the one real channel
- ECS Fargate, CloudWatch, GitHub Actions CI/CD — local `docker-compose.yml` only
- Wallet connection, trading, execution, Phase 2-5
- Multiple history charts — one (funding over time); rest are stubs
- mypy type checking — off by default; ruff is sufficient for MVP

## Open Questions

_(None — all major decisions resolved by user answers above. Minor implementation details left to implementer judgment per task.)_
