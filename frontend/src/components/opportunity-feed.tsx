"use client";

import { useEffect, useState } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import OpportunityCard from "@/components/opportunity-card";
import {
  getOpportunities,
  getAssets,
  getProtocols,
  isLoop,
  type LoopOpportunityOut,
  type CarryOpportunityOut,
} from "@/lib/api";
import { useOpportunities } from "@/lib/opportunities-context";

type AnyOpp = LoopOpportunityOut | CarryOpportunityOut;

const SORT_OPTIONS = [
  { value: "return", label: "Expected Return" },
  { value: "risk", label: "Risk" },
  { value: "confidence", label: "Confidence" },
  { value: "sharpe", label: "Sharpe (approx)" },
  { value: "liquidity", label: "Liquidity" },
];

export default function OpportunityFeed({
  onOpenDetail,
}: {
  onOpenDetail?: (opp: AnyOpp) => void;
}) {
  // Shared base set from the page-level provider (sort=return, no filters, limit
  // 50). When the UI controls are at their defaults, this IS the feed's query →
  // reuse it and skip a duplicate fetch. Only diverge (own fetch) when a filter
  // or sort that the base set wasn't built with is active.
  const { opps: baseOpps, loading: baseLoading, error: baseError } = useOpportunities();

  const [data, setData] = useState<AnyOpp[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [typeFilter, setTypeFilter] = useState("");
  const [assetFilter, setAssetFilter] = useState("");
  const [protocolFilter, setProtocolFilter] = useState("");
  const [sort, setSort] = useState("return");

  const [assets, setAssets] = useState<string[]>([]);
  const [protocols, setProtocols] = useState<string[]>([]);

  const isDefault = !typeFilter && !assetFilter && !protocolFilter && sort === "return";

  useEffect(() => {
    getAssets().then(setAssets).catch(() => {});
    getProtocols()
      .then((p) => setProtocols(p.map((x) => x.name)))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (isDefault) return; // served by the shared base set
    let cancelled = false;
    setLoading(true);
    setError(null);
    getOpportunities({
      ...(typeFilter && { type: typeFilter }),
      ...(assetFilter && { asset: assetFilter }),
      ...(protocolFilter && { protocol: protocolFilter }),
      sort,
      limit: 50,
    })
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [typeFilter, assetFilter, protocolFilter, sort, isDefault]);

  const displayData = isDefault ? baseOpps : data;
  const displayLoading = isDefault ? baseLoading : loading;
  const displayError = isDefault ? baseError : error;

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">Type</label>
          <Select
            value={typeFilter || "all"}
            onValueChange={(v) => setTypeFilter(v ? (v === "all" ? "" : v) : "")}
          >
            <SelectTrigger className="w-32">
              <SelectValue placeholder="All Types" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Types</SelectItem>
              <SelectItem value="loop">Loop</SelectItem>
              <SelectItem value="carry">Carry</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">Asset</label>
          <Select
            value={assetFilter || "all"}
            onValueChange={(v) => setAssetFilter(v ? (v === "all" ? "" : v) : "")}
          >
            <SelectTrigger className="w-36">
              <SelectValue placeholder="All Assets" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Assets</SelectItem>
              {assets.map((a) => (
                <SelectItem key={a} value={a}>
                  {a}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">Protocol</label>
          <Select
            value={protocolFilter || "all"}
            onValueChange={(v) => setProtocolFilter(v ? (v === "all" ? "" : v) : "")}
          >
            <SelectTrigger className="w-36">
              <SelectValue placeholder="All Protocols" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Protocols</SelectItem>
              {protocols.map((p) => (
                <SelectItem key={p} value={p}>
                  {p}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">Sort by</label>
          <Select value={sort} onValueChange={(v) => { if (v) setSort(v); }}>
            <SelectTrigger className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {SORT_OPTIONS.map((o) => (
                <SelectItem key={o.value} value={o.value}>
                  {o.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* States */}
      {displayLoading && (
        <div className="py-8 text-center text-sm text-muted-foreground">Loading…</div>
      )}
      {displayError && (
        <div className="py-8 text-center text-sm text-destructive">{displayError}</div>
      )}
      {!displayLoading && !displayError && displayData.length === 0 && (
        <div className="py-8 text-center text-sm text-muted-foreground">
          No opportunities found.
        </div>
      )}

      {/* Cards */}
      {!displayLoading && !displayError && displayData.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {displayData.map((opp, i) => (
            <OpportunityCard
              key={`${opp.protocol}-${opp.asset}-${i}`}
              opportunity={opp}
              kind={isLoop(opp) ? "loop" : "carry"}
              onOpenDetail={onOpenDetail}
            />
          ))}
        </div>
      )}
    </div>
  );
}
