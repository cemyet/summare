import { useEffect, useRef } from "react";
import { loadStripe } from "@stripe/stripe-js";

const stripePromise = loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY!);

export default function StripeEmbeddedCheckout({
  onComplete,
  height = 720,                       // fits your preview area, not overflowing
}: { onComplete?: (sessionId?: string) => void; height?: number }) {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let checkout: any;
    let alive = true;

    (async () => {
      const res = await fetch("/api/payments/create-embedded-checkout", { method: "POST" });
      const { client_secret, session_id } = await res.json();

      const stripe = await stripePromise;
      if (!stripe || !client_secret || !ref.current || !alive) return;

      // @ts-ignore — initEmbeddedCheckout is available on Stripe.js when using ui_mode: 'embedded'
      checkout = await (stripe as any).initEmbeddedCheckout({
        clientSecret: client_secret,
        async onComplete() {
          try {
            const r = await fetch(`/api/stripe/verify?session_id=${session_id}`);
            const j = await r.json();
            if (j.paid) onComplete?.(session_id);
          } catch {
            onComplete?.(session_id);
          }
        },
      });

      checkout.mount(ref.current);
    })();

    return () => { alive = false; try { checkout?.destroy?.(); } catch {} };
  }, [onComplete]);

  // stay within your preview card frames (rounded border, hidden overflow)
  return (
    <div className="border rounded-xl shadow-sm bg-white"
         style={{ width: "100%", height: `clamp(560px, 75vh, ${height}px)`, overflow: "hidden" }}>
      <div ref={ref} style={{ height: "100%" }} />
    </div>
  );
}
