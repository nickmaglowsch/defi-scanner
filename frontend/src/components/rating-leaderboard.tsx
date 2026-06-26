"use client";

import { useEffect, useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { getRiskLabel, getRiskColor } from "@/components/opportunity-card";
import { useCapital, yieldToDollars } from "@/lib/capital-context";
import { getOpportunities, isLoop, oppYield } from "@/lib/api";
import type { LoopOpportunityOut, CarryOpportunityOut } from "@/lib/api";
import { fmtPct, fmtUsd } from "@/lib/utils";

type Opp = LoopOpportunityOut | CarryOpportunityOut;

function strategyLabel(opp: Opp): string {
  const type = isLoop(opp) ? "Loop" : "Carry";
  return `${opp.protocol} ${opp.asset} ${type}`;
}

export default function RatingLeaderboard({
  onOpenDetail,
}: {
  onOpenDetail?: (opp: Opp) => void;
}) {
  const { capital } = useCapital();
  const [opps, setOpps] = useState<Opp[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    // type defaults to "all": the API rerates the merged set on one scale and
    // returns it score-desc (== rating-desc), so the top `limit` are already the
    // top-rated, in order — no client re-sort needed.
    getOpportunities({ sort: "return", limit: 10 })
      .then(setOpps)
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : String(e))
      )
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="rounded-xl border bg-card p-4 shadow-sm">
      <h2 className="mb-3 text-lg font-semibold">Top Opportunities</h2>

      {loading && (
        <p className="py-6 text-center text-sm text-muted-foreground">
          Loading…
        </p>
      )}
      {error && (
        <p className="py-6 text-center text-sm text-destructive">{error}</p>
      )}
      {!loading && !error && opps.length === 0 && (
        <p className="py-6 text-center text-sm text-muted-foreground">
          No opportunities found.
        </p>
      )}

      {!loading && !error && opps.length > 0 && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10">#</TableHead>
              <TableHead>Strategy</TableHead>
              <TableHead>Expected Return</TableHead>
              <TableHead>Risk</TableHead>
              <TableHead>Confidence</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {opps.map((opp, i) => {
              const pct = oppYield(opp);
              const dollars =
                pct != null ? yieldToDollars(pct, capital) : null;
              const rank = i + 1;
              const rankCell =
                opp.medal ?? String(rank);

              return (
                <TableRow
                  key={`${opp.protocol}-${opp.asset}-${rank}`}
                  className={onOpenDetail ? "cursor-pointer" : undefined}
                  onClick={() => onOpenDetail?.(opp)}
                >
                  <TableCell className="font-medium">{rankCell}</TableCell>
                  <TableCell>{strategyLabel(opp)}</TableCell>
                  <TableCell>
                    <span className="font-medium">{fmtPct(pct)}</span>
                    {dollars != null && (
                      <span className="ml-1 text-xs text-muted-foreground">
                        {fmtUsd(dollars.perYear)}/yr
                      </span>
                    )}
                  </TableCell>
                  <TableCell>
                    <span className={`flex items-center gap-1 ${getRiskColor(opp.risk_score)}`}>
                      <span className="inline-block h-2 w-2 rounded-full bg-current" />
                      {getRiskLabel(opp.risk_score)}
                    </span>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {opp.confidence != null
                      ? opp.confidence.toFixed(0) + "%"
                      : "—"}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
