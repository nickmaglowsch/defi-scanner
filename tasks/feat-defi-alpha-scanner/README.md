# DeFi Alpha Scanner — MVP Vertical Slice

**Branch**: `feat/defi-alpha-scanner` | **Stack**: Python 3.12 / FastAPI + Next.js 15 | **Database**: PostgreSQL 16 + TimescaleDB

## Summary

Read-only DeFi intelligence platform that scans lending protocols and perpetual exchanges for yield opportunities. This MVP vertical slice delivers the full architecture end-to-end: Aave V3 on-chain collector → Hyperliquid REST collector → Postgres/TimescaleDB → calculation engine (looping, carry, ranker) → REST API → Next.js dashboard with cards, tables, and a history chart. Architecture is provider-pluggable — adding a new protocol is a single interface implementation.

## Task Overview

**9 tasks** | Estimated ~4-6 hours of implementation work (parallelizable waves reduce wall-clock time)

| # | Task | Dependencies | TDD? | Category |
|---|------|-------------|------|----------|
| 01 | Repo Scaffold & Dev Environment | None | No | Scaffold |
| 02 | DB Schema & Alembic Migrations | 01 | No | Schema |
| 03 | Aave V3 Lending Adapter & Collector | 02 | No | Collector |
| 04 | Hyperliquid Funding Adapter & Collector | 02, 03 | No | Collector |
| 05 | Looping Simulator | 02 | **Yes** | Calculation |
| 06 | Carry Calculator | 02, 05 | **Yes** | Calculation |
| 07 | Opportunity Engine & REST API | 02, 05, 06 | Ranker only | Integration |
| 08 | Alert Engine & Telegram Notification | 02, 07 | No | Feature |
| 09 | Frontend Dashboard | 01, 07 | No | UI |

## Dependency Graph

```
01 (scaffold)
 └── 02 (schema)
      ├── 03 (aave) ──┐
      │    └── 04 (hyperliquid) ──┐
      ├── 05 (loop calc, TDD) ────┤
      └── 06 (carry calc, TDD) ───┘
           └── 07 (API + ranker)
                ├── 08 (alerts)
                └── 09 (frontend)
```

**Parallel waves**:
- Wave 1: 01
- Wave 2: 02
- Wave 3a: 03, 05, 06 (parallel after 02)
- Wave 3b: 04 (after 03 — shares main.py collector wiring)
- Wave 4: 07
- Wave 5: 08, 09 (parallel after 07)

## How to Use

These task files are prompts for AI agents. Each is self-contained with all context, target files, steps, and acceptance criteria needed to complete it independently.

1. Execute tasks in dependency order (or use the parallel waves above)
2. Delete each task file after completion
3. When all files are deleted, the MVP vertical slice is complete

## Key Files (shared context)

| File | Purpose |
|------|---------|
| `shared-context.md` | Tech stack, test infra, conventions — referenced by all tasks |
| `updated-prd.md` | Full refined specification with architecture, schema, API, decisions log |
| `planning-questions.md` | Original discovery questions + user answers (historical record) |

## Decisions Recap

- **Python pivot**: FastAPI replaces Spring Boot. uv for deps, ruff for lint.
- **Aave data**: On-chain via web3.py (not The Graph). RAY conversion, embedded minimal ABI.
- **TimescaleDB**: Real extension via Docker image + Alembic migration.
- **Resilience**: Retry + skip. 3 attempts, exponential backoff.
- **Auth**: None. Public read-only API.
- **TDD**: Strict test-first for calculation logic (tasks 05, 06, ranker in 07).
- **Raw payload**: JSONB column on snapshots, not separate tables.
- **Ponytail**: Single API routes file, asyncio scheduler (no APScheduler), npm over pnpm, minimal modules.
