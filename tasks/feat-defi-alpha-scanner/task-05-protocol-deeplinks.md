# Task 05: Protocol Deep-Link Map

## Objective
Provide a static protocol-name → app-URL map and a helper so the detail view can render "Open in <protocol> →" only for known protocols (PRD #9).

## Context
**Quick Context:**
- No URL field exists on `Protocol`/`Market` and none will be added. This is a pure frontend static map — no backend, no schema change, no collector.
- Tiny, self-contained task with no data dependency; can run in parallel with backend work.

## ⚠️ MANDATORY FRONTEND PRE-READ
Before writing ANY frontend code: if `frontend/node_modules` is absent run `npm install` (in `frontend/`), then read `frontend/AGENTS.md` and the bundled docs in `frontend/node_modules/next/dist/docs/`. This is a modified Next.js 16 with breaking changes vs. training data — code written from memory will be wrong.

## Requirements
- New file `frontend/src/lib/protocol-links.ts`:
  - `PROTOCOL_LINKS: Record<string, string>` keyed by lowercase protocol name → app base URL (seed the protocols actually present: Aave → `https://app.aave.com`, plus Morpho/Spark/Hyperliquid if they appear in `getProtocols()`).
  - `protocolLink(name: string): string | null` — case-insensitive lookup; returns null when unknown.
- No UI here — task-10 consumes `protocolLink` and only renders the link when non-null.

## Existing Code References
- `frontend/src/lib/api.ts` — `getProtocols()` returns the protocol names to cover.

## Implementation Details
- Keep it a flat object literal + one lookup function. Mark with a `// ponytail:` comment that it's a static stand-in until protocols carry their own URL.

## Acceptance Criteria
- [ ] `protocolLink("Aave")`, `protocolLink("aave")` return the Aave URL; unknown protocol returns null
- [ ] No backend or schema changes
- [ ] `npm run build` succeeds (in `frontend/`)

## Dependencies
- Depends on: None
- Blocks: 10
