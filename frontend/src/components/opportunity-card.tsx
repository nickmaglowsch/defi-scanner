"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useCapital, yieldToDollars } from "@/lib/capital-context";
import { fmtPct, fmtUsd } from "@/lib/utils";
import type { OpportunityOut } from "@/lib/api";

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

const STRATEGY_BADGE: Record<string, string> = {
  loop: "Loop",
  carry: "Carry",
  stable_lending: "Stable Lending",
  staking: "Staking",
  restaking: "Restaking",
  pendle: "Pendle",
  cross_protocol: "Cross-Protocol",
};

export type OpportunityCardProps = {
  opportunity: OpportunityOut;
  /** @deprecated — kept for backward compat; ignored if strategy_type is set */
  kind?: "loop" | "carry";
  onOpenDetail?: (opp: OpportunityOut) => void;
};

// ── Component ──────────────────────────────────────────────────────────────

export default function OpportunityCard({ opportunity: opp, onOpenDetail }: OpportunityCardProps) {
  const [expanded, setExpanded] = useState(false);
  const { capital } = useCapital();

  const strategyType = opp.strategy_type;
  const isLoop = strategyType === "loop";
  const isCarry = strategyType === "carry";
  const strategyBadge = STRATEGY_BADGE[strategyType] ?? strategyType;
  const d = opp.strategy_details ?? {};

  // Loop → effective_yield; carry → net_carry; others → net_apy
  const yieldPct = isLoop ? d.effective_yield : isCarry ? d.net_carry : opp.net_apy;

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
                {strategyBadge} / {opp.protocol} / {opp.asset}
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
        {isLoop && (
          <div className="grid grid-cols-3 gap-2 text-sm">
            <div>
              <div className="text-xs text-muted-foreground">Current LTV</div>
              <div>{d.leverage != null ? Number(d.leverage).toFixed(2) + "x" : "—"}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Safety Margin</div>
              <div>
                {getHealthEmoji(d.safety_margin)}{" "}
                {d.safety_margin != null ? (Number(d.safety_margin) * 100).toFixed(1) + "%" : "—"}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Liq. Distance</div>
              <div>
                {d.liquidation_distance != null
                  ? (Number(d.liquidation_distance) * 100).toFixed(1) + "%"
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
                {isLoop && (
                  <div>
                    <div className="mb-1 font-medium">Loop math</div>
                    <div className="space-y-0.5 text-muted-foreground">
                      <div>Deposit APY: {fmtPct(d.deposit_apy)}</div>
                      <div>Borrow APY: {fmtPct(d.borrow_apy)}</div>
                      <div>Leverage: {d.leverage != null ? Number(d.leverage).toFixed(2) + "x" : "—"}</div>
                      <div className="font-medium text-foreground">
                        → Net yield: {fmtPct(yieldPct)}
                      </div>
                    </div>
                  </div>
                )}

                {/* Carry math */}
                {isCarry && (
                  <div>
                    <div className="mb-1 font-medium">Carry math</div>
                    <div className="space-y-0.5 text-muted-foreground">
                      <div>Funding yield: {fmtPct(d.funding_yield)}</div>
                      <div>Spot yield: {fmtPct(d.spot_yield)}</div>
                      <div>Borrow cost: {fmtPct(d.borrow_cost)}</div>
                      <div>Trading fees: {fmtPct(d.trading_fees)}</div>
                      <div className="font-medium text-foreground">
                        → Net carry: {fmtPct(yieldPct)}
                      </div>
                    </div>
                  </div>
                )}

                {/* Generic strategy details for other types */}
                {!isLoop && !isCarry && Object.keys(d).length > 0 && (
                  <div>
                    <div className="mb-1 font-medium">{strategyBadge} details</div>
                    <div className="space-y-0.5 text-muted-foreground">
                      {Object.entries(d).map(([key, val]) => (
                        <div key={key}>
                          {key.replace(/_/g, " ")}: {val != null ? fmtPct(val) : "—"}
                        </div>
                      ))}
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
