const toBool = (v: any) => ["1","true","yes","on"].includes(String(v).toLowerCase());

const next = (typeof process !== "undefined" && process.env) || {};
const vite = (typeof import.meta !== "undefined" && (import.meta as any).env) || {};

export const API_BASE =
  (next.NEXT_PUBLIC_API_URL || vite.VITE_API_URL || "").trim();

export const STRIPE_PUBLISHABLE_KEY =
  (next.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY || vite.VITE_STRIPE_PUBLISHABLE_KEY || "").trim();

export const USE_EMBED =
  toBool(next.NEXT_PUBLIC_USE_EMBEDDED_CHECKOUT) || toBool(vite.VITE_USE_EMBEDDED_CHECKOUT);
