// utils/flags.ts
const NEXT_API   = process.env.NEXT_PUBLIC_API_URL;
const NEXT_PK    = process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY;
const NEXT_EMBED = process.env.NEXT_PUBLIC_USE_EMBEDDED_CHECKOUT;

const VITE = (typeof import.meta !== "undefined" && (import.meta as any).env) || {};

export const API_BASE =
  (NEXT_API ?? VITE.VITE_API_URL ?? "").trim();

export const STRIPE_PUBLISHABLE_KEY =
  (NEXT_PK ?? VITE.VITE_STRIPE_PUBLISHABLE_KEY ?? "").trim();

export const USE_EMBED =
  String(NEXT_EMBED ?? VITE.VITE_USE_EMBEDDED_CHECKOUT ?? "false").toLowerCase() === "true";

if (typeof window !== "undefined") {
  console.log("[flags] API_BASE:", API_BASE);
  console.log("[flags] STRIPE key present:", !!STRIPE_PUBLISHABLE_KEY);
  console.log("[flags] USE_EMBED:", USE_EMBED);
}
