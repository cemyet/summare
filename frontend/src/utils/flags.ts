// Robust environment variable utilities that work with both Vite and Next.js

export const readBool = (v: any) =>
  ["1", "true", "yes", "on"].includes(String(v).toLowerCase());

const vite = (typeof import.meta !== "undefined" && (import.meta as any).env) || {};
const next = (typeof process !== "undefined" && process.env) || {};

export const USE_EMBED =
  readBool(vite.VITE_USE_EMBEDDED_CHECKOUT) ||
  readBool(next.NEXT_PUBLIC_USE_EMBEDDED_CHECKOUT);

export const API_BASE =
  vite.VITE_API_URL || next.NEXT_PUBLIC_API_URL || "https://api.summare.se";
