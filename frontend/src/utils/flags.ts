// Robust environment variable utilities that work with both Vite and Next.js

export const readBool = (v: any) =>
  ["1", "true", "yes", "on"].includes(String(v).toLowerCase());

export const USE_EMBED =
  readBool((typeof import.meta !== "undefined" && (import.meta as any).env?.VITE_USE_EMBEDDED_CHECKOUT)) ||
  readBool((typeof process !== "undefined" && process.env?.NEXT_PUBLIC_USE_EMBEDDED_CHECKOUT));

export const API_BASE =
  (typeof import.meta !== "undefined" && (import.meta as any).env?.VITE_API_URL) ||
  (typeof process !== "undefined" && process.env?.NEXT_PUBLIC_API_URL) ||
  "";
