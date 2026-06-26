// ponytail: static map — no URL field on Protocol/Market; replace when protocols carry their own URL
export const PROTOCOL_LINKS: Record<string, string> = {
  aave: "https://app.aave.com",
  morpho: "https://app.morpho.org",
  spark: "https://app.spark.fi",
  hyperliquid: "https://app.hyperliquid.xyz",
};

export function protocolLink(name: string): string | null {
  // Registered names are display names ("Aave V3"); keys are the first-token slug.
  const slug = name.toLowerCase().split(" ")[0];
  return PROTOCOL_LINKS[slug] ?? null;
}
