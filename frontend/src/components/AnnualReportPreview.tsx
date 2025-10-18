'use client';
// Force Vercel deployment - reverted to stable commit a3b33fa

import React, { useState, useEffect, useRef } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Table, TableHeader, TableHead, TableRow, TableBody, TableCell } from "@/components/ui/table";
import { calculateRRSums, extractKeyMetrics, formatAmount, type SEData } from '@/utils/seFileCalculations';
import { apiService } from '@/services/api';
import { computeCombinedFinancialSig } from '@/utils/financeSig';
// import { useToast } from '@/hooks/use-toast'; // Commented out for now

// Select accepted SLP difference (positive) from INK2 + companyData
function getAcceptedSLP(ink2Data: any[], companyData: any) {
  const by = (n: string) => ink2Data?.find((x: any) => x.variable_name === n);
  const manualPos =
    Number(by('justering_sarskild_loneskatt')?.amount) ||
    Number((companyData as any)?.justeringSarskildLoneskatt) || 0;
  const signedInInk = Number(by('INK_sarskild_loneskatt')?.amount) || 0; // negative in table
  
  // If we have manual adjustment, use it (it's already the difference)
  if (manualPos !== 0) {
    return Math.abs(manualPos);
  }
  
  // If we have INK value, it should be the difference amount (calculated - booked)
  // The INK value is the adjustment needed, not the total calculated amount
  return Math.abs(signedInInk);
}

// Helper functions for Swedish number formatting (from Noter)
const fmt0 = new Intl.NumberFormat('sv-SE', { maximumFractionDigits: 0 });

const svToNumber = (raw: string): number => {
  if (!raw) return 0;
  const s = raw.replace(/\s/g, "").replace(/\./g, "").replace(/,/g, ".");
  const n = Number(s);
  return Number.isFinite(n) ? n : 0;
};

const numberToSv = (n: number): string => {
  if (!Number.isFinite(n)) return "";
  const sign = n < 0 ? "-" : "";
  const abs = Math.abs(n);
  return sign + fmt0.format(abs);
};

// Ink2AmountInput component based on Noter's smooth input handling
const Ink2AmountInput = ({ value, onChange, onCommit, variableName }: {
  value: number;
  onChange: (value: number) => void;
  onCommit: (value: number) => void;
  variableName: string;
}) => {
  const [focused, setFocused] = React.useState(false);
  const [local, setLocal] = React.useState<string>("");
  const inputRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    if (!focused) setLocal(value ? String(Math.round(value)) : "");
  }, [value, focused]);

  const shown = focused
    ? local
    : (local ? fmt0.format(parseInt(local.replace(/[^\d-]/g, "") || "0", 10)) : "");

  const commit = () => {
    const raw = local.replace(/[^\d-]/g, "");
    const num = svToNumber(raw);
    const adjusted = variableName === 'INK_sarskild_loneskatt' ? -Math.abs(num) : Math.abs(num);
    onChange(adjusted);
    onCommit(adjusted);
  };

  return (
    <input
      ref={inputRef}
      type="text"
      className="w-24 px-1 py-0.5 text-sm border border-gray-400 rounded text-right font-medium h-5 bg-white focus:border-gray-500 focus:outline-none"
      value={shown}
      onFocus={() => { setFocused(true); setLocal(value ? String(Math.round(value)) : ""); }}
      onChange={(e) => {
        let raw = e.target.value.replace(/[^\d-]/g, "");
        if (variableName !== 'INK_sarskild_loneskatt') {
          raw = raw.replace(/-/g, '');
        } else {
          raw = raw.replace(/(?!^)-/g, '');
        }
        setLocal(raw);
      }}
      onBlur={() => { setFocused(false); commit(); }}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          e.currentTarget.blur();
        } else if (e.key === "Tab") {
          e.preventDefault();
          setFocused(false);
          commit();
          // Move to next editable cell
          const currentInput = e.currentTarget;
          const allInputs = document.querySelectorAll('input[type="text"]');
          const currentIndex = Array.from(allInputs).indexOf(currentInput);
          const nextInput = allInputs[currentIndex + 1] as HTMLInputElement;
          if (nextInput) {
            nextInput.focus();
          }
        }
      }}
      placeholder="0"
    />
  );
};
import { Periodiseringsfonder } from './Periodiseringsfonder';
import { Noter } from './Noter';
import { Forvaltningsberattelse } from './Forvaltningsberattelse';
import { Download } from './Download';
import { Signering } from './Signering';

interface CompanyData {
  results?: string;
  result?: number | null;
  dividend: string;
  customDividend?: number;
  significantEvents: string;
  hasEvents: boolean;
  depreciation: string;
  employees: number;
  location: string;
  date: string;
  boardMembers: Array<{ name: string; personalNumber: string }>;
  ink2Data?: any[]; // INK2 tax calculation data
  showTaxPreview?: boolean; // Show tax calculation module
  showRRBR?: boolean;
  taxEditingEnabled?: boolean;
  editableAmounts?: Record<string, number>;
  unusedTaxLossAmount?: number;
  justeringSarskildLoneskatt?: number;
  pensionPremier?: number;
  sarskildLoneskattPension?: number;
  sarskildLoneskattPensionCalculated?: number;
  noterData?: Array<{
    row_id: number;
    row_title: string;
    current_amount: number;
    previous_amount: number;
    variable_name: string;
    show_tag: boolean;
    accounts_included: string;
    account_details?: Array<{
      account_id: string;
      account_text: string;
      balance: number;
    }>;
    block: string;
    always_show: boolean;
    toggle_show: boolean;
    style: string;
    variable_text?: string;
  }>;
  fbTable?: Array<{
    id: number;
    label: string;
    aktiekapital: number;
    reservfond: number;
    uppskrivningsfond: number;
    balanserat_resultat: number;
    arets_resultat: number;
    total: number;
  }>;
  fbVariables?: Record<string, number>;
  seFileData?: SEData & {
    current_accounts?: Record<string, number>;
    annualReport?: {
      header: {
        organization_number: string;
        fiscal_year: number;
        company_name: string;
        location: string;
        date: string;
      };
      financial_results: {
        revenue: number;
        operating_profit: number;
        net_result: number;
        total_assets: number;
        income_statement: any[];
        balance_sheet: any[];
      };
      significant_events: string[];
      depreciation_policy: string;
      employees: {
        count: number;
        description: string;
      };
      board_members: Array<{
        name: string;
        role: string;
      }>;
    };
    // Previous year data from parse-se-python
    income_statement_year_minus1?: Array<{
      id: string;
      label: string;
      amount: number | null;
      level: number;
      section: string;
      bold: boolean;
      sru: string;
    }>;
    balance_sheet_year_minus1?: Array<{
      id: string;
      label: string;
      amount: number;
      level: number;
      section: string;
      type: string;
      bold: boolean;
    }>;
    rr_data?: Array<{
      id: string;
      row_id: number;
      label: string;
      current_amount: number | null;
      previous_amount: number | null;
      level: number;
      section: string;
      bold?: boolean;
      style?: string;
      block_group?: string;
    }>;
    br_data?: Array<{
      id: string;
      label: string;
      current_amount: number | null;
      previous_amount: number | null;
      level: number;
      section: string;
      type: 'asset' | 'liability' | 'equity';
      bold?: boolean;
      style?: string;
      block_group?: string;
    }>;
    ink2_data?: Array<{
      row_id: number;
      row_title: string;
      amount: number;
      variable_name: string;
      show_tag: boolean;
      accounts_included: string;
      show_amount?: boolean;
      style?: string;
      is_calculated?: boolean;
      always_show?: boolean | null;
      explainer?: string;
      block?: string;
      header?: boolean;
      account_details?: Array<{
        account_id: string;
        account_text: string;
        balance: number;
      }>;
    }>;
         company_info?: {
       organization_number?: string;
       fiscal_year?: number;
       company_name?: string;
       location?: string;
       date?: string;
     };
     significant_events?: string[];
     depreciation_policy?: string;
     employees?: {
       count: number;
       description: string;
     };
     board_members?: Array<{
       name: string;
       role: string;
     }>;
  };
  organizationNumber?: string;
  fiscalYear?: number;
  // Previous year data from parse-se-python (camelCase keys)
  incomeStatementYearMinus1?: Array<{
    id: string;
    label: string;
    amount: number | null;
    level: number;
    section: string;
    bold: boolean;
    sru: string;
  }>;
  balanceSheetYearMinus1?: Array<{
    id: string;
    label: string;
    amount: number;
    level: number;
    section: string;
    type: string;
    bold: boolean;
  }>;
  // Client state used by preview
  acceptedInk2Manuals?: Record<string, number>;
  inkBeraknadSkatt?: number;
  arets_utdelning?: number;
  
  // Signering data
  signeringData?: any;
  
  // Tax button tracking
  taxButtonClickedBefore?: boolean; // Track if tax approve button has been clicked before
  triggerChatStep?: number | null; // Trigger navigation to a specific chat step
}

interface AnnualReportPreviewProps {
  companyData: CompanyData;
  currentStep: number;
  editableAmounts?: boolean;
  onDataUpdate?: (updates: Partial<any>) => void;
}

// --- helpers to fetch numbers (adjust paths to your data shape) ---
const num = (v: any) => {
  if (typeof v === 'number' && !isNaN(v)) return v;
  if (typeof v === 'string') {
    const parsed = parseFloat(v);
    return !isNaN(parsed) ? parsed : 0;
  }
  return 0;
};
const arr3 = (a: any): number[] => (Array.isArray(a) ? a : []).slice(0,3).map(num);

function ManagementReportModule({ companyData, onDataUpdate }: any) {
  const fy = companyData?.fiscalYear ?? new Date().getFullYear();

  // Scraper payload (rating_bolag_scraper.py output)
  const scraped = (companyData as any)?.scraped_company_data || {};
  const verksamhetsbeskrivning =
    scraped.verksamhetsbeskrivning || scraped.Verksamhetsbeskrivning || "";
  const sate = scraped.säte || scraped.sate || scraped.Säte || "";
  const moderbolag = scraped.moderbolag || scraped.Moderbolag || "";
  const moderbolag_orgnr = scraped.moderbolag_orgnr || scraped.ModerbolagOrgNr || "";

  let verksamhetContent = (verksamhetsbeskrivning || "").trim();
  if (sate) {
    verksamhetContent += (verksamhetContent ? " " : "") + `Bolaget har sitt säte i ${sate}.`;
  }
  if (moderbolag) {
    const moder_sate = scraped.moderbolag_säte || scraped.moderbolag_sate || sate;
    verksamhetContent += ` Bolaget är dotterbolag till ${moderbolag}${
      moderbolag_orgnr ? ` med organisationsnummer ${moderbolag_orgnr}` : ""
    }, som har sitt säte i ${moder_sate || sate}.`;
  }

  // Arrays (fy-1..fy-3) from scraper - data is in nyckeltal object
  const nyckeltal = scraped.nyckeltal || {};

  // Current year values from seFileData RR/BR
  const seFileData = companyData?.seFileData;
  const rrData = seFileData?.rr_data || [];
  const brData = seFileData?.br_data || [];
  
  // Extract current year values from RR/BR data
  const getAmountByVariableName = (data: any[], variableNames: string[]) => {
    for (const varName of variableNames) {
      const item = data.find(item => 
        item.variable_name && item.variable_name.toLowerCase() === varName.toLowerCase()
      );
      if (item && item.current_amount !== null && item.current_amount !== undefined) {
        return num(item.current_amount);
      }
    }
    return 0;
  };

  const nettoOmsFY = getAmountByVariableName(rrData, ['SumRorelseintakter', 'sumrorelseintakter']);
  const refpFY = getAmountByVariableName(rrData, ['SumResultatEfterFinansiellaPoster', 'sumresultatefterfinansiellaposter']);
  const tillgFY = getAmountByVariableName(brData, ['SumTillgangar', 'sumtillgangar']);
  const egetKapFY = getAmountByVariableName(brData, ['SumEgetKapital', 'sumegetkapital']);
  const obResFY = getAmountByVariableName(brData, ['SumObeskattadeReserver', 'sumobeskattadereserver']);
  
  // Calculate soliditet or use current year from scraper if available
  let soliditetFY = 0;
  if (tillgFY && egetKapFY) {
    soliditetFY = ((egetKapFY + 0.794 * obResFY) / tillgFY) * 100;
  } else {
    // Fallback to current year from scraper if calculation fails
    const currentSoliditet = nyckeltal.Soliditet?.[0];
    soliditetFY = currentSoliditet ? num(currentSoliditet) : 0;
  }
  const [oms1, oms2, oms3] = arr3(nyckeltal.Omsättning || nyckeltal["Total omsättning"]);
  const [ref1, ref2, ref3] = arr3(nyckeltal["Resultat efter finansnetto"] || nyckeltal["Resultat efter finansiella poster"]);
  const [bal1, bal2, bal3] = arr3(nyckeltal.Balansomslutning || nyckeltal["Summa tillgångar"]);
  const [sol1, sol2, sol3] = arr3(nyckeltal.Soliditet);
  
  // Convert SE file values from kronor to tkr (thousands) and round
  const nettoOmsFY_tkr = Math.round(nettoOmsFY / 1000);
  const refpFY_tkr = Math.round(refpFY / 1000);
  const tillgFY_tkr = Math.round(tillgFY / 1000);
  
  // Check if scraped data includes fiscal year using actual years from HTML
  const scrapedYears = nyckeltal.years || [];
  const scrapedIncludesFiscalYear = scrapedYears.length > 0 && scrapedYears[0] === fy;

  const formatAmount = (n: number) => {
    // Fix negative zero issue
    const value = n === 0 ? 0 : Math.round(n);
    return new Intl.NumberFormat('sv-SE', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(value);
  };

  return (
    <Card className="w-full">
      <CardHeader className="pb-2">
        <CardTitle><h1 className="text-2xl font-bold">Förvaltningsberättelse</h1></CardTitle>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* H2 Verksamheten - with edit functionality */}
        <section id="verksamheten" className="mt-6">
          {(() => {
            // Original values for baseline
            const originalVerksamhetContent = verksamhetContent || '';
            const originalVasentligaHandelser = 'Inga väsentliga händelser under året.';
            
            // Local edit state for Verksamheten - EXACT same pattern as NOT1
            const [isEditingVerksamheten, setIsEditingVerksamheten] = useState(false);
            const [editedValues, setEditedValues] = useState<Record<string, string>>({});
            const [committedValues, setCommittedValues] = useState<Record<string, string>>({});
            
            // Track original baseline for proper undo 
            const originalBaselineVerksamheten = React.useRef<Record<string, string>>({});
            const textareaRef = React.useRef<HTMLTextAreaElement>(null);
            const textareaRef2 = React.useRef<HTMLTextAreaElement>(null);
            
            React.useEffect(() => {
              originalBaselineVerksamheten.current = { 
                'allmant_om_verksamheten': originalVerksamhetContent,
                'vasentliga_handelser': originalVasentligaHandelser
              };
            }, [originalVerksamhetContent]);
            
            // getVal function - EXACT same as NOT1 (moved before useEffect)
            const getVal = (vn: string) => {
              if (editedValues[vn] !== undefined) return editedValues[vn];
              if (committedValues[vn] !== undefined) return committedValues[vn];
              if (vn === 'allmant_om_verksamheten') return originalVerksamhetContent;
              if (vn === 'vasentliga_handelser') return originalVasentligaHandelser;
              return '';
            };
            
            // Auto-resize textareas when entering edit mode or content changes
            React.useEffect(() => {
              if (isEditingVerksamheten) {
                if (textareaRef.current) {
                  const textarea = textareaRef.current;
                  textarea.style.height = 'auto';
                  textarea.style.height = textarea.scrollHeight + 'px';
                }
                if (textareaRef2.current) {
                  const textarea2 = textareaRef2.current;
                  textarea2.style.height = 'auto';
                  textarea2.style.height = textarea2.scrollHeight + 'px';
                }
              }
            }, [isEditingVerksamheten, editedValues['allmant_om_verksamheten'], committedValues['allmant_om_verksamheten'], originalVerksamhetContent, editedValues['vasentliga_handelser'], committedValues['vasentliga_handelser']]);
            
            const startEditVerksamheten = () => {
              setIsEditingVerksamheten(true);
            };
            
            const cancelEditVerksamheten = () => {
              setIsEditingVerksamheten(false);
              setEditedValues({});
            };
            
            const undoEditVerksamheten = () => {
              // EXACT same as NOT1 - clear edits and reset committed to baseline
              setEditedValues({});
              setCommittedValues({ ...originalBaselineVerksamheten.current });
              // IMPORTANT: do NOT setIsEditingVerksamheten(false); stay in edit mode
            };
            
            const approveEditVerksamheten = () => {
              // Capture new values BEFORE setState
              const newCommittedValues = { ...committedValues, ...editedValues };
              setCommittedValues(newCommittedValues);
              setEditedValues({});
              setIsEditingVerksamheten(false);
              
              // Bubble changes up to companyData
              console.log('✅ [VERKSAMHETEN-APPROVE] Updating with edits:', newCommittedValues);
              onDataUpdate?.({
                verksamhetContent: newCommittedValues['allmant_om_verksamheten'],
                vasentligaHandelser: newCommittedValues['vasentliga_handelser']
              });
            };
            
            // Tab navigation function (like NOT1)
            const focusByOrd = (fromEl: HTMLInputElement, dir: 1 | -1) => {
              const curOrd = Number(fromEl.dataset.ord || '0');
              const nextOrd = curOrd + dir;
              const next = document.querySelector<HTMLInputElement>(
                `input[data-editable-cell="1"][data-ord="${nextOrd}"], textarea[data-editable-cell="1"][data-ord="${nextOrd}"]`
              );
              if (next) { next.focus(); (next as any).select?.(); }
            };
            
            return (
              <>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-3">
                    <h2 className="text-xl font-semibold">Verksamheten</h2>
                    <button
                      onClick={() => isEditingVerksamheten ? cancelEditVerksamheten() : startEditVerksamheten()}
                      className={`w-6 h-6 rounded-full flex items-center justify-center transition-colors ${
                        isEditingVerksamheten ? 'bg-blue-600 text-white' : 'bg-gray-200 hover:bg-gray-300 text-gray-600'
                      }`}
                      title={isEditingVerksamheten ? 'Avsluta redigering' : 'Redigera värden'}
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                              d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
                      </svg>
                    </button>
                  </div>
                </div>

                <h3 className="text-base font-semibold mb-1 pt-1">Allmänt om verksamheten</h3>
                {isEditingVerksamheten ? (
                  <textarea
                    ref={textareaRef}
                    value={getVal('allmant_om_verksamheten')}
                    onChange={(e) => {
                      setEditedValues(prev => ({ ...prev, 'allmant_om_verksamheten': e.target.value }));
                      // Auto-resize to fit content
                      e.target.style.height = 'auto';
                      e.target.style.height = e.target.scrollHeight + 'px';
                    }}
                    className="w-full p-2 border border-gray-300 rounded-md resize-y text-sm"
                    style={{ minHeight: '80px' }}
                    placeholder="Beskriv verksamheten..."
                    data-editable-cell="1"
                    data-ord={1}
                  />
                ) : (
                  <p className="text-sm">{getVal('allmant_om_verksamheten')}</p>
                )}

                <h3 className="text-base font-semibold mt-4 pt-3">Väsentliga händelser under räkenskapsåret</h3>
                {isEditingVerksamheten ? (
                  <textarea
                    ref={textareaRef2}
                    value={getVal('vasentliga_handelser')}
                    onChange={(e) => {
                      setEditedValues(prev => ({ ...prev, 'vasentliga_handelser': e.target.value }));
                      // Auto-resize to fit content
                      e.target.style.height = 'auto';
                      e.target.style.height = e.target.scrollHeight + 'px';
                    }}
                    className="w-full p-2 border border-gray-300 rounded-md resize-y text-sm"
                    style={{ minHeight: '60px' }}
                    placeholder="Beskriv väsentliga händelser..."
                    data-editable-cell="1"
                    data-ord={2}
                  />
                ) : (
                  <p className="text-sm font-normal not-italic">{getVal('vasentliga_handelser')}</p>
                )}

                {/* Action buttons - only show when editing */}
                {isEditingVerksamheten && (
                  <div className="flex justify-between pt-4">
                    <Button 
                      onClick={undoEditVerksamheten}
                      variant="outline"
                      className="flex items-center gap-2"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"/>
                      </svg>
                      Ångra ändringar
                    </Button>
                    
                    <Button 
                      onClick={approveEditVerksamheten}
                      className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 flex items-center gap-2"
                    >
                      Godkänn ändringar
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 10h-10a8 8 0 00-8 8v2M21 10l-6 6m6-6l-6-6"/>
                      </svg>
                    </Button>
                  </div>
                )}
              </>
            );
          })()}
        </section>

        {/* H2 Flerårsöversikt - with edit functionality */}
        <section id="flerars" className="mt-8 pt-5">
          {(() => {
            // Original values for baseline
            const originalValues = {
              'oms1': oms1, 'oms2': oms2, 'oms3': oms3, 'nettoOmsFY_tkr': nettoOmsFY_tkr,
              'ref1': ref1, 'ref2': ref2, 'ref3': ref3, 'refpFY_tkr': refpFY_tkr,
              'bal1': bal1, 'bal2': bal2, 'bal3': bal3, 'tillgFY_tkr': tillgFY_tkr,
              'sol1': sol1, 'sol2': sol2, 'sol3': sol3, 'soliditetFY': soliditetFY
            };
            
            // Local edit state for Flerårsöversikt - EXACT same pattern as NOT1
            const [isEditingFlerars, setIsEditingFlerars] = useState(false);
            const [editedValues, setEditedValues] = useState<Record<string, number>>({});
            const [committedValues, setCommittedValues] = useState<Record<string, number>>({});
            const [focusedCell, setFocusedCell] = useState<string | null>(null);
            const [rawInputs, setRawInputs] = useState<Record<string, string>>({});
            
            // Track original baseline for proper undo 
            const originalBaselineFlerars = React.useRef<Record<string, number>>({});
            React.useEffect(() => {
              originalBaselineFlerars.current = { ...originalValues };
            }, []);
            
            // getVal function - EXACT same as NOT1
            const getVal = (vn: string) => {
              if (editedValues[vn] !== undefined) return editedValues[vn];
              if (committedValues[vn] !== undefined) return committedValues[vn];
              return originalValues[vn as keyof typeof originalValues] || 0;
            };
            
            const startEditFlerars = () => {
              setIsEditingFlerars(true);
            };
            
            const cancelEditFlerars = () => {
              setIsEditingFlerars(false);
              setEditedValues({});
            };
            
            const undoEditFlerars = () => {
              // EXACT same as NOT1 - clear edits and reset committed to baseline
              setEditedValues({});
              setCommittedValues({ ...originalBaselineFlerars.current });
              // IMPORTANT: do NOT setIsEditingFlerars(false); stay in edit mode
            };
            
            const approveEditFlerars = () => {
              // Capture new values BEFORE setState
              const newCommittedValues = { ...committedValues, ...editedValues };
              setCommittedValues(newCommittedValues);
              setEditedValues({});
              setIsEditingFlerars(false);
              
              // Bubble changes up to companyData
              console.log('✅ [FLERARS-APPROVE] Updating with edits:', newCommittedValues);
              onDataUpdate?.({ flerarsoversikt: newCommittedValues });
            };
            
            // Tab navigation function with row wrapping
            const focusByOrd = (fromEl: HTMLInputElement, dir: 1 | -1) => {
              const curOrd = Number(fromEl.dataset.ord || '0');
              const nextOrd = curOrd + dir;
              let next = document.querySelector<HTMLInputElement>(
                `input[data-editable-cell="1"][data-ord="${nextOrd}"]`
              );
              
              // If no next cell found and going forward, try to wrap to next row
              if (!next && dir === 1) {
                // Look for the next available cell in sequence
                for (let i = nextOrd + 1; i <= 50; i++) {
                  next = document.querySelector<HTMLInputElement>(
                    `input[data-editable-cell="1"][data-ord="${i}"]`
                  );
                  if (next) break;
                }
              }
              
              if (next) { next.focus(); next.select?.(); }
            };
            
            return (
              <>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-3">
                    <h2 className="text-xl font-semibold">Flerårsöversikt</h2>
                    <button
                      onClick={() => isEditingFlerars ? cancelEditFlerars() : startEditFlerars()}
                      className={`w-6 h-6 rounded-full flex items-center justify-center transition-colors ${
                        isEditingFlerars ? 'bg-blue-600 text-white' : 'bg-gray-200 hover:bg-gray-300 text-gray-600'
                      }`}
                      title={isEditingFlerars ? 'Avsluta redigering' : 'Redigera värden'}
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                              d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
                      </svg>
                    </button>
                  </div>
                </div>
                
                <p className="text-sm font-normal not-italic">Belopp i tkr</p>
                <Table className="w-full table-fixed">
                  <TableHeader className="leading-none">
                    <TableRow className="h-8">
                      <TableHead className="p-0 w-[36%] text-left font-normal"></TableHead>
                      {scrapedIncludesFiscalYear ? (
                        // Scraped data includes fiscal year: show scraped years only (or fallback years)
                        (scrapedYears.length > 0 ? scrapedYears : [2024, 2023, 2022]).map((year, i) => (
                          <TableHead key={i} className="p-0 text-right">{year}</TableHead>
                        ))
                      ) : (
                        // Scraped data starts with fy-1: show calculated fiscal year + scraped years
                        [fy, fy-1, fy-2, fy-3].map((year, i) => (
                          <TableHead key={i} className="p-0 text-right">{year}</TableHead>
                        ))
                      )}
                    </TableRow>
                  </TableHeader>
                  <TableBody className="leading-none">
                    {(scrapedIncludesFiscalYear ? (
                      // Use only scraped data (3 years)
                      [
                        { label: "Omsättning", vars: ['oms1', 'oms2', 'oms3'], values: [getVal('oms1'), getVal('oms2'), getVal('oms3')] },
                        { label: "Resultat efter finansiella poster", vars: ['ref1', 'ref2', 'ref3'], values: [getVal('ref1'), getVal('ref2'), getVal('ref3')] },
                        { label: "Balansomslutning", vars: ['bal1', 'bal2', 'bal3'], values: [getVal('bal1'), getVal('bal2'), getVal('bal3')] },
                        { label: "Soliditet", vars: ['sol1', 'sol2', 'sol3'], values: [getVal('sol1'), getVal('sol2'), getVal('sol3')] },
                      ]
                    ) : (
                      // Use calculated fiscal year + scraped data (4 years)
                      [
                        { label: "Omsättning", vars: ['nettoOmsFY_tkr', 'oms1', 'oms2', 'oms3'], values: [getVal('nettoOmsFY_tkr'), getVal('oms1'), getVal('oms2'), getVal('oms3')] },
                        { label: "Resultat efter finansiella poster", vars: ['refpFY_tkr', 'ref1', 'ref2', 'ref3'], values: [getVal('refpFY_tkr'), getVal('ref1'), getVal('ref2'), getVal('ref3')] },
                        { label: "Balansomslutning", vars: ['tillgFY_tkr', 'bal1', 'bal2', 'bal3'], values: [getVal('tillgFY_tkr'), getVal('bal1'), getVal('bal2'), getVal('bal3')] },
                        { label: "Soliditet", vars: ['soliditetFY', 'sol1', 'sol2', 'sol3'], values: [getVal('soliditetFY'), getVal('sol1'), getVal('sol2'), getVal('sol3')] },
                      ]
                    )).map((row, i) => {
                      let ordCounter = i * 10; // Offset each row's inputs
                      return (
                        <TableRow key={i} className="h-8">
                          <TableCell className="p-0 text-left font-normal">{row.label}</TableCell>
                          {row.values.map((v, j) => (
                            <TableCell key={j} className="p-0 text-right">
                              {isEditingFlerars ? (
                                <input
                                  type="text"
                                  inputMode="numeric"
                                  className="w-full max-w-[108px] px-1 py-0.5 text-sm border border-gray-300 rounded text-right font-normal h-6 bg-white focus:border-gray-400 focus:outline-none"
                                  value={(() => {
                                    const cellKey = `${row.vars[j]}`;
                                    // Show raw input when focused, formatted value when not focused
                                    if (focusedCell === cellKey) {
                                      return rawInputs[cellKey] !== undefined ? rawInputs[cellKey] : String(v || 0);
                                    }
                                    // Show rounded soliditet, normal values for others
                                    return row.label === "Soliditet" ? Math.round(v || 0) : (v || 0);
                                  })()}
                                  onFocus={() => {
                                    const cellKey = `${row.vars[j]}`;
                                    setFocusedCell(cellKey);
                                    setRawInputs(prev => ({ ...prev, [cellKey]: String(v || 0) }));
                                  }}
                                  onBlur={() => {
                                    const cellKey = `${row.vars[j]}`;
                                    setFocusedCell(null);
                                    // Commit the raw input to actual value
                                    const rawVal = rawInputs[cellKey] || '0';
                                    let numVal = 0;
                                    
                                    if (row.label === "Resultat efter finansiella poster") {
                                      // Allow negative values
                                      numVal = parseFloat(rawVal) || 0;
                                    } else {
                                      // Other rows - positive only
                                      numVal = Math.abs(parseFloat(rawVal)) || 0;
                                    }
                                    
                                    setEditedValues(prev => ({ ...prev, [row.vars[j]]: numVal }));
                                  }}
                                  onChange={(e) => {
                                    const cellKey = `${row.vars[j]}`;
                                    let val = e.target.value;
                                    
                                    // Filter input based on row type
                                    if (row.label === "Resultat efter finansiella poster") {
                                      // Allow negative values - digits, minus, dot
                                      val = val.replace(/[^\d.-]/g, '');
                                    } else {
                                      // Positive only - digits only
                                      val = val.replace(/[^\d]/g, '');
                                    }
                                    
                                    setRawInputs(prev => ({ ...prev, [cellKey]: val }));
                                  }}
                                  data-editable-cell="1"
                                  data-ord={ordCounter + j + 10}
                                  onKeyDown={(e) => {
                                    if (e.key === 'Tab') {
                                      e.preventDefault();
                                      const dir = e.shiftKey ? -1 : 1;
                                      focusByOrd(e.currentTarget, dir);
                                    }
                                    if (e.key === 'Enter') {
                                      e.currentTarget.blur();
                                    }
                                  }}
                                  placeholder="0"
                                />
                              ) : (
                                row.label === "Soliditet" ? 
                                  `${Math.round(v ?? 0).toLocaleString('sv-SE', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}%` : 
                                  formatAmount(v ?? 0)
                              )}
                            </TableCell>
                          ))}
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>

                {/* Action buttons - only show when editing */}
                {isEditingFlerars && (
                  <div className="flex justify-between pt-4">
                    <Button 
                      onClick={undoEditFlerars}
                      variant="outline"
                      className="flex items-center gap-2"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"/>
                      </svg>
                      Ångra ändringar
                    </Button>
                    
                    <Button 
                      onClick={approveEditFlerars}
                      className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 flex items-center gap-2"
                    >
                      Godkänn ändringar
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 10h-10a8 8 0 00-8 8v2M21 10l-6 6m6-6l-6-6"/>
                      </svg>
                    </Button>
                  </div>
                )}
              </>
            );
          })()}
        </section>

        {/* H2 Förändringar i eget kapital — existing, working table, embedded */}
        <section id="eget-kapital" className="mt-8 pt-5">
          <Forvaltningsberattelse
            embedded
            fbTable={companyData.fbTable || []}
            fbVariables={companyData.fbVariables || {}}
            fiscalYear={fy}
            onDataUpdate={onDataUpdate}
            arets_utdelning={companyData.arets_utdelning}
            sumFrittEgetKapital={companyData.sumFrittEgetKapital}
          />
        </section>

        {/* (Ignore Resultatdisposition for now as requested) */}
      </CardContent>
    </Card>
  );
}

// Database-driven always_show logic - no more hardcoded arrays

export function AnnualReportPreview({ companyData, currentStep, editableAmounts = false, onDataUpdate }: AnnualReportPreviewProps) {
  // Safe access; never destructure undefined
  const cd = companyData as CompanyData;
  
  // IMPORTANT: Wait for currentStep to be properly initialized to prevent flicker
  // If we're on step 510+ (Download/Signering), don't render other sections at all
  // This prevents the flash of content before Download/Signering renders
  
  // Requirement 1: render when showTaxPreview OR showRRBR is true
  // NOTE: Download (510+) and Signering (515+) ska visas även om tax/RRBR-flaggor är av.
  if (!cd.showTaxPreview && !cd.showRRBR && currentStep < 510) {
    return null;
  }

  // const { toast } = useToast(); // Commented out for now
  
  // Requirement 2: inputs become editable when taxEditingEnabled OR editableAmounts is true
  const isEditing = Boolean(cd.taxEditingEnabled || editableAmounts);

  // --- calculated rows (read-only) ---
  const CALCULATED = new Set([
    'INK4.1','INK4.2','INK4.3a','INK_skattemassigt_resultat',
    'INK_beraknad_skatt','INK4.15','INK4.16','Arets_resultat_justerat'
  ]);

  const isHeader = (name?: string) => !!name && /_header$/i.test(name || '');

  const isEditableCell = (name?: string) =>
    !!name && !CALCULATED.has(name) && !isHeader(name);

  // Build a baseline manual map from the currently shown table so the backend uses
  // exactly these amounts for non-calculated rows (unless overridden by chat/session).
  const buildBaselineManualsFromCurrent = (rows: any[]): Record<string, number> => {
    const out: Record<string, number> = {};
    for (const r of rows || []) {
      const v = r.variable_name;
      if (isEditableCell(v)) {
        const n = typeof r.amount === 'number' ? r.amount : Number(r.amount || 0);
        if (Number.isFinite(n)) out[v] = n;
      }
    }
    return out;
  };

  // Translate UI pension row to backend key (UI shows negative, backend expects positive delta)
  const translateManualsForApi = (manuals: Record<string, number>) => {
    const out: Record<string, number> = { ...manuals };
    if (typeof out['INK_sarskild_loneskatt'] === 'number') {
      out['justering_sarskild_loneskatt'] = Math.abs(out['INK_sarskild_loneskatt']);
      delete out['INK_sarskild_loneskatt'];
    }
    return out;
  };

  // Only these variables may change on any recalc
  const CALC_ONLY = new Set<string>([
    'INK_skattemassigt_resultat',
    'INK_beraknad_skatt',
    'INK4.15',
    'INK4.16',
    'Arets_resultat_justerat',
  ]);

  // When a recalc response arrives, only replace CALC_ONLY amounts;
  // for all others, keep the previous amount unless the user explicitly edited
  // or a chat override targets it.
  const selectiveMergeInk2 = (
    prevRows: any[],
    newRows: any[],
    manuals: Record<string, number>
  ) => {
    const prevBy = new Map(prevRows.map((r:any)=>[r.variable_name,r]));
    const nextBy = new Map(newRows.map((r:any)=>[r.variable_name,r]));
    const out: any[] = [];

    // include anything we used as a manual (e.g., 4.14a) even if server omitted it
    const manualNames = Object.keys(manuals);

    const names = new Set<string>([
      ...prevBy.keys(),
      ...nextBy.keys(),
      ...manualNames,
    ]);

    for (const name of names) {
      const prev = prevBy.get(name);
      const next = nextBy.get(name);

      // base row (prefer prev for metadata)
      const base = prev ?? next ?? {
        variable_name: name,
        row_title: name,
        amount: 0,
        always_show: true,
        show_tag: true,
        style: 'TNORMAL',
      };

      let amount = base.amount;

      if (Object.prototype.hasOwnProperty.call(manuals, name)) {
        // 1) manual values (chat / accepted / session) win for non-calculated lines
        amount = manuals[name];
      } else if (CALC_ONLY.has(name) && next) {
        // 2) only these can be refreshed by server
        amount = next.amount;
      }
      // 3) everything else stays exactly as previously shown

      out.push({ ...base, amount });
    }

    out.sort((a,b)=>(a.order_index??0)-(b.order_index??0));
    return out;
  };

  // Manuals the user has approved previously (persisted in companyData)
  const acceptedManuals: Record<string, number> = companyData.acceptedInk2Manuals || {};

  // Two chat overrides (only ones allowed to come from chat)
  const getChatOverrides = (): Record<string, number> => {
    const o: Record<string, number> = {};
    const underskott = Number(companyData.unusedTaxLossAmount || 0);
    const sarskild = Number(companyData.justeringSarskildLoneskatt || 0);
    if (Number.isFinite(underskott) && underskott !== 0) {
      o['INK4.14a'] = underskott; // UI key
    }
    if (Number.isFinite(sarskild) && sarskild !== 0) {
      o['INK_sarskild_loneskatt'] = -Math.abs(sarskild); // UI row shows negative
    }
    return o;
  };

  // In-session edits (cleared when leaving edit mode or on approve)
  const [manualEdits, setManualEdits] = useState<Record<string, number>>({});
  
  const [showAllRR, setShowAllRR] = useState(false);
  const [showAllBR, setShowAllBR] = useState(false);
  const [showAllTax, setShowAllTax] = useState(false);
  const [isInk2ManualEdit, setIsInk2ManualEdit] = useState(false);
  const [isRecalcPending, setIsRecalcPending] = useState(false);
  
  // Unified edit gate: works for both taxEditingEnabled and isInk2ManualEdit paths
  const canEdit = Boolean(isEditing || isInk2ManualEdit);
  
  // Store original baseline for proper undo functionality (like Noter)
  const originalInk2BaselineRef = useRef<any[]>([]);
  const originalRrDataRef = useRef<any[]>([]);
  const originalBrDataRef = useRef<any[]>([]);
  const clearAcceptedOnNextApproveRef = React.useRef(false);

  const [editedAmounts, setEditedAmounts] = useState<Record<string, number>>({});
  const [originalAmounts, setOriginalAmounts] = useState<Record<string, number>>({});
  const [recalculatedData, setRecalculatedData] = useState<any[]>([]);
  const [brDataWithNotes, setBrDataWithNotes] = useState<any[]>([]);
  const [rrDataWithNotes, setRrDataWithNotes] = useState<any[]>([]);

  // Get new database-driven parser data (moved up to avoid initialization errors)
  const seFileData = cd.seFileData;
  const rrData = seFileData?.rr_data || [];
  const brData = seFileData?.br_data || [];
  const ink2Data = cd.ink2Data || seFileData?.ink2_data || [];
  const companyInfo = seFileData?.company_info || {};

  // Helper function to format date from YYYYMMDD to YYYY-MM-DD
  const formatPeriodDate = (dateStr: string): string => {
    if (!dateStr || dateStr.length !== 8) return '';
    const year = dateStr.substring(0, 4);
    const month = dateStr.substring(4, 6);
    const day = dateStr.substring(6, 8);
    return `${year}-${month}-${day}`;
  };

  // Get formatted period end dates
  const getCurrentPeriodEndDate = (): string => {
    const endDate = (companyInfo as any)?.end_date; // e.g. "20241231" - from backend parsing
    if (endDate) {
      return formatPeriodDate(endDate);
    }
    // Fallback: use fiscal year + 12-31
    const fiscalYear = companyInfo.fiscal_year || cd.fiscalYear || new Date().getFullYear();
    return `${fiscalYear}-12-31`;
  };

  const getPreviousPeriodEndDate = (): string => {
    const endDate = (companyInfo as any)?.end_date; // e.g. "20241231" - from backend parsing
    if (endDate && endDate.length === 8) {
      const year = parseInt(endDate.substring(0, 4), 10) - 1;
      const monthDay = endDate.substring(4, 8); // "1231"
      const previousYearEndDate = `${year}${monthDay}`; // "20231231"
      return formatPeriodDate(previousYearEndDate);
    }
    // Fallback: use previous fiscal year + 12-31
    const fiscalYear = companyInfo.fiscal_year || cd.fiscalYear || new Date().getFullYear();
    return `${fiscalYear - 1}-12-31`;
  };

  // Capture original baseline when data first loads (like Noter)
  useEffect(() => {
    if (ink2Data && ink2Data.length > 0 && originalInk2BaselineRef.current.length === 0) {
      originalInk2BaselineRef.current = JSON.parse(JSON.stringify(ink2Data));
    }
    if (rrData && rrData.length > 0 && originalRrDataRef.current.length === 0) {
      originalRrDataRef.current = JSON.parse(JSON.stringify(rrData));
      // Expose to window for chat component access
      (window as any).__originalRrData = originalRrDataRef.current;
    }
    if (brData && brData.length > 0 && originalBrDataRef.current.length === 0) {
      originalBrDataRef.current = JSON.parse(JSON.stringify(brData));
      // Expose to window for chat component access
      (window as any).__originalBrData = originalBrDataRef.current;
    }
  }, [ink2Data, rrData, brData]);

  // Calculate dynamic note numbers based on Noter visibility logic
  const calculateDynamicNoteNumbers = () => {
    const noterData = cd.noterData || [];
    if (!noterData.length) return {};

    // Group items by block
    const groupedItems = noterData.reduce((acc: Record<string, any[]>, item: any) => {
      const block = item.block || 'OTHER';
      if (!acc[block]) acc[block] = [];
      acc[block].push(item);
      return acc;
    }, {});

    const blocks = Object.keys(groupedItems);
    let noteNumber = 3; // Start at 3 since NOT1=1 and NOT2=2 are fixed
    const noteNumbers: Record<string, number> = {};

    // Add fixed note numbers - these are always included
    noteNumbers['NOT1'] = 1;
    noteNumbers['NOT2'] = 2;

    // Helper function to get visible items (simplified version of Noter logic)
    const getVisibleItems = (items: any[]) => {
      if (!items) return [];
      return items.filter(item => {
        if (!item.always_show) {
          const hasNonZeroAmount = (item.current_amount !== 0 && item.current_amount !== null) || 
                                 (item.previous_amount !== 0 && item.previous_amount !== null);
          return hasNonZeroAmount;
        }
        return true;
      });
    };

    blocks.forEach(block => {
      const blockItems = groupedItems[block];
      const visibleItems = getVisibleItems(blockItems);
      
      // For OVRIGA block, always show if there's moderbolag data
      const scrapedData = (cd as any)?.scraped_company_data;
      const moderbolag = scrapedData?.moderbolag;
      const shouldShowOvrigaForModerbolag = block === 'OVRIGA' && moderbolag;
      
      // Check if block should be visible
      let isVisible = true;
      
      if (visibleItems.length === 0 && !shouldShowOvrigaForModerbolag) {
        isVisible = false;
      }
      
      // Hide specific blocks if all amounts are zero
      const blocksToHideIfZero = ['KONCERN', 'INTRESSEFTG', 'BYGG', 'MASKIN', 'INV', 'MAT', 'LVP'];
      if (blocksToHideIfZero.includes(block)) {
        const hasNonZeroAmount = blockItems.some(item => 
          (item.current_amount !== 0 && item.current_amount !== null) || 
          (item.previous_amount !== 0 && item.previous_amount !== null)
        );
        if (!hasNonZeroAmount) isVisible = false;
      }
      
      // Assign note numbers to visible blocks (exclude NOT1, NOT2, EVENTUAL, SAKERHET, OVRIGA)
      let shouldGetNumber = isVisible && 
                           block !== 'NOT1' && 
                           block !== 'NOT2' && 
                           block !== 'EVENTUAL' && 
                           block !== 'SAKERHET' && 
                           block !== 'OVRIGA';
      
      if (shouldGetNumber) {
        noteNumbers[block] = noteNumber++;
      }
    });

    console.log('Final note numbers calculated:', noteNumbers);
    console.log('Available blocks:', blocks);
    console.log('NoterData length:', noterData.length);
    console.log('GroupedItems:', Object.keys(groupedItems));
    return noteNumbers;
  };

  // Load BR and RR data with note numbers when data changes
  // Debounced and guarded API call to prevent multiple requests
  const inFlightRef = useRef(false);
  const lastSigRef = useRef<string>("");

  useEffect(() => {
    const loadDataWithNotes = async () => {
      if (!brData.length && !rrData.length) {
        setBrDataWithNotes([]);
        setRrDataWithNotes([]);
        return;
      }

      // Create a content-sensitive signature so we re-call when amounts change
      const sig = computeCombinedFinancialSig(rrData, brData);
      if (sig === lastSigRef.current || inFlightRef.current) return;

      inFlightRef.current = true;
      lastSigRef.current = sig;

      try {
        // Calculate dynamic note numbers based on Noter visibility
        const dynamicNoteNumbers = calculateDynamicNoteNumbers();
        
        const response = await apiService.addNoteNumbersToBr({ 
          br_data: brData,
          rr_data: rrData,
          note_numbers: dynamicNoteNumbers
        });
        
        if (response.success) {
          setBrDataWithNotes(response.br_data || brData);
          setRrDataWithNotes(response.rr_data || rrData);
          // Also update companyData with enriched data for PDF generation
          onDataUpdate?.({ 
            brData: response.br_data || brData,
            rrData: response.rr_data || rrData
          });
        } else {
          // Fallback to original data if API fails
          setBrDataWithNotes(brData);
          setRrDataWithNotes(rrData);
          onDataUpdate?.({ brData, rrData });
        }
      } catch (error) {
        console.error('Error loading financial data with note numbers:', error);
        // Fallback to original data if API fails
        setBrDataWithNotes(brData);
        setRrDataWithNotes(rrData);
        onDataUpdate?.({ brData, rrData });
      } finally {
        inFlightRef.current = false;
      }
    };

    const t = setTimeout(loadDataWithNotes, 200); // debounce
    return () => clearTimeout(t);
  }, [brData, rrData, cd.noterData, onDataUpdate]);

  // Enter/leave edit mode behavior
  useEffect(() => {
    if (isEditing) {
      // Start session from accepted manuals (get fresh value from companyData)
      const currentAccepted = companyData.acceptedInk2Manuals || {};
      setManualEdits({ ...currentAccepted });
      clearAcceptedOnNextApproveRef.current = false; // fresh session
    } else {
      // Clear session edits when leaving edit mode
      setManualEdits({});
      clearAcceptedOnNextApproveRef.current = false;
    }
  }, [isEditing, companyData.acceptedInk2Manuals]);



  // NEW: options to control whether to include accepted manuals and which baseline to use
  type RecalcOpts = { 
    includeAccepted?: boolean; 
    baselineSource?: 'current' | 'original'; 
    acceptedManualsOverride?: Record<string, number> | null;
    useCurrentRrBr?: boolean; // For chat injections that need SLP effects preserved
  };

  const recalcWithManuals = async (
    sessionManuals: Record<string, number>,
    opts: RecalcOpts = {}
  ) => {
    const { includeAccepted = true, baselineSource = 'current', acceptedManualsOverride = null, useCurrentRrBr = false } = opts;

    // 0) Pick baseline source
    const currentRows = companyData.ink2Data || [];
    const originalRows = originalInk2BaselineRef.current || [];
    const rowsForBaseline = baselineSource === 'original' ? originalRows : currentRows;
    const baseline = buildBaselineManualsFromCurrent(rowsForBaseline);

    // 1) Compose: baseline → (accepted?) → chat → session
    const accepted = includeAccepted 
      ? (acceptedManualsOverride ?? (companyData.acceptedInk2Manuals || {}))
      : {};
    const manualComposite = {
      ...baseline,
      ...accepted,
      ...getChatOverrides(),
      ...sessionManuals,
    };

    // 2) Send to backend (with calc-only hint)
    // Choose RR/BR data source based on context:
    // - Chat injections: use current data (includes SLP effects)
    // - Manual edit mode: use original baseline (prevents feedback loops)
    const rrDataToUse = useCurrentRrBr 
      ? (companyData.seFileData?.rr_data || [])
      : (originalRrDataRef.current.length > 0 ? originalRrDataRef.current : (companyData.seFileData?.rr_data || []));
    const brDataToUse = useCurrentRrBr 
      ? (companyData.seFileData?.br_data || [])
      : (originalBrDataRef.current.length > 0 ? originalBrDataRef.current : (companyData.seFileData?.br_data || []));

    const payload = {
      current_accounts: companyData.seFileData?.current_accounts || {},
      fiscal_year: companyData.fiscalYear,
      rr_data: rrDataToUse,
      br_data: brDataToUse,
      manual_amounts: translateManualsForApi(manualComposite),
      // @ts-ignore - Optional optimization hint; safe if backend ignores it
      recalc_only_vars: Array.from(CALC_ONLY),
    };

    const prev = currentRows;
    const result = await apiService.recalculateInk2(payload);
    if (result?.success) {
      const merged = selectiveMergeInk2(prev, result.ink2_data, manualComposite);
      
      // Store recalculated data in state for display purposes
      setRecalculatedData(merged);
      
      // Only update ink2Data in companyData if not in manual edit mode
      // During manual edit, the recalculatedData state will be used for display
      // This prevents flickering when user is typing
      if (!isInk2ManualEdit) {
        onDataUpdate({
          ink2Data: merged,
          inkBeraknadSkatt:
            merged.find((i:any)=>i.variable_name==='INK_beraknad_skatt')?.amount
            ?? companyData.inkBeraknadSkatt
        });
      } else {
        // In edit mode, only update the calculated tax value
        onDataUpdate({
          inkBeraknadSkatt:
            merged.find((i:any)=>i.variable_name==='INK_beraknad_skatt')?.amount
            ?? companyData.inkBeraknadSkatt
        });
      }
    }
  };

  // Canonical Undo
  const handleUndo = async () => {
    // this session's manual edits are discarded
    setManualEdits({});

    // mark that the next approve should clear old accepted edits
    clearAcceptedOnNextApproveRef.current = true;

    // recalc with baseline=original, without accepted
    await recalcWithManuals({}, { includeAccepted: false, baselineSource: 'original' });
  };

  
  // Debug logging

  

  
  // No fallback needed - database-driven parser provides all data

  // Helper function to get styling classes and style based on style
  const getStyleClasses = (style?: string) => {
    const baseClasses = 'grid gap-4';
    let additionalClasses = '';
    
    // Handle bold styling for header styles only
    if (style === 'H0' || style === 'H1' || style === 'H2' || style === 'H3' || style === 'S1' || style === 'S2' || style === 'S3') {
      additionalClasses += ' font-semibold';
    }
    
    // Handle specific styling for S2 and S3 (thin grey lines above and below)
    if (style === 'S2' || style === 'S3') {
      additionalClasses += ' border-t border-b border-gray-200 pt-1 pb-1';
    }
    
    return {
      className: `${baseClasses}${additionalClasses}`,
      style: { gridTemplateColumns: '4fr 0.5fr 1fr 1fr' }
    };
  };

  // Same styling semantics as RR/BR but for INK2's 2-column layout
  const getInkStyleClasses = (style?: string, variableName?: string) => {
    const s = style || '';
    const classes = ['grid', 'gap-x-2', 'leading-tight']; // no vertical gap, tight line-height

    // Bold styles - TNORMAL should NOT be bold
    const boldStyles = ['H0','H1','H2','H3','S1','S2','S3','TH0','TH1','TH2','TH3','TS1','TS2','TS3'];
    const specialBoldVariables = ['INK_skattemassigt_resultat'];
    if (boldStyles.includes(s) || (variableName && specialBoldVariables.includes(variableName))) {
      classes.push('font-semibold');
    }

    // Headings (keep inner padding)
    const headingStyles = ['H0','H1','H2','H3','TH0','TH1','TH2','TH3'];
    const isHeading = headingStyles.includes(s);
    if (isHeading) classes.push('py-1.5');

    // Lines (S2/S3/TS2/TS3) get borders; do NOT add py-0 later to these
    const lineStyles = ['S2','S3','TS2','TS3'];
    const isLine = lineStyles.includes(s) || (variableName === 'INK_skattemassigt_resultat');
    if (isLine) classes.push('border-t','border-b','border-gray-300');

    // Special spacing:
    // TH3: clear space BEFORE the heading + a touch of top padding inside
    if (s === 'TH3') {
      classes.push('mt-2', 'pt-2');
    }
    // TS2: inner padding AND outer margin so it doesn't look crushed
    if (s === 'TS2') {
      classes.push('py-2', 'my-2'); // More space over and under TS2
    }
    // Extra space before "Skattemässigt resultat" row
    if (variableName === 'INK_skattemassigt_resultat') {
      classes.push('mt-3'); // Extra space before this specific row
    }

    // Compact default rows (not heading, not line, not TNORMAL)
    if (!isHeading && !isLine && s !== 'TNORMAL') {
      classes.push('py-0'); // keep rows ultra-tight by default
    }

    // TNORMAL: tiny inner padding and normal text size, plus indent
    if (s === 'TNORMAL') {
      classes.push('text-base', 'py-0.5', 'pl-6');
    }

    return {
      className: classes.join(' '),
      style: { gridTemplateColumns: '3fr 1fr' },
    };
  };

  // Helper function to format amount (show 0 kr instead of -0 kr)
  const formatAmountDisplay = (amount: number | null): string => {
    if (amount === null || amount === undefined) {
      return '';
    }
    if (amount === 0) {
      return '0 kr';
    }
    return `${formatAmount(amount)} kr`;
  };


  // Canonical Approve
  const handleApproveChanges = async () => {
    // Check if this is the first time the button is clicked
    const isFirstTimeClick = !companyData.taxButtonClickedBefore;
    
    // If Undo was used this session, drop previously accepted edits
    const nextAccepted = clearAcceptedOnNextApproveRef.current
      ? { ...manualEdits }                      // approve only current session edits
      : { ...(companyData.acceptedInk2Manuals || {}), ...manualEdits };

    // Get current INK2 data and update it with the accepted manual values
    // Use recalculatedData if available (has latest values from manual edits), otherwise fall back to companyData.ink2Data
    const currentInk2 = recalculatedData.length > 0 ? recalculatedData : (companyData.ink2Data || []);
    console.log('🔍 handleApproveChanges - using data source:', {
      usingRecalculated: recalculatedData.length > 0,
      recalculatedDataLength: recalculatedData.length,
      companyDataInk2Length: (companyData.ink2Data || []).length,
      currentInk2Length: currentInk2.length
    });
    
    const updatedInk2Data = currentInk2.map((item: any) => {
      // If there's a manual value for this variable, use it
      if (nextAccepted[item.variable_name] !== undefined) {
        return { ...item, amount: nextAccepted[item.variable_name] };
      }
      return item;
    });
    
    // Log key values for debugging
    const beraknadInUpdated = updatedInk2Data.find((i: any) => i.variable_name === 'INK_beraknad_skatt');
    const bokfordInUpdated = updatedInk2Data.find((i: any) => i.variable_name === 'INK_bokford_skatt');
    console.log('🔍 Updated INK2 data key values:', {
      beraknadSkatt: beraknadInUpdated?.amount,
      bokfordSkatt: bokfordInUpdated?.amount,
      difference: (beraknadInUpdated?.amount || 0) - (bokfordInUpdated?.amount || 0)
    });

    // Update accepted edits, ink2Data, and mark the button as clicked
    onDataUpdate({ 
      acceptedInk2Manuals: nextAccepted,
      ink2Data: updatedInk2Data,
      taxButtonClickedBefore: true
    });

    // If this is the first time clicking the button, trigger navigation to step 405
    if (isFirstTimeClick && onDataUpdate) {
      console.log('🎯 First time clicking tax approve button - triggering step 405');
      onDataUpdate({ triggerChatStep: 405 });
    }

    // Check if we need to update RR/BR data based on tax differences
    // Pass the updated INK2 data directly to ensure we use the latest values
    // Always update when user manually approves (forceUpdate = true)
    await handleTaxUpdateLogic(nextAccepted, updatedInk2Data, true);

    // reset the flag and session edits, close edit mode, hide 0-rows right away (no lag)
    clearAcceptedOnNextApproveRef.current = false;
    setManualEdits({});
    setRecalculatedData([]); // Clear recalculated data now that it's been approved
    setIsInk2ManualEdit(false);
    onDataUpdate({ taxEditingEnabled: false, editableAmounts: false, showTaxPreview: true });
    setShowAllTax(false);

    // Auto-scroll to tax module immediately
    setTimeout(() => {
      const taxModule = document.querySelector('[data-section="tax-calculation"]');
      if (taxModule) {
        taxModule.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }, 100);

  // DON'T recalculate INK2 after approval - keep the approved manual edits stable
  // The INK2 data should remain exactly as the user approved it
};

// Handle click on SKATTEBERÄKNING button in RR row 276
const handleTaxCalculationClick = () => {
  console.log('🎯 SKATTEBERÄKNING button clicked - showing tax module');
  
  // Show tax module if hidden
  if (onDataUpdate) {
    onDataUpdate({ showTaxPreview: true });
  }
  
  // Auto-scroll to tax module after a brief delay to ensure it's rendered
  setTimeout(() => {
    const taxModule = document.querySelector('[data-section="tax-calculation"]');
    if (taxModule) {
      taxModule.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } else {
      console.log('⚠️ Tax module not found for scrolling');
    }
  }, 200);
};

  // Handle tax update logic when approving changes
  const handleTaxUpdateLogic = async (acceptedManuals: any, updatedInk2Data?: any[], forceUpdate = false) => {
    try {
      console.log('🔍 Starting handleTaxUpdateLogic...', { forceUpdate });
      console.log('🔍 Accepted manuals:', acceptedManuals);
      
      // Get current INK2 data with accepted manual edits
      // Use provided updatedInk2Data if available (for immediate use after approval)
      const currentInk2Data = updatedInk2Data || (recalculatedData.length > 0 ? recalculatedData : ink2Data);
      
      console.log('📊 Current INK2 data:', {
        recalculatedDataLength: recalculatedData.length,
        ink2DataLength: ink2Data.length,
        currentInk2DataLength: currentInk2Data.length,
        usingRecalculated: recalculatedData.length > 0
      });
      
      // Debug: Log all variable names in the data
      const variableNames = currentInk2Data.map((item: any) => item.variable_name).filter(Boolean);
      console.log('📋 Available variable names:', variableNames);
      
      // Helper function to get value with manual override
      const getValueWithOverride = (variableName: string): number => {
        // Check if there's a manual override first
        if (acceptedManuals && acceptedManuals[variableName] !== undefined) {
          const value = Number(acceptedManuals[variableName]);
          console.log(`🔧 Using manual override for ${variableName}: ${value} (from acceptedManuals)`);
          return value;
        }
        
        // Otherwise get from INK2 data
        const item = currentInk2Data.find((item: any) => item.variable_name === variableName);
        const value = item?.amount || 0;
        console.log(`📊 Using INK2 data for ${variableName}: ${value} (item found: ${!!item})`);
        return value;
      };
      
      // Find INK_beraknad_skatt and INK_bokford_skatt values
      const beraknadSkattItem = currentInk2Data.find((item: any) => item.variable_name === 'INK_beraknad_skatt');
      const bokfordSkattItem = currentInk2Data.find((item: any) => item.variable_name === 'INK_bokford_skatt');
      
      console.log('🔍 Tax items found:', {
        beraknadSkattItem: beraknadSkattItem ? {
          variable_name: beraknadSkattItem.variable_name,
          amount: beraknadSkattItem.amount,
          row_title: beraknadSkattItem.row_title
        } : null,
        bokfordSkattItem: bokfordSkattItem ? {
          variable_name: bokfordSkattItem.variable_name,
          amount: bokfordSkattItem.amount,
          row_title: bokfordSkattItem.row_title
        } : null
      });
      
      if (!beraknadSkattItem || !bokfordSkattItem) {
        console.log('❌ Could not find INK_beraknad_skatt or INK_bokford_skatt items');
        return;
      }

      // Get values with manual overrides applied
      const inkBeraknadSkatt = getValueWithOverride('INK_beraknad_skatt');
      const inkBokfordSkatt = getValueWithOverride('INK_bokford_skatt');
      
      // Get SLP value with manual override applied
      // The UI stores manual edits under 'INK_sarskild_loneskatt', not 'justering_sarskild_loneskatt'
      const inkSarskildLoneskattValue = getValueWithOverride('INK_sarskild_loneskatt');
      const inkSarskildLoneskatt = Math.abs(inkSarskildLoneskattValue);
      
      // Extra debugging for SLP
      console.log('🔍 SLP Debug Info:', {
        acceptedManuals_INK_sarskild_loneskatt: acceptedManuals ? acceptedManuals['INK_sarskild_loneskatt'] : 'no acceptedManuals',
        allAcceptedManualKeys: acceptedManuals ? Object.keys(acceptedManuals) : [],
        currentInk2DataLength: currentInk2Data.length,
        slpItemInData: currentInk2Data.find((i: any) => i.variable_name === 'INK_sarskild_loneskatt')
      });
      
      console.log('💰 Tax and SLP comparison:', { 
        inkBeraknadSkatt, 
        inkBokfordSkatt, 
        inkSarskildLoneskattValue,
        inkSarskildLoneskatt,
        hasManualSLP: acceptedManuals && acceptedManuals['INK_sarskild_loneskatt'] !== undefined
      });
      
      const taxDifference = inkBeraknadSkatt - inkBokfordSkatt;
      
      // Only proceed if there's a tax difference OR an SLP value OR forceUpdate is true
      // forceUpdate = true when user manually approves changes (always update RR/BR)
      // This allows updates for tax-only changes, SLP-only changes, both, or manual approval
      if (!forceUpdate && taxDifference === 0 && inkSarskildLoneskatt === 0) {
        console.log('✅ No tax difference and no SLP, skipping RR/BR updates');
        return;
      }

      if (forceUpdate) {
        console.log('🔧 Force update enabled - proceeding with RR/BR update from manual approval');
      }
      if (taxDifference !== 0) {
        console.log('🚨 Tax difference detected:', taxDifference);
      }
      if (inkSarskildLoneskatt !== 0) {
        console.log('🚨 SLP value detected:', inkSarskildLoneskatt);
      }

      // Call API to update RR/BR data
      console.log('🌐 Calling API to update RR/BR data...');

      const requestData = {
        inkBeraknadSkatt,
        inkBokfordSkatt,
        taxDifference,
        rr_data: companyData.seFileData?.rr_data || [],
        br_data: companyData.seFileData?.br_data || [],
        organizationNumber: companyData.organizationNumber,
        fiscalYear: companyData.fiscalYear,
        // NEW: SLP amount
        inkSarskildLoneskatt,
      };
      
      console.log('📤 API request data:', {
        inkBeraknadSkatt,
        inkBokfordSkatt,
        taxDifference,
        inkSarskildLoneskatt,
        rr_data_length: requestData.rr_data.length,
        br_data_length: requestData.br_data.length,
        organizationNumber: companyData.organizationNumber,
        fiscalYear: companyData.fiscalYear
      });
      
      const response = await fetch(`${import.meta.env.VITE_API_URL || 'https://api.summare.se'}/api/update-tax-in-financial-data`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData),
      });

      console.log('📥 API response status:', response.status);

    if (!response.ok) {
      const errorText = await response.text();
      console.error('❌ API error response:', errorText);
      
      if (response.status === 404) {
        console.log('⚠️ Tax update endpoint not available yet - deployment in progress');
        // Don't throw error for 404, just log and continue
        return;
      }
      
      throw new Error(`HTTP error! status: ${response.status}, body: ${errorText}`);
    }

      const result = await response.json();
      console.log('✅ API response result:', result);
      
      if (result.success) {
        console.log('🎉 Successfully updated RR/BR data with tax changes');
        console.log('📊 Changes made:', result.changes);
        
        // Show success toast notification (commented out for now)
        // const taxAmount = new Intl.NumberFormat('sv-SE', {
        //   minimumFractionDigits: 0,
        //   maximumFractionDigits: 0
        // }).format(inkBeraknadSkatt);
        // 
        // toast({
        //   title: "Skatteberäkning uppdaterad",
        //   description: `Skatt på årets resultat har uppdaterats till ${taxAmount} kr i resultat- och balansräkningen.`,
        //   duration: 4000,
        // });
        
      // Update company data with new RR/BR data
      onDataUpdate({
        seFileData: {
          ...companyData.seFileData,
          rr_data: result.rr_data,
          br_data: result.br_data,
        }
      });
      } else {
        console.error('❌ Failed to update RR/BR data:', result.error);
      }
      
    } catch (error) {
      console.error('Error in handleTaxUpdateLogic:', error);
    }
  };

  // Helper function to check if a block should be shown
  const shouldShowBlock = (data: any[], startIndex: number, endIndex: number, alwaysShowItems: string[], showAll: boolean): boolean => {
    if (showAll) return true;
    
    // Check if any item in the block has non-zero amounts or is in always show list
    for (let i = startIndex; i <= endIndex && i < data.length; i++) {
      const item = data[i];
      const hasNonZeroAmount = (item.current_amount !== null && item.current_amount !== 0) ||
                              (item.previous_amount !== null && item.previous_amount !== 0);
      const isAlwaysShow = alwaysShowItems.includes(item.label);
      
      if (hasNonZeroAmount || isAlwaysShow) {
        return true;
      }
    }
    return false;
  };

  // Helper function to check if a block group has any content
  const blockGroupHasContent = (data: any[], blockGroup: string): boolean => {
    if (!blockGroup) return true; // Show items without block_group
    
    const blockItems = data.filter(item => item.block_group === blockGroup);
    
    for (const item of blockItems) {
      const isHeading = item.style && ['H0', 'H1', 'H2', 'H3', 'S1', 'S2', 'S3'].includes(item.style);
      if (isHeading) continue; // Skip headings when checking block content
      
      const hasNonZeroAmount = (item.current_amount !== null && item.current_amount !== 0) ||
                              (item.previous_amount !== null && item.previous_amount !== 0);
      const isAlwaysShow = item.always_show === true; // Use database field
      
      if (hasNonZeroAmount || isAlwaysShow) {
        return true;
      }
    }
    return false;
  };

  // Helper function to check if a row should be shown
  const shouldShowRow = (item: any, showAll: boolean, data: any[]): boolean => {
    if (showAll) return true;
    
    // Check if this is a heading
    const isHeading = item.style && ['H0', 'H1', 'H2', 'H3'].includes(item.style);
    
    if (isHeading) {
      // For headings, check if their block group has content
      if (item.block_group) {
        return blockGroupHasContent(data, item.block_group);
      }
      // NEW: Even headings without block_group must follow always_show rule
      return item.always_show === true;
    }
    
    // NEW LOGIC: If amount is 0 for both years, hide unless always_show = true OR has note number
    const hasNonZeroAmount = (item.current_amount !== null && item.current_amount !== 0) ||
                            (item.previous_amount !== null && item.previous_amount !== 0);
    const isAlwaysShow = item.always_show === true; // Use database field
    const hasNoteNumber = item.note_number !== undefined && item.note_number !== null; // Has note reference
    
    // Show if: (has non-zero amount) OR (always_show = true) OR (has note number)
    return hasNonZeroAmount || isAlwaysShow || hasNoteNumber;
  };

  // Helper function to get note value for specific rows
  const getNoteValue = (item: any): string => {
    // Check if this item has a note number from the backend
    if (item.note_number) {
      return item.note_number.toString();
    }
    
    // Direct mapping for RR rows that should have note numbers
    // Personalkostnader (id=252) should always show note 2
    if (item.id === "252" || item.label === "Personalkostnader") {
      return "2";
    }
    
    return '';
  };

  const getPreviewContent = () => {
    // Show empty state only if we have no data and are at step 0
    if (currentStep === 0 && !rrData.length && !brDataWithNotes.length) {
      return (
        <div className="text-center py-20">
          <div className="text-muted-foreground mb-4">
            <div className="w-16 h-16 mx-auto mb-4 rounded-lg bg-muted flex items-center justify-center">
              📄
            </div>
            <h3 className="text-lg font-medium mb-2">Årsredovisning</h3>
            <p className="text-sm">Din rapport kommer att visas här när du börjar processen</p>
          </div>
        </div>
      );
    }

    // Show preview content if we have data, regardless of currentStep
    if (!rrData.length && !brDataWithNotes.length) {
      return (
        <div className="text-center py-20">
          <div className="text-muted-foreground mb-4">
            <div className="w-16 h-16 mx-auto mb-4 rounded-lg bg-muted flex items-center justify-center">
              ⏳
            </div>
            <h3 className="text-lg font-medium mb-2">Laddar data...</h3>
            <p className="text-sm">Bearbetar SE-fil data</p>
          </div>
        </div>
      );
    }

    // Use structured data from Python if available, with fallbacks
    // Priority for organization number: scraped data > SE file data > fallback
    const scrapedOrgNumber = (companyData as any).scraped_company_data?.orgnr;
    const seFileOrgNumber = companyInfo?.organization_number;
    const fallbackOrgNumber = (companyData as any).organizationNumber;
    
    const headerData = {
      organization_number: scrapedOrgNumber || seFileOrgNumber || fallbackOrgNumber || 'Ej tillgängligt',
      fiscal_year: companyInfo?.fiscal_year || companyData.fiscalYear || new Date().getFullYear(),
      company_name: companyInfo?.company_name || (companyData as any).companyName || 'Företag AB',
      location: companyInfo?.location || companyData.location || 'Stockholm',
      date: companyData.date || new Date().toLocaleDateString('sv-SE')
    };
    


    return (
      <div className="space-y-6">
        {/* Company Header */}
        <div className="border-b pb-4">
          <h1 className="text-2xl font-bold text-foreground">Årsredovisning</h1>
          <h2 className="text-xl font-semibold text-foreground mt-2">{headerData.company_name}</h2>
          <p className="text-sm text-muted-foreground">
            Organisationsnummer: {headerData.organization_number}
          </p>
          <p className="text-sm text-muted-foreground">
            Räkenskapsår: {headerData.fiscal_year}
          </p>
        </div>

        {/* Financial Results Section */}
        {(
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-foreground">Resultaträkning</h2>
              <div className="flex items-center space-x-2">
                <span className="text-sm text-muted-foreground">Visa alla rader</span>
                <Switch
                  checked={showAllRR}
                  onCheckedChange={setShowAllRR}
                  className={`${showAllRR ? 'bg-green-500' : 'bg-gray-300'}`}
                />
              </div>
            </div>
            
            {/* Column Headers */}
            <div className="grid gap-4 text-sm text-muted-foreground border-b pb-1 font-semibold" style={{gridTemplateColumns: '4fr 0.5fr 1fr 1fr'}}>
              <span></span>
              <span className="text-right">Not</span>
              <span className="text-right">{headerData.fiscal_year}</span>
              <span className="text-right">{headerData.fiscal_year - 1}</span>
            </div>

            {/* Income Statement Rows */}
            {rrData.length > 0 ? (
              (() => {
                const liveSig = computeCombinedFinancialSig(rrData, brData);
                const useRR = (rrDataWithNotes.length > 0 && liveSig === lastSigRef.current) ? rrDataWithNotes : rrData;
                
                
                return useRR.map((item, index) => {
                if (!shouldShowRow(item, showAllRR, rrDataWithNotes.length > 0 ? rrDataWithNotes : rrData)) {
                  return null;
                }
                
                return (
                  <div 
                    key={index} 
                    className={`${getStyleClasses(item.style).className} ${
                      item.level === 0 ? 'border-b pb-1' : ''
                    }`}
                    style={getStyleClasses(item.style).style}
                  >
                    <span className="text-muted-foreground flex items-center justify-between">
                      <span>{item.label}</span>
                      {/* Add SKATTEBERÄKNING button for row_id 277 (Skatt på årets resultat) */}
                      {(() => {
                        return item.id === "277" || item.id === 277;
                      })() && (
                        <Button 
                          variant="outline" 
                          size="sm" 
                          className="ml-2 h-4 px-1.5 text-xs bg-blue-600 hover:bg-blue-700 text-white border-blue-600 hover:border-blue-700" 
                          style={{fontSize: '0.75rem'}}
                          onClick={handleTaxCalculationClick}
                          title="Visa skatteberäkning"
                        >
                          VISA
                        </Button>
                      )}
                    </span>
                    <span className="text-right font-medium">
                      {getNoteValue(item)}
                    </span>
                    <span className="text-right font-medium">
                      {formatAmountDisplay(item.current_amount)}
                    </span>
                    <span className="text-right font-medium">
                      {formatAmountDisplay(item.previous_amount)}
                    </span>
                  </div>
                );
              });
              })()
            ) : (
              <div className="text-sm text-muted-foreground">
                <span className="text-xs text-muted-foreground">SE-fil</span>
                <span>Data från uppladdad SE-fil</span>
              </div>
            )}
          </div>
        )}

        {/* Balance Sheet Section */}
        {(
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-foreground">Balansräkning</h2>
              <div className="flex items-center space-x-2">
                <span className="text-sm text-muted-foreground">Visa alla rader</span>
                <Switch
                  checked={showAllBR}
                  onCheckedChange={setShowAllBR}
                  className={`${showAllBR ? 'bg-green-500' : 'bg-gray-300'}`}
                />
              </div>
            </div>
            
            {/* Column Headers */}
            <div className="grid gap-4 text-sm text-muted-foreground border-b pb-1 font-semibold" style={{gridTemplateColumns: '4fr 0.5fr 1fr 1fr'}}>
              <span></span>
              <span className="text-right">Not</span>
              <span className="text-right">{getCurrentPeriodEndDate()}</span>
              <span className="text-right">{getPreviousPeriodEndDate()}</span>
            </div>

            {/* Balance Sheet Rows */}
            {(() => {
              const liveSig = computeCombinedFinancialSig(rrData, brData);
              const useBR = (brDataWithNotes.length > 0 && liveSig === lastSigRef.current) ? brDataWithNotes : brData;
              return useBR.length > 0 ? (
                useBR.map((item, index) => {
                if (!shouldShowRow(item, showAllBR, brDataWithNotes)) {
                  return null;
                }
                
                return (
                  <div 
                    key={index} 
                    className={`${getStyleClasses(item.style).className} ${
                      item.level === 0 ? 'border-b pb-1' : ''
                    }`}
                    style={getStyleClasses(item.style).style}
                  >
                    <span className="text-muted-foreground">{item.label}</span>
                    <span className="text-right font-medium">
                      {getNoteValue(item)}
                    </span>
                    <span className="text-right font-medium">
                      {formatAmountDisplay(item.current_amount)}
                    </span>
                    <span className="text-right font-medium">
                      {formatAmountDisplay(item.previous_amount)}
                    </span>
                  </div>
                );
              })
              ) : (
                <div className="text-sm text-muted-foreground">
                  <span className="text-xs text-muted-foreground">SE-fil</span>
                  <span>Data från uppladdad SE-fil</span>
                </div>
              );
            })()}
          </div>
        )}

        {/* Tax Calculation Section */}
        {companyData.showTaxPreview && ink2Data && ink2Data.length > 0 && (
          <div className="bg-gradient-to-r from-yellow-50 to-amber-50 p-4 rounded-lg border border-yellow-200" data-section="tax-calculation">
            <div className="mb-4">
              <div className="flex items-center justify-between border-b pb-2">
                <div className="flex items-center gap-3">
                  <h2 className="text-lg font-semibold text-foreground">Skatteberäkning</h2>
                  <button
                    onClick={() => {
                      setIsInk2ManualEdit(!isInk2ManualEdit);
                      // Optional: sync global flag for consistency
                      onDataUpdate({ taxEditingEnabled: !isInk2ManualEdit });
                    }}
                    className={`w-6 h-6 rounded-full flex items-center justify-center transition-colors ${
                      isInk2ManualEdit 
                        ? 'bg-blue-600 text-white' 
                        : 'bg-gray-200 hover:bg-gray-300 text-gray-600'
                    }`}
                    title={isInk2ManualEdit ? 'Avsluta redigering' : 'Redigera värden'}
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
                    </svg>
                  </button>
                </div>
                <div className="flex items-center space-x-2">
                  <label 
                    htmlFor="toggle-show-all-tax" 
                    className="text-sm font-medium cursor-pointer"
                  >
                    Visa hela INK2S
                  </label>
                  <Switch
                    id="toggle-show-all-tax"
                    checked={showAllTax}
                    onCheckedChange={setShowAllTax}
                  />
                </div>
              </div>
              <p className="text-sm leading-relaxed font-normal font-sans text-foreground mt-3">
                Här nedan visas endast de vanligaste skattemässiga justeringarna. Belopp har automatiskt hämtats från bokföringen, men det går bra att justera dem manuellt här. Fullständiga justeringar är möjliga att göra om du klickar på visa hela INK2S.
              </p>
            </div>
            
            {/* Column Headers */}
            <div className="grid gap-4 text-sm text-muted-foreground border-b pb-1 font-semibold" style={{gridTemplateColumns: '3fr 1fr'}}>
              <span></span>
              <span className="text-right">{headerData.fiscal_year}</span>
            </div>

            {/* Tax Calculation Rows */}
            {(() => {
              const allData = recalculatedData.length > 0 ? recalculatedData : ink2Data;
              
              // Find INK_sarskild_loneskatt row for conditional logic
              const sarskildRow = allData.find((item: any) => item.variable_name === 'INK_sarskild_loneskatt');
              
              // Helper function to check if any row in a block should be shown
              const shouldShowBlockContent = (blockName: string): boolean => {
                if (!blockName) return true; // Items without block are always evaluated individually
                
                return allData.some((item: any) => {
                  if (item.block !== blockName || item.header === true) return false; // Skip headers and other blocks
                  
                  // Check individual row visibility rules
                  if (item.show_amount === 'NEVER') return false;
                  
                  // Handle always_show with new boolean/null logic
                  if (item.always_show === true) return true;
                  if (item.always_show === false) return false;
                  
                  // For always_show = null/undefined, show if amount is non-zero OR toggle is on
                  return (item.amount !== null && item.amount !== undefined && 
                         item.amount !== 0) || showAllTax;
                });
              };
              
              const filteredData = allData.filter((item: any) => {
                // Always exclude rows explicitly marked to never show
                if (item.show_amount === 'NEVER') return false;

                // NEW TOGGLE LOGIC: When toggle is ON, override with toggle_show logic
                if (showAllTax) {
                  // Special case: INK_sarskild_loneskatt must still meet its conditions even when toggle is ON
                  if (item.variable_name === 'INK_sarskild_loneskatt') {
                    if (item.toggle_show === false) return false;
                    const pensionPremier = companyData.pensionPremier || 0;
                    const calculated = companyData.sarskildLoneskattPensionCalculated || 0;
                    const actual = companyData.sarskildLoneskattPension || 0;
                    return item.toggle_show === true && (pensionPremier > 0 && calculated > actual);
                  }
                  return item.toggle_show === true;
                }

                // ORIGINAL LOGIC: When toggle is OFF, use original always_show logic
                // In manual edit mode, use the same filtering rules as non-edit mode
                if (isEditing) {
                  // Special case: INK_sarskild_loneskatt overrides all normal logic in edit mode too
                  if (item.variable_name === 'INK_sarskild_loneskatt') {
                    const pensionPremier = companyData.pensionPremier || 0;
                    const calculated = companyData.sarskildLoneskattPensionCalculated || 0;
                    const actual = companyData.sarskildLoneskattPension || 0;
                    return pensionPremier > 0 && calculated > actual;
                  }

                  // Always exclude rows explicitly marked to never show
                  if (item.always_show === false) return false;
                  
                  if (item.header === true) {
                    return shouldShowBlockContent(item.block);
                  }
                  
                  // Same logic as non-edit mode: show if always_show=true OR (always_show=null AND amount≠0)
                  if (item.always_show === true) return true;
                  
                  // For always_show = null/undefined, show only if amount is non-zero
                  const hasNonZeroAmount = item.amount !== null && item.amount !== undefined && 
                                         item.amount !== 0;
                  return hasNonZeroAmount;
                }

                // Normal (read-only) mode filter logic
                // Special case: INK_sarskild_loneskatt overrides all normal logic
                if (item.variable_name === 'INK_sarskild_loneskatt') {
                  const pensionPremier = companyData.pensionPremier || 0;
                  const calculated = companyData.sarskildLoneskattPensionCalculated || 0;
                  const actual = companyData.sarskildLoneskattPension || 0;
                  return pensionPremier > 0 && calculated > actual;
                }

                // Check always_show rules first
                if (item.always_show === true) return true;
                if (item.always_show === false) return false;

                if (item.header === true) {
                  return shouldShowBlockContent(item.block);
                }

                // For non-headers with always_show = null/undefined, show only if amount is non-zero
                const hasNonZeroAmount = item.amount !== null && item.amount !== undefined && 
                                       item.amount !== 0;
                
                return hasNonZeroAmount;
              });
              
              // Debug logging
              console.log('Tax Toggle Debug:', {
                showAllTax,
                totalItems: allData.length,
                filteredItems: filteredData.length,
                sarskildLoneskattCondition: sarskildRow ? {
                  pensionPremier: companyData.pensionPremier || 0,
                  calculated: companyData.sarskildLoneskattPensionCalculated || 0,
                  actual: companyData.sarskildLoneskattPension || 0,
                  pensionPremierCheck: (companyData.pensionPremier || 0) > 0,
                  calculatedGreaterThanActual: (companyData.sarskildLoneskattPensionCalculated || 0) > (companyData.sarskildLoneskattPension || 0),
                  shouldShow: (companyData.pensionPremier || 0) > 0 && (companyData.sarskildLoneskattPensionCalculated || 0) > (companyData.sarskildLoneskattPension || 0),
                  visible: filteredData.includes(sarskildRow)
                } : 'Not found',
                sampleData: allData.slice(0, 3).map(item => ({
                  row_title: item.row_title,
                  variable_name: item.variable_name,
                  amount: item.amount,
                  always_show: item.always_show,
                  toggle_show: item.toggle_show,
                  visible: filteredData.includes(item)
                }))
              });
              
              return filteredData;
            })().map((item, index) => (
              <div
                key={index}
                className={getInkStyleClasses(item.style, item.variable_name).className}
                style={getInkStyleClasses(item.style, item.variable_name).style}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="text-muted-foreground">{item.row_title}</span>
                    {item.explainer && item.explainer.trim() && (
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <button className="w-3.5 h-3.5 rounded-full bg-blue-500 text-white text-xs flex items-center justify-center hover:bg-blue-600 transition-colors">
                              i
                            </button>
                          </TooltipTrigger>
                          <TooltipContent className="max-w-xs">
                            <p className="text-xs font-normal">{item.explainer}</p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    )}
                  </div>
                  {item.show_tag && item.account_details && item.account_details.length > 0 && (
                    <Popover>
                      <PopoverTrigger asChild>
                        <Button variant="outline" size="sm" className="ml-2 h-4 px-1.5 text-xs" style={{fontSize: '0.75rem'}}>
                          VISA
                        </Button>
                      </PopoverTrigger>
                      <PopoverContent className="w-[500px] p-4 bg-white border shadow-lg">
                        <div className="space-y-3">
                          <h4 className="font-medium text-sm">Detaljer för {item.row_title}</h4>
                          <div className="overflow-x-auto">
                            <table className={`w-full text-sm ${item.variable_name === 'INK4.6d' ? 'table-fixed' : ''}`} 
                                   style={item.variable_name === 'INK4.6d' ? {tableLayout: 'fixed'} : {}}>
                              <thead>
                                <tr className="border-b">
                                  <th className={`text-left py-2 ${item.variable_name === 'INK4.6d' ? 'w-16' : ''}`}>Konto</th>
                                  <th className="text-left py-2">{item.variable_name === 'INK4.6d' ? 'Kontotext' : ''}</th>
                                  <th className="text-right py-2">{seFileData?.company_info?.fiscal_year || 'Belopp'}</th>
                                </tr>
                              </thead>
                              <tbody>
                                {item.account_details.map((detail, detailIndex) => (
                                  <tr key={detailIndex} className="border-b">
                                    <td className="py-2">{detail.account_id}</td>
                                    <td className="py-2">{detail.account_text}</td>
                                    <td className="text-right py-2">
                                      {item.variable_name === 'INK4.6d' && detail.tax_rate ? (
                                        /* INK4.6d: Show full calculation in one column */
                                        <span>
                                          {detail.tax_rate} × {new Intl.NumberFormat('sv-SE', {
                                            minimumFractionDigits: 0,
                                            maximumFractionDigits: 0
                                          }).format(Math.abs(detail.balance))} kr = {new Intl.NumberFormat('sv-SE', {
                                            minimumFractionDigits: 0,
                                            maximumFractionDigits: 0
                                          }).format(detail.tax_amount)} kr
                                        </span>
                                      ) : (
                                        /* Standard: Just show amount */
                                        <span>
                                          {new Intl.NumberFormat('sv-SE', {
                                            minimumFractionDigits: 0,
                                            maximumFractionDigits: 0
                                          }).format(Math.abs(detail.balance))} kr
                                        </span>
                                      )}
                                    </td>
                                  </tr>
                                ))}
                                {/* Special calculation row for INK4.6a */}
                                {item.variable_name === 'INK4.6a' ? (
                                  <tr className="border-t border-gray-300 font-semibold">
                                    <td className="py-2">Schablonintäkt:</td>
                                    <td className="py-2 text-gray-600">
                                      2,62% × {new Intl.NumberFormat('sv-SE').format(Math.abs(item.account_details.reduce((sum: number, detail: any) => sum + detail.balance, 0)))} =
                                    </td>
                                    <td className="text-right py-2">
                                      {new Intl.NumberFormat('sv-SE', {
                                        minimumFractionDigits: 0,
                                        maximumFractionDigits: 0
                                      }).format(item.amount)} kr
                                    </td>
                                  </tr>
                                ) : item.variable_name === 'INK4.6d' ? (
                                  /* Special calculation for INK4.6d - total row spans multiple columns */
                  <tr className="border-t border-gray-300 font-semibold">
                                    <td className="py-2" colSpan={2}>
                                      Total uppräkning av återfört belopp:
                                    </td>
                                    <td className="text-right py-2">
                                      {new Intl.NumberFormat('sv-SE', {
                                        minimumFractionDigits: 0,
                                        maximumFractionDigits: 0
                                      }).format(item.amount)} kr
                                    </td>
                                  </tr>
                                ) : (
                                  /* Standard sum row for other variables */
                                  <tr className="border-t border-gray-300 font-semibold">
                                    <td className="py-2">Summa</td>
                                    <td className="py-2"></td>
                                    <td className="text-right py-2">
                                      {new Intl.NumberFormat('sv-SE', {
                                        minimumFractionDigits: 0,
                                        maximumFractionDigits: 0
                                      }).format(Math.abs(item.account_details.reduce((sum: number, detail: any) => sum + detail.balance, 0)))} kr
                                    </td>
                                  </tr>
                                )}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      </PopoverContent>
                    </Popover>
                  )}
                  
                  {/* Custom SHOW button for INK_sarskild_loneskatt - only show if there's a discrepancy */}
                  {item.variable_name === 'INK_sarskild_loneskatt' && 
                   companyData.sarskildLoneskattPensionCalculated > companyData.sarskildLoneskattPension && (
                    <Popover>
                      <PopoverTrigger asChild>
                        <Button variant="outline" size="sm" className="ml-2 h-4 px-1.5 text-xs" style={{fontSize: '0.75rem'}}>
                          VISA
                        </Button>
                      </PopoverTrigger>
                      <PopoverContent className="w-[500px] p-4 bg-white border shadow-lg">
                        <div className="space-y-3">
                          <h4 className="font-medium text-sm">{item.row_title}</h4>
                          <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                              <thead>
                                <tr className="border-b">
                                  <th className="text-left py-2">Konto</th>
                                  <th className="text-left py-2"></th>
                                  <th className="text-right py-2">{seFileData?.company_info?.fiscal_year || 'Belopp'}</th>
                                </tr>
                              </thead>
                              <tbody>
                                {/* Account 7410 - Pension premier */}
                                <tr className="border-b">
                                  <td className="py-2">7410</td>
                                  <td className="py-2 text-left">Pensionspremier</td>
                                  <td className="text-right py-2">
                                    {(() => {
                                      const pensionPremier = companyData.pensionPremier || 0;
                                      const formatted = new Intl.NumberFormat('sv-SE', {
                                        minimumFractionDigits: 0,
                                        maximumFractionDigits: 0
                                      }).format(pensionPremier);
                                      return `${formatted} kr`;
                                    })()}
                                  </td>
                                </tr>
                                {/* Sum row with special calculation - merged columns */}
                                <tr className="border-t border-gray-300">
                                  <td className="py-2" colSpan={2}>
                                    Beräknad särskild löneskatt (24,26%)
                                  </td>
                                  <td className="text-right py-2">
                                    {(() => {
                                      const rate = companyData.sarskildLoneskattPensionCalculated || 0;
                                      const formatted = new Intl.NumberFormat('sv-SE', {
                                        minimumFractionDigits: 0,
                                        maximumFractionDigits: 0
                                      }).format(rate);
                                      return `${formatted} kr`;
                                    })()}
                                  </td>
                                </tr>
                                {/* Show booked amount if > 0 */}
                                {companyData.sarskildLoneskattPension > 0 && (
                                  <tr className="border-b">
                                    <td className="py-1" colSpan={2}>
                                      Bokförd särskild löneskatt
                                    </td>
                                    <td className="text-right py-1">
                                      {(() => {
                                        const booked = companyData.sarskildLoneskattPension || 0;
                                        const formatted = new Intl.NumberFormat('sv-SE', {
                                          minimumFractionDigits: 0,
                                          maximumFractionDigits: 0
                                        }).format(booked);
                                        return `${formatted} kr`;
                                      })()}
                                    </td>
                                  </tr>
                                )}
                                {/* Show adjustment calculation only if booked > 0 AND there's a difference */}
                                {companyData.sarskildLoneskattPension > 0 && 
                                 (companyData.sarskildLoneskattPensionCalculated || 0) !== (companyData.sarskildLoneskattPension || 0) && (
                                  <>
                                    <tr className="border-t border-gray-200">
                                      <td className="py-0" colSpan={3}></td>
                                    </tr>
                                    <tr className="font-semibold">
                                      <td className="py-1" colSpan={2}>
                                        Justering särskild löneskatt
                                      </td>
                                      <td className="text-right py-1">
                                        {(() => {
                                          const calculated = companyData.sarskildLoneskattPensionCalculated || 0;
                                          const booked = companyData.sarskildLoneskattPension || 0;
                                          const adjustment = booked - calculated; // Negative value: booked - calculated
                                          const formatted = new Intl.NumberFormat('sv-SE', {
                                            minimumFractionDigits: 0,
                                            maximumFractionDigits: 0
                                          }).format(adjustment);
                                          return `${formatted} kr`;
                                        })()}
                                      </td>
                                    </tr>
                                  </>
                                )}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      </PopoverContent>
                    </Popover>
                  )}
                </div>
                 <span className="text-right font-medium">
                  {item.show_amount === 'NEVER' || item.header ? '' :
                    (canEdit && isEditableCell(item.variable_name) && item.show_amount) ? (
                  <Ink2AmountInput
                        value={manualEdits[item.variable_name] ?? item.amount ?? 0}
                        onChange={(value) => {
                          if (!canEdit || !isEditableCell(item.variable_name)) return;
                          setManualEdits(prev => ({ ...prev, [item.variable_name]: value }));
                        }}
                        onCommit={(value) => {
                          if (!canEdit || !isEditableCell(item.variable_name)) return;
                          setManualEdits(prev => {
                            const updated = { ...prev, [item.variable_name]: value };
                            // Recalc with Chat + Accepted + current session edits
                            const manuals = { ...getChatOverrides(), ...acceptedManuals, ...updated };
                            recalcWithManuals(updated); // Pass session edits, use defaults (includeAccepted: true, baselineSource: 'current')
                            return updated;
                          });
                        }}
                        variableName={item.variable_name}
                      />
                    ) : (
                      (item.amount !== null && item.amount !== undefined) ? 
                      (item.amount === 0 ? '0 kr' : (() => {
                      // Tax calculation should always show integers with Swedish formatting and kr suffix
                      return new Intl.NumberFormat('sv-SE', {
                        minimumFractionDigits: 0,
                        maximumFractionDigits: 0
                      }).format(item.amount) + ' kr';
                      })()) : '0 kr'
                    )
                  }
                </span>
              </div>
            ))}
            
            {/* Tax Action Buttons */}
            {canEdit && (
              <div className="pt-4 border-t border-gray-200 flex justify-between">
                {/* Undo Button - Left */}
                <Button 
                  onClick={handleUndo}
                  variant="outline"
                  className="flex items-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"/>
                  </svg>
                  Ångra ändringar
                </Button>
                
                {/* Update Button - Right */}
                <Button 
                  onClick={handleApproveChanges}
                  className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 flex items-center gap-2"
                >
                  Godkänn och uppdatera skatt
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 10h-10a8 8 0 00-8 8v2M21 10l-6 6m6-6l-6-6"/>
                  </svg>
                </Button>
              </div>
            )}
          </div>
        )}

        {/* Periodiseringsfonder Section */}
        <Periodiseringsfonder 
          companyData={companyData}
          onDataUpdate={onDataUpdate}
        />

        {/* Noter Section */}
        {companyData.noterData && companyData.noterData.length > 0 && (
          <div data-section="noter">
            <Noter 
              noterData={companyData.noterData}
              fiscalYear={companyData.fiscalYear}
              previousYear={companyData.fiscalYear ? companyData.fiscalYear - 1 : undefined}
              companyData={{
                ...companyData,
                currentPeriodEndDate: getCurrentPeriodEndDate(),
                previousPeriodEndDate: getPreviousPeriodEndDate()
              }}
              onDataUpdate={onDataUpdate}
            />
          </div>
        )}

        {/* Förvaltningsberättelse Section */}
        <div data-section="forvaltningsberattelse">
          <ManagementReportModule 
            companyData={companyData}
            onDataUpdate={onDataUpdate}
          />
        </div>

        {/* Download Section - Show at step 510+ (stays visible even when navigating to Signering) */}
        {(() => {
          console.log('🔍 Download render check:', { currentStep, shouldShow: currentStep >= 510 });
          return currentStep >= 510 && (
            <div data-section="download">
              <Download 
                companyData={companyData}
              />
            </div>
          );
        })()}

        {/* Signering Section - Only show at step 515+ */}
        {currentStep >= 515 && (
          <div data-section="signering">
            <Signering 
              signeringData={companyData.signeringData}
              onDataUpdate={onDataUpdate}
              companyData={companyData}
            />
          </div>
        )}

        {/* Payment Section Anchor - Stripe embedded checkout will be portaled here */}
        <section id="payment-section-anchor" className="mt-8">
          {/* Stripe embedded checkout will be portaled here */}
        </section>

        {/* REMOVED: Väsentliga händelser, Avskrivningsprinciper, Personal, Styrelse sections per user request */}
      </div>
    );
  };

  return (
    <div className="h-full flex flex-col">
      <Card className="flex-1 p-6 bg-card border-border">
        <div className="overflow-y-auto max-h-full">
          {getPreviewContent()}
          {/* Extra padding to ensure last row is visible */}
          <div className="h-20"></div>
        </div>
      </Card>
    </div>
  );
}
