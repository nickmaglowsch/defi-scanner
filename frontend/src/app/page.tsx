"use client";

import { useState } from "react";
import CapitalInput from "@/components/capital-input";
import TerminalHero from "@/components/terminal-hero";
import RatingLeaderboard from "@/components/rating-leaderboard";
import OpportunityFeed from "@/components/opportunity-feed";
import OpportunityDetail from "@/components/opportunity-detail";
import { OpportunitiesProvider } from "@/lib/opportunities-context";
import type { OpportunityOut } from "@/lib/api";

type AnyOpp = OpportunityOut;

export default function Home() {
  const [selectedOpp, setSelectedOpp] = useState<AnyOpp | null>(null);

  return (
    <OpportunitiesProvider>
      <main className="mx-auto max-w-7xl px-4 py-8 space-y-10">
        {/* Header */}
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">DeFi Alpha Scanner</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Mempool monitoring · LP opportunity detection · whale tracking
            </p>
          </div>
          <CapitalInput />
        </div>

        <TerminalHero onOpenDetail={setSelectedOpp} />

        <section>
          <RatingLeaderboard onOpenDetail={setSelectedOpp} />
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold tracking-tight">All Opportunities</h2>
          <OpportunityFeed onOpenDetail={setSelectedOpp} />
        </section>

        {/* Detail overlay */}
        {selectedOpp && (
          <div
            className="fixed inset-0 z-50 flex items-start justify-end bg-black/40 backdrop-blur-sm"
            onClick={() => setSelectedOpp(null)}
          >
            <div
              className="h-full w-full max-w-2xl overflow-y-auto bg-background p-6 shadow-xl"
              onClick={(e) => e.stopPropagation()}
            >
              <OpportunityDetail opp={selectedOpp} onClose={() => setSelectedOpp(null)} />
            </div>
          </div>
        )}
      </main>
    </OpportunitiesProvider>
  );
}
