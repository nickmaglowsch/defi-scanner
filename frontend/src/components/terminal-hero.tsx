"use client";

import { useOpportunities } from "@/lib/opportunities-context";
import {
  isLoop,
  oppYield,
  type LoopOpportunityOut,
  type CarryOpportunityOut,
} from "@/lib/api";
import { riskLevel, type RiskLevel } from "@/components/opportunity-card";
import { fmtPct } from "@/lib/utils";

type AnyOpp = LoopOpportunityOut | CarryOpportunityOut;

function getStrategy(opp: AnyOpp): string {
  const kind = isLoop(opp) ? "Loop" : "Carry";
  return `${kind} ${opp.asset}`;
}

function isShortLived(opp: AnyOpp): boolean {
  return (opp.confidence != null && opp.confidence < 30) ||
    (opp.sharpe != null && opp.sharpe < 0.5);
}

function isAvoid(opp: AnyOpp): boolean {
  return opp.rating_label === "Avoid";
}

// Terminal uses dimmer -400 shades than the card's -500; keyed off the shared band.
const HERO_DOT_COLOR: Record<RiskLevel, string> = {
  low: "text-green-400",
  medium: "text-yellow-400",
  high: "text-red-400",
  unknown: "text-zinc-500",
};

function riskDot(opp: AnyOpp): { dot: string; colorClass: string } {
  return { dot: "●", colorClass: HERO_DOT_COLOR[riskLevel(opp.risk_score)] };
}

export type TerminalHeroProps = {
  onOpenDetail?: (opp: LoopOpportunityOut | CarryOpportunityOut) => void;
};

export default function TerminalHero({ onOpenDetail }: TerminalHeroProps) {
  // Derived from the page-level OpportunitiesProvider (single shared fetch).
  // Hero shows the top 8 by return == the first 8 of the shared sort=return set.
  const { opps: allOpps, loading, error } = useOpportunities();
  const opps = allOpps.slice(0, 8);

  return (
    <div className="rounded-md border border-zinc-700 bg-zinc-950 p-4 font-mono text-sm">
      {/* Header */}
      <div className="mb-3 flex items-center justify-between border-b border-zinc-700 pb-2">
        <span className="text-xs font-semibold tracking-widest text-green-400 uppercase">
          Today&apos;s Best Opportunities
        </span>
        <span className="text-xs text-zinc-500">{new Date().toLocaleDateString()}</span>
      </div>

      {/* States */}
      {loading && (
        <div className="py-4 text-xs text-zinc-500">Loading<span className="animate-pulse">...</span></div>
      )}
      {error && (
        <div className="py-4 text-xs text-red-400">[ERR] {error}</div>
      )}
      {!loading && !error && opps.length === 0 && (
        <div className="py-4 text-xs text-zinc-500">No opportunities found.</div>
      )}

      {/* Rows */}
      {!loading && !error && opps.length > 0 && (
        <ul className="space-y-0.5">
          {opps.map((opp, i) => {
            const { dot, colorClass } = riskDot(opp);
            const yld = oppYield(opp);
            const avoid = isAvoid(opp);
            const shortLived = !avoid && isShortLived(opp);
            return (
              <li
                key={`${opp.protocol}-${opp.asset}-${i}`}
                onClick={() => onOpenDetail?.(opp)}
                className={[
                  "flex items-center gap-2 rounded px-2 py-1 text-xs transition-colors",
                  onOpenDetail ? "cursor-pointer hover:bg-zinc-800" : "",
                  avoid ? "opacity-60" : "",
                ].join(" ")}
              >
                {/* Status dot */}
                <span className={`shrink-0 ${colorClass}`} aria-hidden="true">{dot}</span>

                {/* Strategy */}
                <span className="w-28 shrink-0 truncate text-zinc-200">
                  {getStrategy(opp)}
                </span>

                {/* Protocol */}
                <span className="w-20 shrink-0 truncate text-zinc-500">
                  {opp.protocol}
                </span>

                {/* Yield */}
                <span className="w-14 shrink-0 text-right text-green-400">
                  {fmtPct(yld, 1)}
                </span>

                {/* Rating label */}
                <span className="w-20 shrink-0 truncate text-zinc-400">
                  {opp.rating_label ?? "—"}
                </span>

                {/* Tags */}
                <span className="flex gap-1">
                  {shortLived && (
                    <span className="rounded bg-yellow-900/50 px-1 py-0.5 text-[10px] text-yellow-400">
                      Short-lived
                    </span>
                  )}
                  {avoid && (
                    <span className="rounded bg-red-900/50 px-1 py-0.5 text-[10px] text-red-400">
                      Avoid
                    </span>
                  )}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
