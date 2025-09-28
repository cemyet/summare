// utils/flags.ts
const toBool = (v: any) => ["1","true","yes","on"].includes(String(v).toLowerCase());

// Next-style env (Vercel etc.)
const NEXT = (typeof process !== "undefined" && process.env) || {};

// Vite-style env (local dev or other builds)
const VITE = (typeof import.meta !== "undefined" && (import.meta as any).env) || {};

// Optional runtime override (lets you hot-patch from <script> or the console)
declare global { interface Window { __PUBLIC_ENV__?: Record<string,string> } }
const FROM_WIN = (k: string) =>
  (typeof window !== "undefined" && window.__PUBLIC_ENV__?.[k]) || "";

// ---- Public values we need on the client ----
export const STRIPE_PUBLISHABLE_KEY = (
  NEXT.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY ||
  VITE.VITE_STRIPE_PUBLISHABLE_KEY ||
  FROM_WIN("NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY") ||
  ""
).trim();

export const API_BASE = (
  NEXT.NEXT_PUBLIC_API_URL ||
  VITE.VITE_API_URL ||
  FROM_WIN("NEXT_PUBLIC_API_URL") ||
  // last resort guess
  (typeof window !== "undefined"
    ? (window.location.hostname.includes("summare.se")
        ? "https://api.summare.se"
        : "http://localhost:8080")
    : "")
).trim();

export const USE_EMBED =
  toBool(NEXT.NEXT_PUBLIC_USE_EMBEDDED_CHECKOUT) ||
  toBool(VITE.VITE_USE_EMBEDDED_CHECKOUT) ||
  toBool(FROM_WIN("NEXT_PUBLIC_USE_EMBEDDED_CHECKOUT"));

if (typeof window !== "undefined") {
  console.log("[flags] API_BASE:", API_BASE);
  console.log("[flags] STRIPE key present:", !!STRIPE_PUBLISHABLE_KEY);
  console.log("[flags] USE_EMBED:", USE_EMBED);
}
