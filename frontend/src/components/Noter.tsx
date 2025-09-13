import React, { useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Switch } from '@/components/ui/switch';
import { Pencil, Check, X } from 'lucide-react';

interface NoterItem {
  row_id: number;
  row_title: string;
  current_amount: number | null;
  previous_amount: number | null;
  variable_name?: string;
  show_tag?: boolean;
  accounts_included?: string;
  account_details?: Array<{
    account_id: string;
    account_text: string;
    balance: number;
  }>;
  block: string;
  always_show?: boolean;
  toggle_show?: boolean;
  style?: string;
  variable_text?: string;
}

// Helper functions for Swedish number formatting
// Create formatters once (do NOT create new Intl.NumberFormat in each render)
const fmt0 = new Intl.NumberFormat('sv-SE', { maximumFractionDigits: 0 });

const svToNumber = (raw: string): number => {
  if (!raw) return 0;
  const s = raw.replace(/\s/g, "").replace(/\./g, "").replace(/,/g, ".");
  const n = Number(s);
  return Number.isFinite(n) ? n : 0;
};

// Use memoized formatter everywhere
const numberToSv = (n: number): string => {
  if (!Number.isFinite(n)) return "";
  const sign = n < 0 ? "-" : "";
  const abs = Math.abs(n);
  return sign + fmt0.format(abs);
};

const formatSvInt = (n: number): string => fmt0.format(Math.round(n));

const isHeadingStyle = (s?: string) => ["H0", "H1", "H2", "H3"].includes(s || "NORMAL");

// AccountDetailsDialog component (moved to module scope for shared access)
const AccountDetailsDialog = ({ item }: { item: NoterItem }) => {
  const [selectedItem, setSelectedItem] = useState<NoterItem | null>(null);
  
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Badge 
          variant="secondary" 
          className="ml-2 cursor-pointer hover:bg-gray-200 text-xs"
          onClick={() => setSelectedItem(item)}
        >
          SHOW
        </Badge>
      </DialogTrigger>
      <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Kontouppgifter - {item.row_title}</DialogTitle>
        </DialogHeader>
        <div className="mt-4">
          {item.account_details && item.account_details.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Konto</TableHead>
                  <TableHead>Kontotext</TableHead>
                  <TableHead className="text-right">Saldo</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {item.account_details.map((detail, index) => (
                  <TableRow key={index}>
                    <TableCell className="font-mono">{detail.account_id}</TableCell>
                    <TableCell>{detail.account_text}</TableCell>
                    <TableCell className="text-right font-mono">
                      {new Intl.NumberFormat('sv-SE', {
                        minimumFractionDigits: 0,
                        maximumFractionDigits: 0,
                      }).format(detail.balance)} kr
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-muted-foreground">Inga kontouppgifter tillgängliga.</p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

// Inventarier editor component
const InventarierNote: React.FC<{
  items: NoterItem[];
  heading: string;
  fiscalYear?: number;
  previousYear?: number;
  companyData?: any;
  toggleOn: boolean;
  setToggle: (checked: boolean) => void;
}> = ({ items, heading, fiscalYear, previousYear, companyData, toggleOn, setToggle }) => {
  // Keep original table look-and-feel (same grid as other notes)
  const gridCols = { gridTemplateColumns: "4fr 1fr 1fr" };

  // --- Editable set: only FLOW variables (not IB/UB or redovisat värde) ---
  const isFlowVar = (vn?: string) => {
    if (!vn) return false;
    // forbid IB, UB, and redovisat värde variables
    if (/_ib\b/i.test(vn)) return false;
    if (/_ub\b/i.test(vn)) return false;
    if (/red[_-]?varde/i.test(vn)) return false;
    return true; // everything else is a flow and editable
  };

  // Index rows by variable_name for quick lookups
  const byVar = useMemo(() => {
    const m = new Map<string, NoterItem>();
    items.forEach((it) => it.variable_name && m.set(it.variable_name, it));
    return m;
  }, [items]);

  // Identify core rows used for calculated UB/book value comparison
  const get = (v: string) => byVar.get(v)?.current_amount ?? 0;

  // BR book value: First try BR data, else note's own "red_varde_inventarier"
  const brBookValueUB = useMemo(() => {
    const brData: any[] = companyData?.seFileData?.br_data || [];
    // Heuristics to find the BR line for Inventarier, verktyg och installationer
    const candidates = [
      "InventarierVerktygInstallationer",
      "Inventarier",
      "InventarierVerktygInst",
    ];
    let found = 0;
    for (const c of candidates) {
      const hit = brData.find((x: any) => x.variable_name === c);
      if (hit && Number.isFinite(hit.current_amount)) {
        found = hit.current_amount;
        break;
      }
    }
    if (!found) {
      // Fallback to the note's own computed red_varde_inventarier
      const noteRed = byVar.get("red_varde_inventarier")?.current_amount ?? 0;
      return noteRed;
    }
    return found;
  }, [companyData, byVar]);

  // Local edit state (simplified to match FB)
  const [isEditing, setIsEditing] = useState(false);
  const [editedValues, setEditedValues] = useState<Record<string, number>>({});
  const [editedPrevValues, setEditedPrevValues] = useState<Record<string, number>>({});
  const [mismatch, setMismatch] = useState<{ open: boolean; delta: number }>({ open: false, delta: 0 });
  const [showValidationMessage, setShowValidationMessage] = useState(false);

  // Helper functions (matching FB implementation exactly) - using memoized formatter

  const cleanDigits = (s: string) => (s || '')
    .replace(/\s| |\u00A0|\u202F|,/g, '') // vanliga + NBSP + smalt mellanslag + komma
    .trim();

  const allowDraft = (s: string) => /^-?\d*$/.test(s);        // integers only

  const parseDraft = (s: string): number => {
    if (!s) return 0;
    const cleaned = cleanDigits(s);
    const v = parseInt(cleaned, 10);
    return Number.isNaN(v) ? 0 : v;
  };

  // Helper function to get current value (edited or original) - matching FB
  const getCurrentValue = (variableName: string): number => {
    if (editedValues[variableName] !== undefined) {
      return editedValues[variableName];
    }
    const item = byVar.get(variableName);
    return item?.current_amount ?? 0;
  };


  // Read current/prev amount, considering edits
  const readCur = (it: NoterItem) => getCurrentValue(it.variable_name!);
  const readPrev = (it: NoterItem) => 
    editedPrevValues[it.variable_name!] ?? (it.previous_amount ?? 0);

  // Build visible rows using the same logic as main Noter component
  const visible = useMemo(() => {
    return items.filter((it) => {
      // Headings and rows explicitly always_show=true are always visible
      if (it.always_show) return true;

      const hasNonZero =
        (readCur(it) ?? 0) !== 0 ||
        (readPrev(it) ?? 0) !== 0;

      if (hasNonZero) return true;

      // zero amounts:
      // show only if row is toggleable and the block toggle is ON
      if (it.toggle_show) return toggleOn;

      // zero + not toggleable => never show
      return false;
    });
  }, [items, toggleOn, editedValues]);

  // Compute Redovisat värde (beräknat) from IB + flows -> UB, then red.värde = UB + ack.*
  const calcRedovisatVarde = () => {
    // Safe reads with edited values included
    const v = (name: string) => getCurrentValue(name);

    const ibInv = v("inventarier_ib");
    const ibAvskr = v("ack_avskr_inventarier_ib");
    const ibNedskr = v("ack_nedskr_inventarier_ib");

    const aretsInkop = v("arets_inkop_inventarier");
    const aretsFsg = v("arets_fsg_inventarier");
    const aretsOmklass = v("arets_omklass_inventarier");

    const aretsAvskr = v("arets_avskr_inventarier");
    const aterforAvskrFsg = v("aterfor_avskr_fsg_inventarier");

    const aretsNedskr = v("arets_nedskr_inventarier");
    const aterforNedskr = v("aterfor_nedskr_inventarier");
    const aterforNedskrFsg = v("aterfor_nedskr_fsg_inventarier");

    const invUB = ibInv + aretsInkop - aretsFsg + aretsOmklass;
    const ackAvskrUB = ibAvskr + aterforAvskrFsg - aretsAvskr;
    const ackNedskrUB = ibNedskr + aterforNedskrFsg + aterforNedskr - aretsNedskr;

    return invUB + ackAvskrUB + ackNedskrUB;
  };

  const startEdit = () => {
    setIsEditing(true);
  };

  // Auto-hide validation message after 5 seconds
  React.useEffect(() => {
    if (showValidationMessage) {
      const timer = setTimeout(() => {
        setShowValidationMessage(false);
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [showValidationMessage]);

  const cancelEdit = () => {
    setIsEditing(false);
    setEditedValues({});
    setEditedPrevValues({});  // clear previous year edits
    setMismatch({ open: false, delta: 0 });
    setShowValidationMessage(false);
  };

  const approveEdit = () => {
    // run balance check
    const beraknad = calcRedovisatVarde();
    const delta = Math.round((beraknad - brBookValueUB));
    if (Math.abs(delta) !== 0) {
      setMismatch({ open: false, delta });// show toast + red
      setShowValidationMessage(true);   // show FB-style toast
      return;                           // stay in edit mode
    }

    setMismatch({ open: false, delta: 0 });
    setShowValidationMessage(false);
    setIsEditing(false);
    setEditedPrevValues({}); // clear previous year edits after commit
    // Hide "empty" rows that were only visible via toggle
    setToggle?.(false);
  };

  const AmountCell = React.memo(function AmountCell({
    varName,
    editable,
    value,
    onCommit,
  }: {
    varName: string;
    editable: boolean;
    value: number;
    onCommit: (n: number) => void;
  }) {
    const [focused, setFocused] = React.useState(false);
    const [local, setLocal] = React.useState<string>("");

    // keep local in sync when not focused
    React.useEffect(() => {
      if (!focused) setLocal(value ? String(Math.round(value)) : "");
    }, [value, focused]);

    if (!editable) {
      return <span className="text-right font-medium">{numberToSv(value)} kr</span>;
    }

    const shown = focused ? local : (local ? formatSvInt(parseInt(local.replace(/[^\d-]/g, "") || "0", 10)) : "");

    const commit = () => {
      const n = parseInt((local || "0").replace(/[^\d-]/g, ""), 10);
      onCommit(Number.isFinite(n) ? n : 0);
    };

    return (
      <input
        type="text" // allow '-' freely; avoids IME lag from inputMode="numeric"
        className="w-full max-w-[108px] px-1 py-0.5 text-sm border border-gray-300 rounded text-right font-normal h-6 bg-white focus:border-gray-400 focus:outline-none"
        value={shown}
        onFocus={() => { setFocused(true); setLocal(value ? String(Math.round(value)) : ""); }}
        onChange={(e) => {
          // accept only digits and optional leading '-'
          const raw = e.target.value.replace(/[^\d-]/g, "");
          setLocal(raw); // LOCAL state only → no parent re-render on each key
        }}
        onBlur={() => { setFocused(false); commit(); }}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === "Tab") {
            e.currentTarget.blur(); // triggers commit via onBlur
          }
        }}
        placeholder="0"
      />
    );
  });

  // Precompute expensive bits once per render, not per row
  const calculatedRedValue = isEditing ? calcRedovisatVarde() : 0;

  return (
    <div className="space-y-2 pt-4">
      {/* Header with heading, edit icon, and toggle - matching FB pattern */}
      <div className="flex items-center justify-between border-b pb-1">
        <div className="flex items-center gap-3">
          <h3 className="text-lg font-semibold pt-1">{heading}</h3>
          {/* Round icon toggle, same as FB */}
          <button
            onClick={() => isEditing ? cancelEdit() : startEdit()}
            className={`w-6 h-6 rounded-full flex items-center justify-center transition-colors ${
              isEditing ? 'bg-blue-600 text-white' : 'bg-gray-200 hover:bg-gray-300 text-gray-600'
            }`}
            title={isEditing ? 'Avsluta redigering' : 'Redigera värden'}
          >
            {/* tiny pencil svg like FB */}
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                    d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
            </svg>
          </button>
        </div>
        <div className="flex items-center space-x-2">
          <label 
            htmlFor="toggle-inv-rows" 
            className="text-sm font-medium cursor-pointer"
          >
            Visa alla rader
          </label>
          <Switch
            id="toggle-inv-rows"
            checked={toggleOn}
            onCheckedChange={setToggle}
          />
        </div>
      </div>

      {/* Column headers */}
      <div className="grid gap-4 text-sm text-muted-foreground border-b pb-1 font-semibold" style={gridCols}>
        <span></span>
        <span className="text-right">{fiscalYear ?? new Date().getFullYear()}</span>
        <span className="text-right">{previousYear ?? (fiscalYear ? fiscalYear - 1 : new Date().getFullYear() - 1)}</span>
      </div>

      {/* Rows */}
      {visible.map((it, idx) => {
        // Use same style system as main Noter component
        const getStyleClasses = (style?: string) => {
          const baseClasses = 'grid gap-4';
          let additionalClasses = '';
          const s = style || 'NORMAL';
          
          // Bold styles
          const boldStyles = ['H0','H1','H2','H3','S1','S2','S3','TH0','TH1','TH2','TH3','TS1','TS2','TS3'];
          if (boldStyles.includes(s)) {
            additionalClasses += ' font-semibold';
          }
          
          // Line styles
          const lineStyles = ['S2','S3','TS2','TS3'];
          if (lineStyles.includes(s)) {
            additionalClasses += ' border-t border-b border-gray-200 pt-1 pb-1';
          }
          
          return {
            className: `${baseClasses}${additionalClasses}`,
            style: { gridTemplateColumns: '4fr 1fr 1fr' }
          };
        };

        const currentStyle = it.style || 'NORMAL';
        const isHeading = isHeadingStyle(currentStyle);
        // Kill O(n²) - use direct string comparison instead of indexOf
        const isRedVardeRow = it.variable_name === "red_varde_inventarier";
        const redClass = mismatch.delta !== 0 ? 'text-red-600 font-bold' : '';
        
        // Precompute style classes once per row
        const gc = getStyleClasses(currentStyle);
        
        return (
          <div 
            key={`${it.row_id}-${idx}`} 
            className={gc.className}
            style={gc.style}
          >
            <span className="text-muted-foreground flex items-center">
              {it.row_title}
              {it.show_tag && (
                <span className="ml-2">
                  <AccountDetailsDialog item={it} />
                </span>
              )}
            </span>

            {/* Current year */}
            <span className={`text-right font-medium ${isRedVardeRow ? redClass : ""}`}>
              {isHeading ? "" : (isRedVardeRow && isEditing ? numberToSv(calculatedRedValue) + " kr" : (
                <AmountCell
                  varName={it.variable_name!}
                  editable={isEditing && isFlowVar(it.variable_name)}
                  value={getCurrentValue(it.variable_name!)}
                  onCommit={(n) => {
                    setEditedValues(prev => ({ ...prev, [it.variable_name!]: n }));
                  }}
                />
              ))}
            </span>

            {/* Previous year - editable for flows too */}
            <span className="text-right font-medium">
              {isHeading ? "" : (
                <AmountCell
                  varName={`${it.variable_name!}_prev`}
                  editable={isEditing && isFlowVar(it.variable_name)}
                  value={readPrev(it)}
                  onCommit={(n) => {
                    setEditedPrevValues(prev => ({ ...prev, [it.variable_name!]: n }));
                  }}
                />
              )}
            </span>
          </div>
        );
      })}

      {/* Comparison row – only while editing */}
      {isEditing && (
        <div className="grid gap-4 border-t border-gray-200 pt-1 items-center" style={gridCols}>
          <span className="text-muted-foreground">Redovisat värde (bokfört)</span>
          <span className="text-right font-medium">{numberToSv(brBookValueUB)} kr</span>
          <span /> {/* prev-year empty */}
        </div>
      )}

      {/* Action buttons at bottom - matching FB pattern */}
      {isEditing && (
        <div className="pt-4 border-t border-gray-200 flex justify-between">
          {/* Undo Button - Left */}
          <Button 
            onClick={cancelEdit}
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
            onClick={approveEdit}
            className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 flex items-center gap-2"
          >
            Godkänn ändringar
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 10h-10a8 8 0 00-8 8v2M21 10l-6 6m6-6l-6-6"/>
            </svg>
          </Button>
        </div>
      )}

      {/* Toast Notification - FB style */}
      {showValidationMessage && (
        <div className="fixed bottom-4 right-4 z-50 bg-white border border-gray-200 rounded-lg shadow-lg p-4 max-w-sm animate-in slide-in-from-bottom-2">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <svg className="w-5 h-5 text-red-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </div>
            <div className="ml-3 flex-1">
              <p className="text-sm font-medium text-gray-900">
                Summor balanserar inte
              </p>
              <p className="text-sm text-gray-500 mt-1">
                Redovisat värde (beräknat) stämmer inte med bokfört värde. Skillnad: {numberToSv(mismatch.delta)} kr
              </p>
            </div>
            <button
              onClick={() => setShowValidationMessage(false)}
              className="ml-4 flex-shrink-0 text-gray-400 hover:text-gray-600"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"/>
              </svg>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

interface NoterProps {
  noterData: NoterItem[];
  fiscalYear?: number;
  previousYear?: number;
  companyData?: any; // Add companyData to access scraped data
}

export function Noter({ noterData, fiscalYear, previousYear, companyData }: NoterProps) {
  const [blockToggles, setBlockToggles] = useState<Record<string, boolean>>({});
  const [selectedItem, setSelectedItem] = useState<NoterItem | null>(null);

  const formatAmount = (amount: number) => {
    return new Intl.NumberFormat('sv-SE', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const formatAmountWithDecimals = (amount: number) => {
    return new Intl.NumberFormat('sv-SE', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount);
  };

  // Group items by block
  const groupedItems = noterData.reduce((groups: Record<string, NoterItem[]>, item) => {
    const block = item.block || 'Övriga noter';
    if (!groups[block]) {
      groups[block] = [];
    }
    groups[block].push(item);
    return groups;
  }, {});

  // Sort each block by row column to maintain database order
  Object.keys(groupedItems).forEach(block => {
    groupedItems[block].sort((a, b) => (a.row_id || 0) - (b.row_id || 0));
  });

  // Get unique blocks for toggle controls
  const blocks = Object.keys(groupedItems);

  // Filter items based on toggle states
  const getVisibleItems = (items: NoterItem[], block?: string) => {
    if (!items) return [];
    const toggleOn = block ? (blockToggles[block] || false) : false;

    return items.filter(item => {
      // Headings and rows explicitly always_show=true are always visible
      if (item.always_show) return true;

      const hasNonZero =
        (item.current_amount ?? 0) !== 0 ||
        (item.previous_amount ?? 0) !== 0;

      if (hasNonZero) return true;

      // zero amounts:
      // show only if row is toggleable and the block toggle is ON
      if (item.toggle_show) return toggleOn;

      // zero + not toggleable => never show
      return false;
    });
  };


  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>
          Noter
        </CardTitle>

      </CardHeader>
      
      <CardContent>
        <div className="space-y-6">
          {(() => {
            // First pass: determine which blocks will be visible and calculate note numbers
            let noteNumber = 3; // Start at 3 since NOT1=1 and NOT2=2 are fixed
            const blockVisibility: Record<string, { isVisible: boolean; noteNumber?: number }> = {};
            
            blocks.forEach(block => {
              const blockItems = groupedItems[block];
              const visibleItems = getVisibleItems(blockItems, block);
              
              // For OVRIGA block, always show if there's moderbolag data
              const scrapedData = (companyData as any)?.scraped_company_data;
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
              
              // Check visibility toggles for blocks that have them
              // Note: For EVENTUAL and SAKERHET, we don't set isVisible = false here
              // because we want to show the header with opacity, just not count in numbering
              
              blockVisibility[block] = { isVisible };
              
              // Assign note numbers to visible blocks (except NOT1 and NOT2 which are fixed)
              // Also exclude EVENTUAL and SAKERHET if their visibility toggles are off
              let shouldGetNumber = isVisible && block !== 'NOT1' && block !== 'NOT2';
              
              if (block === 'EVENTUAL') {
                const eventualToggleKey = `eventual-visibility`;
                const isEventualVisible = blockToggles[eventualToggleKey] !== false;
                if (!isEventualVisible) shouldGetNumber = false;
              }
              
              if (block === 'SAKERHET') {
                const sakerhetToggleKey = `sakerhet-visibility`;
                const isSakerhetVisible = blockToggles[sakerhetToggleKey] !== false;
                if (!isSakerhetVisible) shouldGetNumber = false;
              }
              
              if (shouldGetNumber) {
                blockVisibility[block].noteNumber = noteNumber++;
              }
            });
            
            // Second pass: render the blocks with correct numbering
            return blocks.map(block => {
              const blockItems = groupedItems[block];
              const visibleItems = getVisibleItems(blockItems, block);
              const visibility = blockVisibility[block];
              
              if (!visibility.isVisible) return null;
              
              // Get first row title for block heading
              const firstRowTitle = blockItems[0]?.row_title || block;
              let blockHeading = `Not ${firstRowTitle}`;
              
              // Apply note numbering
              if (block === 'NOT1') {
                blockHeading = `Not 1 ${firstRowTitle}`;
              } else if (block === 'NOT2') {
                blockHeading = `Not 2 ${firstRowTitle}`;
              } else if (visibility.noteNumber) {
                blockHeading = `Not ${visibility.noteNumber} ${firstRowTitle}`;
              }
            
            // Special handling for Note 1 (Redovisningsprinciper)
            if (block === 'NOT1') {
              // Find the heading item (row_id 2) and text item (row_id 3)
              const headingItem = blockItems.find(item => item.row_id === 2);
              const textItem = blockItems.find(item => item.row_id === 3);
              
              // Find depreciation period values from noterData
              const getDepreciationValue = (variableName: string) => {
                const item = noterData.find(item => item.variable_name === variableName);
                return item ? item.current_amount : null;
              };
              
              const avskrtidBygg = getDepreciationValue('avskrtid_bygg');
              const avskrtidMask = getDepreciationValue('avskrtid_mask');
              const avskrtidInv = getDepreciationValue('avskrtid_inv');
              const avskrtidOvriga = getDepreciationValue('avskrtid_ovriga');
              
              return (
                <div key={block} className="space-y-4 pt-4">
                  {/* Note 1 heading without toggle */}
                  <div className="border-b pb-1">
                    <h3 className="font-semibold text-lg" style={{paddingTop: '7px'}}>{blockHeading}</h3>
                  </div>
                  
                  {/* Insert text from row_id 3 after heading */}
                  {textItem?.variable_text && (
                    <div className="text-sm leading-relaxed">
                      {textItem.variable_text}
                    </div>
                  )}
                  
                  {/* Depreciation table with only two columns */}
                  <div className="space-y-2">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="font-semibold py-1">Anläggningstillgångar</TableHead>
                          <TableHead className="font-semibold text-right py-1">År</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        <TableRow>
                          <TableCell className="py-1">Byggnader & mark</TableCell>
                          <TableCell className="text-right py-1">
                            {avskrtidBygg !== null ? avskrtidBygg : '-'}
                          </TableCell>
                        </TableRow>
                        <TableRow>
                          <TableCell className="py-1">Maskiner och andra tekniska anläggningar</TableCell>
                          <TableCell className="text-right py-1">
                            {avskrtidMask !== null ? avskrtidMask : '-'}
                          </TableCell>
                        </TableRow>
                        <TableRow>
                          <TableCell className="py-1">Inventarier, verktyg och installationer</TableCell>
                          <TableCell className="text-right py-1">
                            {avskrtidInv !== null ? avskrtidInv : '-'}
                          </TableCell>
                        </TableRow>
                        <TableRow>
                          <TableCell className="py-1">Övriga materiella anläggningstillgångar</TableCell>
                          <TableCell className="text-right py-1">
                            {avskrtidOvriga !== null ? avskrtidOvriga : '-'}
                          </TableCell>
                        </TableRow>
                      </TableBody>
                    </Table>
                  </div>
                </div>
              );
            }
            
            // Special handling for Note 2 (Medelantalet anställda) - no toggle, use scraped data
            if (block === 'NOT2') {
              // Get employee count from scraped data (first value from "Antal anställda")
              const scrapedEmployeeCount = (companyData as any)?.scraped_company_data?.nyckeltal?.["Antal anställda"]?.[0] || 0;
              
              return (
                <div key={block} className="space-y-2 pt-4">
                  {/* Note 2 heading without toggle */}
                  <div className="border-b pb-1">
                    <h3 className="font-semibold text-lg" style={{paddingTop: '7px'}}>{blockHeading}</h3>
                  </div>
                  
                  {/* Column Headers - same as BR/RR */}
                  <div className="grid gap-4 text-sm text-muted-foreground border-b pb-1 font-semibold" style={{gridTemplateColumns: '4fr 1fr 1fr'}}>
                    <span></span>
                    <span className="text-right">{fiscalYear || new Date().getFullYear()}</span>
                    <span className="text-right">{previousYear || (fiscalYear ? fiscalYear - 1 : new Date().getFullYear() - 1)}</span>
                  </div>

                  {/* Employee count row */}
                  <div className="grid gap-4" style={{gridTemplateColumns: '4fr 1fr 1fr'}}>
                    <span className="text-sm">Medelantalet anställda under året</span>
                    <span className="text-right text-sm">{scrapedEmployeeCount}</span>
                    <span className="text-right text-sm">{scrapedEmployeeCount}</span>
                  </div>
                </div>
              );
            }
            
            // Special handling for OVRIGA block - no toggle, add moderbolag text after row 534
            if (block === 'OVRIGA') {
              // Get moderbolag information from scraped data
              const scrapedData = (companyData as any)?.scraped_company_data;
              const moderbolag = scrapedData?.moderbolag;
              const moderbolagOrgnr = scrapedData?.moderbolag_orgnr;
              const sate = scrapedData?.säte;
              
              return (
                <div key={block} className="space-y-2 pt-4">
                  {/* OVRIGA heading without toggle */}
                  <div className="border-b pb-1">
                    <h3 className="font-semibold text-lg" style={{paddingTop: '7px'}}>{blockHeading}</h3>
                  </div>
                  
                  {/* Always show moderbolag text at the start if company has parent company */}
                  {moderbolag && (
                    <div className="text-sm leading-relaxed">
                      Företaget är ett dotterbolag till {moderbolag} med organisationsnummer {moderbolagOrgnr} med säte i {sate}, som upprättar koncernredovisning.
                    </div>
                  )}

                  {/* Noter Rows */}
                  {visibleItems.map((item, index) => {
                    // Use same style system as BR/RR
                    const getStyleClasses = (style?: string) => {
                      const baseClasses = 'grid gap-4';
                      let additionalClasses = '';
                      const s = style || 'NORMAL';
                      
                      // Bold styles
                      const boldStyles = ['H0','H1','H2','H3','S1','S2','S3','TH0','TH1','TH2','TH3','TS1','TS2','TS3'];
                      if (boldStyles.includes(s)) {
                        additionalClasses += ' font-semibold';
                      }
                      
                      // Line styles
                      const lineStyles = ['S2','S3','TS2','TS3'];
                      if (lineStyles.includes(s)) {
                        additionalClasses += ' border-t border-b border-gray-200 pt-1 pb-1';
                      }
                      
                      return {
                        className: `${baseClasses}${additionalClasses}`,
                        style: { gridTemplateColumns: '1fr' }
                      };
                    };

                    const formatAmountDisplay = (amount: number) => {
                      if (amount === 0) return '0 kr';
                      const formatted = Math.abs(amount).toLocaleString('sv-SE', { 
                        minimumFractionDigits: 0,
                        maximumFractionDigits: 0
                      });
                      const sign = amount < 0 ? '-' : '';
                      return `${sign}${formatted} kr`;
                    };

                    const currentStyle = item.style || 'NORMAL';
                    const isHeading = ['H0', 'H1', 'H2', 'H3'].includes(currentStyle);
                    
                    return (
                      <React.Fragment key={index}>
                        <div 
                          className={getStyleClasses(currentStyle).className}
                          style={getStyleClasses(currentStyle).style}
                        >
                          <span className="text-muted-foreground">
                            {item.row_title}
                            {item.show_tag && (
                              <AccountDetailsDialog item={item} />
                            )}
                          </span>
                        </div>
                        
                      </React.Fragment>
                    );
                  })}
                </div>
              );
            }
            
            // Special handling for EVENTUAL block - custom visibility toggle
            if (block === 'EVENTUAL') {
              const eventualToggleKey = `eventual-visibility`;
              const isEventualVisible = blockToggles[eventualToggleKey] !== false; // Default to true
              
              return (
                <div key={block} className="space-y-2 pt-4">
                  {/* EVENTUAL heading with custom visibility toggle */}
                  <div className="border-b pb-1 flex items-center">
                    <h3 className={`font-semibold text-lg ${!isEventualVisible ? 'opacity-35' : ''}`} style={{paddingTop: '7px'}}>
                      {blockHeading}
                    </h3>
                    <div className={`ml-2 flex items-center ${!isEventualVisible ? 'opacity-35' : ''}`} style={{transform: 'scale(0.75)', marginTop: '5px'}}>
                      <Switch
                        checked={isEventualVisible}
                        onCheckedChange={(checked) => 
                          setBlockToggles(prev => ({ ...prev, [eventualToggleKey]: checked }))
                        }
                      />
                      <span className="ml-2 font-medium" style={{fontSize: '17px'}}>Visa not</span>
                    </div>
                  </div>
                  
                  {/* Only show content if toggle is on */}
                  {isEventualVisible && (
                    <>
                      {/* Column Headers - same as BR/RR */}
                      <div className="grid gap-4 text-sm text-muted-foreground border-b pb-1 font-semibold" style={{gridTemplateColumns: '4fr 1fr 1fr'}}>
                        <span></span>
                        <span className="text-right">{fiscalYear || new Date().getFullYear()}</span>
                        <span className="text-right">{previousYear || (fiscalYear ? fiscalYear - 1 : new Date().getFullYear() - 1)}</span>
                      </div>

                      {/* Noter Rows - same grid system as BR/RR */}
                      {visibleItems.map((item, index) => {
                        // Use same style system as BR/RR
                        const getStyleClasses = (style?: string) => {
                          const baseClasses = 'grid gap-4';
                          let additionalClasses = '';
                          const s = style || 'NORMAL';
                          
                          // Bold styles
                          const boldStyles = ['H0','H1','H2','H3','S1','S2','S3','TH0','TH1','TH2','TH3','TS1','TS2','TS3'];
                          if (boldStyles.includes(s)) {
                            additionalClasses += ' font-semibold';
                          }
                          
                          // Line styles
                          const lineStyles = ['S2','S3','TS2','TS3'];
                          if (lineStyles.includes(s)) {
                            additionalClasses += ' border-t border-b border-gray-200 pt-1 pb-1';
                          }
                          
                          return {
                            className: `${baseClasses}${additionalClasses}`,
                            style: { gridTemplateColumns: '4fr 1fr 1fr' }
                          };
                        };

                        const formatAmountDisplay = (amount: number) => {
                          if (amount === 0) return '0 kr';
                          const formatted = Math.abs(amount).toLocaleString('sv-SE', { 
                            minimumFractionDigits: 0,
                            maximumFractionDigits: 0
                          });
                          const sign = amount < 0 ? '-' : '';
                          return `${sign}${formatted} kr`;
                        };

                        const currentStyle = item.style || 'NORMAL';
                        const isHeading = ['H0', 'H1', 'H2', 'H3'].includes(currentStyle);
                        
                        return (
                          <div 
                            key={index} 
                            className={getStyleClasses(currentStyle).className}
                            style={getStyleClasses(currentStyle).style}
                          >
                            <span className="text-muted-foreground">
                              {item.row_title}
                              {item.show_tag && (
                                <AccountDetailsDialog item={item} />
                              )}
                            </span>
                            <span className="text-right font-medium">
                              {isHeading ? '' : formatAmountDisplay(item.current_amount)}
                            </span>
                            <span className="text-right font-medium">
                              {isHeading ? '' : formatAmountDisplay(item.previous_amount)}
                            </span>
                          </div>
                        );
                      })}
                    </>
                  )}
                </div>
              );
            }
            
            // Special handling for SAKERHET block - custom visibility toggle + regular toggle
            if (block === 'SAKERHET') {
              const sakerhetToggleKey = `sakerhet-visibility`;
              const isSakerhetVisible = blockToggles[sakerhetToggleKey] !== false; // Default to true
              
              return (
                <div key={block} className="space-y-2 pt-4">
                  <div className="flex items-center justify-between border-b pb-1">
                    <div className="flex items-center">
                      <h3 className={`font-semibold text-lg ${!isSakerhetVisible ? 'opacity-35' : ''}`} style={{paddingTop: '7px'}}>
                        {blockHeading}
                      </h3>
                      <div className={`ml-2 flex items-center ${!isSakerhetVisible ? 'opacity-35' : ''}`} style={{transform: 'scale(0.75)', marginTop: '5px'}}>
                        <Switch
                          checked={isSakerhetVisible}
                          onCheckedChange={(checked) => 
                            setBlockToggles(prev => ({ ...prev, [sakerhetToggleKey]: checked }))
                          }
                        />
                        <span className="ml-2 font-medium" style={{fontSize: '17px'}}>Visa not</span>
                      </div>
                    </div>
                    {/* Keep the regular "Visa alla rader" toggle */}
                    {isSakerhetVisible && (
                      <div className="flex items-center space-x-2">
                        <label 
                          htmlFor={`toggle-${block}`} 
                          className="text-sm font-medium cursor-pointer"
                        >
                          Visa alla rader
                        </label>
                        <Switch
                          id={`toggle-${block}`}
                          checked={blockToggles[block] || false}
                          onCheckedChange={(checked) => 
                            setBlockToggles(prev => ({ ...prev, [block]: checked }))
                          }
                        />
                      </div>
                    )}
                  </div>
                  
                  {/* Only show content if visibility toggle is on */}
                  {isSakerhetVisible && (
                    <>
                      {/* Column Headers - same as BR/RR */}
                      <div className="grid gap-4 text-sm text-muted-foreground border-b pb-1 font-semibold" style={{gridTemplateColumns: '4fr 1fr 1fr'}}>
                        <span></span>
                        <span className="text-right">{fiscalYear || new Date().getFullYear()}</span>
                        <span className="text-right">{previousYear || (fiscalYear ? fiscalYear - 1 : new Date().getFullYear() - 1)}</span>
                      </div>

                      {/* Noter Rows - same grid system as BR/RR */}
                      {getVisibleItems(blockItems, block).map((item, index) => {
                        // Use same style system as BR/RR
                        const getStyleClasses = (style?: string) => {
                          const baseClasses = 'grid gap-4';
                          let additionalClasses = '';
                          const s = style || 'NORMAL';
                          
                          // Bold styles
                          const boldStyles = ['H0','H1','H2','H3','S1','S2','S3','TH0','TH1','TH2','TH3','TS1','TS2','TS3'];
                          if (boldStyles.includes(s)) {
                            additionalClasses += ' font-semibold';
                          }
                          
                          // Line styles
                          const lineStyles = ['S2','S3','TS2','TS3'];
                          if (lineStyles.includes(s)) {
                            additionalClasses += ' border-t border-b border-gray-200 pt-1 pb-1';
                          }
                          
                          return {
                            className: `${baseClasses}${additionalClasses}`,
                            style: { gridTemplateColumns: '4fr 1fr 1fr' }
                          };
                        };

                        const formatAmountDisplay = (amount: number) => {
                          if (amount === 0) return '0 kr';
                          const formatted = Math.abs(amount).toLocaleString('sv-SE', { 
                            minimumFractionDigits: 0,
                            maximumFractionDigits: 0
                          });
                          const sign = amount < 0 ? '-' : '';
                          return `${sign}${formatted} kr`;
                        };

                        const currentStyle = item.style || 'NORMAL';
                        const isHeading = ['H0', 'H1', 'H2', 'H3'].includes(currentStyle);
                        
                        return (
                          <div 
                            key={index} 
                            className={getStyleClasses(currentStyle).className}
                            style={getStyleClasses(currentStyle).style}
                          >
                            <span className="text-muted-foreground">
                              {item.row_title}
                              {item.show_tag && (
                                <AccountDetailsDialog item={item} />
                              )}
                            </span>
                            <span className="text-right font-medium">
                              {isHeading ? '' : formatAmountDisplay(item.current_amount)}
                            </span>
                            <span className="text-right font-medium">
                              {isHeading ? '' : formatAmountDisplay(item.previous_amount)}
                            </span>
                          </div>
                        );
                      })}
                    </>
                  )}
                </div>
              );
            }
            
            // Special handling for INV block - with manual editing capability
            if (block === 'INV') {
              return (
                <InventarierNote
                  key={block}
                  items={blockItems}
                  heading={blockHeading}
                  fiscalYear={fiscalYear}
                  previousYear={previousYear}
                  companyData={companyData}
                  toggleOn={blockToggles[block] || false}
                  setToggle={(checked: boolean) =>
                    setBlockToggles(prev => ({ ...prev, [block]: checked }))
                  }
                />
              );
            }
            
            return (
              <div key={block} className="space-y-2 pt-4">
                <div className="flex items-center justify-between border-b pb-1">
                  <h3 className="font-semibold text-lg" style={{paddingTop: '7px'}}>{blockHeading}</h3>
                  <div className="flex items-center space-x-2">
                  <label 
                  htmlFor={`toggle-${block}`} 
                  className="text-sm font-medium cursor-pointer"
                  >
                  Visa alla rader
                  </label>
                  <Switch
                    id={`toggle-${block}`}
                  checked={blockToggles[block] || false}
                  onCheckedChange={(checked) => 
                      setBlockToggles(prev => ({ ...prev, [block]: checked }))
                  }
                  />
                  </div>
                </div>
                
                {/* Column Headers - same as BR/RR */}
                <div className="grid gap-4 text-sm text-muted-foreground border-b pb-1 font-semibold" style={{gridTemplateColumns: '4fr 1fr 1fr'}}>
                  <span></span>
                  <span className="text-right">{fiscalYear || new Date().getFullYear()}</span>
                  <span className="text-right">{previousYear || (fiscalYear ? fiscalYear - 1 : new Date().getFullYear() - 1)}</span>
                </div>

                {/* Noter Rows - same grid system as BR/RR */}
                {visibleItems.map((item, index) => {
                  // Use same style system as BR/RR
                  const getStyleClasses = (style?: string) => {
                    const baseClasses = 'grid gap-4';
                    let additionalClasses = '';
                    const s = style || 'NORMAL';
                    
                    // Bold styles
                    const boldStyles = ['H0','H1','H2','H3','S1','S2','S3','TH0','TH1','TH2','TH3','TS1','TS2','TS3'];
                    if (boldStyles.includes(s)) {
                      additionalClasses += ' font-semibold';
                    }
                    
                    // Line styles
                    const lineStyles = ['S2','S3','TS2','TS3'];
                    if (lineStyles.includes(s)) {
                      additionalClasses += ' border-t border-b border-gray-200 pt-1 pb-1';
                    }
                    
                    return {
                      className: `${baseClasses}${additionalClasses}`,
                      style: { gridTemplateColumns: '4fr 1fr 1fr' }
                    };
                  };

                  const formatAmountDisplay = (amount: number) => {
                    if (amount === 0) return '0 kr';
                    const formatted = Math.abs(amount).toLocaleString('sv-SE', { 
                      minimumFractionDigits: 0,
                      maximumFractionDigits: 0
                    });
                    const sign = amount < 0 ? '-' : '';
                    return `${sign}${formatted} kr`;
                  };

                  const currentStyle = item.style || 'NORMAL';
                  const isHeading = ['H0', 'H1', 'H2', 'H3'].includes(currentStyle);
                  
                  return (
                    <div 
                      key={index} 
                      className={getStyleClasses(currentStyle).className}
                      style={getStyleClasses(currentStyle).style}
                    >
                      <span className="text-muted-foreground">
                        {item.row_title}
                        {item.show_tag && (
                          <AccountDetailsDialog item={item} />
                        )}
                      </span>
                      <span className="text-right font-medium">
                        {isHeading ? '' : formatAmountDisplay(item.current_amount)}
                      </span>
                      <span className="text-right font-medium">
                        {isHeading ? '' : formatAmountDisplay(item.previous_amount)}
                      </span>
                    </div>
                  );
                })}
              </div>
            );
          });
          })()}
          
          {blocks.every(block => getVisibleItems(groupedItems[block], block).length === 0) && (
            <div className="text-center text-gray-500 py-4">
              Inga noter att visa. Aktivera sektioner ovan för att se detaljer.
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
