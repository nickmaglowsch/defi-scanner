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

export interface LoopOpportunityOut {
  protocol: string;
  asset: string;
  deposit_apy: number | null;
  borrow_apy: number | null;
  effective_yield: number | null;
  leverage: number | null;
  safety_margin: number | null;
  liquidation_distance: number | null;
  risk_score: number | null;
  score: number;
  rank: number;
  // Task-04 enrichment fields
  market_id?: string | null;
  breakdown?: Record<string, number> | null;
  weights?: Record<string, number> | null;
  rating?: number | null;
  rating_label?: string | null;
  confidence?: number | null;
  medal?: string | null;
  sharpe?: number | null;
  history?: YieldHistoryOut | null;
}

export interface CarryOpportunityOut {
  protocol: string;
  asset: string;
  funding_yield: number | null;
  spot_yield: number | null;
  borrow_cost: number | null;
  trading_fees: number | null;
  net_carry: number | null;
  risk_score: number | null;
  score: number;
  rank: number;
  // Task-04 enrichment fields
  market_id?: string | null;
  breakdown?: Record<string, number> | null;
  weights?: Record<string, number> | null;
  rating?: number | null;
  rating_label?: string | null;
  confidence?: number | null;
  medal?: string | null;
  sharpe?: number | null;
  history?: YieldHistoryOut | null;
}

export interface HistoryPointOut {
  observed_at: string;
  value: number;
}

// ── Opportunity union helpers ──────────────────────────────────────────────

/** Discriminate a loop opportunity from a carry one. */
export function isLoop(
  opp: LoopOpportunityOut | CarryOpportunityOut
): opp is LoopOpportunityOut {
  return "effective_yield" in opp;
}

/** The headline yield for an opportunity: effective_yield for loops, net_carry for carries. */
export function oppYield(opp: LoopOpportunityOut | CarryOpportunityOut): number | null {
  return isLoop(opp) ? opp.effective_yield : opp.net_carry;
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
): Promise<(LoopOpportunityOut | CarryOpportunityOut)[]> {
  return fetchAPI<(LoopOpportunityOut | CarryOpportunityOut)[]>(
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
): Promise<LoopOpportunityOut[]> {
  return fetchAPI<LoopOpportunityOut[]>("/api/v1/looping", params as Record<string, string | number>);
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
