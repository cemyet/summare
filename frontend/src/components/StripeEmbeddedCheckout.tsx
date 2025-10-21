import { useEffect, useRef } from "react";
import { loadStripe } from "@stripe/stripe-js";
import { API_BASE, STRIPE_PUBLISHABLE_KEY } from "@/utils/flags";
// Force deployment v2

export default function StripeEmbeddedCheckout({ onComplete, onFailure, height = 720 }: { onComplete?: () => void; onFailure?: () => void; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Suppress harmless Chrome extension errors in Stripe iframe
    const originalError = console.error;
    const filteredError = (...args: any[]) => {
      const message = args[0]?.toString() || '';
      // Filter out extension-related errors that don't affect functionality
      if (
        message.includes('chrome-extension://') ||
        message.includes('runtime/sendMessage') ||
        message.includes('message channel closed')
      ) {
        return; // Suppress these errors
      }
      originalError.apply(console, args);
    };
    console.error = filteredError;

    // Restore original console.error on cleanup
    const cleanup = () => {
      console.error = originalError;
    };

    let alive = true;
    let checkout: any;

    (async () => {
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
              window.dispatchEvent(new CustomEvent("summare:paymentSuccess"));
              onComplete?.();
            } else {
              // Payment failed - trigger chat step 508
              window.dispatchEvent(new CustomEvent("summare:paymentFailure"));
              onFailure?.();
            }
          } catch (error) {
            console.error("🔥 Payment verification error:", error);
            // On error, assume failure and trigger step 508
            window.dispatchEvent(new CustomEvent("summare:paymentFailure"));
            onFailure?.();
          }
        }
      });

      checkout = embedded;
      embedded.mount(ref.current);
    })();

    return () => { 
      alive = false; 
      cleanup(); // Restore original console.error
      try { checkout?.destroy?.(); } catch {} 
    };
  }, [onComplete]);

  // stay within your preview card frames (rounded border, hidden overflow)
  return (
    <div className="rounded-2xl border border-neutral-200 bg-white shadow-sm overflow-hidden">
      <div className="px-5 py-3 border-b border-neutral-200">
        <h3 className="text-xl font-medium text-neutral-700">Betalning</h3>
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
