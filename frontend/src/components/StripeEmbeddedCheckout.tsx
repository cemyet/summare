import { useEffect, useRef } from "react";
import { loadStripe } from "@stripe/stripe-js";
import { API_BASE, STRIPE_PUBLISHABLE_KEY } from "@/utils/flags";

export default function StripeEmbeddedCheckout({ onComplete, height = 720 }: { onComplete?: () => void; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let alive = true;
    let checkout: any;

    (async () => {
      console.log("🔧 API_BASE:", API_BASE);
      console.log("🔧 STRIPE_PUBLISHABLE_KEY present:", !!STRIPE_PUBLISHABLE_KEY);
      if (!STRIPE_PUBLISHABLE_KEY) {
        if (ref.current) ref.current.innerHTML = "Stripe-nyckel saknas.";
        return;
      }

      const res = await fetch(`${API_BASE}/api/payments/create-embedded-checkout`, { method: "POST" });
      const raw = await res.text().catch(() => "");
      let data: any = {};
      try { data = raw ? JSON.parse(raw) : {}; } catch {}

      if (!res.ok) {
        console.error("❌ Backend error:", res.status, raw);
        if (ref.current) ref.current.innerHTML = `Serverfel (${res.status}).`;
        return;
      }

      const clientSecret = data?.client_secret;
      const sessionId = data?.session_id;
      if (typeof clientSecret !== "string" || !clientSecret.startsWith("cs_")) {
        console.error("❌ Missing/invalid client_secret:", data);
        if (ref.current) ref.current.innerHTML = "Saknar client_secret.";
        return;
      }

      const stripe = await loadStripe(STRIPE_PUBLISHABLE_KEY);
      if (!stripe || !ref.current || !alive) return;

      // @ts-ignore (types for initEmbeddedCheckout may lag)
      const embedded = await stripe.initEmbeddedCheckout({
        clientSecret,
        onComplete: async () => {
          try {
            const r = await fetch(`${API_BASE}/api/stripe/verify?session_id=${sessionId}`);
            const j = await r.json();
            if (j?.paid) onComplete?.();
          } catch { onComplete?.(); }
        }
      });

      checkout = embedded;
      embedded.mount(ref.current);
    })();

    return () => { alive = false; try { checkout?.destroy?.(); } catch {} };
  }, [onComplete]);

  // stay within your preview card frames (rounded border, hidden overflow)
  return <div ref={ref} style={{ height }} />;
}
