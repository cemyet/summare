import { useEffect, useState } from "react";
import { AnnualReportPreview } from "@/components/AnnualReportPreview"; // your existing component
import StripeEmbeddedCheckout from "@/components/StripeEmbeddedCheckout";
import { USE_EMBED } from "@/utils/flags";

// Debug logging
console.log('🔧 RightPane USE_EMBED:', USE_EMBED);
console.log('🔧 RightPane NEXT_PUBLIC_USE_EMBEDDED_CHECKOUT:', process.env.NEXT_PUBLIC_USE_EMBEDDED_CHECKOUT);
console.log('🔧 RightPane VITE_USE_EMBEDDED_CHECKOUT:', (typeof import.meta !== "undefined" && (import.meta as any).env?.VITE_USE_EMBEDDED_CHECKOUT));
console.log('🔧 RightPane All NEXT_PUBLIC env vars:', Object.keys(process.env || {}).filter(key => key.startsWith('NEXT_PUBLIC')));

interface RightPaneProps {
  companyData: any;
  currentStep: number;
  editableAmounts?: boolean;
  onDataUpdate?: (updates: Partial<any>) => void;
}

export default function RightPane({ companyData, currentStep, editableAmounts = false, onDataUpdate }: RightPaneProps) {
  const [showPayment, setShowPayment] = useState(false);

  useEffect(() => {
    const onShow = () => {
      console.log('🔧 RightPane received summare:showPayment event');
      console.log('🔧 USE_EMBED in onShow:', USE_EMBED);
      if (USE_EMBED) {
        console.log('🔧 Setting showPayment to true');
        setShowPayment(true);
      } else {
        console.log('🔧 USE_EMBED is false, not showing embedded checkout');
      }
    };
    const onHide = () => {
      console.log('🔧 RightPane received summare:hidePayment event');
      setShowPayment(false);
    };

    console.log('🔧 RightPane setting up event listeners');
    window.addEventListener("summare:showPayment", onShow);
    window.addEventListener("summare:hidePayment", onHide);
    return () => {
      console.log('🔧 RightPane cleaning up event listeners');
      window.removeEventListener("summare:showPayment", onShow);
      window.removeEventListener("summare:hidePayment", onHide);
    };
  }, []);

  console.log('🔧 RightPane render check:', { USE_EMBED, showPayment, shouldShowEmbedded: USE_EMBED && showPayment });

  if (USE_EMBED && showPayment) {
    console.log('🔧 RightPane rendering StripeEmbeddedCheckout');
    return (
      <StripeEmbeddedCheckout
        onComplete={() => {
          console.log('🔧 StripeEmbeddedCheckout onComplete called');
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
