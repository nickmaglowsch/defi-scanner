"use client";

import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getHistory, HistoryPointOut, LoopOpportunityOut, CarryOpportunityOut } from "@/lib/api";
import { protocolLink } from "@/lib/protocol-links";
import { getRiskLabel, getRiskColor } from "@/components/opportunity-card";
import { fmtPct } from "@/lib/utils";

// ── Small recharts wrapper ─────────────────────────────────────────────────

type ChartStatus = { loading: boolean; error: string | null; data: { time: string; value: number }[] };

function HistoryChart({ status, label }: { status: ChartStatus; label: string }) {
  const { loading, error, data } = status;
  return (
    <div className="space-y-1">
      <div className="text-sm font-medium">{label}</div>
      {loading && (
        <div className="py-6 text-center text-xs text-muted-foreground">Loading…</div>
      )}
      {!loading && error && (
        <div className="py-6 text-center text-xs text-destructive">{error}</div>
      )}
      {!loading && !error && data.length === 0 && (
        <div className="py-6 text-center text-xs text-muted-foreground">No data</div>
      )}
      {!loading && !error && data.length > 0 && (
        <div className="rounded-md border p-3">
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" tick={{ fontSize: 10 }} />
              <YAxis
                tick={{ fontSize: 10 }}
                tickFormatter={(v: number) => v.toFixed(2) + "%"}
              />
              <Tooltip
                formatter={(v: unknown) => [
                  typeof v === "number" ? v.toFixed(4) + "%" : String(v),
                  label,
                ]}
                labelFormatter={(l: unknown) => `Date: ${String(l)}`}
              />
              <Line
                type="monotone"
                dataKey="value"
                stroke="var(--color-chart-1)"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────────

function toChartData(pts: HistoryPointOut[]) {
  return pts.map((p) => ({
    time: new Date(p.observed_at).toLocaleDateString(),
    value: p.value,
  }));
}

function spreadSeries(deposits: HistoryPointOut[], borrows: HistoryPointOut[]) {
  const borrowMap = new Map(borrows.map((p) => [p.observed_at, p.value]));
  return deposits
    .filter((p) => borrowMap.has(p.observed_at))
    .map((p) => ({
      time: new Date(p.observed_at).toLocaleDateString(),
      value: p.value - borrowMap.get(p.observed_at)!,
    }));
}

// ── Main component ─────────────────────────────────────────────────────────

export type OpportunityDetailProps = {
  opp: LoopOpportunityOut | CarryOpportunityOut;
  onClose: () => void;
};

export default function OpportunityDetail({ opp, onClose }: OpportunityDetailProps) {
  const isLoop = "effective_yield" in opp;
  const loop = isLoop ? (opp as LoopOpportunityOut) : null;
  const carry = !isLoop ? (opp as CarryOpportunityOut) : null;

  const link = protocolLink(opp.protocol);

  // ── Chart state ──────────────────────────────────────────────────────────
  const empty: ChartStatus = { loading: false, error: null, data: [] };
  const [yieldChart, setYieldChart] = useState<ChartStatus>({ loading: true, error: null, data: [] });
  const [borrowChart, setBorrowChart] = useState<ChartStatus>(isLoop ? { loading: true, error: null, data: [] } : empty);
  const [spreadChart, setSpreadChart] = useState<ChartStatus>(isLoop ? { loading: true, error: null, data: [] } : empty);

  const marketId = opp.market_id ?? null;

  useEffect(() => {
    if (!marketId) {
      setYieldChart({ loading: false, error: "No market ID", data: [] });
      setBorrowChart({ loading: false, error: null, data: [] });
      setSpreadChart({ loading: false, error: null, data: [] });
      return;
    }

    if (isLoop) {
      // Fetch deposit and borrow in parallel; derive spread client-side
      let depositPts: HistoryPointOut[] = [];
      let borrowPts: HistoryPointOut[] = [];

      const depositFetch = getHistory({ type: "lending", market_id: marketId, field: "deposit_apy", limit: 100 })
        .then((pts) => { depositPts = pts; })
        .catch((e: Error) => {
          setYieldChart({ loading: false, error: e.message, data: [] });
        });

      const borrowFetch = getHistory({ type: "lending", market_id: marketId, field: "borrow_apy", limit: 100 })
        .then((pts) => { borrowPts = pts; })
        .catch((e: Error) => {
          setBorrowChart({ loading: false, error: e.message, data: [] });
        });

      Promise.all([depositFetch, borrowFetch]).then(() => {
        setYieldChart({ loading: false, error: null, data: toChartData(depositPts) });
        setBorrowChart({ loading: false, error: null, data: toChartData(borrowPts) });
        setSpreadChart({ loading: false, error: null, data: spreadSeries(depositPts, borrowPts) });
      });
    } else {
      // Carry: only yield chart
      getHistory({ type: "funding", market_id: marketId, field: "annualized_funding", limit: 100 })
        .then((pts) => setYieldChart({ loading: false, error: null, data: toChartData(pts) }))
        .catch((e: Error) => setYieldChart({ loading: false, error: e.message, data: [] }));
    }
  // ponytail: opp identity covers all derived fields; exhaustive deps would retrigger on every render
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [marketId, isLoop]);

  return (
    <div className="flex flex-col gap-6">
      {/* ── Header ── */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold">
            {isLoop ? "Loop" : "Carry"} / {opp.protocol} / {opp.asset}
          </h2>
          <div className={`mt-1 text-sm font-medium ${getRiskColor(opp.risk_score)}`}>
            {getRiskLabel(opp.risk_score)} risk
          </div>
          {link && (
            <a
              href={link}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-1 inline-block text-sm text-blue-500 hover:underline"
            >
              Open in {opp.protocol} →
            </a>
          )}
        </div>
        <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close">
          <X className="size-4" />
        </Button>
      </div>

      {/* ── Metrics ── */}
      <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
        {isLoop && loop && (
          <>
            <div>
              <div className="text-xs text-muted-foreground">Deposit APY</div>
              <div className="font-medium">{fmtPct(loop.deposit_apy)}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Borrow APY</div>
              <div className="font-medium">{fmtPct(loop.borrow_apy)}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Effective Yield</div>
              <div className="font-medium">{fmtPct(loop.effective_yield)}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Leverage</div>
              <div className="font-medium">{loop.leverage != null ? loop.leverage.toFixed(2) + "x" : "—"}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Safety Margin</div>
              <div className="font-medium">
                {loop.safety_margin != null ? (loop.safety_margin * 100).toFixed(1) + "%" : "—"}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Liq. Distance</div>
              <div className="font-medium">
                {loop.liquidation_distance != null ? (loop.liquidation_distance * 100).toFixed(1) + "%" : "—"}
              </div>
            </div>
          </>
        )}
        {!isLoop && carry && (
          <>
            <div>
              <div className="text-xs text-muted-foreground">Funding Yield</div>
              <div className="font-medium">{fmtPct(carry.funding_yield)}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Net Carry</div>
              <div className="font-medium">{fmtPct(carry.net_carry)}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Borrow Cost</div>
              <div className="font-medium">{fmtPct(carry.borrow_cost)}</div>
            </div>
          </>
        )}
        <div>
          <div className="text-xs text-muted-foreground">Risk Score</div>
          <div className="font-medium">{opp.risk_score != null ? opp.risk_score.toFixed(2) : "—"}</div>
        </div>
      </div>

      {/* ── Charts ── */}
      <div className="space-y-6">
        <HistoryChart status={yieldChart} label="Historical Yield" />
        {isLoop && (
          <>
            <HistoryChart status={borrowChart} label="Historical Borrow Rate" />
            <HistoryChart status={spreadChart} label="Historical Spread (Deposit − Borrow)" />
          </>
        )}
      </div>
    </div>
  );
}
