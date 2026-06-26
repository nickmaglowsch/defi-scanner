"use client";

import { useEffect, useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  getLooping,
  getOpportunities,
  getFunding,
  LoopOpportunityOut,
  CarryOpportunityOut,
  FundingSnapshotOut,
} from "@/lib/api";

interface CardState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

function useCardFetch<T>(fetcher: () => Promise<T>): CardState<T> & { retry: () => void } {
  const [state, setState] = useState<CardState<T>>({
    data: null,
    loading: true,
    error: null,
  });

  const fetchData = () => {
    setState({ data: null, loading: true, error: null });
    fetcher()
      .then((data) => setState({ data, loading: false, error: null }))
      .catch((e: Error) =>
        setState({ data: null, loading: false, error: e.message })
      );
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- legitimate data-fetching effect
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { ...state, retry: fetchData };
}

function fmtPct(val: number | null | undefined): string {
  if (val == null) return "N/A";
  return val.toFixed(2) + "%";
}

function CardWrapper({
  title,
  value,
  subtitle,
  loading,
  error,
  onRetry,
}: {
  title: string;
  value: string;
  subtitle: string;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{subtitle}</CardDescription>
      </CardHeader>
      <CardContent>
        {loading && (
          <div className="h-8 w-24 animate-pulse rounded bg-muted" />
        )}
        {error && (
          <div>
            <p className="text-sm text-destructive">Unable to load</p>
            <button
              onClick={onRetry}
              className="mt-1 text-xs underline underline-offset-2 hover:text-foreground"
            >
              Retry
            </button>
          </div>
        )}
        {!loading && !error && (
          <p className="text-2xl font-bold tracking-tight">{value}</p>
        )}
      </CardContent>
    </Card>
  );
}

export default function HomeCards() {
  const bestLoop = useCardFetch<LoopOpportunityOut>(() =>
    getLooping({ limit: 1 }).then((r) => r[0])
  );
  const bestCarry = useCardFetch<CarryOpportunityOut>(() =>
    getOpportunities({ type: "carry", limit: 1 }).then((r) => r[0] as CarryOpportunityOut)
  );
  const stableYield = useCardFetch<LoopOpportunityOut>(() =>
    getLooping({ asset: "USDC", limit: 1 }).then((r) => r[0])
  );
  const highestFunding = useCardFetch<FundingSnapshotOut>(() =>
    getFunding({ limit: 1 }).then((r) => r[0])
  );

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {/* Best Loop */}
      <CardWrapper
        title="Best Loop"
        value={bestLoop.data ? fmtPct(bestLoop.data.effective_yield) : "—"}
        subtitle={
          bestLoop.data
            ? `${bestLoop.data.protocol} · ${bestLoop.data.asset}`
            : "No data"
        }
        loading={bestLoop.loading}
        error={bestLoop.error}
        onRetry={bestLoop.retry}
      />

      {/* Best Carry */}
      <CardWrapper
        title="Best Carry"
        value={bestCarry.data ? fmtPct(bestCarry.data.net_carry) : "—"}
        subtitle={
          bestCarry.data
            ? `${bestCarry.data.protocol} · ${bestCarry.data.asset}`
            : "No data"
        }
        loading={bestCarry.loading}
        error={bestCarry.error}
        onRetry={bestCarry.retry}
      />

      {/* Best Stable Yield */}
      <CardWrapper
        title="Best Stable Yield"
        value={stableYield.data ? fmtPct(stableYield.data.effective_yield) : "—"}
        subtitle={
          stableYield.data
            ? `${stableYield.data.protocol} · ${stableYield.data.asset}`
            : "No data"
        }
        loading={stableYield.loading}
        error={stableYield.error}
        onRetry={stableYield.retry}
      />

      {/* Highest Funding */}
      <CardWrapper
        title="Highest Funding"
        value={
          highestFunding.data
            ? fmtPct(highestFunding.data.annualized_funding)
            : "—"
        }
        subtitle={
          highestFunding.data
            ? highestFunding.data.market_id.slice(0, 12) + "…"
            : "No data"
        }
        loading={highestFunding.loading}
        error={highestFunding.error}
        onRetry={highestFunding.retry}
      />
    </div>
  );
}
