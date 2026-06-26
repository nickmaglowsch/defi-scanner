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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getFunding, getHistory, HistoryPointOut } from "@/lib/api";

export default function FundingChart() {
  const [markets, setMarkets] = useState<{ market_id: string }[]>([]);
  const [selectedMarket, setSelectedMarket] = useState<string>("");
  const [history, setHistory] = useState<HistoryPointOut[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chartType, setChartType] = useState<"funding" | "lending">("funding"); // stub

  // Fetch available markets on mount
  useEffect(() => {
    getFunding({ limit: 50 })
      .then((snaps) => {
        // dedupe by market_id
        const seen = new Set<string>();
        const unique: { market_id: string }[] = [];
        for (const s of snaps) {
          if (!seen.has(s.market_id)) {
            seen.add(s.market_id);
            unique.push({ market_id: s.market_id });
          }
        }
        setMarkets(unique);
        if (unique.length > 0 && !selectedMarket) {
          setSelectedMarket(unique[0].market_id);
        }
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Fetch history when market changes
  useEffect(() => {
    if (!selectedMarket) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- legitimate data-fetching effect
    setLoading(true);
     
    setError(null);
    getHistory({
      type: "funding",
      market_id: selectedMarket,
      field: "annualized_funding",
      limit: 100,
    })
      .then(setHistory)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [selectedMarket]);

  const chartData = history.map((p) => ({
    time: new Date(p.observed_at).toLocaleDateString(),
    value: p.value,
  }));

  return (
    <div className="space-y-4">
      {/* Toolbar: market selector + chart type stubs */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">
            Market
          </label>
          <Select value={selectedMarket} onValueChange={(v) => setSelectedMarket(v ?? "")}>
            <SelectTrigger className="w-64">
              <SelectValue placeholder="Select market" />
            </SelectTrigger>
            <SelectContent>
              {markets.map((m) => (
                <SelectItem key={m.market_id} value={m.market_id}>
                  {m.market_id.slice(0, 16)}…
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Stub chart type buttons */}
        <button
          onClick={() => setChartType("funding")}
          className={`rounded-md px-3 py-1.5 text-xs font-medium border ${
            chartType === "funding"
              ? "bg-primary text-primary-foreground border-primary"
              : "bg-background text-muted-foreground border-input hover:bg-muted"
          }`}
        >
          Funding Rate
        </button>
        <button
          onClick={() =>
            console.log("coming soon: lending rate chart")
          }
          className="rounded-md px-3 py-1.5 text-xs font-medium border border-input bg-background text-muted-foreground hover:bg-muted"
        >
          Lending Rate
        </button>
      </div>

      {/* Chart */}
      {loading && (
        <div className="py-8 text-center text-sm text-muted-foreground">
          Loading chart…
        </div>
      )}
      {error && (
        <div className="py-8 text-center text-sm text-destructive">{error}</div>
      )}
      {!loading && !error && chartData.length === 0 && (
        <div className="py-8 text-center text-sm text-muted-foreground">
          No history data for this market.
        </div>
      )}
      {!loading && !error && chartData.length > 0 && (
        <div className="rounded-md border p-4">
          <ResponsiveContainer width="100%" height={350}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" tick={{ fontSize: 11 }} />
              <YAxis
                tick={{ fontSize: 11 }}
                tickFormatter={(v: number) => v.toFixed(2) + "%"}
              />
              <Tooltip
                formatter={(v: unknown) => [
                  typeof v === "number" ? v.toFixed(4) + "%" : String(v),
                  "Funding",
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
