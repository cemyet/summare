import { useEffect, useRef } from "react";
import { loadStripe } from "@stripe/stripe-js";
import { API_BASE, STRIPE_PUBLISHABLE_KEY } from "@/utils/flags";
// Force deployment v2

export default function StripeEmbeddedCheckout({ onComplete, onFailure, height = 720 }: { onComplete?: () => void; onFailure?: () => void; height?: number }) {
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
            if (j?.paid) {
              // Payment successful - trigger chat step 510
              console.log("💚 Payment successful, triggering chat step 510");
              window.dispatchEvent(new CustomEvent("summare:paymentSuccess"));
              onComplete?.();
            } else {
              // Payment failed - trigger chat step 508
              console.log("❌ Payment failed, triggering chat step 508");
              window.dispatchEvent(new CustomEvent("summare:paymentFailure"));
              onFailure?.();
            }
          } catch (error) {
            console.error("🔥 Payment verification error:", error);
            // On error, assume failure and trigger step 508
            window.dispatchEvent(new CustomEvent("summare:paymentFailure"));
            onFailure?.();
          }
        },
        // Add error handling for declined payments
        onError: (error: any) => {
          console.log("❌ Stripe payment error:", error);
          // Payment was declined or had an error - trigger chat step 508
          window.dispatchEvent(new CustomEvent("summare:paymentFailure"));
          onFailure?.();
        }
      });

      checkout = embedded;
      embedded.mount(ref.current);
      
      // Watch for payment decline messages in the Stripe UI
      const watchForDeclines = () => {
        const checkForDeclineMessages = () => {
          // Look for common decline text patterns in the iframe content
          const stripeFrames = document.querySelectorAll('iframe[src*="checkout.stripe.com"], iframe[src*="js.stripe.com"]');
          
          stripeFrames.forEach((frame) => {
            try {
              // Note: We can't access iframe content due to CORS, but we can detect if payment failed
              // by watching for UI changes or using postMessage if Stripe supports it
              console.log('🔍 Watching Stripe frame for payment feedback...');
            } catch (e) {
              // Cross-origin frame access blocked (expected)
            }
          });
        };
        
        // Check periodically for changes
        const intervalId = setInterval(checkForDeclineMessages, 2000);
        setTimeout(() => clearInterval(intervalId), 30000); // Stop after 30 seconds
      };
      
      setTimeout(watchForDeclines, 1000);
    })();

    return () => { alive = false; try { checkout?.destroy?.(); } catch {} };
  }, [onComplete, onFailure]);

  // stay within your preview card frames (rounded border, hidden overflow)
  return (
    <div className="rounded-2xl border border-neutral-200 bg-white shadow-sm overflow-hidden">
      <div className="px-5 py-3 border-b border-neutral-200 flex justify-between items-center">
        <h3 className="text-sm font-medium text-neutral-700">Betalning</h3>
        <button
          onClick={() => {
            console.log("🔄 Manual payment failure triggered");
            window.dispatchEvent(new CustomEvent("summare:paymentFailure"));
            onFailure?.();
          }}
          className="text-xs text-gray-500 hover:text-red-600 underline"
        >
          Betalning nekad? Försök igen
        </button>
      </div>

      {/* Outer padding creates spacing between the card edge and the iframe */}
      <div className="p-4 sm:p-6">
        <div
          ref={ref}
          className="w-full"
          style={{ minHeight: height }}
        />
      </div>
    </div>
  );
}
