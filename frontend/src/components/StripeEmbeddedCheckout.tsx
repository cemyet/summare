import { useEffect, useRef } from "react";
import { loadStripe } from "@stripe/stripe-js";
import { API_BASE } from "@/utils/flags";

const stripePromise = loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY!);

export default function StripeEmbeddedCheckout({
  onComplete,
  height = 720,                       // fits your preview area, not overflowing
}: { onComplete?: (sessionId?: string) => void; height?: number }) {
  const ref = useRef<HTMLDivElement | null>(null);

  console.log('🔧 StripeEmbeddedCheckout component rendered');

  useEffect(() => {
    let checkout: any;
    let alive = true;

    console.log('🔧 StripeEmbeddedCheckout useEffect started');

    (async () => {
      try {
        console.log('🔧 Fetching embedded checkout session...');
        console.log('🔧 API_BASE:', API_BASE);
        const res = await fetch(`${API_BASE}/api/payments/create-embedded-checkout`, { method: "POST" });
        console.log('🔧 Fetch response status:', res.status);

        if (!res.ok) {
          const text = await res.text().catch(() => "");
          console.error("❌ Backend returned error creating embedded checkout:", res.status, text);
          // show a friendly message in the preview instead of mounting
          if (ref.current) {
            ref.current.innerHTML = `<div style="padding:12px;font:14px system-ui;">
              <b>Betalning otillgänglig</b><br/>Serverfel (${res.status}). Försök igen eller öppna i ny flik.
            </div>`;
          }
          return; // 🔴 do NOT continue to parse JSON or init Stripe
        }

        const { client_secret, session_id } = await res.json();
        if (!client_secret) {
          console.error("❌ No client_secret in response");
          if (ref.current) {
            ref.current.innerHTML = `<div style="padding:12px;font:14px system-ui;">
              <b>Betalning otillgänglig</b><br/>Saknar client_secret.
            </div>`;
          }
          return;
        }
        console.log('🔧 Got session:', { client_secret: client_secret ? 'present' : 'missing', session_id });

        const stripe = await stripePromise;
        console.log('🔧 Stripe loaded:', !!stripe);
        console.log('🔧 Ref current:', !!ref.current);
        console.log('🔧 Alive:', alive);
        
        if (!stripe || !client_secret || !ref.current || !alive) {
          console.log('🔧 Early return - missing requirements');
          return;
        }

        console.log('🔧 Initializing embedded checkout...');
        // @ts-ignore — initEmbeddedCheckout is available on Stripe.js when using ui_mode: 'embedded'
        checkout = await (stripe as any).initEmbeddedCheckout({
          clientSecret: client_secret,
          async onComplete() {
            console.log('🔧 Stripe checkout completed');
            try {
              const r = await fetch(`${API_BASE}/api/stripe/verify?session_id=${session_id}`);
              const j = await r.json();
              if (j.paid) onComplete?.(session_id);
            } catch {
              onComplete?.(session_id);
            }
          },
        });

        console.log('🔧 Mounting checkout to ref...');
        checkout.mount(ref.current);
        console.log('🔧 Checkout mounted successfully');
      } catch (error) {
        console.error('🔧 Error in StripeEmbeddedCheckout:', error);
      }
    })();

    return () => { 
      console.log('🔧 StripeEmbeddedCheckout cleanup');
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
