import HomeCards from "@/components/home-cards";
import LoopTable from "@/components/loop-table";
import CarryTable from "@/components/carry-table";
import FundingChart from "@/components/funding-chart";

export default function Home() {
  return (
    <main className="mx-auto max-w-7xl px-4 py-8 space-y-10">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">DeFi Alpha Scanner</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Mempool monitoring · LP opportunity detection · whale tracking
        </p>
      </div>

      <section>
        <HomeCards />
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold tracking-tight">
          Loop Opportunities
        </h2>
        <LoopTable />
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold tracking-tight">
          Carry Opportunities
        </h2>
        <CarryTable />
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold tracking-tight">
          Funding Rate History
        </h2>
        <FundingChart />
      </section>
    </main>
  );
}
