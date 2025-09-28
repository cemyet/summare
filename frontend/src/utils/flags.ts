// utils/flags.ts  (temporary hardcoded TEST config)

export const API_BASE = "https://api.summare.se";
export const STRIPE_PUBLISHABLE_KEY = "pk_test_51RuGItRd07xh2DS6MZ6VgEO8ZywkLww4YPb4E23Edv7JPRpmBto5mBe0VfZqSPYcM8Zcgj7YVMM1DWSfuzsWnub000qtW9IR0z";
export const USE_EMBED = true;

// helpful one-time debug in the browser
if (typeof window !== "undefined") {
  console.log("[flags] API_BASE:", API_BASE);
  console.log("[flags] STRIPE key present:", !!STRIPE_PUBLISHABLE_KEY);
  console.log("[flags] USE_EMBED:", USE_EMBED);
}
