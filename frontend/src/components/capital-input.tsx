"use client";

import { useCapital } from "@/lib/capital-context";
import { Input } from "@/components/ui/input";

export default function CapitalInput() {
  const { capital, setCapital } = useCapital();

  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="text-muted-foreground whitespace-nowrap">Capital $</span>
      <Input
        type="number"
        min={0}
        className="w-32"
        value={capital}
        onChange={(e) => {
          const v = Number(e.target.value);
          if (!Number.isNaN(v) && v >= 0) setCapital(v);
        }}
      />
    </label>
  );
}
