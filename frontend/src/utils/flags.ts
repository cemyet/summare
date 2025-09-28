// utils/flags.ts

// Next.js: these get inlined at build time
const NEXT_API   = process.env.NEXT_PUBLIC_API_URL;
const NEXT_PK    = process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY;
const NEXT_EMBED = process.env.NEXT_PUBLIC_USE_EMBEDDED_CHECKOUT;

// Vite: read from import.meta.env if present (ignored in Next)
const VITE = (typeof import.meta !== "undefined" && (import.meta as any).env) || {};
const VITE_API   = VITE.VITE_API_URL;
const VITE_PK    = VITE.VITE_STRIPE_PUBLISHABLE_KEY;
const VITE_EMBED = VITE.VITE_USE_EMBEDDED_CHECKOUT;

// Final values with simple fallbacks
export const API_BASE =
  (NEXT_API ?? VITE_API ?? "").trim();

export const STRIPE_PUBLISHABLE_KEY =
  (NEXT_PK ?? VITE_PK ?? "").trim();

export const USE_EMBED =
  String(NEXT_EMBED ?? VITE_EMBED ?? "false").toLowerCase() === "true";

// Helpful one-time debug
if (typeof window !== "undefined") {
  console.log("[flags] API_BASE:", API_BASE);
  console.log("[flags] STRIPE key present:", !!STRIPE_PUBLISHABLE_KEY);
  console.log("[flags] USE_EMBED:", USE_EMBED);
}
