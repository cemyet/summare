import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { AnnualReportPreview } from "@/components/AnnualReportPreview"; // your existing component
import StripeEmbeddedCheckout from "@/components/StripeEmbeddedCheckout";
import { USE_EMBED } from "@/utils/flags";

// Debug logging
console.log('🔧 RightPane USE_EMBED:', USE_EMBED);

interface RightPaneProps {
  companyData: any;
  currentStep: number;
  editableAmounts?: boolean;
  onDataUpdate?: (updates: Partial<any>) => void;
}

export default function RightPane({ companyData, currentStep, editableAmounts = false, onDataUpdate }: RightPaneProps) {
  const [showPayment, setShowPayment] = useState(false);
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);

  useEffect(() => {
    const onShow = () => {
      console.log('🔧 RightPane received summare:showPayment event');
      setShowPayment(true);
    };
    const onHide = () => {
      console.log('🔧 RightPane received summare:hidePayment event');
      setShowPayment(false);
    };

    window.addEventListener("summare:showPayment", onShow);
    window.addEventListener("summare:hidePayment", onHide);
    return () => {
      window.removeEventListener("summare:showPayment", onShow);
      window.removeEventListener("summare:hidePayment", onHide);
    };
  }, []);

  // Grab the anchor after first render of preview
  useEffect(() => {
    const el = document.getElementById("payment-section-anchor");
    console.log('🔧 Looking for payment-section-anchor:', !!el);
    setAnchorEl(el || null);
  }, [showPayment]); // re-check after toggling

  console.log('🔧 RightPane render check:', { showPayment, hasAnchor: !!anchorEl });

  return (
    <>
      <AnnualReportPreview 
        companyData={companyData}
        currentStep={currentStep}
        editableAmounts={editableAmounts}
        onDataUpdate={onDataUpdate}
      />
      {showPayment && anchorEl ? (
        <>
          {console.log('🔧 Portaling StripeEmbeddedCheckout into payment-section-anchor')}
          {createPortal(
            <div className="mt-4">
              <StripeEmbeddedCheckout
                onComplete={() => {
                  console.log('🔧 StripeEmbeddedCheckout onComplete called');
                  window.dispatchEvent(new CustomEvent("summare:paymentSuccess"));
                  setShowPayment(false);
                }}
                height={720}
              />
            </div>,
            anchorEl
          )}
        </>
      ) : null}
    </>
  );
}
