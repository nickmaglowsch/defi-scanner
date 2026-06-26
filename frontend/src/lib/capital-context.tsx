"use client";

import { createContext, useContext, useEffect, useState } from "react";

const STORAGE_KEY = "defi-capital";
const DEFAULT_CAPITAL = 20000;

interface CapitalContextValue {
  capital: number;
  setCapital: (v: number) => void;
}

const CapitalContext = createContext<CapitalContextValue>({
  capital: DEFAULT_CAPITAL,
  setCapital: () => {},
});

export function CapitalProvider({ children }: { children: React.ReactNode }) {
  // ponytail: initialize to default to avoid SSR/hydration mismatch; load from localStorage in effect
  const [capital, setCapitalState] = useState<number>(DEFAULT_CAPITAL);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored !== null) {
      const parsed = Number(stored);
      if (!Number.isNaN(parsed)) setCapitalState(parsed);
    }
  }, []);

  function setCapital(v: number) {
    setCapitalState(v);
    localStorage.setItem(STORAGE_KEY, String(v));
  }

  return (
    <CapitalContext.Provider value={{ capital, setCapital }}>
      {children}
    </CapitalContext.Provider>
  );
}

export function useCapital() {
  return useContext(CapitalContext);
}

export function yieldToDollars(
  returnPct: number,
  capital: number
): { perYear: number; perMonth: number } {
  const perYear = capital * (returnPct / 100);
  return { perYear, perMonth: perYear / 12 };
}
