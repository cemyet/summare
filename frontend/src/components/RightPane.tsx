import { useEffect, useState } from "react";
import AnnualReportPreview from "@/components/AnnualReportPreview"; // your existing component
import StripeEmbeddedCheckout from "@/components/StripeEmbeddedCheckout";

const USE_EMBED = process.env.NEXT_PUBLIC_USE_EMBEDDED_CHECKOUT === "true";

export default function RightPane() {
  const [showPayment, setShowPayment] = useState(false);

  useEffect(() => {
    const onShow = () => USE_EMBED && setShowPayment(true);
    const onHide = () => setShowPayment(false);

    window.addEventListener("summare:showPayment", onShow);
    window.addEventListener("summare:hidePayment", onHide);
    return () => {
      window.removeEventListener("summare:showPayment", onShow);
      window.removeEventListener("summare:hidePayment", onHide);
    };
  }, []);

  if (USE_EMBED && showPayment) {
    return (
      <StripeEmbeddedCheckout
        onComplete={() => {
          window.dispatchEvent(new CustomEvent("summare:paymentSuccess"));
          setShowPayment(false);
        }}
      />
    );
  }

  return <AnnualReportPreview />; // your existing preview
}
