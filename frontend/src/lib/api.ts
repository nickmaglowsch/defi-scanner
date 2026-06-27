const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Response types (match backend/app/schemas/responses.py) ──────────────

export interface ProtocolOut {
  id: string;
  name: string;
  type: string;
  chain: string | null;
  risk_score: number;
}

export interface MarketOut {
  id: string;
  protocol_id: string;
  asset: string;
  market_type: string;
}

export interface LendingSnapshotOut {
  id: string;
  market_id: string;
  observed_at: string;
  deposit_apy: number | null;
  borrow_apy: number | null;
  utilization: number | null;
  available_liquidity: number | null;
  total_supplied: number | null;
  total_borrowed: number | null;
  tvl: number | null;
}

export interface FundingSnapshotOut {
  id: string;
  market_id: string;
  observed_at: string;
  asset: string;
  protocol: string;
  funding_rate: number | null;
  funding_interval_hours: number | null;
  annualized_funding: number | null;
  open_interest: number | null;
  volume_24h: number | null;
  long_short_ratio: number | null;
  mark_price: number | null;
  index_price: number | null;
}

export interface YieldHistoryOut {
  today: number | null;
  yesterday: number | null;
  avg_7d: number | null;
  avg_30d: number | null;
}

/** Generic opportunity schema with strategy_type discriminator. */
export interface OpportunityOut {
  strategy_type: "loop" | "carry" | string;
  protocol: string;
  asset: string;
  chain?: string | null;
  net_apy: number | null;
  risk_score: number | null;
  score: number;
  rank: number;
  market_id?: string | null;
  breakdown?: Record<string, number> | null;
  weights?: Record<string, number> | null;
  rating?: number | null;
  rating_label?: string | null;
  confidence?: number | null;
  medal?: string | null;
  sharpe?: number | null;
  history?: YieldHistoryOut | null;
  /** Strategy-specific fields (loop leverage, carry funding yield, etc.) */
  strategy_details: Record<string, number | null>;
  // Task-10 future fields
  percentile_90d?: number | null;
  historical_rank?: string | null;
}

// ponytail: deprecated — kept so existing call-sites compile without changes.
export type LoopOpportunityOut = OpportunityOut;
export type CarryOpportunityOut = OpportunityOut;

export interface HistoryPointOut {
  observed_at: string;
  value: number;
}

// ── Opportunity helpers ───────────────────────────────────────────────────

/** Discriminate a loop opportunity by strategy_type. */
export function isLoop(opp: OpportunityOut): boolean {
  return opp.strategy_type === "loop";
}

/** The headline yield: net_apy (unified field) — falls back to strategy_details. */
export function oppYield(opp: OpportunityOut): number | null {
  return opp.net_apy;
}

// ── Generic fetch wrapper ─────────────────────────────────────────────────

async function fetchAPI<T>(
  path: string,
  params?: Record<string, string | number>
): Promise<T> {
  let url = `${BASE}${path}`;
  if (params) {
    const sp = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== "" && v !== undefined && v !== null) sp.set(k, String(v));
    }
    const qs = sp.toString();
    if (qs) url += `?${qs}`;
  }
  const res = await fetch(url);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}

// ── Typed endpoint functions ──────────────────────────────────────────────

export interface OppParams {
  type?: string;
  asset?: string;
  protocol?: string;
  min_yield?: number;
  min_liquidity?: number;
  limit?: number;
  sort?: string;
}
export async function getOpportunities(
  params?: OppParams
): Promise<OpportunityOut[]> {
  return fetchAPI<OpportunityOut[]>(
    "/api/v1/opportunities",
    params as Record<string, string | number>
  );
}

export interface LoopParams {
  asset?: string;
  protocol?: string;
  min_yield?: number;
  min_liquidity?: number;
  limit?: number;
}
export async function getLooping(
  params?: LoopParams
): Promise<OpportunityOut[]> {
  return fetchAPI<OpportunityOut[]>("/api/v1/looping", params as Record<string, string | number>);
}

export interface FundingParams {
  asset?: string;
  protocol?: string;
  limit?: number;
}
export async function getFunding(
  params?: FundingParams
): Promise<FundingSnapshotOut[]> {
  return fetchAPI<FundingSnapshotOut[]>("/api/v1/funding", params as Record<string, string | number>);
}

export interface HistoryParams {
  type?: string;
  market_id?: string;
  field?: string;
  from?: string;
  to?: string;
  limit?: number;
}
export async function getHistory(
  params: HistoryParams
): Promise<HistoryPointOut[]> {
  return fetchAPI<HistoryPointOut[]>("/api/v1/history", params as Record<string, string | number>);
}

export async function getProtocols(): Promise<ProtocolOut[]> {
  return fetchAPI<ProtocolOut[]>("/api/v1/protocols");
}

export async function getAssets(): Promise<string[]> {
  return fetchAPI<string[]>("/api/v1/assets");
}
