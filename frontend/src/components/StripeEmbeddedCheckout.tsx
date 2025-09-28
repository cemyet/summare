import { useEffect, useRef } from "react";
import { loadStripe } from "@stripe/stripe-js";
import { API_BASE, STRIPE_PUBLISHABLE_KEY } from "@/utils/flags";

export default function StripeEmbeddedCheckout({
  onComplete,
  height = 720,                       // fits your preview area, not overflowing
}: { onComplete?: (sessionId?: string) => void; height?: number }) {
  const ref = useRef<HTMLDivElement | null>(null);

  console.log('🔧 StripeEmbeddedCheckout component rendered - v2024.01.28');

  useEffect(() => {
    let checkout: any;
    let alive = true;

    (async () => {
      console.log("🔧 API_BASE:", API_BASE);
      console.log("🔧 STRIPE_PUBLISHABLE_KEY present:", !!STRIPE_PUBLISHABLE_KEY);
      if (!STRIPE_PUBLISHABLE_KEY) {
        if (ref.current) {
          ref.current.innerHTML = "<div style='padding:12px'>Stripe-nyckel saknas.</div>";
        }
        return;
      }

      try {
        const res = await fetch(`${API_BASE}/api/payments/create-embedded-checkout`, { method: "POST" });
        console.log("🔧 Fetch response status:", res.status);
        const raw = await res.text().catch(() => "");
        let data: any = {};
        try { 
          data = raw ? JSON.parse(raw) : {}; 
        } catch (parseError) {
          console.error("❌ JSON parse error:", parseError);
        }
        console.log("🔧 Raw session payload:", raw);

        if (!res.ok) {
          console.error("❌ Backend returned error:", res.status, raw);
          if (ref.current) {
            ref.current.innerHTML = `<div style="padding:12px;font:14px system-ui;">
              <b>Betalning otillgänglig</b><br/>Serverfel (${res.status}). Försök igen eller öppna i ny flik.
            </div>`;
          }
          return;
        }

        const clientSecret = data?.client_secret;
        const sessionId = data?.session_id;
        if (!clientSecret || !String(clientSecret).startsWith("cs_")) {
          if (ref.current) {
            ref.current.innerHTML = "<div style='padding:12px'>Saknar client_secret.</div>";
          }
          return;
        }

        // ✅ init Stripe with the key now (not at module import time)
        const stripe = await loadStripe(STRIPE_PUBLISHABLE_KEY);
        if (!stripe || !ref.current || !alive) return;

        console.log("🔧 Initializing embedded checkout with client_secret:", clientSecret.substring(0, 20) + "...");

        // @ts-ignore
        checkout = await (stripe as any).initEmbeddedCheckout({
          clientSecret,
          onComplete: async () => {
            console.log("🔧 Stripe checkout completed");
            try {
              const r = await fetch(`${API_BASE}/api/stripe/verify?session_id=${sessionId}`);
              const j = await r.json();
              console.log("🔧 Payment verification result:", j);
              if (j.paid) onComplete?.(sessionId);
            } catch { 
              onComplete?.(sessionId); 
            }
          },
        });

        console.log("🔧 Mounting checkout to ref...");
        checkout.mount(ref.current);
        console.log("🔧 Checkout mounted successfully");

      } catch (error) {
        console.error("🔧 Error in StripeEmbeddedCheckout:", error);
        if (ref.current) {
          ref.current.innerHTML = `<div style="padding:12px;font:14px system-ui;">
            <b>Fel vid laddning</b><br/>${error instanceof Error ? error.message : 'Okänt fel'}
          </div>`;
        }
      }
    })();

    return () => { 
      alive = false; 
      try { checkout?.destroy?.(); } catch {} 
    };
  }, [onComplete]);

  // stay within your preview card frames (rounded border, hidden overflow)
  return (
    <div className="border rounded-xl shadow-sm bg-white"
         style={{ width: "100%", height: `clamp(560px, 75vh, ${height}px)`, overflow: "hidden" }}>
      <div ref={ref} style={{ height: "100%" }} />
    </div>
  );
}
