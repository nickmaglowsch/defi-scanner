# DeFi Alpha Scanner — Decision Engine Build

Transforms the scanner from a DefiLlama-style data explorer into a Bloomberg/TradingView-style decision engine: a unified opportunity feed with risk-first cards, an Opportunity Rating Engine (0-100 + confidence + leaderboard), a global capital simulator, historical yield context, and a terminal-style "Today's Best" hero.

See `updated-prd.md` for the codebase-grounded spec (including exact rating/confidence/Sharpe formulas) and `shared-context.md` for tech stack, test infra, and conventions shared across tasks.

## Tasks (11 total)

**Backend (TDD — pytest):**
- `task-01` Expose ranker component score breakdown
- `task-02` Yield history aggregation (today/yesterday/7D/30D)
- `task-03` Opportunity Rating Engine (rating/label/confidence/Sharpe, stubbed metadata)
- `task-04` Wire breakdown + history + rating + sharpe into the API (+ `api.ts` types, FundingSnapshotOut fix)

**Frontend (no tests — modified Next.js 16, read bundled docs first):**
- `task-05` Protocol deep-link static map
- `task-06` Capital simulator context + provider + input
- `task-07` Shared opportunity card (risk-first, ⭐/100, $ conversion, health, WHY breakdown, history)
- `task-08` Terminal-style "Today's Best" hero
- `task-09` Unified feed/screener + rebuilt landing page (deletes old tables)
- `task-10` Opportunity detail view + historical charts + deep link
- `task-11` Rating leaderboard 🥇🥈🥉

## Dependency graph

```
01 ─┐
02 ─┼─► 04 ─┬─────────────────────────► 06? (no) 
03 ─┘       │
01 ─► 03    │  (04 blocks all frontend data consumers)
            ├─► 07 ─┬─► 08 ─┐
06 ─────────┤       ├─► 11 ─┤
05 ─────────┼─► 10 ─┤       │
            │       └───────┴─► 09 (landing page, composes everything)
            └─► 09
```

Concretely:
- **01, 02** have no deps → can start immediately, in parallel.
- **03** depends on 01.
- **04** depends on 01, 02, 03 (the backend integration point; blocks all frontend data consumers).
- **05, 06** have no deps → can start immediately (frontend, parallel with backend).
- **07** depends on 04 + 06.
- **08** depends on 04 + 07.
- **10** depends on 04 + 05 + 07.
- **11** depends on 04 + 06 + 07.
- **09** depends on 04 + 06 + 07 + 08 + 10 + 11 (final composition; deletes old tables).

Suggested waves: (01,02,05,06) → (03) → (04) → (07) → (08,10,11) → (09).

## Stubbed / deferred data (accepted by the user)
Protocol age, audit history, and opportunity persistence are NOT collected. Tasks 03/04 use a static stubbed protocols-metadata map; rating **confidence** is partly synthetic and intentionally reads lower for stubbed-heavy / thin-history opportunities. No new collectors are built. See `updated-prd.md` → "Constraints accepted by the user".

## How to use these files
These task files are prompts for AI agents. Each is self-contained (plus `shared-context.md`). Implement in dependency order. **Delete each file after its task is completed.** When all task files are deleted, the feature is complete.

## Open questions / human input
None blocking — all planning questions were answered. Non-blocking notes are in `updated-prd.md` → "Open Questions" (relative rating scale always allows "Excellent"; Sharpe is null when volatility is unavailable).
