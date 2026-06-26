import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Format a percentage value, or "—" when null/undefined. */
export function fmtPct(v: number | null | undefined, digits = 2): string {
  if (v == null) return "—"
  return v.toFixed(digits) + "%"
}

/** Format a whole-dollar USD amount. */
export function fmtUsd(v: number): string {
  return v.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 })
}
