"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useCapital, yieldToDollars } from "@/lib/capital-context";
import { fmtPct, fmtUsd } from "@/lib/utils";
import type { LoopOpportunityOut, CarryOpportunityOut } from "@/lib/api";

// ── Risk band (single source of truth, exported for tasks 08/11) ────────────

export type RiskLevel = "low" | "medium" | "high" | "unknown";

/** Classify a risk_score (0-1) into a band. The one place thresholds live. */
export function riskLevel(risk_score: number | null | undefined): RiskLevel {
  if (risk_score == null) return "unknown";
  if (risk_score < 0.3) return "low";
  if (risk_score < 0.6) return "medium";
  return "high";
}

const RISK_LABEL: Record<RiskLevel, string> = { low: "Low", medium: "Medium", high: "High", unknown: "Unknown" };
const RISK_COLOR: Record<RiskLevel, string> = {
  low: "text-green-500",
  medium: "text-yellow-500",
  high: "text-red-500",
  unknown: "text-muted-foreground",
};
const RISK_DOT: Record<RiskLevel, string> = { low: "🟢", medium: "🟡", high: "🔴", unknown: "⚪" };

export function getRiskLabel(risk_score: number | null | undefined): string {
  return RISK_LABEL[riskLevel(risk_score)];
}

export function getRiskColor(risk_score: number | null | undefined): string {
  return RISK_COLOR[riskLevel(risk_score)];
}

function getRiskDot(risk_score: number | null | undefined): string {
  return RISK_DOT[riskLevel(risk_score)];
}

const HISTORY_LABELS = { today: "Today", yesterday: "Yesterday", avg_7d: "7D Avg", avg_30d: "30D Avg" } as const;

function getHealthEmoji(safety_margin: number | null | undefined): string {
  if (safety_margin == null) return "⚪";
  if (safety_margin > 0.3) return "🟢";
  if (safety_margin > 0.15) return "🟡";
  return "🔴";
}

/** Scale 0-100 rating to 0-5 stars */
function renderStars(rating: number | null | undefined): string {
  if (rating == null) return "—";
  const filled = Math.round((rating / 100) * 5);
  return "⭐".repeat(filled) + "☆".repeat(5 - filled);
}

// ── Props ──────────────────────────────────────────────────────────────────

export type OpportunityCardProps = {
  opportunity: LoopOpportunityOut | CarryOpportunityOut;
  kind: "loop" | "carry";
  onOpenDetail?: (opp: LoopOpportunityOut | CarryOpportunityOut) => void;
};

// ── Component ──────────────────────────────────────────────────────────────

export default function OpportunityCard({ opportunity: opp, kind, onOpenDetail }: OpportunityCardProps) {
  const [expanded, setExpanded] = useState(false);
  const { capital } = useCapital();

  const isLoop = kind === "loop";
  const loop = isLoop ? (opp as LoopOpportunityOut) : null;

  const yieldPct = isLoop
    ? (opp as LoopOpportunityOut).effective_yield
    : (opp as CarryOpportunityOut).net_carry;

  const dollars = yieldPct != null ? yieldToDollars(yieldPct, capital) : null;

  const hasBreakdown = opp.breakdown != null && opp.weights != null;

  return (
    <Card
      className="cursor-pointer transition-shadow hover:shadow-md"
      onClick={() => onOpenDetail?.(opp)}
    >
      {/* ── Headline ── */}
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="flex items-center gap-2">
              <span>
                {isLoop ? "Loop" : "Carry"} / {opp.protocol} / {opp.asset}
              </span>
              {opp.medal && <span>{opp.medal}</span>}
            </CardTitle>
            <CardDescription className="mt-1 flex items-center gap-2">
              <span className="text-lg font-semibold text-foreground">
                {fmtPct(yieldPct)}
              </span>
              <span className={getRiskColor(opp.risk_score)}>
                {getRiskDot(opp.risk_score)} {getRiskLabel(opp.risk_score)} risk
              </span>
            </CardDescription>
          </div>
          {opp.rating != null && (
            <div className="shrink-0 text-right">
              <div className="text-sm">{renderStars(opp.rating)}</div>
              {opp.rating_label && (
                <div className="text-xs text-muted-foreground">{opp.rating_label}</div>
              )}
              {opp.confidence != null && (
                <div className="text-xs text-muted-foreground">
                  {opp.confidence.toFixed(0)}% confidence
                </div>
              )}
            </div>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        {/* ── Capital conversion ── */}
        {dollars != null && (
          <div className="rounded-md bg-muted/50 px-3 py-2 text-sm">
            Expected Return{" "}
            <span className="font-medium">{fmtPct(yieldPct)}</span> ≈{" "}
            <span className="font-medium">{fmtUsd(dollars.perYear)}/year</span>{" "}
            <span className="text-muted-foreground">
              (≈ {fmtUsd(dollars.perMonth)}/month)
            </span>
          </div>
        )}

        {/* ── Loop health ── */}
        {isLoop && loop && (
          <div className="grid grid-cols-3 gap-2 text-sm">
            <div>
              <div className="text-xs text-muted-foreground">Current LTV</div>
              <div>{loop.leverage != null ? loop.leverage.toFixed(2) + "x" : "—"}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Safety Margin</div>
              <div>
                {getHealthEmoji(loop.safety_margin)}{" "}
                {loop.safety_margin != null ? (loop.safety_margin * 100).toFixed(1) + "%" : "—"}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Liq. Distance</div>
              <div>
                {loop.liquidation_distance != null
                  ? (loop.liquidation_distance * 100).toFixed(1) + "%"
                  : "—"}
              </div>
            </div>
          </div>
        )}

        {/* ── History ── */}
        {opp.history && (
          <div className="grid grid-cols-4 gap-2 border-t pt-2 text-center text-xs">
            {(["today", "yesterday", "avg_7d", "avg_30d"] as const).map((key) => (
              <div key={key}>
                <div className="text-muted-foreground">{HISTORY_LABELS[key]}</div>
                <div className="font-medium">{fmtPct(opp.history![key])}</div>
              </div>
            ))}
          </div>
        )}

        {/* ── Sharpe ── */}
        {opp.sharpe != null && (
          <div className="text-xs text-muted-foreground">
            Sharpe (approx): <span className="font-medium text-foreground">{opp.sharpe.toFixed(2)}</span>
          </div>
        )}

        {/* ── WHY expander ── */}
        {hasBreakdown && (
          <div>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 gap-1 px-2 text-xs"
              onClick={(e) => {
                e.stopPropagation();
                setExpanded((v) => !v);
              }}
            >
              {expanded ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
              WHY this score?
            </Button>

            {expanded && (
              <div className="mt-2 space-y-3 rounded-md border bg-muted/30 p-3 text-xs">
                {/* Component breakdown */}
                <div>
                  <div className="mb-1 font-medium">Score breakdown</div>
                  <div className="space-y-1">
                    {Object.entries(opp.breakdown!).map(([key, score]) => {
                      const weight = opp.weights![key];
                      const pct = weight != null ? (weight * 100).toFixed(0) + "%" : "—";
                      return (
                        <div key={key} className="flex items-center justify-between gap-2">
                          <span className="capitalize text-muted-foreground">
                            {key.replace(/_/g, " ")} {pct}
                          </span>
                          <span className="font-medium">{score.toFixed(2)}/1.0</span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Loop math */}
                {isLoop && loop && (
                  <div>
                    <div className="mb-1 font-medium">Loop math</div>
                    <div className="space-y-0.5 text-muted-foreground">
                      <div>Deposit APY: {fmtPct((opp as LoopOpportunityOut).deposit_apy)}</div>
                      <div>Borrow APY: {fmtPct((opp as LoopOpportunityOut).borrow_apy)}</div>
                      <div>Leverage: {loop.leverage != null ? loop.leverage.toFixed(2) + "x" : "—"}</div>
                      <div className="font-medium text-foreground">
                        → Net yield: {fmtPct(yieldPct)}
                      </div>
                    </div>
                  </div>
                )}

                {/* Carry math */}
                {!isLoop && (
                  <div>
                    <div className="mb-1 font-medium">Carry math</div>
                    <div className="space-y-0.5 text-muted-foreground">
                      <div>Funding yield: {fmtPct((opp as CarryOpportunityOut).funding_yield)}</div>
                      <div>Spot yield: {fmtPct((opp as CarryOpportunityOut).spot_yield)}</div>
                      <div>Borrow cost: {fmtPct((opp as CarryOpportunityOut).borrow_cost)}</div>
                      <div>Trading fees: {fmtPct((opp as CarryOpportunityOut).trading_fees)}</div>
                      <div className="font-medium text-foreground">
                        → Net carry: {fmtPct(yieldPct)}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
