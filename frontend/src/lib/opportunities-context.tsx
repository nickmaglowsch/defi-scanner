"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { getOpportunities, type OpportunityOut } from "@/lib/api";

type AnyOpp = OpportunityOut;

interface OpportunitiesContextValue {
  // Base set: /opportunities?sort=return&limit=50 (top 50 by score == rating desc
  // for type=all, the same ordering hero/leaderboard/feed-default want). Re-fetched
  // only here, on mount; consumers derive slices from it.
  opps: AnyOpp[];
  loading: boolean;
  error: string | null;
}

const OpportunitiesContext = createContext<OpportunitiesContextValue>({
  opps: [],
  loading: true,
  error: null,
});

export function OpportunitiesProvider({ children }: { children: React.ReactNode }) {
  const [opps, setOpps] = useState<AnyOpp[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getOpportunities({ sort: "return", limit: 50 })
      .then(setOpps)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <OpportunitiesContext.Provider value={{ opps, loading, error }}>
      {children}
    </OpportunitiesContext.Provider>
  );
}

export function useOpportunities() {
  return useContext(OpportunitiesContext);
}