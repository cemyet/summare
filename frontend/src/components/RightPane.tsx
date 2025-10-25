import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { AnnualReportPreview } from "@/components/AnnualReportPreview"; // your existing component
import StripeEmbeddedCheckout from "@/components/StripeEmbeddedCheckout";
import { USE_EMBED } from "@/utils/flags";

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
      setShowPayment(true);
    };
    const onHide = () => {
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
    setAnchorEl(el || null);
  }, [showPayment]); // re-check after toggling

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
          {createPortal(
            <div className="mt-4 max-w-[980px]">
              <StripeEmbeddedCheckout
                onComplete={() => {
                  setShowPayment(false);
                }}
                onFailure={() => {
                  setShowPayment(false);
                }}
                height={720}
                organizationNumber={companyData?.organizationNumber || companyData?.seFileData?.company_info?.organization_number}
                customerEmail={companyData?.customerEmail}
              />
            </div>,
            anchorEl
          )}
        </>
      ) : null}
    </>
  );
}
