'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Table, TableHeader, TableHead, TableRow, TableBody, TableCell } from "@/components/ui/table";
import { calculateRRSums, extractKeyMetrics, formatAmount, type SEData } from '@/utils/seFileCalculations';
import { apiService } from '@/services/api';
import { Periodiseringsfonder } from './Periodiseringsfonder';
import { Noter } from './Noter';
import { Forvaltningsberattelse } from './Forvaltningsberattelse';

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
        {/* H2 Verksamheten */}
        <section id="verksamheten" className="mt-6">
          <h2 className="text-xl font-semibold mb-2">Verksamheten</h2>

          <h3 className="text-base font-semibold mb-1 pt-1">Allmänt om verksamheten</h3>
          <p className="text-sm">{verksamhetContent}</p>

          <h3 className="text-base font-semibold mt-4 pt-3">Väsentliga händelser under räkenskapsåret</h3>
          <p className="text-sm font-normal not-italic">Inga väsentliga händelser under året.</p>
        </section>

        {/* H2 Flerårsöversikt */}
        <section id="flerars" className="mt-8 pt-5">
          <h2 className="text-xl font-semibold">Flerårsöversikt</h2>
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
                  { label: "Omsättning",                        values: [oms1, oms2, oms3] },
                  { label: "Resultat efter finansiella poster", values: [ref1, ref2, ref3] },
                  { label: "Balansomslutning",                  values: [bal1, bal2, bal3] },
                  { label: "Soliditet",                         values: [sol1, sol2, sol3] },
                ]
              ) : (
                // Use calculated fiscal year + scraped data (4 years)
                [
                  { label: "Omsättning",                        values: [nettoOmsFY_tkr, oms1, oms2, oms3] },
                  { label: "Resultat efter finansiella poster", values: [refpFY_tkr, ref1, ref2, ref3] },
                  { label: "Balansomslutning",                  values: [tillgFY_tkr, bal1, bal2, bal3] },
                  { label: "Soliditet",                         values: [soliditetFY, sol1, sol2, sol3] },
                ]
              )).map((row, i) => (
                <TableRow key={i} className="h-8">
                  <TableCell className="p-0 text-left font-normal">{row.label}</TableCell>
                  {row.values.map((v, j) => (
                    <TableCell key={j} className="p-0 text-right">
                      {row.label === "Soliditet" ? 
                        `${Math.round(v ?? 0).toLocaleString('sv-SE', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}%` : 
                        formatAmount(v ?? 0)
                      }
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </section>

        {/* H2 Förändringar i eget kapital — existing, working table, embedded */}
        <section id="eget-kapital" className="mt-8 pt-5">
          <Forvaltningsberattelse
            embedded
            fbTable={companyData.fbTable || []}
            fbVariables={companyData.fbVariables || {}}
            fiscalYear={fy}
            onDataUpdate={onDataUpdate}
          />
        </section>

        {/* (Ignore Resultatdisposition for now as requested) */}
      </CardContent>
    </Card>
  );
}

// INK2 AmountCell component (defined outside to avoid initialization issues)
const Ink2AmountCell = React.memo(function Ink2AmountCell({
  variableName,
  value,
  editable,
  onCommit,
  onTabNavigate,
  formatAmountDisplay
}: {
  variableName: string;
  value: number;
  editable: boolean;
  onCommit: (value: number) => void;
  onTabNavigate?: (direction: 'next' | 'prev') => void;
  formatAmountDisplay: (amount: number | null) => string;
}) {
  const [focused, setFocused] = useState(false);
  const [local, setLocal] = useState<string>("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!focused) setLocal(value ? String(Math.round(value)) : "");
  }, [value, focused]);

  if (!editable) {
    return (
      <span className={`text-right font-medium ${value === 0 ? 'opacity-50 text-gray-500' : ''}`}>
        {formatAmountDisplay(value)}
      </span>
    );
  }

  const shown = focused
    ? local
    : (local ? new Intl.NumberFormat('sv-SE').format(parseInt(local.replace(/[^\d-]/g, "") || "0", 10)) : "");

  const commit = () => {
    const raw = (local || "0").replace(/[^\d-]/g, "");
    let parsed = parseInt(raw || "0", 10);
    if (!Number.isFinite(parsed)) parsed = 0;
    onCommit(parsed);
  };

  return (
    <input
      ref={inputRef}
      type="text"
      data-variable={variableName}
      className={`w-full max-w-[108px] px-1 py-0.5 text-sm border border-gray-300 rounded text-right font-normal h-6 focus:border-gray-400 focus:outline-none ${
        value === 0 ? 'bg-gray-50 opacity-70' : 'bg-white'
      }`}
      value={shown}
      onFocus={() => { setFocused(true); setLocal(value ? String(Math.round(value)) : ""); }}
      onChange={(e) => {
        const raw = e.target.value.replace(/[^\d-]/g, "");
        setLocal(raw);
      }}
      onBlur={() => { setFocused(false); commit(); }}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          e.currentTarget.blur();
          commit();
        } else if (e.key === "Tab") {
          e.preventDefault();
          setFocused(false);
          commit();
          // Move to next/previous cell
          setTimeout(() => onTabNavigate?.(e.shiftKey ? 'prev' : 'next'), 50);
        }
      }}
      placeholder="0"
    />
  );
});

// Database-driven always_show logic - no more hardcoded arrays

export function AnnualReportPreview({ companyData, currentStep, editableAmounts = false, onDataUpdate }: AnnualReportPreviewProps) {
  // Safe access; never destructure undefined
  const cd = companyData as CompanyData;
  
  // Requirement 2: inputs become editable when taxEditingEnabled OR editableAmounts is true OR manual edit button is clicked
  const isEditing = Boolean(cd.taxEditingEnabled || editableAmounts);
  const isInk2EditingActive = isInk2Editing || isEditing;

  // Requirement 1: render when showTaxPreview OR showRRBR is true
  if (!cd.showTaxPreview && !cd.showRRBR) {
    return null;
  }
  
  const [showAllRR, setShowAllRR] = useState(false);
  const [showAllBR, setShowAllBR] = useState(false);
  const [showAllTax, setShowAllTax] = useState(false);
  const [isInk2Editing, setIsInk2Editing] = useState(false);
  const [ink2EditedAmounts, setInk2EditedAmounts] = useState<Record<string, number>>({});

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
  useEffect(() => {
    const loadDataWithNotes = async () => {
      if (brData.length > 0 || rrData.length > 0) {
        try {
          // Calculate dynamic note numbers based on Noter visibility
          const dynamicNoteNumbers = calculateDynamicNoteNumbers();
          console.log('Dynamic note numbers for BR/RR:', dynamicNoteNumbers);
          console.log('Sending to API - BR data length:', brData.length);
          console.log('Sending to API - RR data length:', rrData.length);
          console.log('RR data sample:', rrData.slice(0, 3));
          
          const response = await apiService.addNoteNumbersToBr({ 
            br_data: brData,
            rr_data: rrData,
            note_numbers: dynamicNoteNumbers
          });
          if (response.success) {
            console.log('API Response - BR data length:', response.br_data?.length || 0);
            console.log('API Response - RR data length:', response.rr_data?.length || 0);
            console.log('API Response - RR data sample with notes:', response.rr_data?.slice(0, 5));
            setBrDataWithNotes(response.br_data || brData);
            setRrDataWithNotes(response.rr_data || rrData);
          } else {
            // Fallback to original data if API fails
            setBrDataWithNotes(brData);
            setRrDataWithNotes(rrData);
          }
        } catch (error) {
          console.error('Error loading financial data with note numbers:', error);
          // Fallback to original data if API fails
          setBrDataWithNotes(brData);
          setRrDataWithNotes(rrData);
        }
      } else {
        setBrDataWithNotes([]);
        setRrDataWithNotes([]);
      }
    };

    loadDataWithNotes();
  }, [brData, rrData, cd.noterData]);

  // Capture original amounts when isEditing becomes true (for undo functionality)
  useEffect(() => {
    if (isEditing && Object.keys(originalAmounts).length === 0) {
      const currentData = recalculatedData.length > 0 ? recalculatedData : ink2Data;
      const amounts: Record<string, number> = {};
      currentData.forEach((item: any) => {
        if ((!item.is_calculated || item.variable_name === 'INK_sarskild_loneskatt') && item.show_amount) {
          amounts[item.variable_name] = item.amount || 0;
        }
      });
      setOriginalAmounts(amounts);
    }
  }, [isEditing, ink2Data, recalculatedData, originalAmounts]);



  // Undo all changes
  const handleUndo = async () => {
    setEditedAmounts(originalAmounts);
    await recalculateValues(originalAmounts);
  };

  // Recalculate dependent values when amounts change
  const recalculateValues = async (updatedAmounts: Record<string, number>) => {
    try {
      console.log('Recalculating with amounts:', updatedAmounts);
      
      // Handle pension tax field mapping and preserve existing values
      const preservedAmounts = { ...updatedAmounts };
      
      // Preserve INK4.14a (unused tax loss) if it exists and not being manually edited
      if (companyData.unusedTaxLossAmount && !('INK4.14a' in updatedAmounts)) {
        preservedAmounts['INK4.14a'] = companyData.unusedTaxLossAmount;
        console.log('Preserving existing INK4.14a (unused tax loss):', companyData.unusedTaxLossAmount);
      }
      
      // If user edited INK_sarskild_loneskatt, convert it to justering_sarskild_loneskatt for backend
      if ('INK_sarskild_loneskatt' in updatedAmounts) {
        // Frontend stores positive value, backend expects justering_sarskild_loneskatt (positive = increase, negative = decrease)
        preservedAmounts.justering_sarskild_loneskatt = updatedAmounts.INK_sarskild_loneskatt;
        delete preservedAmounts.INK_sarskild_loneskatt; // Remove the INK version
        console.log('Converting INK_sarskild_loneskatt to justering_sarskild_loneskatt:', preservedAmounts.justering_sarskild_loneskatt);
      } else if (typeof companyData.justeringSarskildLoneskatt === 'number' && companyData.justeringSarskildLoneskatt !== 0) {
        // Preserve existing numeric value if not being edited
        preservedAmounts.justering_sarskild_loneskatt = companyData.justeringSarskildLoneskatt;
        console.log('Preserving existing justering_sarskild_loneskatt:', companyData.justeringSarskildLoneskatt);
      } else {
        // Check if there's an existing INK_sarskild_loneskatt value in the current ink2_data that needs to be preserved
        const currentData = recalculatedData.length > 0 ? recalculatedData : ink2Data;
        const existingSarskildRow = currentData.find((item: any) => item.variable_name === 'INK_sarskild_loneskatt');
        if (existingSarskildRow && existingSarskildRow.amount && existingSarskildRow.amount !== 0) {
          // Preserve the existing value by converting it to justering_sarskild_loneskatt
          preservedAmounts.justering_sarskild_loneskatt = existingSarskildRow.amount;
          console.log('Preserving existing INK_sarskild_loneskatt from ink2_data:', existingSarskildRow.amount);
        }
      }
      
      // Call backend API to recalculate INK2 values using API service
      const result = await apiService.recalculateInk2({
        current_accounts: seFileData?.current_accounts || {},
        fiscal_year: seFileData?.company_info?.fiscal_year,
        rr_data: seFileData?.rr_data || [],
        br_data: seFileData?.br_data || [],
        manual_amounts: preservedAmounts
      });
      
      if (result.success) {
        // Update the seFileData with new calculated values
        if (companyData.seFileData) {
          companyData.seFileData.ink2_data = result.ink2_data;
          // Force re-render by updating the state
          setRecalculatedData(result.ink2_data);
        }
        console.log('Successfully recalculated INK2 values');
      } else {
        console.error('Failed to recalculate: API returned success=false');
      }
    } catch (error) {
      console.error('Error recalculating values:', error);
    }
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
    const baseClasses = 'grid gap-4';
    let additionalClasses = '';

    // Support legacy and T-styles (TH1/TH2/TH3/TS1/TS2/TS3/TNORMAL)
    const s = style || '';
    
    // Bold styles - TNORMAL should NOT be bold
    const boldStyles = ['H0','H1','H2','H3','S1','S2','S3','TH0','TH1','TH2','TH3','TS1','TS2','TS3'];
    // Special case: Apply bold styling to specific variable names
    const specialBoldVariables = ['INK_skattemassigt_resultat'];
    if (boldStyles.includes(s) || (variableName && specialBoldVariables.includes(variableName))) {
      additionalClasses += ' font-semibold';
    }
    
    // Line styles - only S2/S3/TS2/TS3 get darker lines
    const lineStyles = ['S2','S3','TS2','TS3'];
    // Special case: Apply line styling to specific variable names
    const specialLineVariables = ['INK_skattemassigt_resultat'];
    if (lineStyles.includes(s) || (variableName && specialLineVariables.includes(variableName))) {
      additionalClasses += ' border-t border-b border-gray-300 pt-1 pb-1';
    }

    // Indentation for TNORMAL only
    const indentStyles = ['TNORMAL'];
    const indentation = indentStyles.includes(s) ? ' pl-6' : '';

    return {
      className: `${baseClasses}${additionalClasses}${indentation}`,
      style: { gridTemplateColumns: '3fr 1fr' }
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

  // INK2 Edit mode functions
  const startInk2Edit = () => {
    setIsInk2Editing(true);
    setShowAllTax(true); // Show all rows for editing
  };

  const cancelInk2Edit = () => {
    setIsInk2Editing(false);
    setInk2EditedAmounts({});
    setShowAllTax(false); // Hide extra rows
  };

  // Auto-recalculate when manual amounts change (mirroring Noter pattern)
  const handleInk2AmountChange = async (variableName: string, value: number) => {
    const newEditedAmounts = {
      ...ink2EditedAmounts,
      [variableName]: value
    };
    
    setInk2EditedAmounts(newEditedAmounts);
    
    // Trigger immediate recalculation (like Noter does)
    try {
      const result = await apiService.recalculateInk2({
        current_accounts: companyData.seFileData.current_accounts || {},
        fiscal_year: companyData.fiscalYear,
        rr_data: companyData.seFileData.rr_data || [],
        br_data: companyData.seFileData.br_data || [],
        manual_amounts: newEditedAmounts,
        // Preserve chat-inserted values
        justering_sarskild_loneskatt: companyData.justeringSarskildLoneskatt || 0,
        ink4_14a_outnyttjat_underskott: companyData.unusedTaxLossAmount || 0,
        ink4_16_underskott_adjustment: companyData.ink4_16_underskott_adjustment || 0
      });
      
      if (result.success) {
        setRecalculatedData(result.ink2_data);
      }
    } catch (error) {
      console.error('Error recalculating INK2:', error);
    }
  };

  // Apply final changes and exit edit mode (called by "Godkänn ändringar")
  const applyInk2Changes = async () => {
    try {
      // Use the most recent recalculated data
      if (recalculatedData.length > 0) {
        onDataUpdate({ ink2Data: recalculatedData });
      }
      
      setIsInk2Editing(false);
      setInk2EditedAmounts({});
      setShowAllTax(false);
    } catch (error) {
      console.error('Error applying INK2 changes:', error);
    }
  };

  // Undo function - preserve chat values, clear manual edits
  const undoInk2Changes = () => {
    // Clear only manual edits, preserve chat-inserted values
    const preservedValues: Record<string, number> = {};
    
    // Preserve specific chat-inserted values
    if (companyData.justeringSarskildLoneskatt) {
      preservedValues['justering_sarskild_loneskatt'] = companyData.justeringSarskildLoneskatt;
    }
    if (companyData.unusedTaxLossAmount) {
      preservedValues['INK4.14a'] = companyData.unusedTaxLossAmount;
    }
    if (companyData.ink4_16_underskott_adjustment) {
      preservedValues['ink4_16_underskott_adjustment'] = companyData.ink4_16_underskott_adjustment;
    }
    
    setInk2EditedAmounts(preservedValues);
    setRecalculatedData([]); // Reset to original data
  };

  // Tab navigation for INK2 cells
  const handleTabNavigation = (currentVariable: string, direction: 'next' | 'prev') => {
    // Get all editable variables in order
    const allData = recalculatedData.length > 0 ? recalculatedData : ink2Data;
    const editableVariables = allData
      .filter(item => !item.header && (!item.is_calculated || item.variable_name === 'INK_sarskild_loneskatt') && item.show_amount)
      .map(item => item.variable_name);
    
    const currentIndex = editableVariables.indexOf(currentVariable);
    if (currentIndex === -1) return;
    
    const nextIndex = direction === 'next' 
      ? (currentIndex + 1) % editableVariables.length
      : (currentIndex - 1 + editableVariables.length) % editableVariables.length;
    
    const nextVariable = editableVariables[nextIndex];
    
    // Focus the next input
    setTimeout(() => {
      const nextInput = document.querySelector(`input[data-variable="${nextVariable}"]`) as HTMLInputElement;
      if (nextInput) {
        nextInput.focus();
      }
    }, 10);
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
              (rrDataWithNotes.length > 0 ? rrDataWithNotes : rrData).map((item, index) => {
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
                    <span className="text-muted-foreground">{item.label}</span>
                    <span className="text-right font-medium">
                      {getNoteValue(item.label)}
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
              <span className="text-right">{headerData.fiscal_year}</span>
              <span className="text-right">{headerData.fiscal_year - 1}</span>
            </div>

            {/* Balance Sheet Rows */}
            {brDataWithNotes.length > 0 ? (
              brDataWithNotes.map((item, index) => {
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
            )}
          </div>
        )}

        {/* Tax Calculation Section */}
        {companyData.showTaxPreview && ink2Data && ink2Data.length > 0 && (
          <div className="space-y-4 bg-gradient-to-r from-yellow-50 to-amber-50 p-4 rounded-lg border border-yellow-200" data-section="tax-calculation">
            <div className="mb-4">
              <div className="flex items-center justify-between border-b pb-2">
                <div className="flex items-center gap-3">
                  <h2 className="text-lg font-semibold text-foreground">Skatteberäkning</h2>
                  <button
                    onClick={() => isInk2Editing ? cancelInk2Edit() : startInk2Edit()}
                    className={`w-6 h-6 rounded-full flex items-center justify-center transition-colors ${
                      isInk2Editing 
                        ? 'bg-blue-600 text-white' 
                        : 'bg-gray-200 hover:bg-gray-300 text-gray-600'
                    }`}
                    title={isInk2Editing ? 'Avsluta redigering' : 'Redigera värden'}
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
                if (isInk2EditingActive) {
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
                  
                  // For always_show = null/undefined, show if amount is non-zero OR has been manually edited
                  const hasNonZeroAmount = item.amount !== null && item.amount !== undefined && 
                                         item.amount !== 0;
                  const hasBeenEdited = ink2EditedAmounts.hasOwnProperty(item.variable_name);
                  return hasNonZeroAmount || hasBeenEdited;
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

                // For non-headers with always_show = null/undefined, show if amount is non-zero OR has been manually edited
                const hasNonZeroAmount = item.amount !== null && item.amount !== undefined && 
                                       item.amount !== 0;
                const hasBeenEdited = ink2EditedAmounts.hasOwnProperty(item.variable_name);
                
                return hasNonZeroAmount || hasBeenEdited;
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
                            <button className="w-4 h-4 rounded-full bg-blue-500 text-white text-xs flex items-center justify-center hover:bg-blue-600 transition-colors">
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
                        <Button variant="outline" size="sm" className="ml-2 h-5 px-2 text-xs">
                          SHOW
                        </Button>
                      </PopoverTrigger>
                      <PopoverContent className="w-[500px] p-4 bg-white border shadow-lg">
                        <div className="space-y-3">
                          <h4 className="font-medium text-sm">Detaljer för {item.row_title}</h4>
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
                                {item.account_details.map((detail, detailIndex) => (
                                  <tr key={detailIndex} className="border-b">
                                    <td className="py-2">{detail.account_id}</td>
                                    <td className="py-2">{detail.account_text}</td>
                                    <td className="text-right py-2">
                                      {new Intl.NumberFormat('sv-SE', {
                                        minimumFractionDigits: 0,
                                        maximumFractionDigits: 0
                                      }).format(detail.balance)} kr
                                    </td>
                                  </tr>
                                ))}
                                {/* Sum row */}
                                <tr className="border-t border-gray-300 font-semibold">
                                  <td className="py-2">Summa</td>
                                  <td className="py-2"></td>
                                  <td className="text-right py-2">
                                    {new Intl.NumberFormat('sv-SE', {
                                      minimumFractionDigits: 0,
                                      maximumFractionDigits: 0
                                    }).format(item.account_details.reduce((sum: number, detail: any) => sum + detail.balance, 0))} kr
                                  </td>
                                </tr>
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
                        <Button variant="outline" size="sm" className="ml-2 h-5 px-2 text-xs">
                          SHOW
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
                                    Särskild löneskatt (24,26%)
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
                              </tbody>
                            </table>
                          </div>
                        </div>
                      </PopoverContent>
                    </Popover>
                  )}
                </div>
                 <span className="text-right font-medium">
                  {item.show_amount === 'NEVER' || item.header ? '' : (() => {
                    // Determine if this field should be editable
                    const shouldBeEditable = isInk2EditingActive && (!item.is_calculated || item.variable_name === 'INK_sarskild_loneskatt') && item.show_amount;
                    
                    // Get current value (use recalculated data if available, then edited values, then original)
                    const allData = recalculatedData.length > 0 ? recalculatedData : ink2Data;
                    const dataItem = allData.find(d => d.variable_name === item.variable_name);
                    const currentValue = dataItem?.amount ?? item.amount ?? 0;
                    
                    return (
                      <Ink2AmountCell
                        variableName={item.variable_name}
                        value={currentValue}
                        editable={shouldBeEditable}
                        onCommit={(value) => handleInk2AmountChange(item.variable_name, value)}
                        onTabNavigate={(direction) => handleTabNavigation(item.variable_name, direction)}
                        formatAmountDisplay={formatAmountDisplay}
                      />
                    );
                  })()}
                </span>
              </div>
            ))}
            
            {/* Tax Action Buttons */}
            {isInk2EditingActive && (
              <div className="pt-4 border-t border-gray-200 flex justify-between">
                {/* Undo Button - Left */}
                <Button 
                  onClick={undoInk2Changes}
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
                  onClick={applyInk2Changes}
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
          <Noter 
            noterData={companyData.noterData}
            fiscalYear={companyData.fiscalYear}
            previousYear={companyData.fiscalYear ? companyData.fiscalYear - 1 : undefined}
            companyData={companyData}
          />
        )}

        {/* Förvaltningsberättelse Section */}
        <ManagementReportModule 
          companyData={companyData}
          onDataUpdate={onDataUpdate}
        />

        {/* Significant Events Section */}
        {currentStep >= 2 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-foreground border-b pb-2">Väsentliga händelser</h2>
            <div className="text-sm text-muted-foreground space-y-2">
              {seFileData?.significant_events ? (
                seFileData.significant_events.map((event, index) => (
                  <p key={index}>• {event}</p>
                ))
              ) : (
                <p>{companyData.significantEvents || "Inga väsentliga händelser att rapportera."}</p>
              )}
            </div>
          </div>
        )}

        {/* Depreciation Policy */}
        {currentStep >= 3 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-foreground border-b pb-2">Avskrivningsprinciper</h2>
            <p className="text-sm text-muted-foreground">
              {seFileData?.depreciation_policy || 
               (companyData.depreciation === "samma" 
                 ? "Samma avskrivningstider som föregående år tillämpas."
                 : "Förändrade avskrivningstider tillämpas detta år."
               )
              }
            </p>
          </div>
        )}

        {/* Employee Information */}
        {currentStep >= 4 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-foreground border-b pb-2">Personal</h2>
            <p className="text-sm text-muted-foreground">
              {seFileData?.employees?.description || 
               `Antal anställda under räkenskapsåret: ${seFileData?.employees?.count || companyData.employees}`
              }
            </p>
          </div>
        )}

        {/* Board Members */}
        {currentStep >= 5 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-foreground border-b pb-2">Styrelse</h2>
            <div className="space-y-2">
              {seFileData?.board_members ? (
                seFileData.board_members.map((member, index) => (
                  <div key={index} className="text-sm">
                    <span className="font-medium">{member.name}</span>
                    <span className="text-muted-foreground ml-2">({member.role})</span>
                  </div>
                ))
              ) : (
                companyData.boardMembers.map((member, index) => (
                  <div key={index} className="text-sm">
                    <span className="font-medium">{member.name}</span>
                    <span className="text-muted-foreground ml-2">({member.personalNumber})</span>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
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
