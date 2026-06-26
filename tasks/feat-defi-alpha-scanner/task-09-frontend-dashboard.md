# Task 09: Frontend Dashboard

## Objective
Build the Next.js dashboard with Home cards (Best Loop, Best Carry, Best Stable Yield, Highest Funding), Loop Opportunities table with filters, Carry Opportunities table, and one history chart (funding rate over time).

## Context
This is the user-facing UI. It fetches data from the REST API (task-07) and renders the opportunity intelligence. The frontend was initialized in task-01 with Next.js, Tailwind, shadcn/ui, TanStack Table, and Recharts. All API calls go through a shared client module. See `updated-prd.md` Sections "Dashboard" and "REST API Endpoints".

**Quick Context**:
- API base URL: `NEXT_PUBLIC_API_URL` env var (set in docker-compose, task-01).
- shadcn/ui components already available via `npx shadcn-ui@latest add` — add `card`, `table`, `select`, `input`, `button` as needed.
- TanStack Table for sortable/filterable tables.
- Recharts for the funding history chart.

## Target Files
- `frontend/src/app/layout.tsx` (update if needed)
- `frontend/src/app/page.tsx`
- `frontend/src/lib/api.ts`
- `frontend/src/components/home-cards.tsx`
- `frontend/src/components/loop-table.tsx`
- `frontend/src/components/carry-table.tsx`
- `frontend/src/components/funding-chart.tsx`
- `frontend/src/types/` (optional — TypeScript types for API responses)

## Dependencies
- task-07 (API must be running — the dashboard fetches from it)
- task-01 (frontend init + shadcn/ui setup)

## Steps

### Part A: API Client & Types
1. Write `frontend/src/lib/api.ts`:
   - Base URL from `process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"`.
   - Typed fetch wrappers (ponytail: simple `fetch`, no axios dependency):
     ```typescript
     async function fetchAPI<T>(path: string, params?: Record<string, string>): Promise<T>
     ```
   - Exported functions matching each endpoint:
     - `getOpportunities(params)` → `GET /api/v1/opportunities`
     - `getLooping(params)` → `GET /api/v1/looping`
     - `getFunding(params)` → `GET /api/v1/funding`
     - `getHistory(params)` → `GET /api/v1/history`
     - `getProtocols()` → `GET /api/v1/protocols`
     - `getAssets()` → `GET /api/v1/assets`
   - TypeScript interfaces for response types (inline or in a types file — ponytail: inline in api.ts if < 50 lines of types; else `frontend/src/types/api.ts`).

### Part B: Components
2. Install required shadcn/ui components: `npx shadcn-ui@latest add card table select input button` (select/interactive filters).
3. Write `frontend/src/components/home-cards.tsx`:
   - 4 cards in a responsive grid (1 col mobile, 2 col tablet, 4 col desktop).
   - Each card: shadcn `<Card>` with title + value + subtitle.
   - **Best Loop**: fetches `/looping?limit=1`, displays protocol/asset + effective_yield%.
   - **Best Carry**: fetches `/opportunities?type=carry&limit=1`, displays net_carry%.
   - **Best Stable Yield**: fetches `/looping?asset=USDC&limit=1` (or USDT fallback), displays effective_yield%.
   - **Highest Funding**: fetches `/funding?limit=1`, displays asset + annualized_funding%.
   - Loading state: skeleton placeholder (shadcn Skeleton or simple "Loading...").
   - Error state: "Unable to load" with retry.
   - All cards fetch in parallel on mount via `Promise.all` or separate `useEffect` hooks.
4. Write `frontend/src/components/loop-table.tsx`:
   - Fetches `/looping` with user-adjustable filters.
   - Filter bar above table: Asset (select dropdown, populated from `/assets`), Protocol (select, from `/protocols`), Min Yield (number input), Min Liquidity (number input).
   - TanStack Table with columns: Protocol | Asset | Deposit APY | Borrow APY | Effective Yield | Score.
   - Sortable by Effective Yield (default descending), Score.
   - Format percentages to 2 decimal places with "%" suffix.
   - Loading/empty/error states handled.
5. Write `frontend/src/components/carry-table.tsx`:
   - Same pattern as loop-table but for carry opportunities.
   - Fetches `/opportunities?type=carry`.
   - Columns: Asset | Protocol | Funding Rate | Borrow Cost | Net Carry | Score.
   - Filters: Asset, Protocol, Min Net Carry.
6. Write `frontend/src/components/funding-chart.tsx`:
   - Fetches `/history?type=funding&market_id=<selected>&limit=100`.
   - Market selector (dropdown, populated from `/funding` markets).
   - Recharts `<LineChart>` with X = observed_at (time), Y = annualized_funding%.
   - Tooltip showing exact value + timestamp on hover.
   - Responsive container.
   - Ponytail: one chart, funding rate over time. Other chart types are stubs — add placeholder tabs/buttons that log "coming soon" but don't implement.

### Part C: Page Assembly
7. Update `frontend/src/app/page.tsx`:
   - Import and render: `<HomeCards />`, `<LoopTable />`, `<CarryTable />`, `<FundingChart />`.
   - Vertical layout with sections separated by headings.
8. Update `frontend/src/app/layout.tsx` if needed: ensure Tailwind globals, font, metadata title "DeFi Alpha Scanner".
9. Test: run backend (with some data from collectors or seed script), run frontend, verify:
   - Home cards show values (or "No data" if DB empty).
   - Tables render with correct columns.
   - Filters work (selecting asset narrows results).
   - Chart renders with time axis + funding line (or empty state).

## Acceptance Criteria
- [ ] Home page renders 4 cards in responsive grid: Best Loop, Best Carry, Best Stable Yield, Highest Funding
- [ ] Cards show skeleton while loading; error state with retry on fetch failure
- [ ] Loop Opportunities table displays with columns Protocol|Asset|Deposit|Borrow|Effective Yield|Score
- [ ] Loop table filters (Asset, Protocol, Min Yield, Min Liquidity) narrow results
- [ ] Carry Opportunities table displays with columns Asset|Protocol|Funding|Borrow|Net Carry|Score
- [ ] Carry table filters work (Asset, Protocol, Min Net Carry)
- [ ] Funding chart renders a Recharts line chart with time axis and annualized funding %
- [ ] Market selector on chart changes displayed market
- [ ] All API calls go through `lib/api.ts` with typed responses
- [ ] Percentage values formatted to 2 decimal places with "%"
- [ ] Dashboard works with empty DB (shows "No data available" states, no crashes)
- [ ] `npm run build` succeeds in `frontend/`
- [ ] `npm run lint` passes (per Next.js defaults)
