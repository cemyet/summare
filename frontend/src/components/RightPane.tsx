import { useEffect, useState } from "react";
import { AnnualReportPreview } from "@/components/AnnualReportPreview"; // your existing component
import StripeEmbeddedCheckout from "@/components/StripeEmbeddedCheckout";

const USE_EMBED = process.env.NEXT_PUBLIC_USE_EMBEDDED_CHECKOUT === "true";

// Debug logging
console.log('🔧 RightPane USE_EMBED:', USE_EMBED);
console.log('🔧 RightPane NEXT_PUBLIC_USE_EMBEDDED_CHECKOUT:', process.env.NEXT_PUBLIC_USE_EMBEDDED_CHECKOUT);

interface RightPaneProps {
  companyData: any;
  currentStep: number;
  editableAmounts?: boolean;
  onDataUpdate?: (updates: Partial<any>) => void;
}

export default function RightPane({ companyData, currentStep, editableAmounts = false, onDataUpdate }: RightPaneProps) {
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

  return <AnnualReportPreview 
    companyData={companyData}
    currentStep={currentStep}
    editableAmounts={editableAmounts}
    onDataUpdate={onDataUpdate}
  />; // your existing preview
}
