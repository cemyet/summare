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
const isSumLine = (s?: string) => ['S2', 'S3', 'TS2', 'TS3'].includes(s || '');
const isSubTotalTrigger = (s?: string) => s === 'S2' || s === 'TS2';

type VisibleOpts = {
  items: NoterItem[];
  toggleOn: boolean;
  // read current/previous values from your state (edited/committed etc.)
  readCur: (it: NoterItem) => number | undefined;
  readPrev: (it: NoterItem) => number | undefined;
};

/** One-stop visibility builder for all notes (Bygg, Maskiner, Övriga MAT, Inventarier). */
export function buildVisibleWithHeadings({
  items, toggleOn, readCur, readPrev
}: VisibleOpts): NoterItem[] {
  // --- Pass 1: base visibility (row itself is visible?) ---
  const baseVisible = items.filter((it) => {
    if (it.always_show) return true;
    const cur = readCur(it) ?? 0;
    const prev = readPrev(it) ?? 0;
    if (cur !== 0 || prev !== 0) return true;
    if (it.toggle_show) return toggleOn;
    return false;
  });
  const baseSet = new Set(baseVisible.map(r => r.row_id));

  // Rows allowed to TRIGGER headings/subtotals (content rows only)
  const triggerRows = items.filter((it) => {
    if (isSumLine(it.style)) return false;
    if (it.always_show) return false;
    const cur = readCur(it) ?? 0;
    const prev = readPrev(it) ?? 0;
    if (cur !== 0 || prev !== 0) return true;
    if (it.toggle_show) return toggleOn;
    return false;
  });
  const triggerSet = new Set(triggerRows.map(r => r.row_id));

  // --- Pass 2: add H2/H3 headings + S2/TS2 subtotals based on nearby trigger rows ---
  const out: NoterItem[] = [];
  for (let i = 0; i < items.length; i++) {
    const it = items[i];

    // Already visible? keep it.
    if (baseSet.has(it.row_id)) {
      out.push(it);
      continue;
    }

    // Headings (H2/H3): show if ANY following trigger row until next heading is present
    if (isHeadingStyle(it.style)) {
      let show = false;
      for (let j = i + 1; j < items.length; j++) {
        const nxt = items[j];
        if (isHeadingStyle(nxt.style)) break; // stop at next block/subblock
        if (triggerSet.has(nxt.row_id)) { show = true; break; }
      }
      if (show) { out.push(it); continue; }
    }

    // Subtotals (S2/TS2): show if ANY preceding trigger row until previous heading/S2 is present
    if (isSubTotalTrigger(it.style)) {
      let show = false;
      for (let j = i - 1; j >= 0; j--) {
        const prev = items[j];
        if (isHeadingStyle(prev.style) || isSubTotalTrigger(prev.style)) break;
        if (triggerSet.has(prev.row_id)) { show = true; break; }
      }
      if (show) { out.push(it); continue; }
    }
  }

  return out;
}

// AmountCell component (shared between all manual editing note components)
const AmountCell = React.memo(function AmountCell({
  year,
  varName,
  baseVar,
  label,
  editable,
  value,
  ord,
  onCommit,
  onTabNavigate,
  onSignForced,
  expectedSignFor,
}: {
  year: 'cur' | 'prev';
  varName: string;
  baseVar: string;
  label?: string;
  editable: boolean;
  value: number;
  ord?: number;
  onCommit: (n: number) => void;
  onTabNavigate?: (el: HTMLInputElement, dir: 1 | -1) => void;
  onSignForced?: (e: {
    baseVar: string;
    label?: string;
    year: 'cur' | 'prev';
    expected: '+' | '-';
    typed: number;
    adjusted: number;
  }) => void;
  expectedSignFor: (vn?: string) => '+' | '-' | null;
}) {
  const [focused, setFocused] = React.useState(false);
  const [local, setLocal] = React.useState<string>("");
  const [forcedFlash, setForcedFlash] = React.useState<null | ('+' | '-')>(null);
  const inputRef = React.useRef<HTMLInputElement>(null);

  const signRule = expectedSignFor(baseVar);

  React.useEffect(() => {
    if (!focused) setLocal(value ? String(Math.round(value)) : "");
  }, [value, focused]);

  if (!editable) {
    return <span className="text-right font-medium">{numberToSv(value)} kr</span>;
  }

  const shown = focused
    ? local
    : (local ? fmt0.format(parseInt(local.replace(/[^\d-]/g, "") || "0", 10)) : "");

  const commit = () => {
    const raw = (local || "0").replace(/[^\d-]/g, "");
    let typed = parseInt(raw || "0", 10);
    if (!Number.isFinite(typed)) typed = 0;

    let adjusted = typed;
    let wasForced = false;

    if (signRule === '-') {
      adjusted = -Math.abs(typed);
      wasForced = (typed > 0);
    } else if (signRule === '+') {
      adjusted = Math.max(0, Math.abs(typed));
      wasForced = (typed < 0);
    }

    if (wasForced && signRule) {
      setForcedFlash(signRule);
      setTimeout(() => setForcedFlash(null), 1500);
      onSignForced?.({ baseVar, label, year, expected: signRule, typed, adjusted });
    }

    onCommit(adjusted);
  };

  return (
    <div className="relative inline-block">
      <input
        ref={inputRef}
        type="text"
        data-editable-cell="1"
        data-year={year}
        data-ord={ord}
        className="w-full max-w-[108px] px-1 py-0.5 text-sm border border-gray-300 rounded text-right font-normal h-6 bg-white focus:border-gray-400 focus:outline-none"
        value={shown}
        onFocus={() => { setFocused(true); setLocal(value ? String(Math.round(value)) : ""); }}
        onChange={(e) => {
          let raw = e.target.value.replace(/[^\d-]/g, "");
          if (signRule === '+') {
            raw = raw.replace(/-/g, '');
          } else if (signRule === '-') {
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
            const el = inputRef.current || (e.currentTarget as HTMLInputElement);
            requestAnimationFrame(() => onTabNavigate?.(el, e.shiftKey ? -1 : 1));
          }
        }}
        placeholder={signRule === '-' ? "-0" : "0"}
        aria-describedby={forcedFlash ? `${varName}-signmsg` : undefined}
      />

      {forcedFlash && (
        <div
          id={`${varName}-signmsg`}
          className="absolute -top-5 right-0 px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 border border-amber-200 shadow-sm"
          style={{ fontSize: '10px' }}
          role="status" aria-live="polite"
          title={forcedFlash === '-' ? 'Tecken justerat till minus' : 'Negativt värde ej tillåtet'}
        >
          {forcedFlash === '-' ? '(-) JUSTERAD' : 'ENDAST +'}
        </div>
      )}
    </div>
  );
});

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

// Maskiner editor component
const MaskinerNote: React.FC<{
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

  // BR book value (UB) for both years - MASKIN specific
  const { brBookValueUBCur, brBookValueUBPrev } = React.useMemo(() => {
    const brData: any[] = companyData?.seFileData?.br_data || [];
    const candidates = [
      "MaskinerAndraTekniskaAnlaggningar",
      "Maskiner",
      "MaskinerTekniska",
    ];
    let cur = 0, prev = 0;

    for (const c of candidates) {
      const hit = brData.find((x: any) => x.variable_name === c);
      if (hit) {
        if (Number.isFinite(hit.current_amount))  cur  = hit.current_amount;
        if (Number.isFinite(hit.previous_amount)) prev = hit.previous_amount;
        if (cur || prev) break;
      }
    }

    // Fallback to note values if BR is missing
    if (!cur)  cur  = byVar.get("red_varde_maskiner")?.current_amount  ?? 0;
    if (!prev) prev = byVar.get("red_varde_maskiner")?.previous_amount ?? 0;

    return { brBookValueUBCur: cur, brBookValueUBPrev: prev };
  }, [companyData, byVar]);

  // Baseline management - save original values for proper undo
  const originalBaselineRef = React.useRef<{cur: Record<string, number>, prev: Record<string, number>}>({cur:{}, prev:{}});
  React.useEffect(() => {
    const cur: Record<string, number> = {};
    const prev: Record<string, number> = {};
    items.forEach(it => {
      const vn = it.variable_name;
      if (!vn) return;
      if (!isFlowVar(vn)) return;
      cur[vn] = it.current_amount ?? 0;
      prev[vn] = it.previous_amount ?? 0;
    });
    originalBaselineRef.current = { cur, prev };
  }, [items]);

  // Local edit state
  const [isEditing, setIsEditing] = useState(false);
  const [editedValues, setEditedValues] = useState<Record<string, number>>({});
  const [editedPrevValues, setEditedPrevValues] = useState<Record<string, number>>({});
  const [committedValues, setCommittedValues] = useState<Record<string, number>>({});
  const [committedPrevValues, setCommittedPrevValues] = useState<Record<string, number>>({});
  const [mismatch, setMismatch] = useState<{ open: boolean; deltaCur: number; deltaPrev: number }>({
    open: false,
    deltaCur: 0,
    deltaPrev: 0,
  });
  const [showValidationMessage, setShowValidationMessage] = useState(false);

  // Sign enforcement from CSV mapping - MASKIN specific
  const injectedSignMap: Record<string, '+' | '-'> | undefined = (companyData?.signByVar) || undefined;

  const heuristicSign = (vn: string): '+' | '-' | null => {
    // Based on variable_mapping_noter_rows (3).csv for MASKIN block
    const positiveVars = [
      'arets_inkop_maskiner',
      'aterfor_avskr_fsg_maskiner', 
      'aterfor_nedskr_fsg_maskiner',
      'aterfor_nedskr_maskiner'
    ];
    
    const negativeVars = [
      'arets_fsg_maskiner',
      'arets_avskr_maskiner', 
      'arets_nedskr_maskiner'
    ];
    
    if (positiveVars.includes(vn)) return '+';
    if (negativeVars.includes(vn)) return '-';
    return null; // flexible - can be both + or -
  };

  const expectedSignFor = (vn?: string): '+' | '-' | null => {
    if (!vn) return null;
    return injectedSignMap?.[vn] ?? heuristicSign(vn);
  };

  // Single accessor that S2 and "beräknat" use
  const getVal = React.useCallback((vn: string, year: 'cur' | 'prev') => {
    if (year === 'cur') {
      if (editedValues[vn] !== undefined) return editedValues[vn];
      if (committedValues[vn] !== undefined) return committedValues[vn];
      return byVar.get(vn)?.current_amount ?? 0;
    } else {
      if (editedPrevValues[vn] !== undefined) return editedPrevValues[vn];
      if (committedPrevValues[vn] !== undefined) return committedPrevValues[vn];
      return byVar.get(vn)?.previous_amount ?? 0;
    }
  }, [editedValues, committedValues, editedPrevValues, committedPrevValues, byVar]);

  // Read current/prev amount, considering edits
  const readCur = (it: NoterItem) => getVal(it.variable_name!, 'cur');
  const readPrev = (it: NoterItem) => getVal(it.variable_name!, 'prev');

  const visible = useMemo(() => {
    return buildVisibleWithHeadings({
      items,
      toggleOn,
      readCur: (it) => readCur(it),
      readPrev: (it) => readPrev(it),
    });
  }, [items, toggleOn, editedValues, editedPrevValues, committedValues, committedPrevValues]);

  // Compute Redovisat värde (beräknat) - MASKIN specific formula
  const calcRedovisatVarde = React.useCallback((year: 'cur' | 'prev') => {
    const v = (name: string) => getVal(name, year) || 0;

    const maskinerUB = v('maskiner_ib') + v('arets_inkop_maskiner') + v('arets_fsg_maskiner') + v('arets_omklass_maskiner');
    const avskrUB   = v('ack_avskr_maskiner_ib') + v('arets_avskr_maskiner') + v('aterfor_avskr_fsg_maskiner') + v('omklass_avskr_maskiner');
    const nedskrUB  = v('ack_nedskr_maskiner_ib') + v('arets_nedskr_maskiner') + v('aterfor_nedskr_maskiner') + v('aterfor_nedskr_fsg_maskiner') + v('omklass_nedskr_maskiner');

    return maskinerUB + avskrUB + nedskrUB;
  }, [getVal]);

  const startEdit = () => {
    setIsEditing(true);
    setToggle?.(true); // show hidden rows when entering edit
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
    setEditedPrevValues({});
    setMismatch({ open: false, deltaCur: 0, deltaPrev: 0 });
    setShowValidationMessage(false);
    setToggle?.(false);
  };

  const undoEdit = () => {
    blurAllEditableInputs();
    setEditedValues({});
    setEditedPrevValues({});
    setCommittedValues({ ...originalBaselineRef.current.cur });
    setCommittedPrevValues({ ...originalBaselineRef.current.prev });
    setMismatch({ open: false, deltaCur: 0, deltaPrev: 0 });
    setShowValidationMessage(false);
  };

  const approveEdit = () => {
    const redCurCalc  = calcRedovisatVarde('cur');
    const redPrevCalc = calcRedovisatVarde('prev');

    const deltaCur  = redCurCalc  - brBookValueUBCur;
    const deltaPrev = redPrevCalc - brBookValueUBPrev;

    const hasMismatch = Math.round(deltaCur) !== 0 || Math.round(deltaPrev) !== 0;

    if (hasMismatch) {
      setMismatch({ open: true, deltaCur, deltaPrev });
      setShowValidationMessage(true);
      return;
    }

    setCommittedValues(prev => ({ ...prev, ...editedValues }));
    setCommittedPrevValues(prev => ({ ...prev, ...editedPrevValues }));
    setEditedValues({});
    setEditedPrevValues({});
    setMismatch({ open: false, deltaCur: 0, deltaPrev: 0 });
    setShowValidationMessage(false);
    setIsEditing(false);
    setToggle?.(false);
  };

  // Reuse the same AmountCell from InventarierNote (already defined above)
  // Reuse the same helper functions

  // Helpers for S2 row calculation
  const isSumRow = (it: NoterItem) => it.style === 'S2';
  const isHeading = (it: NoterItem) => isHeadingStyle(it.style);

  const sumGroupAbove = React.useCallback(
    (list: NoterItem[], index: number, year: 'cur' | 'prev') => {
      let sum = 0;
      for (let i = index - 1; i >= 0; i--) {
        const r = list[i];
        if (!r) break;
        if (isHeading(r) || r.style === 'S2') break;
        if (r.variable_name) sum += getVal(r.variable_name, year);
      }
      return sum;
    },
    [getVal]
  );

  // Container ref + tab navigation helper (reuse from InventarierNote)
  const containerRef = React.useRef<HTMLDivElement>(null);

  const focusByOrd = (fromEl: HTMLInputElement, dir: 1 | -1) => {
    const root = containerRef.current;
    if (!root) return;
    const curOrd = Number(fromEl.dataset.ord || '0');
    const nextOrd = curOrd + dir;
    const next = root.querySelector<HTMLInputElement>(
      `input[data-editable-cell="1"][data-ord="${nextOrd}"]`
    );
    if (next) { next.focus(); next.select?.(); }
  };

  const blurAllEditableInputs = () => {
    const root = containerRef.current;
    if (!root) return;
    const nodes = root.querySelectorAll<HTMLInputElement>('input[data-editable-cell="1"]');
    nodes.forEach((el) => el.blur());
  };

  const pushSignNotice = (e: any) => {
    console.log(`Sign forced for ${e.label} (${e.year}): ${e.typed} → ${e.adjusted}`);
  };

  // Helper: get the dynamic S2 subtotal for MASKIN UB rows
  const ubSum = React.useCallback((ubVar: string, year: 'cur' | 'prev') => {
    const v = (name: string) => getVal(name, year) || 0;
    const idx = visible.findIndex(r => r.variable_name === ubVar);
    if (idx !== -1 && visible[idx]?.style === 'S2') {
      // Use exactly what the UI shows for that S2 row
      return sumGroupAbove(visible, idx, year);
    }
    // Fallbacks if the UB row isn't visible:
    switch (ubVar) {
      case 'maskiner_ub':
        return v('maskiner_ib') + v('arets_inkop_maskiner') + v('arets_fsg_maskiner') + v('arets_omklass_maskiner');
      case 'ack_avskr_maskiner_ub':
        return v('ack_avskr_maskiner_ib') + v('arets_avskr_maskiner') + v('aterfor_avskr_fsg_maskiner') + v('omklass_avskr_maskiner');
      case 'ack_nedskr_maskiner_ub':
        return v('ack_nedskr_maskiner_ib') + v('arets_nedskr_maskiner') + v('aterfor_nedskr_maskiner') + v('aterfor_nedskr_fsg_maskiner') + v('omklass_nedskr_maskiner');
      default:
        return getVal(ubVar, year);
    }
  }, [visible, sumGroupAbove, getVal]);

  // Sum the actual S2 subtotals for MASKIN (no uppskrivningar)
  const redCur  = ['maskiner_ub','ack_avskr_maskiner_ub','ack_nedskr_maskiner_ub']
    .map(n => ubSum(n, 'cur'))
    .reduce((a,b) => a + b, 0);

  const redPrev = ['maskiner_ub','ack_avskr_maskiner_ub','ack_nedskr_maskiner_ub']
    .map(n => ubSum(n, 'prev'))
    .reduce((a,b) => a + b, 0);

  return (
    <div ref={containerRef} className="space-y-2 pt-4">
      {/* Header with heading, edit icon, and toggle - matching FB pattern */}
      <div className="flex items-center justify-between border-b pb-1">
        <div className="flex items-center gap-3">
          <h3 className="text-lg font-semibold pt-1">{heading}</h3>
          <button
            onClick={() => isEditing ? cancelEdit() : startEdit()}
            className={`w-6 h-6 rounded-full flex items-center justify-center transition-colors ${
              isEditing ? 'bg-blue-600 text-white' : 'bg-gray-200 hover:bg-gray-300 text-gray-600'
            }`}
            title={isEditing ? 'Avsluta redigering' : 'Redigera värden'}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                    d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
            </svg>
          </button>
        </div>
        <div className="flex items-center space-x-2">
          <label htmlFor="toggle-maskin-rows" className="text-sm font-medium cursor-pointer">
            Visa alla rader
          </label>
          <Switch
            id="toggle-maskin-rows"
            checked={toggleOn}
            onCheckedChange={setToggle}
          />
        </div>
      </div>

      {/* Column headers */}
      <div className="grid gap-4 text-sm text-muted-foreground border-b pb-1 font-semibold" style={gridCols}>
        <span></span>
        <span className="text-right">{companyData?.currentPeriodEndDate || `${fiscalYear ?? new Date().getFullYear()}-12-31`}</span>
        <span className="text-right">{companyData?.previousPeriodEndDate || `${(previousYear ?? (fiscalYear ? fiscalYear - 1 : new Date().getFullYear() - 1))}-12-31`}</span>
      </div>

      {/* Rows */}
      {(() => {
        let ordCounter = 0;
        return visible.map((it, idx) => {
          const getStyleClasses = (style?: string, isRedovisatVarde = false) => {
            const baseClasses = 'grid gap-4';
            let additionalClasses = '';
            const s = style || 'NORMAL';
            
            const boldStyles = ['H0','H1','H2','H3','S1','S2','S3','TH0','TH1','TH2','TH3','TS1','TS2','TS3'];
            if (boldStyles.includes(s)) {
              additionalClasses += ' font-semibold';
            }
            
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
          const isHeadingRow = isHeadingStyle(currentStyle);
          const isS2 = isSumRow(it);
          const editable = isEditing && isFlowVar(it.variable_name);
          
          const ordCur  = editable ? ++ordCounter : undefined;
          const ordPrev = editable ? ++ordCounter : undefined;
          
          const isRedVardeRow = it.variable_name === "red_varde_maskiner";
          
          const curVal = isRedVardeRow
            ? redCur
            : (isS2 ? sumGroupAbove(visible, idx, 'cur') : getVal(it.variable_name ?? '', 'cur'));
          const prevVal = isRedVardeRow
            ? redPrev
            : (isS2 ? sumGroupAbove(visible, idx, 'prev') : getVal(it.variable_name ?? '', 'prev'));

          const curMismatch  = isEditing && isRedVardeRow && Math.round(redCur)  !== Math.round(brBookValueUBCur);
          const prevMismatch = isEditing && isRedVardeRow && Math.round(redPrev) !== Math.round(brBookValueUBPrev);
          
          const gc = getStyleClasses(currentStyle, isRedVardeRow);
          
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
              <span className={`text-right font-medium ${isRedVardeRow && curMismatch ? 'text-red-600 font-bold' : ''}`}>
                {isHeadingRow ? '' : isRedVardeRow
                  ? `${numberToSv(curVal)} kr`
                  : <AmountCell
                      year="cur"
                      varName={it.variable_name!}
                      baseVar={it.variable_name!}
                      label={it.row_title}
                      editable={editable}
                      value={curVal}
                      ord={ordCur}
                      onCommit={(n) => setEditedValues(p => ({ ...p, [it.variable_name!]: n }))}
                      onTabNavigate={(el, dir) => focusByOrd(el, dir)}
                      onSignForced={(e) => pushSignNotice(e)}
                      expectedSignFor={expectedSignFor}
                    />
                }
              </span>

              {/* Previous year */}
              <span className={`text-right font-medium ${isRedVardeRow && prevMismatch ? 'text-red-600 font-bold' : ''}`}>
                {isHeadingRow ? '' : isRedVardeRow
                  ? `${numberToSv(prevVal)} kr`
                  : <AmountCell
                      year="prev"
                      varName={`${it.variable_name!}_prev`}
                      baseVar={it.variable_name!}
                      label={it.row_title}
                      editable={editable}
                      value={prevVal}
                      ord={ordPrev}
                      onCommit={(n) => setEditedPrevValues(p => ({ ...p, [it.variable_name!]: n }))}
                      onTabNavigate={(el, dir) => focusByOrd(el, dir)}
                      onSignForced={(e) => pushSignNotice(e)}
                      expectedSignFor={expectedSignFor}
                    />
                }
              </span>
            </div>
          );
        });
      })()}

      {/* Comparison row – only while editing */}
      {isEditing && (
        <div className="grid gap-4 border-t border-b border-gray-200 pt-1 pb-1 font-semibold bg-gray-50/50" style={gridCols}>
          <span className="text-muted-foreground font-semibold">Redovisat värde (bokfört)</span>
          <span className="text-right font-medium">{numberToSv(brBookValueUBCur)} kr</span>
          <span className="text-right font-medium">{numberToSv(brBookValueUBPrev)} kr</span>
        </div>
      )}

      {/* Action buttons at bottom */}
      {isEditing && (
        <div className="pt-4 flex justify-between">
          <Button 
            onClick={undoEdit}
            variant="outline"
            className="flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"/>
            </svg>
            Ångra ändringar
          </Button>
          
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

      {/* Toast Notification */}
      {showValidationMessage && (
        <div className="fixed bottom-4 right-4 z-50 bg-white rounded-lg shadow-lg p-4 max-w-sm animate-in slide-in-from-bottom-2">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <svg className="w-5 h-5 text-red-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                      d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </div>
            <div className="ml-3">
              {(() => {
                const curMism = Math.round(mismatch.deltaCur) !== 0;
                const prevMism = Math.round(mismatch.deltaPrev) !== 0;
                
                if (curMism && !prevMism) {
                  return (
                    <>
                      <p className="text-sm font-medium text-gray-900">
                        Summor balanserar inte {fiscalYear}
                      </p>
                      <p className="mt-1 text-sm text-gray-700">
                        Beräknat redovisat värde stämmer inte med bokfört värde. Differensen är {numberToSv(Math.abs(Math.round(mismatch.deltaCur)))} kr.
                      </p>
                    </>
                  );
                } else if (prevMism && !curMism) {
                  return (
                    <>
                      <p className="text-sm font-medium text-gray-900">
                        Summor balanserar inte {previousYear}
                      </p>
                      <p className="mt-1 text-sm text-gray-700">
                        Beräknat redovisat värde stämmer inte med bokfört värde. Differensen är {numberToSv(Math.abs(Math.round(mismatch.deltaPrev)))} kr.
                      </p>
                    </>
                  );
                } else {
                  return (
                    <>
                      <p className="text-sm font-medium text-gray-900">
                        Summor balanserar inte
                      </p>
                      <p className="mt-1 text-sm text-gray-700">
                        Beräknat redovisat värde stämmer inte med bokfört värde.
                      </p>
                      <ul className="mt-2 text-sm text-gray-900">
                        <li><strong>{fiscalYear}</strong>: Differens {numberToSv(Math.abs(Math.round(mismatch.deltaCur)))} kr</li>
                        <li><strong>{previousYear}</strong>: Differens {numberToSv(Math.abs(Math.round(mismatch.deltaPrev)))} kr</li>
                      </ul>
                    </>
                  );
                }
              })()}
            </div>
            <button
              onClick={() => { setShowValidationMessage(false); setMismatch(m => ({ ...m, open: false })); }}
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

// Byggnader editor component (includes UPPSKRIVNINGAR subblock)
const ByggnaderNote: React.FC<{
  items: NoterItem[];
  heading: string;
  fiscalYear?: number;
  previousYear?: number;
  companyData?: any;
  toggleOn: boolean;
  setToggle: (checked: boolean) => void;
}> = ({ items, heading, fiscalYear, previousYear, companyData, toggleOn, setToggle }) => {
  const gridCols = { gridTemplateColumns: "4fr 1fr 1fr" };

  const isFlowVar = (vn?: string) => {
    if (!vn) return false;
    if (/_ib\b/i.test(vn)) return false;
    if (/_ub\b/i.test(vn)) return false;
    if (/red[_-]?varde/i.test(vn)) return false;
    return true;
  };

  const byVar = useMemo(() => {
    const m = new Map<string, NoterItem>();
    items.forEach((it) => it.variable_name && m.set(it.variable_name, it));
    return m;
  }, [items]);

  // BR book value (UB) for both years - BYGG specific
  const { brBookValueUBCur, brBookValueUBPrev } = React.useMemo(() => {
    const brData: any[] = companyData?.seFileData?.br_data || [];
    const candidates = [
      "ByggnaderMark",
      "Byggnader",
      "ByggnaderOchMark",
    ];
    let cur = 0, prev = 0;

    for (const c of candidates) {
      const hit = brData.find((x: any) => x.variable_name === c);
      if (hit) {
        if (Number.isFinite(hit.current_amount))  cur  = hit.current_amount;
        if (Number.isFinite(hit.previous_amount)) prev = hit.previous_amount;
        if (cur || prev) break;
      }
    }

    if (!cur)  cur  = byVar.get("red_varde_bygg")?.current_amount  ?? 0;
    if (!prev) prev = byVar.get("red_varde_bygg")?.previous_amount ?? 0;

    return { brBookValueUBCur: cur, brBookValueUBPrev: prev };
  }, [companyData, byVar]);

  // Baseline management
  const originalBaselineRef = React.useRef<{cur: Record<string, number>, prev: Record<string, number>}>({cur:{}, prev:{}});
  React.useEffect(() => {
    const cur: Record<string, number> = {};
    const prev: Record<string, number> = {};
    items.forEach(it => {
      const vn = it.variable_name;
      if (!vn) return;
      if (!isFlowVar(vn)) return;
      cur[vn] = it.current_amount ?? 0;
      prev[vn] = it.previous_amount ?? 0;
    });
    originalBaselineRef.current = { cur, prev };
  }, [items]);

  // Local edit state
  const [isEditing, setIsEditing] = useState(false);
  const [editedValues, setEditedValues] = useState<Record<string, number>>({});
  const [editedPrevValues, setEditedPrevValues] = useState<Record<string, number>>({});
  const [committedValues, setCommittedValues] = useState<Record<string, number>>({});
  const [committedPrevValues, setCommittedPrevValues] = useState<Record<string, number>>({});
  const [mismatch, setMismatch] = useState<{ open: boolean; deltaCur: number; deltaPrev: number }>({
    open: false,
    deltaCur: 0,
    deltaPrev: 0,
  });
  const [showValidationMessage, setShowValidationMessage] = useState(false);

  // Sign enforcement from CSV mapping - BYGG specific (includes UPPSKR variables)
  const injectedSignMap: Record<string, '+' | '-'> | undefined = (companyData?.signByVar) || undefined;

  const heuristicSign = (vn: string): '+' | '-' | null => {
    // Based on variable_mapping_noter_rows (bygg).csv - corrected structure
    const positiveVars = [
      'arets_inkop_bygg',
      'aterfor_avskr_fsg_bygg', 
      'aterfor_nedskr_fsg_bygg',
      'aterfor_nedskr_bygg',
      'arets_uppskr_bygg'  // UPPSKR positive
    ];
    
    const negativeVars = [
      'arets_fsg_bygg',
      'arets_avskr_bygg', 
      'arets_nedskr_bygg',
      'aterfor_uppskr_fsg_bygg',  // UPPSKR negative
      'arets_avskr_uppskr_bygg'   // UPPSKR negative
    ];
    
    // Flexible variables (can be both + or -, all omklassificeringar)
    const flexibleVars = [
      'arets_omklass_bygg',      // Anskaffningsvärden
      'omklass_avskr_bygg',      // Avskrivningar
      'omklass_uppskr_bygg',     // Uppskrivningar
      'omklass_nedskr_bygg'      // Nedskrivningar
    ];
    
    if (positiveVars.includes(vn)) return '+';
    if (negativeVars.includes(vn)) return '-';
    return null; // flexible (including omklassificeringar)
  };

  const expectedSignFor = (vn?: string): '+' | '-' | null => {
    if (!vn) return null;
    return injectedSignMap?.[vn] ?? heuristicSign(vn);
  };

  const getVal = React.useCallback((vn: string, year: 'cur' | 'prev') => {
    if (year === 'cur') {
      if (editedValues[vn] !== undefined) return editedValues[vn];
      if (committedValues[vn] !== undefined) return committedValues[vn];
      return byVar.get(vn)?.current_amount ?? 0;
    } else {
      if (editedPrevValues[vn] !== undefined) return editedPrevValues[vn];
      if (committedPrevValues[vn] !== undefined) return committedPrevValues[vn];
      return byVar.get(vn)?.previous_amount ?? 0;
    }
  }, [editedValues, committedValues, editedPrevValues, committedPrevValues, byVar]);

  const readCur = (it: NoterItem) => getVal(it.variable_name!, 'cur');
  const readPrev = (it: NoterItem) => getVal(it.variable_name!, 'prev');

  const visible = useMemo(() => {
    return buildVisibleWithHeadings({
      items,
      toggleOn,
      readCur: (it) => readCur(it),
      readPrev: (it) => readPrev(it),
    });
  }, [items, toggleOn, editedValues, editedPrevValues, committedValues, committedPrevValues]);

  // Compute Redovisat värde (beräknat) - BYGG specific formula
  const calcRedovisatVarde = React.useCallback((year: 'cur' | 'prev') => {
    const v = (name: string) => getVal(name, year) || 0;

    // Use the exact formula from CSV: bygg_ub+ack_avskr_bygg_ub+ack_uppskr_bygg_ub+ack_nedskr_bygg_ub
    // But since we're editing flows, we need to calculate the UB values from flows
    
    // Anskaffningsvärden UB
    const byggUB = v('bygg_ib') + v('arets_inkop_bygg') + v('arets_fsg_bygg') + v('arets_omklass_bygg');
    
    // Avskrivningar UB
    const avskrUB = v('ack_avskr_bygg_ib') + v('arets_avskr_bygg') + v('aterfor_avskr_fsg_bygg') + v('omklass_avskr_bygg');
    
    // Uppskrivningar UB (this was missing from CSV formula but needed for complete calculation)
    const uppskrUB = v('ack_uppskr_bygg_ib') + v('arets_uppskr_bygg') + v('aterfor_uppskr_fsg_bygg') + v('arets_avskr_uppskr_bygg') + v('omklass_uppskr_bygg');
    
    // Nedskrivningar UB
    const nedskrUB = v('ack_nedskr_bygg_ib') + v('arets_nedskr_bygg') + v('aterfor_nedskr_fsg_bygg') + v('aterfor_nedskr_bygg') + v('omklass_nedskr_bygg');

    // Complete formula: anskaffning + avskrivningar + uppskrivningar + nedskrivningar
    return byggUB + avskrUB + uppskrUB + nedskrUB;
  }, [getVal]);

  const startEdit = () => {
    setIsEditing(true);
    setToggle?.(true);
  };

  React.useEffect(() => {
    if (showValidationMessage) {
      const timer = setTimeout(() => setShowValidationMessage(false), 5000);
      return () => clearTimeout(timer);
    }
  }, [showValidationMessage]);

  const cancelEdit = () => {
    setIsEditing(false);
    setEditedValues({});
    setEditedPrevValues({});
    setMismatch({ open: false, deltaCur: 0, deltaPrev: 0 });
    setShowValidationMessage(false);
    setToggle?.(false);
  };

  const undoEdit = () => {
    blurAllEditableInputs();
    setEditedValues({});
    setEditedPrevValues({});
    setCommittedValues({ ...originalBaselineRef.current.cur });
    setCommittedPrevValues({ ...originalBaselineRef.current.prev });
    setMismatch({ open: false, deltaCur: 0, deltaPrev: 0 });
    setShowValidationMessage(false);
  };

  const approveEdit = () => {
    const redCurCalc  = calcRedovisatVarde('cur');
    const redPrevCalc = calcRedovisatVarde('prev');

    const deltaCur  = redCurCalc  - brBookValueUBCur;
    const deltaPrev = redPrevCalc - brBookValueUBPrev;

    const hasMismatch = Math.round(deltaCur) !== 0 || Math.round(deltaPrev) !== 0;

    if (hasMismatch) {
      setMismatch({ open: true, deltaCur, deltaPrev });
      setShowValidationMessage(true);
      return;
    }

    setCommittedValues(prev => ({ ...prev, ...editedValues }));
    setCommittedPrevValues(prev => ({ ...prev, ...editedPrevValues }));
    setEditedValues({});
    setEditedPrevValues({});
    setMismatch({ open: false, deltaCur: 0, deltaPrev: 0 });
    setShowValidationMessage(false);
    setIsEditing(false);
    setToggle?.(false);
  };

  // Helper functions (reuse from module scope)
  const isSumRow = (it: NoterItem) => it.style === 'S2';
  const isHeading = (it: NoterItem) => isHeadingStyle(it.style);

  const sumGroupAbove = React.useCallback(
    (list: NoterItem[], index: number, year: 'cur' | 'prev') => {
      let sum = 0;
      for (let i = index - 1; i >= 0; i--) {
        const r = list[i];
        if (!r) break;
        if (isHeading(r) || r.style === 'S2') break;
        if (r.variable_name) sum += getVal(r.variable_name, year);
      }
      return sum;
    },
    [getVal]
  );

  const containerRef = React.useRef<HTMLDivElement>(null);

  const focusByOrd = (fromEl: HTMLInputElement, dir: 1 | -1) => {
    const root = containerRef.current;
    if (!root) return;
    const curOrd = Number(fromEl.dataset.ord || '0');
    const nextOrd = curOrd + dir;
    const next = root.querySelector<HTMLInputElement>(
      `input[data-editable-cell="1"][data-ord="${nextOrd}"]`
    );
    if (next) { next.focus(); next.select?.(); }
  };

  const blurAllEditableInputs = () => {
    const root = containerRef.current;
    if (!root) return;
    const nodes = root.querySelectorAll<HTMLInputElement>('input[data-editable-cell="1"]');
    nodes.forEach((el) => el.blur());
  };

  const pushSignNotice = (e: any) => {
    console.log(`Sign forced for ${e.label} (${e.year}): ${e.typed} → ${e.adjusted}`);
  };

  // Helper: get the dynamic S2 subtotal for a given UB-row if present,
  // otherwise fall back to the formula-based UB for that section.
  const ubSum = React.useCallback((ubVar: string, year: 'cur' | 'prev') => {
    const v = (name: string) => getVal(name, year) || 0;
    const idx = visible.findIndex(r => r.variable_name === ubVar);
    if (idx !== -1 && visible[idx]?.style === 'S2') {
      // Use exactly what the UI shows for that S2 row
      return sumGroupAbove(visible, idx, year);
    }
    // Fallbacks if the UB row isn't visible:
    switch (ubVar) {
      case 'bygg_ub':
        return v('bygg_ib') + v('arets_inkop_bygg') + v('arets_fsg_bygg') + v('arets_omklass_bygg');
      case 'ack_avskr_bygg_ub':
        return v('ack_avskr_bygg_ib') + v('arets_avskr_bygg') + v('aterfor_avskr_fsg_bygg') + v('omklass_avskr_bygg');
      case 'ack_uppskr_bygg_ub':
        return v('ack_uppskr_bygg_ib') + v('arets_uppskr_bygg') + v('aterfor_uppskr_fsg_bygg') + v('arets_avskr_uppskr_bygg') + v('omklass_uppskr_bygg');
      case 'ack_nedskr_bygg_ub':
        return v('ack_nedskr_bygg_ib') + v('arets_nedskr_bygg') + v('aterfor_nedskr_fsg_bygg') + v('aterfor_nedskr_bygg') + v('omklass_nedskr_bygg');
      default:
        return getVal(ubVar, year);
    }
  }, [visible, sumGroupAbove, getVal]);

  // Sum the actual S2 subtotals instead of re-deriving from flows
  const redCur  = ['bygg_ub','ack_avskr_bygg_ub','ack_uppskr_bygg_ub','ack_nedskr_bygg_ub']
    .map(n => ubSum(n, 'cur'))
    .reduce((a,b) => a + b, 0);

  const redPrev = ['bygg_ub','ack_avskr_bygg_ub','ack_uppskr_bygg_ub','ack_nedskr_bygg_ub']
    .map(n => ubSum(n, 'prev'))
    .reduce((a,b) => a + b, 0);

  return (
    <div ref={containerRef} className="space-y-2 pt-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b pb-1">
        <div className="flex items-center gap-3">
          <h3 className="text-lg font-semibold pt-1">{heading}</h3>
          <button
            onClick={() => isEditing ? cancelEdit() : startEdit()}
            className={`w-6 h-6 rounded-full flex items-center justify-center transition-colors ${
              isEditing ? 'bg-blue-600 text-white' : 'bg-gray-200 hover:bg-gray-300 text-gray-600'
            }`}
            title={isEditing ? 'Avsluta redigering' : 'Redigera värden'}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                    d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
            </svg>
          </button>
        </div>
        <div className="flex items-center space-x-2">
          <label htmlFor="toggle-bygg-rows" className="text-sm font-medium cursor-pointer">
            Visa alla rader
          </label>
          <Switch
            id="toggle-bygg-rows"
            checked={toggleOn}
            onCheckedChange={setToggle}
          />
        </div>
      </div>

      {/* Column headers */}
      <div className="grid gap-4 text-sm text-muted-foreground border-b pb-1 font-semibold" style={gridCols}>
        <span></span>
        <span className="text-right">{companyData?.currentPeriodEndDate || `${fiscalYear ?? new Date().getFullYear()}-12-31`}</span>
        <span className="text-right">{companyData?.previousPeriodEndDate || `${(previousYear ?? (fiscalYear ? fiscalYear - 1 : new Date().getFullYear() - 1))}-12-31`}</span>
      </div>

      {/* Rows */}
      {(() => {
        let ordCounter = 0;
        return visible.map((it, idx) => {
          const getStyleClasses = (style?: string) => {
            const baseClasses = 'grid gap-4';
            let additionalClasses = '';
            const s = style || 'NORMAL';
            
            const boldStyles = ['H0','H1','H2','H3','S1','S2','S3','TH0','TH1','TH2','TH3','TS1','TS2','TS3'];
            if (boldStyles.includes(s)) {
              additionalClasses += ' font-semibold';
            }
            
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
          const isHeadingRow = isHeadingStyle(currentStyle);
          const isS2 = isSumRow(it);
          const editable = isEditing && isFlowVar(it.variable_name);
          
          const ordCur  = editable ? ++ordCounter : undefined;
          const ordPrev = editable ? ++ordCounter : undefined;
          
          const isRedVardeRow = it.variable_name === "red_varde_bygg";
          
          const curVal = isRedVardeRow
            ? redCur
            : (isS2 ? sumGroupAbove(visible, idx, 'cur') : getVal(it.variable_name ?? '', 'cur'));
          const prevVal = isRedVardeRow
            ? redPrev
            : (isS2 ? sumGroupAbove(visible, idx, 'prev') : getVal(it.variable_name ?? '', 'prev'));

          const curMismatch  = isEditing && isRedVardeRow && Math.round(redCur)  !== Math.round(brBookValueUBCur);
          const prevMismatch = isEditing && isRedVardeRow && Math.round(redPrev) !== Math.round(brBookValueUBPrev);
          
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
              <span className={`text-right font-medium ${isRedVardeRow && curMismatch ? 'text-red-600 font-bold' : ''}`}>
                {isHeadingRow ? '' : isRedVardeRow
                  ? `${numberToSv(curVal)} kr`
                  : <AmountCell
                      year="cur"
                      varName={it.variable_name!}
                      baseVar={it.variable_name!}
                      label={it.row_title}
                      editable={editable}
                      value={curVal}
                      ord={ordCur}
                      onCommit={(n) => setEditedValues(p => ({ ...p, [it.variable_name!]: n }))}
                      onTabNavigate={(el, dir) => focusByOrd(el, dir)}
                      onSignForced={(e) => pushSignNotice(e)}
                      expectedSignFor={expectedSignFor}
                    />
                }
              </span>

              {/* Previous year */}
              <span className={`text-right font-medium ${isRedVardeRow && prevMismatch ? 'text-red-600 font-bold' : ''}`}>
                {isHeadingRow ? '' : isRedVardeRow
                  ? `${numberToSv(prevVal)} kr`
                  : <AmountCell
                      year="prev"
                      varName={`${it.variable_name!}_prev`}
                      baseVar={it.variable_name!}
                      label={it.row_title}
                      editable={editable}
                      value={prevVal}
                      ord={ordPrev}
                      onCommit={(n) => setEditedPrevValues(p => ({ ...p, [it.variable_name!]: n }))}
                      onTabNavigate={(el, dir) => focusByOrd(el, dir)}
                      onSignForced={(e) => pushSignNotice(e)}
                      expectedSignFor={expectedSignFor}
                    />
                }
              </span>
            </div>
          );
        });
      })()}

      {/* Comparison row – only while editing */}
      {isEditing && (
        <div className="grid gap-4 border-t border-b border-gray-200 pt-1 pb-1 font-semibold bg-gray-50/50" style={gridCols}>
          <span className="text-muted-foreground font-semibold">Redovisat värde (bokfört)</span>
          <span className="text-right font-medium">{numberToSv(brBookValueUBCur)} kr</span>
          <span className="text-right font-medium">{numberToSv(brBookValueUBPrev)} kr</span>
        </div>
      )}

      {/* Action buttons */}
      {isEditing && (
        <div className="pt-4 flex justify-between">
          <Button 
            onClick={undoEdit}
            variant="outline"
            className="flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"/>
            </svg>
            Ångra ändringar
          </Button>
          
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

      {/* Toast Notification */}
      {showValidationMessage && (
        <div className="fixed bottom-4 right-4 z-50 bg-white rounded-lg shadow-lg p-4 max-w-sm animate-in slide-in-from-bottom-2">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <svg className="w-5 h-5 text-red-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                      d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </div>
            <div className="ml-3">
              {(() => {
                const curMism = Math.round(mismatch.deltaCur) !== 0;
                const prevMism = Math.round(mismatch.deltaPrev) !== 0;
                
                if (curMism && !prevMism) {
                  return (
                    <>
                      <p className="text-sm font-medium text-gray-900">
                        Summor balanserar inte {fiscalYear}
                      </p>
                      <p className="mt-1 text-sm text-gray-700">
                        Beräknat redovisat värde stämmer inte med bokfört värde. Differensen är {numberToSv(Math.abs(Math.round(mismatch.deltaCur)))} kr.
                      </p>
                    </>
                  );
                } else if (prevMism && !curMism) {
                  return (
                    <>
                      <p className="text-sm font-medium text-gray-900">
                        Summor balanserar inte {previousYear}
                      </p>
                      <p className="mt-1 text-sm text-gray-700">
                        Beräknat redovisat värde stämmer inte med bokfört värde. Differensen är {numberToSv(Math.abs(Math.round(mismatch.deltaPrev)))} kr.
                      </p>
                    </>
                  );
                } else {
                  return (
                    <>
                      <p className="text-sm font-medium text-gray-900">
                        Summor balanserar inte
                      </p>
                      <p className="mt-1 text-sm text-gray-700">
                        Beräknat redovisat värde stämmer inte med bokfört värde.
                      </p>
                      <ul className="mt-2 text-sm text-gray-900">
                        <li><strong>{fiscalYear}</strong>: Differens {numberToSv(Math.abs(Math.round(mismatch.deltaCur)))} kr</li>
                        <li><strong>{previousYear}</strong>: Differens {numberToSv(Math.abs(Math.round(mismatch.deltaPrev)))} kr</li>
                      </ul>
                    </>
                  );
                }
              })()}
            </div>
            <button
              onClick={() => { setShowValidationMessage(false); setMismatch(m => ({ ...m, open: false })); }}
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

// Övriga materiella anläggningstillgångar editor component
const OvrigaMateriellaNote: React.FC<{
  items: NoterItem[];
  heading: string;
  fiscalYear?: number;
  previousYear?: number;
  companyData?: any;
  toggleOn: boolean;
  setToggle: (checked: boolean) => void;
}> = ({ items, heading, fiscalYear, previousYear, companyData, toggleOn, setToggle }) => {
  const gridCols = { gridTemplateColumns: "4fr 1fr 1fr" };

  const isFlowVar = (vn?: string) => {
    if (!vn) return false;
    if (/_ib\b/i.test(vn)) return false;
    if (/_ub\b/i.test(vn)) return false;
    if (/red[_-]?varde/i.test(vn)) return false;
    return true;
  };

  const byVar = useMemo(() => {
    const m = new Map<string, NoterItem>();
    items.forEach((it) => it.variable_name && m.set(it.variable_name, it));
    return m;
  }, [items]);

  // BR book value (UB) for both years - MAT specific
  const { brBookValueUBCur, brBookValueUBPrev } = React.useMemo(() => {
    const brData: any[] = companyData?.seFileData?.br_data || [];
    const candidates = [
      "OvrigaMateriellaAnlaggningstillgangar",
      "OvrigaMateriella",
      "OvrigaMat",
    ];
    let cur = 0, prev = 0;

    for (const c of candidates) {
      const hit = brData.find((x: any) => x.variable_name === c);
      if (hit) {
        if (Number.isFinite(hit.current_amount))  cur  = hit.current_amount;
        if (Number.isFinite(hit.previous_amount)) prev = hit.previous_amount;
        if (cur || prev) break;
      }
    }

    if (!cur)  cur  = byVar.get("red_varde_ovrmat")?.current_amount  ?? 0;
    if (!prev) prev = byVar.get("red_varde_ovrmat")?.previous_amount ?? 0;

    return { brBookValueUBCur: cur, brBookValueUBPrev: prev };
  }, [companyData, byVar]);

  // Baseline management
  const originalBaselineRef = React.useRef<{cur: Record<string, number>, prev: Record<string, number>}>({cur:{}, prev:{}});
  React.useEffect(() => {
    const cur: Record<string, number> = {};
    const prev: Record<string, number> = {};
    items.forEach(it => {
      const vn = it.variable_name;
      if (!vn) return;
      if (!isFlowVar(vn)) return;
      cur[vn] = it.current_amount ?? 0;
      prev[vn] = it.previous_amount ?? 0;
    });
    originalBaselineRef.current = { cur, prev };
  }, [items]);

  // Local edit state
  const [isEditing, setIsEditing] = useState(false);
  const [editedValues, setEditedValues] = useState<Record<string, number>>({});
  const [editedPrevValues, setEditedPrevValues] = useState<Record<string, number>>({});
  const [committedValues, setCommittedValues] = useState<Record<string, number>>({});
  const [committedPrevValues, setCommittedPrevValues] = useState<Record<string, number>>({});
  const [mismatch, setMismatch] = useState<{ open: boolean; deltaCur: number; deltaPrev: number }>({
    open: false,
    deltaCur: 0,
    deltaPrev: 0,
  });
  const [showValidationMessage, setShowValidationMessage] = useState(false);

  // Sign enforcement from CSV mapping - MAT specific
  const injectedSignMap: Record<string, '+' | '-'> | undefined = (companyData?.signByVar) || undefined;

  const heuristicSign = (vn: string): '+' | '-' | null => {
    // Based on variable_mapping_noter_rows 5.csv for MAT block
    const positiveVars = [
      'arets_inkop_ovrmat',
      'aterfor_avskr_fsg_ovrmat', 
      'aterfor_nedskr_fsg_ovrmat',
      'aterfor_nedskr_ovrmat'
    ];
    
    const negativeVars = [
      'arets_fsg_ovrmat',
      'arets_avskr_ovrmat', 
      'arets_nedskr_ovrmat'
    ];
    
    // Flexible variables (newly added omklassificeringar)
    const flexibleVars = [
      'arets_omklass_ovrmat',      // Anskaffningsvärden
      'omklass_avskr_ovrmat',      // Avskrivningar
      'omklass_nedskr_ovrmat'      // Nedskrivningar
    ];
    
    if (positiveVars.includes(vn)) return '+';
    if (negativeVars.includes(vn)) return '-';
    return null; // flexible
  };

  const expectedSignFor = (vn?: string): '+' | '-' | null => {
    if (!vn) return null;
    return injectedSignMap?.[vn] ?? heuristicSign(vn);
  };

  const getVal = React.useCallback((vn: string, year: 'cur' | 'prev') => {
    if (year === 'cur') {
      if (editedValues[vn] !== undefined) return editedValues[vn];
      if (committedValues[vn] !== undefined) return committedValues[vn];
      return byVar.get(vn)?.current_amount ?? 0;
    } else {
      if (editedPrevValues[vn] !== undefined) return editedPrevValues[vn];
      if (committedPrevValues[vn] !== undefined) return committedPrevValues[vn];
      return byVar.get(vn)?.previous_amount ?? 0;
    }
  }, [editedValues, committedValues, editedPrevValues, committedPrevValues, byVar]);

  const readCur = (it: NoterItem) => getVal(it.variable_name!, 'cur');
  const readPrev = (it: NoterItem) => getVal(it.variable_name!, 'prev');

  const visible = useMemo(() => {
    return buildVisibleWithHeadings({
      items,
      toggleOn,
      readCur: (it) => readCur(it),
      readPrev: (it) => readPrev(it),
    });
  }, [items, toggleOn, editedValues, editedPrevValues, committedValues, committedPrevValues]);

  const startEdit = () => {
    setIsEditing(true);
    setToggle?.(true);
  };

  React.useEffect(() => {
    if (showValidationMessage) {
      const timer = setTimeout(() => setShowValidationMessage(false), 5000);
      return () => clearTimeout(timer);
    }
  }, [showValidationMessage]);

  const cancelEdit = () => {
    setIsEditing(false);
    setEditedValues({});
    setEditedPrevValues({});
    setMismatch({ open: false, deltaCur: 0, deltaPrev: 0 });
    setShowValidationMessage(false);
    setToggle?.(false);
  };

  const undoEdit = () => {
    blurAllEditableInputs();
    setEditedValues({});
    setEditedPrevValues({});
    setCommittedValues({ ...originalBaselineRef.current.cur });
    setCommittedPrevValues({ ...originalBaselineRef.current.prev });
    setMismatch({ open: false, deltaCur: 0, deltaPrev: 0 });
    setShowValidationMessage(false);
  };

  const approveEdit = () => {
    const redCurCalc  = redCur;
    const redPrevCalc = redPrev;

    const deltaCur  = redCurCalc  - brBookValueUBCur;
    const deltaPrev = redPrevCalc - brBookValueUBPrev;

    const hasMismatch = Math.round(deltaCur) !== 0 || Math.round(deltaPrev) !== 0;

    if (hasMismatch) {
      setMismatch({ open: true, deltaCur, deltaPrev });
      setShowValidationMessage(true);
      return;
    }

    setCommittedValues(prev => ({ ...prev, ...editedValues }));
    setCommittedPrevValues(prev => ({ ...prev, ...editedPrevValues }));
    setEditedValues({});
    setEditedPrevValues({});
    setMismatch({ open: false, deltaCur: 0, deltaPrev: 0 });
    setShowValidationMessage(false);
    setIsEditing(false);
    setToggle?.(false);
  };

  // Helper functions
  const isSumRow = (it: NoterItem) => it.style === 'S2';
  const isHeading = (it: NoterItem) => isHeadingStyle(it.style);

  const sumGroupAbove = React.useCallback(
    (list: NoterItem[], index: number, year: 'cur' | 'prev') => {
      let sum = 0;
      for (let i = index - 1; i >= 0; i--) {
        const r = list[i];
        if (!r) break;
        if (isHeading(r) || r.style === 'S2') break;
        if (r.variable_name) sum += getVal(r.variable_name, year);
      }
      return sum;
    },
    [getVal]
  );

  const containerRef = React.useRef<HTMLDivElement>(null);

  const focusByOrd = (fromEl: HTMLInputElement, dir: 1 | -1) => {
    const root = containerRef.current;
    if (!root) return;
    const curOrd = Number(fromEl.dataset.ord || '0');
    const nextOrd = curOrd + dir;
    const next = root.querySelector<HTMLInputElement>(
      `input[data-editable-cell="1"][data-ord="${nextOrd}"]`
    );
    if (next) { next.focus(); next.select?.(); }
  };

  const blurAllEditableInputs = () => {
    const root = containerRef.current;
    if (!root) return;
    const nodes = root.querySelectorAll<HTMLInputElement>('input[data-editable-cell="1"]');
    nodes.forEach((el) => el.blur());
  };

  const pushSignNotice = (e: any) => {
    console.log(`Sign forced for ${e.label} (${e.year}): ${e.typed} → ${e.adjusted}`);
  };

  // Helper: get the dynamic S2 subtotal for MAT UB rows
  const ubSum = React.useCallback((ubVar: string, year: 'cur' | 'prev') => {
    const v = (name: string) => getVal(name, year) || 0;
    const idx = visible.findIndex(r => r.variable_name === ubVar);
    if (idx !== -1 && visible[idx]?.style === 'S2') {
      return sumGroupAbove(visible, idx, year);
    }
    // Fallbacks if the UB row isn't visible:
    switch (ubVar) {
      case 'ovrmat_ub':
        return v('ovrmat_ib') + v('arets_inkop_ovrmat') + v('arets_fsg_ovrmat') + v('arets_omklass_ovrmat');
      case 'ack_avskr_ovrmat_ub':
        return v('ack_avskr_ovrmat_ib') + v('arets_avskr_ovrmat') + v('aterfor_avskr_fsg_ovrmat') + v('omklass_avskr_ovrmat');
      case 'ack_nedskr_ovrmat_ub':
        return v('ack_nedskr_ovrmat_ib') + v('arets_nedskr_ovrmat') + v('aterfor_nedskr_fsg_ovrmat') + v('aterfor_nedskr_ovrmat') + v('omklass_nedskr_ovrmat');
      default:
        return getVal(ubVar, year);
    }
  }, [visible, sumGroupAbove, getVal]);

  // Sum the actual S2 subtotals for MAT (no uppskrivningar)
  const redCur  = ['ovrmat_ub','ack_avskr_ovrmat_ub','ack_nedskr_ovrmat_ub']
    .map(n => ubSum(n, 'cur'))
    .reduce((a,b) => a + b, 0);

  const redPrev = ['ovrmat_ub','ack_avskr_ovrmat_ub','ack_nedskr_ovrmat_ub']
    .map(n => ubSum(n, 'prev'))
    .reduce((a,b) => a + b, 0);

  return (
    <div ref={containerRef} className="space-y-2 pt-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b pb-1">
        <div className="flex items-center gap-3">
          <h3 className="text-lg font-semibold pt-1">{heading}</h3>
          <button
            onClick={() => isEditing ? cancelEdit() : startEdit()}
            className={`w-6 h-6 rounded-full flex items-center justify-center transition-colors ${
              isEditing ? 'bg-blue-600 text-white' : 'bg-gray-200 hover:bg-gray-300 text-gray-600'
            }`}
            title={isEditing ? 'Avsluta redigering' : 'Redigera värden'}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                    d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
            </svg>
          </button>
        </div>
        <div className="flex items-center space-x-2">
          <label htmlFor="toggle-mat-rows" className="text-sm font-medium cursor-pointer">
            Visa alla rader
          </label>
          <Switch
            id="toggle-mat-rows"
            checked={toggleOn}
            onCheckedChange={setToggle}
          />
        </div>
      </div>

      {/* Column headers */}
      <div className="grid gap-4 text-sm text-muted-foreground border-b pb-1 font-semibold" style={gridCols}>
        <span></span>
        <span className="text-right">{companyData?.currentPeriodEndDate || `${fiscalYear ?? new Date().getFullYear()}-12-31`}</span>
        <span className="text-right">{companyData?.previousPeriodEndDate || `${(previousYear ?? (fiscalYear ? fiscalYear - 1 : new Date().getFullYear() - 1))}-12-31`}</span>
      </div>

      {/* Rows */}
      {(() => {
        let ordCounter = 0;
        return visible.map((it, idx) => {
          const getStyleClasses = (style?: string) => {
            const baseClasses = 'grid gap-4';
            let additionalClasses = '';
            const s = style || 'NORMAL';
            
            const boldStyles = ['H0','H1','H2','H3','S1','S2','S3','TH0','TH1','TH2','TH3','TS1','TS2','TS3'];
            if (boldStyles.includes(s)) {
              additionalClasses += ' font-semibold';
            }
            
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
          const isHeadingRow = isHeadingStyle(currentStyle);
          const isS2 = isSumRow(it);
          const editable = isEditing && isFlowVar(it.variable_name);
          
          const ordCur  = editable ? ++ordCounter : undefined;
          const ordPrev = editable ? ++ordCounter : undefined;
          
          const isRedVardeRow = it.variable_name === "red_varde_ovrmat";
          
          const curVal = isRedVardeRow
            ? redCur
            : (isS2 ? sumGroupAbove(visible, idx, 'cur') : getVal(it.variable_name ?? '', 'cur'));
          const prevVal = isRedVardeRow
            ? redPrev
            : (isS2 ? sumGroupAbove(visible, idx, 'prev') : getVal(it.variable_name ?? '', 'prev'));

          const curMismatch  = isEditing && isRedVardeRow && Math.round(redCur)  !== Math.round(brBookValueUBCur);
          const prevMismatch = isEditing && isRedVardeRow && Math.round(redPrev) !== Math.round(brBookValueUBPrev);
          
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
              <span className={`text-right font-medium ${isRedVardeRow && curMismatch ? 'text-red-600 font-bold' : ''}`}>
                {isHeadingRow ? '' : isRedVardeRow
                  ? `${numberToSv(curVal)} kr`
                  : <AmountCell
                      year="cur"
                      varName={it.variable_name!}
                      baseVar={it.variable_name!}
                      label={it.row_title}
                      editable={editable}
                      value={curVal}
                      ord={ordCur}
                      onCommit={(n) => setEditedValues(p => ({ ...p, [it.variable_name!]: n }))}
                      onTabNavigate={(el, dir) => focusByOrd(el, dir)}
                      onSignForced={(e) => pushSignNotice(e)}
                      expectedSignFor={expectedSignFor}
                    />
                }
              </span>

              {/* Previous year */}
              <span className={`text-right font-medium ${isRedVardeRow && prevMismatch ? 'text-red-600 font-bold' : ''}`}>
                {isHeadingRow ? '' : isRedVardeRow
                  ? `${numberToSv(prevVal)} kr`
                  : <AmountCell
                      year="prev"
                      varName={`${it.variable_name!}_prev`}
                      baseVar={it.variable_name!}
                      label={it.row_title}
                      editable={editable}
                      value={prevVal}
                      ord={ordPrev}
                      onCommit={(n) => setEditedPrevValues(p => ({ ...p, [it.variable_name!]: n }))}
                      onTabNavigate={(el, dir) => focusByOrd(el, dir)}
                      onSignForced={(e) => pushSignNotice(e)}
                      expectedSignFor={expectedSignFor}
                    />
                }
              </span>
            </div>
          );
        });
      })()}

      {/* Comparison row – only while editing */}
      {isEditing && (
        <div className="grid gap-4 border-t border-b border-gray-200 pt-1 pb-1 font-semibold bg-gray-50/50" style={gridCols}>
          <span className="text-muted-foreground font-semibold">Redovisat värde (bokfört)</span>
          <span className="text-right font-medium">{numberToSv(brBookValueUBCur)} kr</span>
          <span className="text-right font-medium">{numberToSv(brBookValueUBPrev)} kr</span>
        </div>
      )}

      {/* Action buttons */}
      {isEditing && (
        <div className="pt-4 flex justify-between">
          <Button 
            onClick={undoEdit}
            variant="outline"
            className="flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"/>
            </svg>
            Ångra ändringar
          </Button>
          
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

      {/* Toast Notification */}
      {showValidationMessage && (
        <div className="fixed bottom-4 right-4 z-50 bg-white rounded-lg shadow-lg p-4 max-w-sm animate-in slide-in-from-bottom-2">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <svg className="w-5 h-5 text-red-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                      d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </div>
            <div className="ml-3">
              {(() => {
                const curMism = Math.round(mismatch.deltaCur) !== 0;
                const prevMism = Math.round(mismatch.deltaPrev) !== 0;
                
                if (curMism && !prevMism) {
                  return (
                    <>
                      <p className="text-sm font-medium text-gray-900">
                        Summor balanserar inte {fiscalYear}
                      </p>
                      <p className="mt-1 text-sm text-gray-700">
                        Beräknat redovisat värde stämmer inte med bokfört värde. Differensen är {numberToSv(Math.abs(Math.round(mismatch.deltaCur)))} kr.
                      </p>
                    </>
                  );
                } else if (prevMism && !curMism) {
                  return (
                    <>
                      <p className="text-sm font-medium text-gray-900">
                        Summor balanserar inte {previousYear}
                      </p>
                      <p className="mt-1 text-sm text-gray-700">
                        Beräknat redovisat värde stämmer inte med bokfört värde. Differensen är {numberToSv(Math.abs(Math.round(mismatch.deltaPrev)))} kr.
                      </p>
                    </>
                  );
                } else {
                  return (
                    <>
                      <p className="text-sm font-medium text-gray-900">
                        Summor balanserar inte
                      </p>
                      <p className="mt-1 text-sm text-gray-700">
                        Beräknat redovisat värde stämmer inte med bokfört värde.
                      </p>
                      <ul className="mt-2 text-sm text-gray-900">
                        <li><strong>{fiscalYear}</strong>: Differens {numberToSv(Math.abs(Math.round(mismatch.deltaCur)))} kr</li>
                        <li><strong>{previousYear}</strong>: Differens {numberToSv(Math.abs(Math.round(mismatch.deltaPrev)))} kr</li>
                      </ul>
                    </>
                  );
                }
              })()}
            </div>
            <button
              onClick={() => { setShowValidationMessage(false); setMismatch(m => ({ ...m, open: false })); }}
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

// Koncern editor component
const KoncernNote: React.FC<{
  items: NoterItem[];
  heading: string;
  fiscalYear?: number;
  previousYear?: number;
  companyData?: any;
  toggleOn: boolean;
  setToggle: (checked: boolean) => void;
}> = ({ items, heading, fiscalYear, previousYear, companyData, toggleOn, setToggle }) => {
  const gridCols = { gridTemplateColumns: "4fr 1fr 1fr" };

  const isFlowVar = (vn?: string) => {
    if (!vn) return false;
    if (/_ib\b/i.test(vn)) return false;
    if (/_ub\b/i.test(vn)) return false;
    if (/red[_-]?varde/i.test(vn)) return false;
    return true;
  };

  const byVar = useMemo(() => {
    const m = new Map<string, NoterItem>();
    items.forEach((it) => it.variable_name && m.set(it.variable_name, it));
    return m;
  }, [items]);

  // BR book value (UB) for both years - KONCERN specific
  const { brBookValueUBCur, brBookValueUBPrev } = React.useMemo(() => {
    const brData: any[] = companyData?.seFileData?.br_data || [];
    const candidates = [
      "AndelarKoncernforetag",
      "AndelarKoncern",
      "Koncernforetag",
    ];
    let cur = 0, prev = 0;

    for (const c of candidates) {
      const hit = brData.find((x: any) => x.variable_name === c);
      if (hit) {
        if (Number.isFinite(hit.current_amount))  cur  = hit.current_amount;
        if (Number.isFinite(hit.previous_amount)) prev = hit.previous_amount;
        if (cur || prev) break;
      }
    }

    if (!cur)  cur  = byVar.get("red_varde_koncern")?.current_amount  ?? 0;
    if (!prev) prev = byVar.get("red_varde_koncern")?.previous_amount ?? 0;

    return { brBookValueUBCur: cur, brBookValueUBPrev: prev };
  }, [companyData, byVar]);

  // Baseline management
  const originalBaselineRef = React.useRef<{cur: Record<string, number>, prev: Record<string, number>}>({cur:{}, prev:{}});
  React.useEffect(() => {
    const cur: Record<string, number> = {};
    const prev: Record<string, number> = {};
    items.forEach(it => {
      const vn = it.variable_name;
      if (!vn) return;
      if (!isFlowVar(vn)) return;
      cur[vn] = it.current_amount ?? 0;
      prev[vn] = it.previous_amount ?? 0;
    });
    originalBaselineRef.current = { cur, prev };
  }, [items]);

  // Local edit state
  const [isEditing, setIsEditing] = useState(false);
  const [editedValues, setEditedValues] = useState<Record<string, number>>({});
  const [editedPrevValues, setEditedPrevValues] = useState<Record<string, number>>({});
  const [committedValues, setCommittedValues] = useState<Record<string, number>>({});
  const [committedPrevValues, setCommittedPrevValues] = useState<Record<string, number>>({});
  const [mismatch, setMismatch] = useState<{ open: boolean; deltaCur: number; deltaPrev: number }>({
    open: false,
    deltaCur: 0,
    deltaPrev: 0,
  });
  const [showValidationMessage, setShowValidationMessage] = useState(false);

  // Sign enforcement from CSV mapping - KONCERN specific
  const injectedSignMap: Record<string, '+' | '-'> | undefined = (companyData?.signByVar) || undefined;

  const heuristicSign = (vn: string): '+' | '-' | null => {
    // Based on variable_mapping_noter_rows (KONCERN).csv
    const positiveVars = [
      'inkop_koncern',
      'aktieagartillskott_lamnad_koncern',
      'aterfor_nedskr_fusion_koncern',
      'aterfor_nedskr_fsg_koncern',
      'aterfor_nedskr_koncern'
    ];
    
    const negativeVars = [
      'fsg_koncern',
      'aktieagartillskott_aterbetald_koncern',
      'arets_nedskr_koncern'
    ];
    
    // Flexible variables
    const flexibleVars = [
      'fusion_koncern',           // No +/- in CSV
      'resultatandel_koncern',    // No +/- in CSV
      'omklass_koncern',          // No +/- in CSV
      'omklass_nedskr_koncern'    // No +/- in CSV
    ];
    
    if (positiveVars.includes(vn)) return '+';
    if (negativeVars.includes(vn)) return '-';
    return null; // flexible
  };

  const expectedSignFor = (vn?: string): '+' | '-' | null => {
    if (!vn) return null;
    return injectedSignMap?.[vn] ?? heuristicSign(vn);
  };

  const getVal = React.useCallback((vn: string, year: 'cur' | 'prev') => {
    if (year === 'cur') {
      if (editedValues[vn] !== undefined) return editedValues[vn];
      if (committedValues[vn] !== undefined) return committedValues[vn];
      return byVar.get(vn)?.current_amount ?? 0;
    } else {
      if (editedPrevValues[vn] !== undefined) return editedPrevValues[vn];
      if (committedPrevValues[vn] !== undefined) return committedPrevValues[vn];
      return byVar.get(vn)?.previous_amount ?? 0;
    }
  }, [editedValues, committedValues, editedPrevValues, committedPrevValues, byVar]);

  const readCur = (it: NoterItem) => getVal(it.variable_name!, 'cur');
  const readPrev = (it: NoterItem) => getVal(it.variable_name!, 'prev');

  const visible = useMemo(() => {
    return buildVisibleWithHeadings({
      items,
      toggleOn,
      readCur: (it) => readCur(it),
      readPrev: (it) => readPrev(it),
    });
  }, [items, toggleOn, editedValues, editedPrevValues, committedValues, committedPrevValues]);

  const startEdit = () => {
    setIsEditing(true);
    setToggle?.(true);
  };

  React.useEffect(() => {
    if (showValidationMessage) {
      const timer = setTimeout(() => setShowValidationMessage(false), 5000);
      return () => clearTimeout(timer);
    }
  }, [showValidationMessage]);

  const cancelEdit = () => {
    setIsEditing(false);
    setEditedValues({});
    setEditedPrevValues({});
    setMismatch({ open: false, deltaCur: 0, deltaPrev: 0 });
    setShowValidationMessage(false);
    setToggle?.(false);
  };

  const undoEdit = () => {
    blurAllEditableInputs();
    setEditedValues({});
    setEditedPrevValues({});
    setCommittedValues({ ...originalBaselineRef.current.cur });
    setCommittedPrevValues({ ...originalBaselineRef.current.prev });
    setMismatch({ open: false, deltaCur: 0, deltaPrev: 0 });
    setShowValidationMessage(false);
  };

  const approveEdit = () => {
    const redCurCalc  = redCur;
    const redPrevCalc = redPrev;

    const deltaCur  = redCurCalc  - brBookValueUBCur;
    const deltaPrev = redPrevCalc - brBookValueUBPrev;

    const hasMismatch = Math.round(deltaCur) !== 0 || Math.round(deltaPrev) !== 0;

    if (hasMismatch) {
      setMismatch({ open: true, deltaCur, deltaPrev });
      setShowValidationMessage(true);
      return;
    }

    setCommittedValues(prev => ({ ...prev, ...editedValues }));
    setCommittedPrevValues(prev => ({ ...prev, ...editedPrevValues }));
    setEditedValues({});
    setEditedPrevValues({});
    setMismatch({ open: false, deltaCur: 0, deltaPrev: 0 });
    setShowValidationMessage(false);
    setIsEditing(false);
    setToggle?.(false);
  };

  // Helper functions
  const isSumRow = (it: NoterItem) => it.style === 'S2';
  const isHeading = (it: NoterItem) => isHeadingStyle(it.style);

  const sumGroupAbove = React.useCallback(
    (list: NoterItem[], index: number, year: 'cur' | 'prev') => {
      let sum = 0;
      for (let i = index - 1; i >= 0; i--) {
        const r = list[i];
        if (!r) break;
        if (isHeading(r) || r.style === 'S2') break;
        if (r.variable_name) sum += getVal(r.variable_name, year);
      }
      return sum;
    },
    [getVal]
  );

  const containerRef = React.useRef<HTMLDivElement>(null);

  const focusByOrd = (fromEl: HTMLInputElement, dir: 1 | -1) => {
    const root = containerRef.current;
    if (!root) return;
    const curOrd = Number(fromEl.dataset.ord || '0');
    const nextOrd = curOrd + dir;
    const next = root.querySelector<HTMLInputElement>(
      `input[data-editable-cell="1"][data-ord="${nextOrd}"]`
    );
    if (next) { next.focus(); next.select?.(); }
  };

  const blurAllEditableInputs = () => {
    const root = containerRef.current;
    if (!root) return;
    const nodes = root.querySelectorAll<HTMLInputElement>('input[data-editable-cell="1"]');
    nodes.forEach((el) => el.blur());
  };

  const pushSignNotice = (e: any) => {
    console.log(`Sign forced for ${e.label} (${e.year}): ${e.typed} → ${e.adjusted}`);
  };

  // Helper: get the dynamic S2 subtotal for KONCERN UB rows
  const ubSum = React.useCallback((ubVar: string, year: 'cur' | 'prev') => {
    const v = (name: string) => getVal(name, year) || 0;
    const idx = visible.findIndex(r => r.variable_name === ubVar);
    if (idx !== -1 && visible[idx]?.style === 'S2') {
      return sumGroupAbove(visible, idx, year);
    }
    // Fallbacks if the UB row isn't visible:
    switch (ubVar) {
      case 'koncern_ub':
        return v('koncern_ib') + v('inkop_koncern') + v('fusion_koncern') + v('fsg_koncern') + v('aktieagartillskott_lamnad_koncern') + v('aktieagartillskott_aterbetald_koncern') + v('resultatandel_koncern') + v('omklass_koncern');
      case 'ack_nedskr_koncern_ub':
        return v('ack_nedskr_koncern_ib') + v('aterfor_nedskr_fusion_koncern') + v('aterfor_nedskr_fsg_koncern') + v('aterfor_nedskr_koncern') + v('omklass_nedskr_koncern') + v('arets_nedskr_koncern');
      default:
        return getVal(ubVar, year);
    }
  }, [visible, sumGroupAbove, getVal]);

  // Sum the actual S2 subtotals for KONCERN (anskaffning + nedskrivningar only)
  const redCur  = ['koncern_ub','ack_nedskr_koncern_ub']
    .map(n => ubSum(n, 'cur'))
    .reduce((a,b) => a + b, 0);

  const redPrev = ['koncern_ub','ack_nedskr_koncern_ub']
    .map(n => ubSum(n, 'prev'))
    .reduce((a,b) => a + b, 0);

  return (
    <div ref={containerRef} className="space-y-2 pt-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b pb-1">
        <div className="flex items-center gap-3">
          <h3 className="text-lg font-semibold pt-1">{heading}</h3>
          <button
            onClick={() => isEditing ? cancelEdit() : startEdit()}
            className={`w-6 h-6 rounded-full flex items-center justify-center transition-colors ${
              isEditing ? 'bg-blue-600 text-white' : 'bg-gray-200 hover:bg-gray-300 text-gray-600'
            }`}
            title={isEditing ? 'Avsluta redigering' : 'Redigera värden'}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                    d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
            </svg>
          </button>
        </div>
        <div className="flex items-center space-x-2">
          <label htmlFor="toggle-koncern-rows" className="text-sm font-medium cursor-pointer">
            Visa alla rader
          </label>
          <Switch
            id="toggle-koncern-rows"
            checked={toggleOn}
            onCheckedChange={setToggle}
          />
        </div>
      </div>

      {/* Column headers */}
      <div className="grid gap-4 text-sm text-muted-foreground border-b pb-1 font-semibold" style={gridCols}>
        <span></span>
        <span className="text-right">{companyData?.currentPeriodEndDate || `${fiscalYear ?? new Date().getFullYear()}-12-31`}</span>
        <span className="text-right">{companyData?.previousPeriodEndDate || `${(previousYear ?? (fiscalYear ? fiscalYear - 1 : new Date().getFullYear() - 1))}-12-31`}</span>
      </div>

      {/* Rows */}
      {(() => {
        let ordCounter = 0;
        return visible.map((it, idx) => {
          const getStyleClasses = (style?: string) => {
            const baseClasses = 'grid gap-4';
            let additionalClasses = '';
            const s = style || 'NORMAL';
            
            const boldStyles = ['H0','H1','H2','H3','S1','S2','S3','TH0','TH1','TH2','TH3','TS1','TS2','TS3'];
            if (boldStyles.includes(s)) {
              additionalClasses += ' font-semibold';
            }
            
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
          const isHeadingRow = isHeadingStyle(currentStyle);
          const isS2 = isSumRow(it);
          const editable = isEditing && isFlowVar(it.variable_name);
          
          const ordCur  = editable ? ++ordCounter : undefined;
          const ordPrev = editable ? ++ordCounter : undefined;
          
          const isRedVardeRow = it.variable_name === "red_varde_koncern";
          
          const curVal = isRedVardeRow
            ? redCur
            : (isS2 ? sumGroupAbove(visible, idx, 'cur') : getVal(it.variable_name ?? '', 'cur'));
          const prevVal = isRedVardeRow
            ? redPrev
            : (isS2 ? sumGroupAbove(visible, idx, 'prev') : getVal(it.variable_name ?? '', 'prev'));

          const curMismatch  = isEditing && isRedVardeRow && Math.round(redCur)  !== Math.round(brBookValueUBCur);
          const prevMismatch = isEditing && isRedVardeRow && Math.round(redPrev) !== Math.round(brBookValueUBPrev);
          
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
              <span className={`text-right font-medium ${isRedVardeRow && curMismatch ? 'text-red-600 font-bold' : ''}`}>
                {isHeadingRow ? '' : isRedVardeRow
                  ? `${numberToSv(curVal)} kr`
                  : <AmountCell
                      year="cur"
                      varName={it.variable_name!}
                      baseVar={it.variable_name!}
                      label={it.row_title}
                      editable={editable}
                      value={curVal}
                      ord={ordCur}
                      onCommit={(n) => setEditedValues(p => ({ ...p, [it.variable_name!]: n }))}
                      onTabNavigate={(el, dir) => focusByOrd(el, dir)}
                      onSignForced={(e) => pushSignNotice(e)}
                      expectedSignFor={expectedSignFor}
                    />
                }
              </span>

              {/* Previous year */}
              <span className={`text-right font-medium ${isRedVardeRow && prevMismatch ? 'text-red-600 font-bold' : ''}`}>
                {isHeadingRow ? '' : isRedVardeRow
                  ? `${numberToSv(prevVal)} kr`
                  : <AmountCell
                      year="prev"
                      varName={`${it.variable_name!}_prev`}
                      baseVar={it.variable_name!}
                      label={it.row_title}
                      editable={editable}
                      value={prevVal}
                      ord={ordPrev}
                      onCommit={(n) => setEditedPrevValues(p => ({ ...p, [it.variable_name!]: n }))}
                      onTabNavigate={(el, dir) => focusByOrd(el, dir)}
                      onSignForced={(e) => pushSignNotice(e)}
                      expectedSignFor={expectedSignFor}
                    />
                }
              </span>
            </div>
          );
        });
      })()}

      {/* Comparison row – only while editing */}
      {isEditing && (
        <div className="grid gap-4 border-t border-b border-gray-200 pt-1 pb-1 font-semibold bg-gray-50/50" style={gridCols}>
          <span className="text-muted-foreground font-semibold">Redovisat värde (bokfört)</span>
          <span className="text-right font-medium">{numberToSv(brBookValueUBCur)} kr</span>
          <span className="text-right font-medium">{numberToSv(brBookValueUBPrev)} kr</span>
        </div>
      )}

      {/* Action buttons */}
      {isEditing && (
        <div className="pt-4 flex justify-between">
          <Button 
            onClick={undoEdit}
            variant="outline"
            className="flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"/>
            </svg>
            Ångra ändringar
          </Button>
          
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

      {/* Toast Notification */}
      {showValidationMessage && (
        <div className="fixed bottom-4 right-4 z-50 bg-white rounded-lg shadow-lg p-4 max-w-sm animate-in slide-in-from-bottom-2">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <svg className="w-5 h-5 text-red-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                      d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </div>
            <div className="ml-3">
              {(() => {
                const curMism = Math.round(mismatch.deltaCur) !== 0;
                const prevMism = Math.round(mismatch.deltaPrev) !== 0;
                
                if (curMism && !prevMism) {
                  return (
                    <>
                      <p className="text-sm font-medium text-gray-900">
                        Summor balanserar inte {fiscalYear}
                      </p>
                      <p className="mt-1 text-sm text-gray-700">
                        Beräknat redovisat värde stämmer inte med bokfört värde. Differensen är {numberToSv(Math.abs(Math.round(mismatch.deltaCur)))} kr.
                      </p>
                    </>
                  );
                } else if (prevMism && !curMism) {
                  return (
                    <>
                      <p className="text-sm font-medium text-gray-900">
                        Summor balanserar inte {previousYear}
                      </p>
                      <p className="mt-1 text-sm text-gray-700">
                        Beräknat redovisat värde stämmer inte med bokfört värde. Differensen är {numberToSv(Math.abs(Math.round(mismatch.deltaPrev)))} kr.
                      </p>
                    </>
                  );
                } else {
                  return (
                    <>
                      <p className="text-sm font-medium text-gray-900">
                        Summor balanserar inte
                      </p>
                      <p className="mt-1 text-sm text-gray-700">
                        Beräknat redovisat värde stämmer inte med bokfört värde.
                      </p>
                      <ul className="mt-2 text-sm text-gray-900">
                        <li><strong>{fiscalYear}</strong>: Differens {numberToSv(Math.abs(Math.round(mismatch.deltaCur)))} kr</li>
                        <li><strong>{previousYear}</strong>: Differens {numberToSv(Math.abs(Math.round(mismatch.deltaPrev)))} kr</li>
                      </ul>
                    </>
                  );
                }
              })()}
            </div>
            <button
              onClick={() => { setShowValidationMessage(false); setMismatch(m => ({ ...m, open: false })); }}
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

// Intresseföretag editor component
const IntresseforetagNote: React.FC<{
  items: NoterItem[];
  heading: string;
  fiscalYear?: number;
  previousYear?: number;
  companyData?: any;
  toggleOn: boolean;
  setToggle: (checked: boolean) => void;
}> = ({ items, heading, fiscalYear, previousYear, companyData, toggleOn, setToggle }) => {
  const gridCols = { gridTemplateColumns: "4fr 1fr 1fr" };

  const isFlowVar = (vn?: string) => {
    if (!vn) return false;
    if (/_ib\b/i.test(vn)) return false;
    if (/_ub\b/i.test(vn)) return false;
    if (/red[_-]?varde/i.test(vn)) return false;
    return true;
  };

  const byVar = useMemo(() => {
    const m = new Map<string, NoterItem>();
    items.forEach((it) => it.variable_name && m.set(it.variable_name, it));
    return m;
  }, [items]);

  // BR book value (UB) for both years - INTRESSEFTG specific
  const { brBookValueUBCur, brBookValueUBPrev } = React.useMemo(() => {
    const brData: any[] = companyData?.seFileData?.br_data || [];
    const candidates = [
      "AndelarIntresseforetagGemensamtStyrdaForetag",
      "AndelarIntresseforetag",
      "Intresseforetag",
    ];
    let cur = 0, prev = 0;

    for (const c of candidates) {
      const hit = brData.find((x: any) => x.variable_name === c);
      if (hit) {
        if (Number.isFinite(hit.current_amount))  cur  = hit.current_amount;
        if (Number.isFinite(hit.previous_amount)) prev = hit.previous_amount;
        if (cur || prev) break;
      }
    }

    if (!cur)  cur  = byVar.get("red_varde_intresseftg")?.current_amount  ?? 0;
    if (!prev) prev = byVar.get("red_varde_intresseftg")?.previous_amount ?? 0;

    return { brBookValueUBCur: cur, brBookValueUBPrev: prev };
  }, [companyData, byVar]);

  // Baseline management
  const originalBaselineRef = React.useRef<{cur: Record<string, number>, prev: Record<string, number>}>({cur:{}, prev:{}});
  React.useEffect(() => {
    const cur: Record<string, number> = {};
    const prev: Record<string, number> = {};
    items.forEach(it => {
      const vn = it.variable_name;
      if (!vn) return;
      if (!isFlowVar(vn)) return;
      cur[vn] = it.current_amount ?? 0;
      prev[vn] = it.previous_amount ?? 0;
    });
    originalBaselineRef.current = { cur, prev };
  }, [items]);

  // Local edit state
  const [isEditing, setIsEditing] = useState(false);
  const [editedValues, setEditedValues] = useState<Record<string, number>>({});
  const [editedPrevValues, setEditedPrevValues] = useState<Record<string, number>>({});
  const [committedValues, setCommittedValues] = useState<Record<string, number>>({});
  const [committedPrevValues, setCommittedPrevValues] = useState<Record<string, number>>({});
  const [mismatch, setMismatch] = useState<{ open: boolean; deltaCur: number; deltaPrev: number }>({
    open: false,
    deltaCur: 0,
    deltaPrev: 0,
  });
  const [showValidationMessage, setShowValidationMessage] = useState(false);

  // Sign enforcement from CSV mapping - INTRESSEFTG specific
  const injectedSignMap: Record<string, '+' | '-'> | undefined = (companyData?.signByVar) || undefined;

  const heuristicSign = (vn: string): '+' | '-' | null => {
    // Based on variable_mapping_noter_rows (intftg).csv
    const positiveVars = [
      'inkop_intresseftg',
      'fusion_intresseftg',
      'aktieagartillskott_lamnad_intresseftg',
      'aterfor_nedskr_fusion_intresseftg',
      'aterfor_nedskr_fsg_intresseftg',
      'aterfor_nedskr_intresseftg'
    ];
    
    const negativeVars = [
      'fsg_intresseftg',
      'aktieagartillskott_aterbetald_intresseftg',
      'arets_nedskr_intresseftg'
    ];
    
    // Flexible variables
    const flexibleVars = [
      'resultatandel_intresseftg',    // No +/- in CSV
      'omklass_intresseftg',          // No +/- in CSV
      'omklass_nedskr_intresseftg'    // No +/- in CSV
    ];
    
    if (positiveVars.includes(vn)) return '+';
    if (negativeVars.includes(vn)) return '-';
    return null; // flexible
  };

  const expectedSignFor = (vn?: string): '+' | '-' | null => {
    if (!vn) return null;
    return injectedSignMap?.[vn] ?? heuristicSign(vn);
  };

  const getVal = React.useCallback((vn: string, year: 'cur' | 'prev') => {
    if (year === 'cur') {
      if (editedValues[vn] !== undefined) return editedValues[vn];
      if (committedValues[vn] !== undefined) return committedValues[vn];
      return byVar.get(vn)?.current_amount ?? 0;
    } else {
      if (editedPrevValues[vn] !== undefined) return editedPrevValues[vn];
      if (committedPrevValues[vn] !== undefined) return committedPrevValues[vn];
      return byVar.get(vn)?.previous_amount ?? 0;
    }
  }, [editedValues, committedValues, editedPrevValues, committedPrevValues, byVar]);

  const readCur = (it: NoterItem) => getVal(it.variable_name!, 'cur');
  const readPrev = (it: NoterItem) => getVal(it.variable_name!, 'prev');

  const visible = useMemo(() => {
    return buildVisibleWithHeadings({
      items,
      toggleOn,
      readCur: (it) => readCur(it),
      readPrev: (it) => readPrev(it),
    });
  }, [items, toggleOn, editedValues, editedPrevValues, committedValues, committedPrevValues]);

  const startEdit = () => {
    setIsEditing(true);
    setToggle?.(true);
  };

  React.useEffect(() => {
    if (showValidationMessage) {
      const timer = setTimeout(() => setShowValidationMessage(false), 5000);
      return () => clearTimeout(timer);
    }
  }, [showValidationMessage]);

  const cancelEdit = () => {
    setIsEditing(false);
    setEditedValues({});
    setEditedPrevValues({});
    setMismatch({ open: false, deltaCur: 0, deltaPrev: 0 });
    setShowValidationMessage(false);
    setToggle?.(false);
  };

  const undoEdit = () => {
    blurAllEditableInputs();
    setEditedValues({});
    setEditedPrevValues({});
    setCommittedValues({ ...originalBaselineRef.current.cur });
    setCommittedPrevValues({ ...originalBaselineRef.current.prev });
    setMismatch({ open: false, deltaCur: 0, deltaPrev: 0 });
    setShowValidationMessage(false);
  };

  const approveEdit = () => {
    const redCurCalc  = redCur;
    const redPrevCalc = redPrev;

    const deltaCur  = redCurCalc  - brBookValueUBCur;
    const deltaPrev = redPrevCalc - brBookValueUBPrev;

    const hasMismatch = Math.round(deltaCur) !== 0 || Math.round(deltaPrev) !== 0;

    if (hasMismatch) {
      setMismatch({ open: true, deltaCur, deltaPrev });
      setShowValidationMessage(true);
      return;
    }

    setCommittedValues(prev => ({ ...prev, ...editedValues }));
    setCommittedPrevValues(prev => ({ ...prev, ...editedPrevValues }));
    setEditedValues({});
    setEditedPrevValues({});
    setMismatch({ open: false, deltaCur: 0, deltaPrev: 0 });
    setShowValidationMessage(false);
    setIsEditing(false);
    setToggle?.(false);
  };

  // Helper functions
  const isSumRow = (it: NoterItem) => it.style === 'S2';
  const isHeading = (it: NoterItem) => isHeadingStyle(it.style);

  const sumGroupAbove = React.useCallback(
    (list: NoterItem[], index: number, year: 'cur' | 'prev') => {
      let sum = 0;
      for (let i = index - 1; i >= 0; i--) {
        const r = list[i];
        if (!r) break;
        if (isHeading(r) || r.style === 'S2') break;
        if (r.variable_name) sum += getVal(r.variable_name, year);
      }
      return sum;
    },
    [getVal]
  );

  const containerRef = React.useRef<HTMLDivElement>(null);

  const focusByOrd = (fromEl: HTMLInputElement, dir: 1 | -1) => {
    const root = containerRef.current;
    if (!root) return;
    const curOrd = Number(fromEl.dataset.ord || '0');
    const nextOrd = curOrd + dir;
    const next = root.querySelector<HTMLInputElement>(
      `input[data-editable-cell="1"][data-ord="${nextOrd}"]`
    );
    if (next) { next.focus(); next.select?.(); }
  };

  const blurAllEditableInputs = () => {
    const root = containerRef.current;
    if (!root) return;
    const nodes = root.querySelectorAll<HTMLInputElement>('input[data-editable-cell="1"]');
    nodes.forEach((el) => el.blur());
  };

  const pushSignNotice = (e: any) => {
    console.log(`Sign forced for ${e.label} (${e.year}): ${e.typed} → ${e.adjusted}`);
  };

  // Helper: get the dynamic S2 subtotal for INTRESSEFTG UB rows
  const ubSum = React.useCallback((ubVar: string, year: 'cur' | 'prev') => {
    const v = (name: string) => getVal(name, year) || 0;
    const idx = visible.findIndex(r => r.variable_name === ubVar);
    if (idx !== -1 && visible[idx]?.style === 'S2') {
      return sumGroupAbove(visible, idx, year);
    }
    // Fallbacks if the UB row isn't visible:
    switch (ubVar) {
      case 'intresseftg_ub':
        return v('intresseftg_ib') + v('inkop_intresseftg') + v('fusion_intresseftg') + v('fsg_intresseftg') + v('aktieagartillskott_lamnad_intresseftg') + v('aktieagartillskott_aterbetald_intresseftg') + v('resultatandel_intresseftg') + v('omklass_intresseftg');
      case 'ack_nedskr_intresseftg_ub':
        return v('ack_nedskr_intresseftg_ib') + v('aterfor_nedskr_fusion_intresseftg') + v('aterfor_nedskr_fsg_intresseftg') + v('aterfor_nedskr_intresseftg') + v('omklass_nedskr_intresseftg') + v('arets_nedskr_intresseftg');
      default:
        return getVal(ubVar, year);
    }
  }, [visible, sumGroupAbove, getVal]);

  // Sum the actual S2 subtotals for INTRESSEFTG (anskaffning + nedskrivningar only)
  const redCur  = ['intresseftg_ub','ack_nedskr_intresseftg_ub']
    .map(n => ubSum(n, 'cur'))
    .reduce((a,b) => a + b, 0);

  const redPrev = ['intresseftg_ub','ack_nedskr_intresseftg_ub']
    .map(n => ubSum(n, 'prev'))
    .reduce((a,b) => a + b, 0);

  return (
    <div ref={containerRef} className="space-y-2 pt-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b pb-1">
        <div className="flex items-center gap-3">
          <h3 className="text-lg font-semibold pt-1">{heading}</h3>
          <button
            onClick={() => isEditing ? cancelEdit() : startEdit()}
            className={`w-6 h-6 rounded-full flex items-center justify-center transition-colors ${
              isEditing ? 'bg-blue-600 text-white' : 'bg-gray-200 hover:bg-gray-300 text-gray-600'
            }`}
            title={isEditing ? 'Avsluta redigering' : 'Redigera värden'}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                    d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
            </svg>
          </button>
        </div>
        <div className="flex items-center space-x-2">
          <label htmlFor="toggle-intresseftg-rows" className="text-sm font-medium cursor-pointer">
            Visa alla rader
          </label>
          <Switch
            id="toggle-intresseftg-rows"
            checked={toggleOn}
            onCheckedChange={setToggle}
          />
        </div>
      </div>

      {/* Column headers */}
      <div className="grid gap-4 text-sm text-muted-foreground border-b pb-1 font-semibold" style={gridCols}>
        <span></span>
        <span className="text-right">{companyData?.currentPeriodEndDate || `${fiscalYear ?? new Date().getFullYear()}-12-31`}</span>
        <span className="text-right">{companyData?.previousPeriodEndDate || `${(previousYear ?? (fiscalYear ? fiscalYear - 1 : new Date().getFullYear() - 1))}-12-31`}</span>
      </div>

      {/* Rows */}
      {(() => {
        let ordCounter = 0;
        return visible.map((it, idx) => {
          const getStyleClasses = (style?: string) => {
            const baseClasses = 'grid gap-4';
            let additionalClasses = '';
            const s = style || 'NORMAL';
            
            const boldStyles = ['H0','H1','H2','H3','S1','S2','S3','TH0','TH1','TH2','TH3','TS1','TS2','TS3'];
            if (boldStyles.includes(s)) {
              additionalClasses += ' font-semibold';
            }
            
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
          const isHeadingRow = isHeadingStyle(currentStyle);
          const isS2 = isSumRow(it);
          const editable = isEditing && isFlowVar(it.variable_name);
          
          const ordCur  = editable ? ++ordCounter : undefined;
          const ordPrev = editable ? ++ordCounter : undefined;
          
          const isRedVardeRow = it.variable_name === "red_varde_intresseftg";
          
          const curVal = isRedVardeRow
            ? redCur
            : (isS2 ? sumGroupAbove(visible, idx, 'cur') : getVal(it.variable_name ?? '', 'cur'));
          const prevVal = isRedVardeRow
            ? redPrev
            : (isS2 ? sumGroupAbove(visible, idx, 'prev') : getVal(it.variable_name ?? '', 'prev'));

          const curMismatch  = isEditing && isRedVardeRow && Math.round(redCur)  !== Math.round(brBookValueUBCur);
          const prevMismatch = isEditing && isRedVardeRow && Math.round(redPrev) !== Math.round(brBookValueUBPrev);
          
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
              <span className={`text-right font-medium ${isRedVardeRow && curMismatch ? 'text-red-600 font-bold' : ''}`}>
                {isHeadingRow ? '' : isRedVardeRow
                  ? `${numberToSv(curVal)} kr`
                  : <AmountCell
                      year="cur"
                      varName={it.variable_name!}
                      baseVar={it.variable_name!}
                      label={it.row_title}
                      editable={editable}
                      value={curVal}
                      ord={ordCur}
                      onCommit={(n) => setEditedValues(p => ({ ...p, [it.variable_name!]: n }))}
                      onTabNavigate={(el, dir) => focusByOrd(el, dir)}
                      onSignForced={(e) => pushSignNotice(e)}
                      expectedSignFor={expectedSignFor}
                    />
                }
              </span>

              {/* Previous year */}
              <span className={`text-right font-medium ${isRedVardeRow && prevMismatch ? 'text-red-600 font-bold' : ''}`}>
                {isHeadingRow ? '' : isRedVardeRow
                  ? `${numberToSv(prevVal)} kr`
                  : <AmountCell
                      year="prev"
                      varName={`${it.variable_name!}_prev`}
                      baseVar={it.variable_name!}
                      label={it.row_title}
                      editable={editable}
                      value={prevVal}
                      ord={ordPrev}
                      onCommit={(n) => setEditedPrevValues(p => ({ ...p, [it.variable_name!]: n }))}
                      onTabNavigate={(el, dir) => focusByOrd(el, dir)}
                      onSignForced={(e) => pushSignNotice(e)}
                      expectedSignFor={expectedSignFor}
                    />
                }
              </span>
            </div>
          );
        });
      })()}

      {/* Comparison row – only while editing */}
      {isEditing && (
        <div className="grid gap-4 border-t border-b border-gray-200 pt-1 pb-1 font-semibold bg-gray-50/50" style={gridCols}>
          <span className="text-muted-foreground font-semibold">Redovisat värde (bokfört)</span>
          <span className="text-right font-medium">{numberToSv(brBookValueUBCur)} kr</span>
          <span className="text-right font-medium">{numberToSv(brBookValueUBPrev)} kr</span>
        </div>
      )}

      {/* Action buttons */}
      {isEditing && (
        <div className="pt-4 flex justify-between">
          <Button 
            onClick={undoEdit}
            variant="outline"
            className="flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"/>
            </svg>
            Ångra ändringar
          </Button>
          
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

      {/* Toast Notification */}
      {showValidationMessage && (
        <div className="fixed bottom-4 right-4 z-50 bg-white rounded-lg shadow-lg p-4 max-w-sm animate-in slide-in-from-bottom-2">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <svg className="w-5 h-5 text-red-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                      d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </div>
            <div className="ml-3">
              {(() => {
                const curMism = Math.round(mismatch.deltaCur) !== 0;
                const prevMism = Math.round(mismatch.deltaPrev) !== 0;
                
                if (curMism && !prevMism) {
                  return (
                    <>
                      <p className="text-sm font-medium text-gray-900">
                        Summor balanserar inte {fiscalYear}
                      </p>
                      <p className="mt-1 text-sm text-gray-700">
                        Beräknat redovisat värde stämmer inte med bokfört värde. Differensen är {numberToSv(Math.abs(Math.round(mismatch.deltaCur)))} kr.
                      </p>
                    </>
                  );
                } else if (prevMism && !curMism) {
                  return (
                    <>
                      <p className="text-sm font-medium text-gray-900">
                        Summor balanserar inte {previousYear}
                      </p>
                      <p className="mt-1 text-sm text-gray-700">
                        Beräknat redovisat värde stämmer inte med bokfört värde. Differensen är {numberToSv(Math.abs(Math.round(mismatch.deltaPrev)))} kr.
                      </p>
                    </>
                  );
                } else {
                  return (
                    <>
                      <p className="text-sm font-medium text-gray-900">
                        Summor balanserar inte
                      </p>
                      <p className="mt-1 text-sm text-gray-700">
                        Beräknat redovisat värde stämmer inte med bokfört värde.
                      </p>
                      <ul className="mt-2 text-sm text-gray-900">
                        <li><strong>{fiscalYear}</strong>: Differens {numberToSv(Math.abs(Math.round(mismatch.deltaCur)))} kr</li>
                        <li><strong>{previousYear}</strong>: Differens {numberToSv(Math.abs(Math.round(mismatch.deltaPrev)))} kr</li>
                      </ul>
                    </>
                  );
                }
              })()}
            </div>
            <button
              onClick={() => { setShowValidationMessage(false); setMismatch(m => ({ ...m, open: false })); }}
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

// Andra långfristiga värdepappersinnehav editor component
const LangfristigaVardepapperNote: React.FC<{
  items: NoterItem[];
  heading: string;
  fiscalYear?: number;
  previousYear?: number;
  companyData?: any;
  toggleOn: boolean;
  setToggle: (checked: boolean) => void;
}> = ({ items, heading, fiscalYear, previousYear, companyData, toggleOn, setToggle }) => {
  const gridCols = { gridTemplateColumns: "4fr 1fr 1fr" };

  const isFlowVar = (vn?: string) => {
    if (!vn) return false;
    if (/_ib\b/i.test(vn)) return false;
    if (/_ub\b/i.test(vn)) return false;
    if (/red[_-]?varde/i.test(vn)) return false;
    return true;
  };

  const byVar = useMemo(() => {
    const m = new Map<string, NoterItem>();
    items.forEach((it) => it.variable_name && m.set(it.variable_name, it));
    return m;
  }, [items]);

  // BR book value (UB) for both years - LVP specific
  const { brBookValueUBCur, brBookValueUBPrev } = React.useMemo(() => {
    const brData: any[] = companyData?.seFileData?.br_data || [];
    const candidates = [
      "AndraLangfristigaVardepappersinnehav",
      "LangfristigaVardepapper",
      "AndraVardepapper",
    ];
    let cur = 0, prev = 0;

    for (const c of candidates) {
      const hit = brData.find((x: any) => x.variable_name === c);
      if (hit) {
        if (Number.isFinite(hit.current_amount))  cur  = hit.current_amount;
        if (Number.isFinite(hit.previous_amount)) prev = hit.previous_amount;
        if (cur || prev) break;
      }
    }

    if (!cur)  cur  = byVar.get("red_varde_lang_vardepapper")?.current_amount  ?? 0;
    if (!prev) prev = byVar.get("red_varde_lang_vardepapper")?.previous_amount ?? 0;

    return { brBookValueUBCur: cur, brBookValueUBPrev: prev };
  }, [companyData, byVar]);

  // Baseline management
  const originalBaselineRef = React.useRef<{cur: Record<string, number>, prev: Record<string, number>}>({cur:{}, prev:{}});
  React.useEffect(() => {
    const cur: Record<string, number> = {};
    const prev: Record<string, number> = {};
    items.forEach(it => {
      const vn = it.variable_name;
      if (!vn) return;
      if (!isFlowVar(vn)) return;
      cur[vn] = it.current_amount ?? 0;
      prev[vn] = it.previous_amount ?? 0;
    });
    originalBaselineRef.current = { cur, prev };
  }, [items]);

  // Local edit state
  const [isEditing, setIsEditing] = useState(false);
  const [editedValues, setEditedValues] = useState<Record<string, number>>({});
  const [editedPrevValues, setEditedPrevValues] = useState<Record<string, number>>({});
  const [committedValues, setCommittedValues] = useState<Record<string, number>>({});
  const [committedPrevValues, setCommittedPrevValues] = useState<Record<string, number>>({});
  const [mismatch, setMismatch] = useState<{ open: boolean; deltaCur: number; deltaPrev: number }>({
    open: false,
    deltaCur: 0,
    deltaPrev: 0,
  });
  const [showValidationMessage, setShowValidationMessage] = useState(false);

  // Sign enforcement from CSV mapping - LVP specific
  const injectedSignMap: Record<string, '+' | '-'> | undefined = (companyData?.signByVar) || undefined;

  const heuristicSign = (vn: string): '+' | '-' | null => {
    // Based on variable_mapping_noter_rows (LVP).csv
    const positiveVars = [
      'arets_inkop_lang_vardepapper',
      'aterfor_nedskr_fsg_lang_vardepapper',
      'aterfor_nedskr_lang_vardepapper'
    ];
    
    const negativeVars = [
      'arets_fsg_lang_vardepapper',
      'arets_nedskr_lang_vardepapper'
    ];
    
    // Flexible variables
    const flexibleVars = [
      'omklass_lang_vardepapper',          // No +/- in CSV
      'omklass_nedskr_lang_vardepapper'    // No +/- in CSV
    ];
    
    if (positiveVars.includes(vn)) return '+';
    if (negativeVars.includes(vn)) return '-';
    return null; // flexible
  };

  const expectedSignFor = (vn?: string): '+' | '-' | null => {
    if (!vn) return null;
    return injectedSignMap?.[vn] ?? heuristicSign(vn);
  };

  const getVal = React.useCallback((vn: string, year: 'cur' | 'prev') => {
    if (year === 'cur') {
      if (editedValues[vn] !== undefined) return editedValues[vn];
      if (committedValues[vn] !== undefined) return committedValues[vn];
      return byVar.get(vn)?.current_amount ?? 0;
    } else {
      if (editedPrevValues[vn] !== undefined) return editedPrevValues[vn];
      if (committedPrevValues[vn] !== undefined) return committedPrevValues[vn];
      return byVar.get(vn)?.previous_amount ?? 0;
    }
  }, [editedValues, committedValues, editedPrevValues, committedPrevValues, byVar]);

  const readCur = (it: NoterItem) => getVal(it.variable_name!, 'cur');
  const readPrev = (it: NoterItem) => getVal(it.variable_name!, 'prev');

  const visible = useMemo(() => {
    return buildVisibleWithHeadings({
      items,
      toggleOn,
      readCur: (it) => readCur(it),
      readPrev: (it) => readPrev(it),
    });
  }, [items, toggleOn, editedValues, editedPrevValues, committedValues, committedPrevValues]);

  const startEdit = () => {
    setIsEditing(true);
    setToggle?.(true);
  };

  React.useEffect(() => {
    if (showValidationMessage) {
      const timer = setTimeout(() => setShowValidationMessage(false), 5000);
      return () => clearTimeout(timer);
    }
  }, [showValidationMessage]);

  const cancelEdit = () => {
    setIsEditing(false);
    setEditedValues({});
    setEditedPrevValues({});
    setMismatch({ open: false, deltaCur: 0, deltaPrev: 0 });
    setShowValidationMessage(false);
    setToggle?.(false);
  };

  const undoEdit = () => {
    blurAllEditableInputs();
    setEditedValues({});
    setEditedPrevValues({});
    setCommittedValues({ ...originalBaselineRef.current.cur });
    setCommittedPrevValues({ ...originalBaselineRef.current.prev });
    setMismatch({ open: false, deltaCur: 0, deltaPrev: 0 });
    setShowValidationMessage(false);
  };

  const approveEdit = () => {
    const redCurCalc  = redCur;
    const redPrevCalc = redPrev;

    const deltaCur  = redCurCalc  - brBookValueUBCur;
    const deltaPrev = redPrevCalc - brBookValueUBPrev;

    const hasMismatch = Math.round(deltaCur) !== 0 || Math.round(deltaPrev) !== 0;

    if (hasMismatch) {
      setMismatch({ open: true, deltaCur, deltaPrev });
      setShowValidationMessage(true);
      return;
    }

    setCommittedValues(prev => ({ ...prev, ...editedValues }));
    setCommittedPrevValues(prev => ({ ...prev, ...editedPrevValues }));
    setEditedValues({});
    setEditedPrevValues({});
    setMismatch({ open: false, deltaCur: 0, deltaPrev: 0 });
    setShowValidationMessage(false);
    setIsEditing(false);
    setToggle?.(false);
  };

  // Helper functions
  const isSumRow = (it: NoterItem) => it.style === 'S2';
  const isHeading = (it: NoterItem) => isHeadingStyle(it.style);

  const sumGroupAbove = React.useCallback(
    (list: NoterItem[], index: number, year: 'cur' | 'prev') => {
      let sum = 0;
      for (let i = index - 1; i >= 0; i--) {
        const r = list[i];
        if (!r) break;
        if (isHeading(r) || r.style === 'S2') break;
        if (r.variable_name) sum += getVal(r.variable_name, year);
      }
      return sum;
    },
    [getVal]
  );

  const containerRef = React.useRef<HTMLDivElement>(null);

  const focusByOrd = (fromEl: HTMLInputElement, dir: 1 | -1) => {
    const root = containerRef.current;
    if (!root) return;
    const curOrd = Number(fromEl.dataset.ord || '0');
    const nextOrd = curOrd + dir;
    const next = root.querySelector<HTMLInputElement>(
      `input[data-editable-cell="1"][data-ord="${nextOrd}"]`
    );
    if (next) { next.focus(); next.select?.(); }
  };

  const blurAllEditableInputs = () => {
    const root = containerRef.current;
    if (!root) return;
    const nodes = root.querySelectorAll<HTMLInputElement>('input[data-editable-cell="1"]');
    nodes.forEach((el) => el.blur());
  };

  const pushSignNotice = (e: any) => {
    console.log(`Sign forced for ${e.label} (${e.year}): ${e.typed} → ${e.adjusted}`);
  };

  // Helper: get the dynamic S2 subtotal for LVP UB rows
  const ubSum = React.useCallback((ubVar: string, year: 'cur' | 'prev') => {
    const v = (name: string) => getVal(name, year) || 0;
    const idx = visible.findIndex(r => r.variable_name === ubVar);
    if (idx !== -1 && visible[idx]?.style === 'S2') {
      return sumGroupAbove(visible, idx, year);
    }
    // Fallbacks if the UB row isn't visible:
    switch (ubVar) {
      case 'lang_vardepapper_ub':
        return v('lang_vardepapper_ib') + v('arets_inkop_lang_vardepapper') + v('arets_fsg_lang_vardepapper') + v('omklass_lang_vardepapper');
      case 'ack_nedskr_lang_vardepapper_ub':
        return v('ack_nedskr_lang_vardepapper_ib') + v('aterfor_nedskr_fsg_lang_vardepapper') + v('aterfor_nedskr_lang_vardepapper') + v('omklass_nedskr_lang_vardepapper') + v('arets_nedskr_lang_vardepapper');
      default:
        return getVal(ubVar, year);
    }
  }, [visible, sumGroupAbove, getVal]);

  // Sum the actual S2 subtotals for LVP (anskaffning + nedskrivningar only)
  const redCur  = ['lang_vardepapper_ub','ack_nedskr_lang_vardepapper_ub']
    .map(n => ubSum(n, 'cur'))
    .reduce((a,b) => a + b, 0);

  const redPrev = ['lang_vardepapper_ub','ack_nedskr_lang_vardepapper_ub']
    .map(n => ubSum(n, 'prev'))
    .reduce((a,b) => a + b, 0);

  return (
    <div ref={containerRef} className="space-y-2 pt-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b pb-1">
        <div className="flex items-center gap-3">
          <h3 className="text-lg font-semibold pt-1">{heading}</h3>
          <button
            onClick={() => isEditing ? cancelEdit() : startEdit()}
            className={`w-6 h-6 rounded-full flex items-center justify-center transition-colors ${
              isEditing ? 'bg-blue-600 text-white' : 'bg-gray-200 hover:bg-gray-300 text-gray-600'
            }`}
            title={isEditing ? 'Avsluta redigering' : 'Redigera värden'}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                    d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
            </svg>
          </button>
        </div>
        <div className="flex items-center space-x-2">
          <label htmlFor="toggle-lvp-rows" className="text-sm font-medium cursor-pointer">
            Visa alla rader
          </label>
          <Switch
            id="toggle-lvp-rows"
            checked={toggleOn}
            onCheckedChange={setToggle}
          />
        </div>
      </div>

      {/* Column headers */}
      <div className="grid gap-4 text-sm text-muted-foreground border-b pb-1 font-semibold" style={gridCols}>
        <span></span>
        <span className="text-right">{companyData?.currentPeriodEndDate || `${fiscalYear ?? new Date().getFullYear()}-12-31`}</span>
        <span className="text-right">{companyData?.previousPeriodEndDate || `${(previousYear ?? (fiscalYear ? fiscalYear - 1 : new Date().getFullYear() - 1))}-12-31`}</span>
      </div>

      {/* Rows */}
      {(() => {
        let ordCounter = 0;
        return visible.map((it, idx) => {
          const getStyleClasses = (style?: string) => {
            const baseClasses = 'grid gap-4';
            let additionalClasses = '';
            const s = style || 'NORMAL';
            
            const boldStyles = ['H0','H1','H2','H3','S1','S2','S3','TH0','TH1','TH2','TH3','TS1','TS2','TS3'];
            if (boldStyles.includes(s)) {
              additionalClasses += ' font-semibold';
            }
            
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
          const isHeadingRow = isHeadingStyle(currentStyle);
          const isS2 = isSumRow(it);
          const editable = isEditing && isFlowVar(it.variable_name);
          
          const ordCur  = editable ? ++ordCounter : undefined;
          const ordPrev = editable ? ++ordCounter : undefined;
          
          const isRedVardeRow = it.variable_name === "red_varde_lang_vardepapper";
          
          const curVal = isRedVardeRow
            ? redCur
            : (isS2 ? sumGroupAbove(visible, idx, 'cur') : getVal(it.variable_name ?? '', 'cur'));
          const prevVal = isRedVardeRow
            ? redPrev
            : (isS2 ? sumGroupAbove(visible, idx, 'prev') : getVal(it.variable_name ?? '', 'prev'));

          const curMismatch  = isEditing && isRedVardeRow && Math.round(redCur)  !== Math.round(brBookValueUBCur);
          const prevMismatch = isEditing && isRedVardeRow && Math.round(redPrev) !== Math.round(brBookValueUBPrev);
          
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
              <span className={`text-right font-medium ${isRedVardeRow && curMismatch ? 'text-red-600 font-bold' : ''}`}>
                {isHeadingRow ? '' : isRedVardeRow
                  ? `${numberToSv(curVal)} kr`
                  : <AmountCell
                      year="cur"
                      varName={it.variable_name!}
                      baseVar={it.variable_name!}
                      label={it.row_title}
                      editable={editable}
                      value={curVal}
                      ord={ordCur}
                      onCommit={(n) => setEditedValues(p => ({ ...p, [it.variable_name!]: n }))}
                      onTabNavigate={(el, dir) => focusByOrd(el, dir)}
                      onSignForced={(e) => pushSignNotice(e)}
                      expectedSignFor={expectedSignFor}
                    />
                }
              </span>

              {/* Previous year */}
              <span className={`text-right font-medium ${isRedVardeRow && prevMismatch ? 'text-red-600 font-bold' : ''}`}>
                {isHeadingRow ? '' : isRedVardeRow
                  ? `${numberToSv(prevVal)} kr`
                  : <AmountCell
                      year="prev"
                      varName={`${it.variable_name!}_prev`}
                      baseVar={it.variable_name!}
                      label={it.row_title}
                      editable={editable}
                      value={prevVal}
                      ord={ordPrev}
                      onCommit={(n) => setEditedPrevValues(p => ({ ...p, [it.variable_name!]: n }))}
                      onTabNavigate={(el, dir) => focusByOrd(el, dir)}
                      onSignForced={(e) => pushSignNotice(e)}
                      expectedSignFor={expectedSignFor}
                    />
                }
              </span>
            </div>
          );
        });
      })()}

      {/* Comparison row – only while editing */}
      {isEditing && (
        <div className="grid gap-4 border-t border-b border-gray-200 pt-1 pb-1 font-semibold bg-gray-50/50" style={gridCols}>
          <span className="text-muted-foreground font-semibold">Redovisat värde (bokfört)</span>
          <span className="text-right font-medium">{numberToSv(brBookValueUBCur)} kr</span>
          <span className="text-right font-medium">{numberToSv(brBookValueUBPrev)} kr</span>
        </div>
      )}

      {/* Action buttons */}
      {isEditing && (
        <div className="pt-4 flex justify-between">
          <Button 
            onClick={undoEdit}
            variant="outline"
            className="flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"/>
            </svg>
            Ångra ändringar
          </Button>
          
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

      {/* Toast Notification */}
      {showValidationMessage && (
        <div className="fixed bottom-4 right-4 z-50 bg-white rounded-lg shadow-lg p-4 max-w-sm animate-in slide-in-from-bottom-2">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <svg className="w-5 h-5 text-red-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                      d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </div>
            <div className="ml-3">
              {(() => {
                const curMism = Math.round(mismatch.deltaCur) !== 0;
                const prevMism = Math.round(mismatch.deltaPrev) !== 0;
                
                if (curMism && !prevMism) {
                  return (
                    <>
                      <p className="text-sm font-medium text-gray-900">
                        Summor balanserar inte {fiscalYear}
                      </p>
                      <p className="mt-1 text-sm text-gray-700">
                        Beräknat redovisat värde stämmer inte med bokfört värde. Differensen är {numberToSv(Math.abs(Math.round(mismatch.deltaCur)))} kr.
                      </p>
                    </>
                  );
                } else if (prevMism && !curMism) {
                  return (
                    <>
                      <p className="text-sm font-medium text-gray-900">
                        Summor balanserar inte {previousYear}
                      </p>
                      <p className="mt-1 text-sm text-gray-700">
                        Beräknat redovisat värde stämmer inte med bokfört värde. Differensen är {numberToSv(Math.abs(Math.round(mismatch.deltaPrev)))} kr.
                      </p>
                    </>
                  );
                } else {
                  return (
                    <>
                      <p className="text-sm font-medium text-gray-900">
                        Summor balanserar inte
                      </p>
                      <p className="mt-1 text-sm text-gray-700">
                        Beräknat redovisat värde stämmer inte med bokfört värde.
                      </p>
                      <ul className="mt-2 text-sm text-gray-900">
                        <li><strong>{fiscalYear}</strong>: Differens {numberToSv(Math.abs(Math.round(mismatch.deltaCur)))} kr</li>
                        <li><strong>{previousYear}</strong>: Differens {numberToSv(Math.abs(Math.round(mismatch.deltaPrev)))} kr</li>
                      </ul>
                    </>
                  );
                }
              })()}
            </div>
            <button
              onClick={() => { setShowValidationMessage(false); setMismatch(m => ({ ...m, open: false })); }}
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

// Fordringar hos koncernföretag editor component
const FordringarKoncernNote: React.FC<{
  items: NoterItem[];
  heading: string;
  fiscalYear?: number;
  previousYear?: number;
  companyData?: any;
  toggleOn: boolean;
  setToggle: (checked: boolean) => void;
}> = ({ items, heading, fiscalYear, previousYear, companyData, toggleOn, setToggle }) => {
  const gridCols = { gridTemplateColumns: "4fr 1fr 1fr" };

  const isFlowVar = (vn?: string) => {
    if (!vn) return false;
    if (/_ib\b/i.test(vn)) return false;
    if (/_ub\b/i.test(vn)) return false;
    if (/red[_-]?varde/i.test(vn)) return false;
    return true;
  };

  const byVar = useMemo(() => {
    const m = new Map<string, NoterItem>();
    items.forEach((it) => it.variable_name && m.set(it.variable_name, it));
    return m;
  }, [items]);

  // BR book value (UB) for both years - FORDRKONC specific
  const { brBookValueUBCur, brBookValueUBPrev } = React.useMemo(() => {
    const brData: any[] = companyData?.seFileData?.br_data || [];
    const candidates = [
      "FordringarKoncernforetagLangfristiga",
      "FordringarKoncern",
      "KoncernFordringar",
    ];
    let cur = 0, prev = 0;

    for (const c of candidates) {
      const hit = brData.find((x: any) => x.variable_name === c);
      if (hit) {
        if (Number.isFinite(hit.current_amount))  cur  = hit.current_amount;
        if (Number.isFinite(hit.previous_amount)) prev = hit.previous_amount;
        if (cur || prev) break;
      }
    }

    if (!cur)  cur  = byVar.get("red_varde_fordr_koncern")?.current_amount  ?? 0;
    if (!prev) prev = byVar.get("red_varde_fordr_koncern")?.previous_amount ?? 0;

    return { brBookValueUBCur: cur, brBookValueUBPrev: prev };
  }, [companyData, byVar]);

  // Baseline management
  const originalBaselineRef = React.useRef<{cur: Record<string, number>, prev: Record<string, number>}>({cur:{}, prev:{}});
  React.useEffect(() => {
    const cur: Record<string, number> = {};
    const prev: Record<string, number> = {};
    items.forEach(it => {
      const vn = it.variable_name;
      if (!vn) return;
      if (!isFlowVar(vn)) return;
      cur[vn] = it.current_amount ?? 0;
      prev[vn] = it.previous_amount ?? 0;
    });
    originalBaselineRef.current = { cur, prev };
  }, [items]);

  // Local edit state
  const [isEditing, setIsEditing] = useState(false);
  const [editedValues, setEditedValues] = useState<Record<string, number>>({});
  const [editedPrevValues, setEditedPrevValues] = useState<Record<string, number>>({});
  const [committedValues, setCommittedValues] = useState<Record<string, number>>({});
  const [committedPrevValues, setCommittedPrevValues] = useState<Record<string, number>>({});
  const [mismatch, setMismatch] = useState<{ open: boolean; deltaCur: number; deltaPrev: number }>({
    open: false,
    deltaCur: 0,
    deltaPrev: 0,
  });
  const [showValidationMessage, setShowValidationMessage] = useState(false);

  // Sign enforcement from CSV mapping - FORDRKONC specific
  const injectedSignMap: Record<string, '+' | '-'> | undefined = (companyData?.signByVar) || undefined;

  const heuristicSign = (vn: string): '+' | '-' | null => {
    // Based on variable_mapping_noter_rows (FORDRKONC).csv
    const positiveVars = [
      'nya_fordr_koncern',
      'fusion_fordr_koncern',
      'aterfor_nedskr_reglerade_fordr_koncern',
      'aterfor_nedskr_fusion_fordr_koncern',
      'aterfor_nedskr_fordr_koncern',
      'aterfor_nedskr_bortskrivna_fordr_koncern'
    ];
    
    const negativeVars = [
      'reglerade_fordr_koncern',
      'bortskrivna_fordr_koncern',
      'arets_nedskr_fordr_koncern'
    ];
    
    // Flexible variables
    const flexibleVars = [
      'omklass_fordr_koncern',          // No +/- in CSV
      'omklass_nedskr_fordr_koncern'    // No +/- in CSV
    ];
    
    if (positiveVars.includes(vn)) return '+';
    if (negativeVars.includes(vn)) return '-';
    return null; // flexible
  };

  const expectedSignFor = (vn?: string): '+' | '-' | null => {
    if (!vn) return null;
    return injectedSignMap?.[vn] ?? heuristicSign(vn);
  };

  const getVal = React.useCallback((vn: string, year: 'cur' | 'prev') => {
    if (year === 'cur') {
      if (editedValues[vn] !== undefined) return editedValues[vn];
      if (committedValues[vn] !== undefined) return committedValues[vn];
      return byVar.get(vn)?.current_amount ?? 0;
    } else {
      if (editedPrevValues[vn] !== undefined) return editedPrevValues[vn];
      if (committedPrevValues[vn] !== undefined) return committedPrevValues[vn];
      return byVar.get(vn)?.previous_amount ?? 0;
    }
  }, [editedValues, committedValues, editedPrevValues, committedPrevValues, byVar]);

  const readCur = (it: NoterItem) => getVal(it.variable_name!, 'cur');
  const readPrev = (it: NoterItem) => getVal(it.variable_name!, 'prev');

  const visible = useMemo(() => {
    return buildVisibleWithHeadings({
      items,
      toggleOn,
      readCur: (it) => readCur(it),
      readPrev: (it) => readPrev(it),
    });
  }, [items, toggleOn, editedValues, editedPrevValues, committedValues, committedPrevValues]);

  const startEdit = () => {
    setIsEditing(true);
    setToggle?.(true);
  };

  React.useEffect(() => {
    if (showValidationMessage) {
      const timer = setTimeout(() => setShowValidationMessage(false), 5000);
      return () => clearTimeout(timer);
    }
  }, [showValidationMessage]);

  const cancelEdit = () => {
    setIsEditing(false);
    setEditedValues({});
    setEditedPrevValues({});
    setMismatch({ open: false, deltaCur: 0, deltaPrev: 0 });
    setShowValidationMessage(false);
    setToggle?.(false);
  };

  const undoEdit = () => {
    blurAllEditableInputs();
    setEditedValues({});
    setEditedPrevValues({});
    setCommittedValues({ ...originalBaselineRef.current.cur });
    setCommittedPrevValues({ ...originalBaselineRef.current.prev });
    setMismatch({ open: false, deltaCur: 0, deltaPrev: 0 });
    setShowValidationMessage(false);
  };

  const approveEdit = () => {
    const redCurCalc  = redCur;
    const redPrevCalc = redPrev;

    const deltaCur  = redCurCalc  - brBookValueUBCur;
    const deltaPrev = redPrevCalc - brBookValueUBPrev;

    const hasMismatch = Math.round(deltaCur) !== 0 || Math.round(deltaPrev) !== 0;

    if (hasMismatch) {
      setMismatch({ open: true, deltaCur, deltaPrev });
      setShowValidationMessage(true);
      return;
    }

    setCommittedValues(prev => ({ ...prev, ...editedValues }));
    setCommittedPrevValues(prev => ({ ...prev, ...editedPrevValues }));
    setEditedValues({});
    setEditedPrevValues({});
    setMismatch({ open: false, deltaCur: 0, deltaPrev: 0 });
    setShowValidationMessage(false);
    setIsEditing(false);
    setToggle?.(false);
  };

  // Helper functions
  const isSumRow = (it: NoterItem) => it.style === 'S2';
  const isHeading = (it: NoterItem) => isHeadingStyle(it.style);

  const sumGroupAbove = React.useCallback(
    (list: NoterItem[], index: number, year: 'cur' | 'prev') => {
      let sum = 0;
      for (let i = index - 1; i >= 0; i--) {
        const r = list[i];
        if (!r) break;
        if (isHeading(r) || r.style === 'S2') break;
        if (r.variable_name) sum += getVal(r.variable_name, year);
      }
      return sum;
    },
    [getVal]
  );

  const containerRef = React.useRef<HTMLDivElement>(null);

  const focusByOrd = (fromEl: HTMLInputElement, dir: 1 | -1) => {
    const root = containerRef.current;
    if (!root) return;
    const curOrd = Number(fromEl.dataset.ord || '0');
    const nextOrd = curOrd + dir;
    const next = root.querySelector<HTMLInputElement>(
      `input[data-editable-cell="1"][data-ord="${nextOrd}"]`
    );
    if (next) { next.focus(); next.select?.(); }
  };

  const blurAllEditableInputs = () => {
    const root = containerRef.current;
    if (!root) return;
    const nodes = root.querySelectorAll<HTMLInputElement>('input[data-editable-cell="1"]');
    nodes.forEach((el) => el.blur());
  };

  const pushSignNotice = (e: any) => {
    console.log(`Sign forced for ${e.label} (${e.year}): ${e.typed} → ${e.adjusted}`);
  };

  // Helper: get the dynamic S2 subtotal for FORDRKONC UB rows
  const ubSum = React.useCallback((ubVar: string, year: 'cur' | 'prev') => {
    const v = (name: string) => getVal(name, year) || 0;
    const idx = visible.findIndex(r => r.variable_name === ubVar);
    if (idx !== -1 && visible[idx]?.style === 'S2') {
      return sumGroupAbove(visible, idx, year);
    }
    // Fallbacks if the UB row isn't visible:
    switch (ubVar) {
      case 'fordr_koncern_ub':
        return v('fordr_koncern_ib') + v('nya_fordr_koncern') + v('fusion_fordr_koncern') + v('reglerade_fordr_koncern') + v('bortskrivna_fordr_koncern') + v('omklass_fordr_koncern');
      case 'ack_nedskr_fordr_koncern_ub':
        return v('ack_nedskr_fordr_koncern_ib') + v('aterfor_nedskr_reglerade_fordr_koncern') + v('aterfor_nedskr_fusion_fordr_koncern') + v('aterfor_nedskr_fordr_koncern') + v('aterfor_nedskr_bortskrivna_fordr_koncern') + v('omklass_nedskr_fordr_koncern') + v('arets_nedskr_fordr_koncern');
      default:
        return getVal(ubVar, year);
    }
  }, [visible, sumGroupAbove, getVal]);

  // Sum the actual S2 subtotals for FORDRKONC (anskaffning + nedskrivningar only)
  const redCur  = ['fordr_koncern_ub','ack_nedskr_fordr_koncern_ub']
    .map(n => ubSum(n, 'cur'))
    .reduce((a,b) => a + b, 0);

  const redPrev = ['fordr_koncern_ub','ack_nedskr_fordr_koncern_ub']
    .map(n => ubSum(n, 'prev'))
    .reduce((a,b) => a + b, 0);

  return (
    <div ref={containerRef} className="space-y-2 pt-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b pb-1">
        <div className="flex items-center gap-3">
          <h3 className="text-lg font-semibold pt-1">{heading}</h3>
          <button
            onClick={() => isEditing ? cancelEdit() : startEdit()}
            className={`w-6 h-6 rounded-full flex items-center justify-center transition-colors ${
              isEditing ? 'bg-blue-600 text-white' : 'bg-gray-200 hover:bg-gray-300 text-gray-600'
            }`}
            title={isEditing ? 'Avsluta redigering' : 'Redigera värden'}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                    d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
            </svg>
          </button>
        </div>
        <div className="flex items-center space-x-2">
          <label htmlFor="toggle-fordrkonc-rows" className="text-sm font-medium cursor-pointer">
            Visa alla rader
          </label>
          <Switch
            id="toggle-fordrkonc-rows"
            checked={toggleOn}
            onCheckedChange={setToggle}
          />
        </div>
      </div>

      {/* Column headers */}
      <div className="grid gap-4 text-sm text-muted-foreground border-b pb-1 font-semibold" style={gridCols}>
        <span></span>
        <span className="text-right">{companyData?.currentPeriodEndDate || `${fiscalYear ?? new Date().getFullYear()}-12-31`}</span>
        <span className="text-right">{companyData?.previousPeriodEndDate || `${(previousYear ?? (fiscalYear ? fiscalYear - 1 : new Date().getFullYear() - 1))}-12-31`}</span>
      </div>

      {/* Rows */}
      {(() => {
        let ordCounter = 0;
        return visible.map((it, idx) => {
          const getStyleClasses = (style?: string) => {
            const baseClasses = 'grid gap-4';
            let additionalClasses = '';
            const s = style || 'NORMAL';
            
            const boldStyles = ['H0','H1','H2','H3','S1','S2','S3','TH0','TH1','TH2','TH3','TS1','TS2','TS3'];
            if (boldStyles.includes(s)) {
              additionalClasses += ' font-semibold';
            }
            
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
          const isHeadingRow = isHeadingStyle(currentStyle);
          const isS2 = isSumRow(it);
          const editable = isEditing && isFlowVar(it.variable_name);
          
          const ordCur  = editable ? ++ordCounter : undefined;
          const ordPrev = editable ? ++ordCounter : undefined;
          
          const isRedVardeRow = it.variable_name === "red_varde_fordr_koncern";
          
          const curVal = isRedVardeRow
            ? redCur
            : (isS2 ? sumGroupAbove(visible, idx, 'cur') : getVal(it.variable_name ?? '', 'cur'));
          const prevVal = isRedVardeRow
            ? redPrev
            : (isS2 ? sumGroupAbove(visible, idx, 'prev') : getVal(it.variable_name ?? '', 'prev'));

          const curMismatch  = isEditing && isRedVardeRow && Math.round(redCur)  !== Math.round(brBookValueUBCur);
          const prevMismatch = isEditing && isRedVardeRow && Math.round(redPrev) !== Math.round(brBookValueUBPrev);
          
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
              <span className={`text-right font-medium ${isRedVardeRow && curMismatch ? 'text-red-600 font-bold' : ''}`}>
                {isHeadingRow ? '' : isRedVardeRow
                  ? `${numberToSv(curVal)} kr`
                  : <AmountCell
                      year="cur"
                      varName={it.variable_name!}
                      baseVar={it.variable_name!}
                      label={it.row_title}
                      editable={editable}
                      value={curVal}
                      ord={ordCur}
                      onCommit={(n) => setEditedValues(p => ({ ...p, [it.variable_name!]: n }))}
                      onTabNavigate={(el, dir) => focusByOrd(el, dir)}
                      onSignForced={(e) => pushSignNotice(e)}
                      expectedSignFor={expectedSignFor}
                    />
                }
              </span>

              {/* Previous year */}
              <span className={`text-right font-medium ${isRedVardeRow && prevMismatch ? 'text-red-600 font-bold' : ''}`}>
                {isHeadingRow ? '' : isRedVardeRow
                  ? `${numberToSv(prevVal)} kr`
                  : <AmountCell
                      year="prev"
                      varName={`${it.variable_name!}_prev`}
                      baseVar={it.variable_name!}
                      label={it.row_title}
                      editable={editable}
                      value={prevVal}
                      ord={ordPrev}
                      onCommit={(n) => setEditedPrevValues(p => ({ ...p, [it.variable_name!]: n }))}
                      onTabNavigate={(el, dir) => focusByOrd(el, dir)}
                      onSignForced={(e) => pushSignNotice(e)}
                      expectedSignFor={expectedSignFor}
                    />
                }
              </span>
            </div>
          );
        });
      })()}

      {/* Comparison row – only while editing */}
      {isEditing && (
        <div className="grid gap-4 border-t border-b border-gray-200 pt-1 pb-1 font-semibold bg-gray-50/50" style={gridCols}>
          <span className="text-muted-foreground font-semibold">Redovisat värde (bokfört)</span>
          <span className="text-right font-medium">{numberToSv(brBookValueUBCur)} kr</span>
          <span className="text-right font-medium">{numberToSv(brBookValueUBPrev)} kr</span>
        </div>
      )}

      {/* Action buttons */}
      {isEditing && (
        <div className="pt-4 flex justify-between">
          <Button 
            onClick={undoEdit}
            variant="outline"
            className="flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"/>
            </svg>
            Ångra ändringar
          </Button>
          
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

      {/* Toast Notification */}
      {showValidationMessage && (
        <div className="fixed bottom-4 right-4 z-50 bg-white rounded-lg shadow-lg p-4 max-w-sm animate-in slide-in-from-bottom-2">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <svg className="w-5 h-5 text-red-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                      d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </div>
            <div className="ml-3">
              {(() => {
                const curMism = Math.round(mismatch.deltaCur) !== 0;
                const prevMism = Math.round(mismatch.deltaPrev) !== 0;
                
                if (curMism && !prevMism) {
                  return (
                    <>
                      <p className="text-sm font-medium text-gray-900">
                        Summor balanserar inte {fiscalYear}
                      </p>
                      <p className="mt-1 text-sm text-gray-700">
                        Beräknat redovisat värde stämmer inte med bokfört värde. Differensen är {numberToSv(Math.abs(Math.round(mismatch.deltaCur)))} kr.
                      </p>
                    </>
                  );
                } else if (prevMism && !curMism) {
                  return (
                    <>
                      <p className="text-sm font-medium text-gray-900">
                        Summor balanserar inte {previousYear}
                      </p>
                      <p className="mt-1 text-sm text-gray-700">
                        Beräknat redovisat värde stämmer inte med bokfört värde. Differensen är {numberToSv(Math.abs(Math.round(mismatch.deltaPrev)))} kr.
                      </p>
                    </>
                  );
                } else {
                  return (
                    <>
                      <p className="text-sm font-medium text-gray-900">
                        Summor balanserar inte
                      </p>
                      <p className="mt-1 text-sm text-gray-700">
                        Beräknat redovisat värde stämmer inte med bokfört värde.
                      </p>
                      <ul className="mt-2 text-sm text-gray-900">
                        <li><strong>{fiscalYear}</strong>: Differens {numberToSv(Math.abs(Math.round(mismatch.deltaCur)))} kr</li>
                        <li><strong>{previousYear}</strong>: Differens {numberToSv(Math.abs(Math.round(mismatch.deltaPrev)))} kr</li>
                      </ul>
                    </>
                  );
                }
              })()}
            </div>
            <button
              onClick={() => { setShowValidationMessage(false); setMismatch(m => ({ ...m, open: false })); }}
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

// Fordringar hos intresseföretag editor component
const FordringarIntresseNote: React.FC<{
  items: NoterItem[];
  heading: string;
  fiscalYear?: number;
  previousYear?: number;
  companyData?: any;
  toggleOn: boolean;
  setToggle: (checked: boolean) => void;
}> = ({ items, heading, fiscalYear, previousYear, companyData, toggleOn, setToggle }) => {
  const gridCols = { gridTemplateColumns: "4fr 1fr 1fr" };

  const isFlowVar = (vn?: string) => {
    if (!vn) return false;
    if (/_ib\b/i.test(vn)) return false;
    if (/_ub\b/i.test(vn)) return false;
    if (/red[_-]?varde/i.test(vn)) return false;
    return true;
  };

  const byVar = useMemo(() => {
    const m = new Map<string, NoterItem>();
    items.forEach((it) => it.variable_name && m.set(it.variable_name, it));
    return m;
  }, [items]);

  // BR book value (UB) for both years - FORDRINTRE specific
  const { brBookValueUBCur, brBookValueUBPrev } = React.useMemo(() => {
    const brData: any[] = companyData?.seFileData?.br_data || [];
    const candidates = [
      "FordringarIntresseforetagGemensamtStyrdaForetagLangfristiga",
      "FordringarIntresse",
      "IntresseFordringar",
    ];
    let cur = 0, prev = 0;

    for (const c of candidates) {
      const hit = brData.find((x: any) => x.variable_name === c);
      if (hit) {
        if (Number.isFinite(hit.current_amount))  cur  = hit.current_amount;
        if (Number.isFinite(hit.previous_amount)) prev = hit.previous_amount;
        if (cur || prev) break;
      }
    }

    if (!cur)  cur  = byVar.get("red_varde_fordr_intresse")?.current_amount  ?? 0;
    if (!prev) prev = byVar.get("red_varde_fordr_intresse")?.previous_amount ?? 0;

    return { brBookValueUBCur: cur, brBookValueUBPrev: prev };
  }, [companyData, byVar]);

  // Baseline management
  const originalBaselineRef = React.useRef<{cur: Record<string, number>, prev: Record<string, number>}>({cur:{}, prev:{}});
  React.useEffect(() => {
    const cur: Record<string, number> = {};
    const prev: Record<string, number> = {};
    items.forEach(it => {
      const vn = it.variable_name;
      if (!vn) return;
      if (!isFlowVar(vn)) return;
      cur[vn] = it.current_amount ?? 0;
      prev[vn] = it.previous_amount ?? 0;
    });
    originalBaselineRef.current = { cur, prev };
  }, [items]);

  // Local edit state
  const [isEditing, setIsEditing] = useState(false);
  const [editedValues, setEditedValues] = useState<Record<string, number>>({});
  const [editedPrevValues, setEditedPrevValues] = useState<Record<string, number>>({});
  const [committedValues, setCommittedValues] = useState<Record<string, number>>({});
  const [committedPrevValues, setCommittedPrevValues] = useState<Record<string, number>>({});
  const [mismatch, setMismatch] = useState<{ open: boolean; deltaCur: number; deltaPrev: number }>({
    open: false,
    deltaCur: 0,
    deltaPrev: 0,
  });
  const [showValidationMessage, setShowValidationMessage] = useState(false);

  // Sign enforcement from CSV mapping - FORDRINTRE specific
  const injectedSignMap: Record<string, '+' | '-'> | undefined = (companyData?.signByVar) || undefined;

  const heuristicSign = (vn: string): '+' | '-' | null => {
    // Based on variable_mapping_noter_rows (FORDRINTRE).csv
    const positiveVars = [
      'nya_fordr_intresse',
      'fusion_fordr_intresse',
      'aterfor_nedskr_reglerade_fordr_intresse',
      'aterfor_nedskr_fusion_fordr_intresse',
      'aterfor_nedskr_bortskrivna_fordr_intresse'
    ];
    
    const negativeVars = [
      'reglerade_fordr_intresse',
      'bortskrivna_fordr_intresse',
      'arets_nedskr_fordr_intresse'
    ];
    
    // Flexible variables
    const flexibleVars = [
      'omklass_fordr_intresse',          // No +/- in CSV
      'aterfor_nedskr_fordr_intresse',   // No +/- in CSV
      'omklass_nedskr_fordr_intresse'    // No +/- in CSV
    ];
    
    if (positiveVars.includes(vn)) return '+';
    if (negativeVars.includes(vn)) return '-';
    return null; // flexible
  };

  const expectedSignFor = (vn?: string): '+' | '-' | null => {
    if (!vn) return null;
    return injectedSignMap?.[vn] ?? heuristicSign(vn);
  };

  const getVal = React.useCallback((vn: string, year: 'cur' | 'prev') => {
    if (year === 'cur') {
      if (editedValues[vn] !== undefined) return editedValues[vn];
      if (committedValues[vn] !== undefined) return committedValues[vn];
      return byVar.get(vn)?.current_amount ?? 0;
    } else {
      if (editedPrevValues[vn] !== undefined) return editedPrevValues[vn];
      if (committedPrevValues[vn] !== undefined) return committedPrevValues[vn];
      return byVar.get(vn)?.previous_amount ?? 0;
    }
  }, [editedValues, committedValues, editedPrevValues, committedPrevValues, byVar]);

  const readCur = (it: NoterItem) => getVal(it.variable_name!, 'cur');
  const readPrev = (it: NoterItem) => getVal(it.variable_name!, 'prev');

  const visible = useMemo(() => {
    return buildVisibleWithHeadings({
      items,
      toggleOn,
      readCur: (it) => readCur(it),
      readPrev: (it) => readPrev(it),
    });
  }, [items, toggleOn, editedValues, editedPrevValues, committedValues, committedPrevValues]);

  const startEdit = () => {
    setIsEditing(true);
    setToggle?.(true);
  };

  React.useEffect(() => {
    if (showValidationMessage) {
      const timer = setTimeout(() => setShowValidationMessage(false), 5000);
      return () => clearTimeout(timer);
    }
  }, [showValidationMessage]);

  const cancelEdit = () => {
    setIsEditing(false);
    setEditedValues({});
    setEditedPrevValues({});
    setMismatch({ open: false, deltaCur: 0, deltaPrev: 0 });
    setShowValidationMessage(false);
    setToggle?.(false);
  };

  const undoEdit = () => {
    blurAllEditableInputs();
    setEditedValues({});
    setEditedPrevValues({});
    setCommittedValues({ ...originalBaselineRef.current.cur });
    setCommittedPrevValues({ ...originalBaselineRef.current.prev });
    setMismatch({ open: false, deltaCur: 0, deltaPrev: 0 });
    setShowValidationMessage(false);
  };

  const approveEdit = () => {
    const redCurCalc  = redCur;
    const redPrevCalc = redPrev;

    const deltaCur  = redCurCalc  - brBookValueUBCur;
    const deltaPrev = redPrevCalc - brBookValueUBPrev;

    const hasMismatch = Math.round(deltaCur) !== 0 || Math.round(deltaPrev) !== 0;

    if (hasMismatch) {
      setMismatch({ open: true, deltaCur, deltaPrev });
      setShowValidationMessage(true);
      return;
    }

    setCommittedValues(prev => ({ ...prev, ...editedValues }));
    setCommittedPrevValues(prev => ({ ...prev, ...editedPrevValues }));
    setEditedValues({});
    setEditedPrevValues({});
    setMismatch({ open: false, deltaCur: 0, deltaPrev: 0 });
    setShowValidationMessage(false);
    setIsEditing(false);
    setToggle?.(false);
  };

  // Helper functions
  const isSumRow = (it: NoterItem) => it.style === 'S2';
  const isHeading = (it: NoterItem) => isHeadingStyle(it.style);

  const sumGroupAbove = React.useCallback(
    (list: NoterItem[], index: number, year: 'cur' | 'prev') => {
      let sum = 0;
      for (let i = index - 1; i >= 0; i--) {
        const r = list[i];
        if (!r) break;
        if (isHeading(r) || r.style === 'S2') break;
        if (r.variable_name) sum += getVal(r.variable_name, year);
      }
      return sum;
    },
    [getVal]
  );

  const containerRef = React.useRef<HTMLDivElement>(null);

  const focusByOrd = (fromEl: HTMLInputElement, dir: 1 | -1) => {
    const root = containerRef.current;
    if (!root) return;
    const curOrd = Number(fromEl.dataset.ord || '0');
    const nextOrd = curOrd + dir;
    const next = root.querySelector<HTMLInputElement>(
      `input[data-editable-cell="1"][data-ord="${nextOrd}"]`
    );
    if (next) { next.focus(); next.select?.(); }
  };

  const blurAllEditableInputs = () => {
    const root = containerRef.current;
    if (!root) return;
    const nodes = root.querySelectorAll<HTMLInputElement>('input[data-editable-cell="1"]');
    nodes.forEach((el) => el.blur());
  };

  const pushSignNotice = (e: any) => {
    console.log(`Sign forced for ${e.label} (${e.year}): ${e.typed} → ${e.adjusted}`);
  };

  // Helper: get the dynamic S2 subtotal for FORDRINTRE UB rows
  const ubSum = React.useCallback((ubVar: string, year: 'cur' | 'prev') => {
    const v = (name: string) => getVal(name, year) || 0;
    const idx = visible.findIndex(r => r.variable_name === ubVar);
    if (idx !== -1 && visible[idx]?.style === 'S2') {
      return sumGroupAbove(visible, idx, year);
    }
    // Fallbacks if the UB row isn't visible:
    switch (ubVar) {
      case 'fordr_intresse_ub':
        return v('fordr_intresse_ib') + v('nya_fordr_intresse') + v('fusion_fordr_intresse') + v('reglerade_fordr_intresse') + v('bortskrivna_fordr_intresse') + v('omklass_fordr_intresse');
      case 'ack_nedskr_fordr_intresse_ub':
        return v('ack_nedskr_fordr_intresse_ib') + v('aterfor_nedskr_reglerade_fordr_intresse') + v('aterfor_nedskr_fusion_fordr_intresse') + v('aterfor_nedskr_fordr_intresse') + v('aterfor_nedskr_bortskrivna_fordr_intresse') + v('omklass_nedskr_fordr_intresse') + v('arets_nedskr_fordr_intresse');
      default:
        return getVal(ubVar, year);
    }
  }, [visible, sumGroupAbove, getVal]);

  // Sum the actual S2 subtotals for FORDRINTRE (anskaffning + nedskrivningar only)
  const redCur  = ['fordr_intresse_ub','ack_nedskr_fordr_intresse_ub']
    .map(n => ubSum(n, 'cur'))
    .reduce((a,b) => a + b, 0);

  const redPrev = ['fordr_intresse_ub','ack_nedskr_fordr_intresse_ub']
    .map(n => ubSum(n, 'prev'))
    .reduce((a,b) => a + b, 0);

  return (
    <div ref={containerRef} className="space-y-2 pt-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b pb-1">
        <div className="flex items-center gap-3">
          <h3 className="text-lg font-semibold pt-1">{heading}</h3>
          <button
            onClick={() => isEditing ? cancelEdit() : startEdit()}
            className={`w-6 h-6 rounded-full flex items-center justify-center transition-colors ${
              isEditing ? 'bg-blue-600 text-white' : 'bg-gray-200 hover:bg-gray-300 text-gray-600'
            }`}
            title={isEditing ? 'Avsluta redigering' : 'Redigera värden'}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                    d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
            </svg>
          </button>
        </div>
        <div className="flex items-center space-x-2">
          <label htmlFor="toggle-fordrintre-rows" className="text-sm font-medium cursor-pointer">
            Visa alla rader
          </label>
          <Switch
            id="toggle-fordrintre-rows"
            checked={toggleOn}
            onCheckedChange={setToggle}
          />
        </div>
      </div>

      {/* Column headers */}
      <div className="grid gap-4 text-sm text-muted-foreground border-b pb-1 font-semibold" style={gridCols}>
        <span></span>
        <span className="text-right">{companyData?.currentPeriodEndDate || `${fiscalYear ?? new Date().getFullYear()}-12-31`}</span>
        <span className="text-right">{companyData?.previousPeriodEndDate || `${(previousYear ?? (fiscalYear ? fiscalYear - 1 : new Date().getFullYear() - 1))}-12-31`}</span>
      </div>

      {/* Rows */}
      {(() => {
        let ordCounter = 0;
        return visible.map((it, idx) => {
          const getStyleClasses = (style?: string) => {
            const baseClasses = 'grid gap-4';
            let additionalClasses = '';
            const s = style || 'NORMAL';
            
            const boldStyles = ['H0','H1','H2','H3','S1','S2','S3','TH0','TH1','TH2','TH3','TS1','TS2','TS3'];
            if (boldStyles.includes(s)) {
              additionalClasses += ' font-semibold';
            }
            
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
          const isHeadingRow = isHeadingStyle(currentStyle);
          const isS2 = isSumRow(it);
          const editable = isEditing && isFlowVar(it.variable_name);
          
          const ordCur  = editable ? ++ordCounter : undefined;
          const ordPrev = editable ? ++ordCounter : undefined;
          
          const isRedVardeRow = it.variable_name === "red_varde_fordr_intresse";
          
          const curVal = isRedVardeRow
            ? redCur
            : (isS2 ? sumGroupAbove(visible, idx, 'cur') : getVal(it.variable_name ?? '', 'cur'));
          const prevVal = isRedVardeRow
            ? redPrev
            : (isS2 ? sumGroupAbove(visible, idx, 'prev') : getVal(it.variable_name ?? '', 'prev'));

          const curMismatch  = isEditing && isRedVardeRow && Math.round(redCur)  !== Math.round(brBookValueUBCur);
          const prevMismatch = isEditing && isRedVardeRow && Math.round(redPrev) !== Math.round(brBookValueUBPrev);
          
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
              <span className={`text-right font-medium ${isRedVardeRow && curMismatch ? 'text-red-600 font-bold' : ''}`}>
                {isHeadingRow ? '' : isRedVardeRow
                  ? `${numberToSv(curVal)} kr`
                  : <AmountCell
                      year="cur"
                      varName={it.variable_name!}
                      baseVar={it.variable_name!}
                      label={it.row_title}
                      editable={editable}
                      value={curVal}
                      ord={ordCur}
                      onCommit={(n) => setEditedValues(p => ({ ...p, [it.variable_name!]: n }))}
                      onTabNavigate={(el, dir) => focusByOrd(el, dir)}
                      onSignForced={(e) => pushSignNotice(e)}
                      expectedSignFor={expectedSignFor}
                    />
                }
              </span>

              {/* Previous year */}
              <span className={`text-right font-medium ${isRedVardeRow && prevMismatch ? 'text-red-600 font-bold' : ''}`}>
                {isHeadingRow ? '' : isRedVardeRow
                  ? `${numberToSv(prevVal)} kr`
                  : <AmountCell
                      year="prev"
                      varName={`${it.variable_name!}_prev`}
                      baseVar={it.variable_name!}
                      label={it.row_title}
                      editable={editable}
                      value={prevVal}
                      ord={ordPrev}
                      onCommit={(n) => setEditedPrevValues(p => ({ ...p, [it.variable_name!]: n }))}
                      onTabNavigate={(el, dir) => focusByOrd(el, dir)}
                      onSignForced={(e) => pushSignNotice(e)}
                      expectedSignFor={expectedSignFor}
                    />
                }
              </span>
            </div>
          );
        });
      })()}

      {/* Comparison row – only while editing */}
      {isEditing && (
        <div className="grid gap-4 border-t border-b border-gray-200 pt-1 pb-1 font-semibold bg-gray-50/50" style={gridCols}>
          <span className="text-muted-foreground font-semibold">Redovisat värde (bokfört)</span>
          <span className="text-right font-medium">{numberToSv(brBookValueUBCur)} kr</span>
          <span className="text-right font-medium">{numberToSv(brBookValueUBPrev)} kr</span>
        </div>
      )}

      {/* Action buttons */}
      {isEditing && (
        <div className="pt-4 flex justify-between">
          <Button 
            onClick={undoEdit}
            variant="outline"
            className="flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"/>
            </svg>
            Ångra ändringar
          </Button>
          
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

      {/* Toast Notification */}
      {showValidationMessage && (
        <div className="fixed bottom-4 right-4 z-50 bg-white rounded-lg shadow-lg p-4 max-w-sm animate-in slide-in-from-bottom-2">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <svg className="w-5 h-5 text-red-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                      d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </div>
            <div className="ml-3">
              {(() => {
                const curMism = Math.round(mismatch.deltaCur) !== 0;
                const prevMism = Math.round(mismatch.deltaPrev) !== 0;
                
                if (curMism && !prevMism) {
                  return (
                    <>
                      <p className="text-sm font-medium text-gray-900">
                        Summor balanserar inte {fiscalYear}
                      </p>
                      <p className="mt-1 text-sm text-gray-700">
                        Beräknat redovisat värde stämmer inte med bokfört värde. Differensen är {numberToSv(Math.abs(Math.round(mismatch.deltaCur)))} kr.
                      </p>
                    </>
                  );
                } else if (prevMism && !curMism) {
                  return (
                    <>
                      <p className="text-sm font-medium text-gray-900">
                        Summor balanserar inte {previousYear}
                      </p>
                      <p className="mt-1 text-sm text-gray-700">
                        Beräknat redovisat värde stämmer inte med bokfört värde. Differensen är {numberToSv(Math.abs(Math.round(mismatch.deltaPrev)))} kr.
                      </p>
                    </>
                  );
                } else {
                  return (
                    <>
                      <p className="text-sm font-medium text-gray-900">
                        Summor balanserar inte
                      </p>
                      <p className="mt-1 text-sm text-gray-700">
                        Beräknat redovisat värde stämmer inte med bokfört värde.
                      </p>
                      <ul className="mt-2 text-sm text-gray-900">
                        <li><strong>{fiscalYear}</strong>: Differens {numberToSv(Math.abs(Math.round(mismatch.deltaCur)))} kr</li>
                        <li><strong>{previousYear}</strong>: Differens {numberToSv(Math.abs(Math.round(mismatch.deltaPrev)))} kr</li>
                      </ul>
                    </>
                  );
                }
              })()}
            </div>
            <button
              onClick={() => { setShowValidationMessage(false); setMismatch(m => ({ ...m, open: false })); }}
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

// Fordringar hos övriga företag editor component
const FordringarOvrigaNote: React.FC<{
  items: NoterItem[];
  heading: string;
  fiscalYear?: number;
  previousYear?: number;
  companyData?: any;
  toggleOn: boolean;
  setToggle: (checked: boolean) => void;
}> = ({ items, heading, fiscalYear, previousYear, companyData, toggleOn, setToggle }) => {
  const gridCols = { gridTemplateColumns: "4fr 1fr 1fr" };

  const isFlowVar = (vn?: string) => {
    if (!vn) return false;
    if (/_ib\b/i.test(vn)) return false;
    if (/_ub\b/i.test(vn)) return false;
    if (/red[_-]?varde/i.test(vn)) return false;
    return true;
  };

  const byVar = useMemo(() => {
    const m = new Map<string, NoterItem>();
    items.forEach((it) => it.variable_name && m.set(it.variable_name, it));
    return m;
  }, [items]);

  // BR book value (UB) for both years - FORDROVRFTG specific
  const { brBookValueUBCur, brBookValueUBPrev } = React.useMemo(() => {
    const brData: any[] = companyData?.seFileData?.br_data || [];
    const candidates = [
      "FordringarOvrigaForetagAgarintresseLangfristiga",
      "FordringarOvrigaForetag",
      "OvrigaFordringar",
    ];
    let cur = 0, prev = 0;

    for (const c of candidates) {
      const hit = brData.find((x: any) => x.variable_name === c);
      if (hit) {
        if (Number.isFinite(hit.current_amount))  cur  = hit.current_amount;
        if (Number.isFinite(hit.previous_amount)) prev = hit.previous_amount;
        if (cur || prev) break;
      }
    }

    if (!cur)  cur  = byVar.get("red_varde_fordr_ovrigaftg")?.current_amount  ?? 0;
    if (!prev) prev = byVar.get("red_varde_fordr_ovrigaftg")?.previous_amount ?? 0;

    return { brBookValueUBCur: cur, brBookValueUBPrev: prev };
  }, [companyData, byVar]);

  // Baseline management
  const originalBaselineRef = React.useRef<{cur: Record<string, number>, prev: Record<string, number>}>({cur:{}, prev:{}});
  React.useEffect(() => {
    const cur: Record<string, number> = {};
    const prev: Record<string, number> = {};
    items.forEach(it => {
      const vn = it.variable_name;
      if (!vn) return;
      if (!isFlowVar(vn)) return;
      cur[vn] = it.current_amount ?? 0;
      prev[vn] = it.previous_amount ?? 0;
    });
    originalBaselineRef.current = { cur, prev };
  }, [items]);

  // Local edit state
  const [isEditing, setIsEditing] = useState(false);
  const [editedValues, setEditedValues] = useState<Record<string, number>>({});
  const [editedPrevValues, setEditedPrevValues] = useState<Record<string, number>>({});
  const [committedValues, setCommittedValues] = useState<Record<string, number>>({});
  const [committedPrevValues, setCommittedPrevValues] = useState<Record<string, number>>({});
  const [mismatch, setMismatch] = useState<{ open: boolean; deltaCur: number; deltaPrev: number }>({
    open: false,
    deltaCur: 0,
    deltaPrev: 0,
  });
  const [showValidationMessage, setShowValidationMessage] = useState(false);

  // Sign enforcement from CSV mapping - FORDROVRFTG specific (all flexible)
  const injectedSignMap: Record<string, '+' | '-'> | undefined = (companyData?.signByVar) || undefined;

  const heuristicSign = (vn: string): '+' | '-' | null => {
    // Based on variable_mapping_noter_rows (FORDROVRFTG).csv - all variables have no +/- sign
    // All variables are flexible (can be both + or -)
    return null; // all flexible
  };

  const expectedSignFor = (vn?: string): '+' | '-' | null => {
    if (!vn) return null;
    return injectedSignMap?.[vn] ?? heuristicSign(vn);
  };

  const getVal = React.useCallback((vn: string, year: 'cur' | 'prev') => {
    if (year === 'cur') {
      if (editedValues[vn] !== undefined) return editedValues[vn];
      if (committedValues[vn] !== undefined) return committedValues[vn];
      return byVar.get(vn)?.current_amount ?? 0;
    } else {
      if (editedPrevValues[vn] !== undefined) return editedPrevValues[vn];
      if (committedPrevValues[vn] !== undefined) return committedPrevValues[vn];
      return byVar.get(vn)?.previous_amount ?? 0;
    }
  }, [editedValues, committedValues, editedPrevValues, committedPrevValues, byVar]);

  const readCur = (it: NoterItem) => getVal(it.variable_name!, 'cur');
  const readPrev = (it: NoterItem) => getVal(it.variable_name!, 'prev');

  const visible = useMemo(() => {
    return buildVisibleWithHeadings({
      items,
      toggleOn,
      readCur: (it) => readCur(it),
      readPrev: (it) => readPrev(it),
    });
  }, [items, toggleOn, editedValues, editedPrevValues, committedValues, committedPrevValues]);

  const startEdit = () => {
    setIsEditing(true);
    setToggle?.(true);
  };

  React.useEffect(() => {
    if (showValidationMessage) {
      const timer = setTimeout(() => setShowValidationMessage(false), 5000);
      return () => clearTimeout(timer);
    }
  }, [showValidationMessage]);

  const cancelEdit = () => {
    setIsEditing(false);
    setEditedValues({});
    setEditedPrevValues({});
    setMismatch({ open: false, deltaCur: 0, deltaPrev: 0 });
    setShowValidationMessage(false);
    setToggle?.(false);
  };

  const undoEdit = () => {
    blurAllEditableInputs();
    setEditedValues({});
    setEditedPrevValues({});
    setCommittedValues({ ...originalBaselineRef.current.cur });
    setCommittedPrevValues({ ...originalBaselineRef.current.prev });
    setMismatch({ open: false, deltaCur: 0, deltaPrev: 0 });
    setShowValidationMessage(false);
  };

  const approveEdit = () => {
    const redCurCalc  = redCur;
    const redPrevCalc = redPrev;

    const deltaCur  = redCurCalc  - brBookValueUBCur;
    const deltaPrev = redPrevCalc - brBookValueUBPrev;

    const hasMismatch = Math.round(deltaCur) !== 0 || Math.round(deltaPrev) !== 0;

    if (hasMismatch) {
      setMismatch({ open: true, deltaCur, deltaPrev });
      setShowValidationMessage(true);
      return;
    }

    setCommittedValues(prev => ({ ...prev, ...editedValues }));
    setCommittedPrevValues(prev => ({ ...prev, ...editedPrevValues }));
    setEditedValues({});
    setEditedPrevValues({});
    setMismatch({ open: false, deltaCur: 0, deltaPrev: 0 });
    setShowValidationMessage(false);
    setIsEditing(false);
    setToggle?.(false);
  };

  // Helper functions
  const isSumRow = (it: NoterItem) => it.style === 'S2';
  const isHeading = (it: NoterItem) => isHeadingStyle(it.style);

  const sumGroupAbove = React.useCallback(
    (list: NoterItem[], index: number, year: 'cur' | 'prev') => {
      let sum = 0;
      for (let i = index - 1; i >= 0; i--) {
        const r = list[i];
        if (!r) break;
        if (isHeading(r) || r.style === 'S2') break;
        if (r.variable_name) sum += getVal(r.variable_name, year);
      }
      return sum;
    },
    [getVal]
  );

  const containerRef = React.useRef<HTMLDivElement>(null);

  const focusByOrd = (fromEl: HTMLInputElement, dir: 1 | -1) => {
    const root = containerRef.current;
    if (!root) return;
    const curOrd = Number(fromEl.dataset.ord || '0');
    const nextOrd = curOrd + dir;
    const next = root.querySelector<HTMLInputElement>(
      `input[data-editable-cell="1"][data-ord="${nextOrd}"]`
    );
    if (next) { next.focus(); next.select?.(); }
  };

  const blurAllEditableInputs = () => {
    const root = containerRef.current;
    if (!root) return;
    const nodes = root.querySelectorAll<HTMLInputElement>('input[data-editable-cell="1"]');
    nodes.forEach((el) => el.blur());
  };

  const pushSignNotice = (e: any) => {
    console.log(`Sign forced for ${e.label} (${e.year}): ${e.typed} → ${e.adjusted}`);
  };

  // Helper: get the dynamic S2 subtotal for FORDROVRFTG UB rows
  const ubSum = React.useCallback((ubVar: string, year: 'cur' | 'prev') => {
    const v = (name: string) => getVal(name, year) || 0;
    const idx = visible.findIndex(r => r.variable_name === ubVar);
    if (idx !== -1 && visible[idx]?.style === 'S2') {
      return sumGroupAbove(visible, idx, year);
    }
    // Fallbacks if the UB row isn't visible:
    switch (ubVar) {
      case 'fordr_ovrigaftg_ub':
        return v('fordr_ovrigaftg_ib') + v('nya_fordr_ovrigaftg') + v('fusion_fordr_ovrigaftg') + v('reglerade_fordr_ovrigaftg') + v('bortskrivna_fordr_ovrigaftg') + v('omklass_fordr_ovrigaftg');
      case 'ack_nedskr_fordr_ovrigaftg_ub':
        return v('ack_nedskr_fordr_ovrigaftg_ib') + v('aterfor_nedskr_reglerade_fordr_ovrigaftg') + v('aterfor_nedskr_fusion_fordr_ovrigaftg') + v('aterfor_nedskr_fordr_ovrigaftg') + v('aterfor_nedskr_bortskrivna_fordr_ovrigaftg') + v('omklass_nedskr_fordr_ovrigaftg') + v('arets_nedskr_fordr_ovrigaftg');
      default:
        return getVal(ubVar, year);
    }
  }, [visible, sumGroupAbove, getVal]);

  // Sum the actual S2 subtotals for FORDROVRFTG (anskaffning + nedskrivningar only)
  const redCur  = ['fordr_ovrigaftg_ub','ack_nedskr_fordr_ovrigaftg_ub']
    .map(n => ubSum(n, 'cur'))
    .reduce((a,b) => a + b, 0);

  const redPrev = ['fordr_ovrigaftg_ub','ack_nedskr_fordr_ovrigaftg_ub']
    .map(n => ubSum(n, 'prev'))
    .reduce((a,b) => a + b, 0);

  return (
    <div ref={containerRef} className="space-y-2 pt-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b pb-1">
        <div className="flex items-center gap-3">
          <h3 className="text-lg font-semibold pt-1">{heading}</h3>
          <button
            onClick={() => isEditing ? cancelEdit() : startEdit()}
            className={`w-6 h-6 rounded-full flex items-center justify-center transition-colors ${
              isEditing ? 'bg-blue-600 text-white' : 'bg-gray-200 hover:bg-gray-300 text-gray-600'
            }`}
            title={isEditing ? 'Avsluta redigering' : 'Redigera värden'}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                    d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
            </svg>
          </button>
        </div>
        <div className="flex items-center space-x-2">
          <label htmlFor="toggle-fordrovrftg-rows" className="text-sm font-medium cursor-pointer">
            Visa alla rader
          </label>
          <Switch
            id="toggle-fordrovrftg-rows"
            checked={toggleOn}
            onCheckedChange={setToggle}
          />
        </div>
      </div>

      {/* Column headers */}
      <div className="grid gap-4 text-sm text-muted-foreground border-b pb-1 font-semibold" style={gridCols}>
        <span></span>
        <span className="text-right">{companyData?.currentPeriodEndDate || `${fiscalYear ?? new Date().getFullYear()}-12-31`}</span>
        <span className="text-right">{companyData?.previousPeriodEndDate || `${(previousYear ?? (fiscalYear ? fiscalYear - 1 : new Date().getFullYear() - 1))}-12-31`}</span>
      </div>

      {/* Rows */}
      {(() => {
        let ordCounter = 0;
        return visible.map((it, idx) => {
          const getStyleClasses = (style?: string) => {
            const baseClasses = 'grid gap-4';
            let additionalClasses = '';
            const s = style || 'NORMAL';
            
            const boldStyles = ['H0','H1','H2','H3','S1','S2','S3','TH0','TH1','TH2','TH3','TS1','TS2','TS3'];
            if (boldStyles.includes(s)) {
              additionalClasses += ' font-semibold';
            }
            
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
          const isHeadingRow = isHeadingStyle(currentStyle);
          const isS2 = isSumRow(it);
          const editable = isEditing && isFlowVar(it.variable_name);
          
          const ordCur  = editable ? ++ordCounter : undefined;
          const ordPrev = editable ? ++ordCounter : undefined;
          
          const isRedVardeRow = it.variable_name === "red_varde_fordr_ovrigaftg";
          
          const curVal = isRedVardeRow
            ? redCur
            : (isS2 ? sumGroupAbove(visible, idx, 'cur') : getVal(it.variable_name ?? '', 'cur'));
          const prevVal = isRedVardeRow
            ? redPrev
            : (isS2 ? sumGroupAbove(visible, idx, 'prev') : getVal(it.variable_name ?? '', 'prev'));

          const curMismatch  = isEditing && isRedVardeRow && Math.round(redCur)  !== Math.round(brBookValueUBCur);
          const prevMismatch = isEditing && isRedVardeRow && Math.round(redPrev) !== Math.round(brBookValueUBPrev);
          
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
              <span className={`text-right font-medium ${isRedVardeRow && curMismatch ? 'text-red-600 font-bold' : ''}`}>
                {isHeadingRow ? '' : isRedVardeRow
                  ? `${numberToSv(curVal)} kr`
                  : <AmountCell
                      year="cur"
                      varName={it.variable_name!}
                      baseVar={it.variable_name!}
                      label={it.row_title}
                      editable={editable}
                      value={curVal}
                      ord={ordCur}
                      onCommit={(n) => setEditedValues(p => ({ ...p, [it.variable_name!]: n }))}
                      onTabNavigate={(el, dir) => focusByOrd(el, dir)}
                      onSignForced={(e) => pushSignNotice(e)}
                      expectedSignFor={expectedSignFor}
                    />
                }
              </span>

              {/* Previous year */}
              <span className={`text-right font-medium ${isRedVardeRow && prevMismatch ? 'text-red-600 font-bold' : ''}`}>
                {isHeadingRow ? '' : isRedVardeRow
                  ? `${numberToSv(prevVal)} kr`
                  : <AmountCell
                      year="prev"
                      varName={`${it.variable_name!}_prev`}
                      baseVar={it.variable_name!}
                      label={it.row_title}
                      editable={editable}
                      value={prevVal}
                      ord={ordPrev}
                      onCommit={(n) => setEditedPrevValues(p => ({ ...p, [it.variable_name!]: n }))}
                      onTabNavigate={(el, dir) => focusByOrd(el, dir)}
                      onSignForced={(e) => pushSignNotice(e)}
                      expectedSignFor={expectedSignFor}
                    />
                }
              </span>
            </div>
          );
        });
      })()}

      {/* Comparison row – only while editing */}
      {isEditing && (
        <div className="grid gap-4 border-t border-b border-gray-200 pt-1 pb-1 font-semibold bg-gray-50/50" style={gridCols}>
          <span className="text-muted-foreground font-semibold">Redovisat värde (bokfört)</span>
          <span className="text-right font-medium">{numberToSv(brBookValueUBCur)} kr</span>
          <span className="text-right font-medium">{numberToSv(brBookValueUBPrev)} kr</span>
        </div>
      )}

      {/* Action buttons */}
      {isEditing && (
        <div className="pt-4 flex justify-between">
          <Button 
            onClick={undoEdit}
            variant="outline"
            className="flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"/>
            </svg>
            Ångra ändringar
          </Button>
          
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

      {/* Toast Notification */}
      {showValidationMessage && (
        <div className="fixed bottom-4 right-4 z-50 bg-white rounded-lg shadow-lg p-4 max-w-sm animate-in slide-in-from-bottom-2">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <svg className="w-5 h-5 text-red-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                      d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </div>
            <div className="ml-3">
              {(() => {
                const curMism = Math.round(mismatch.deltaCur) !== 0;
                const prevMism = Math.round(mismatch.deltaPrev) !== 0;
                
                if (curMism && !prevMism) {
                  return (
                    <>
                      <p className="text-sm font-medium text-gray-900">
                        Summor balanserar inte {fiscalYear}
                      </p>
                      <p className="mt-1 text-sm text-gray-700">
                        Beräknat redovisat värde stämmer inte med bokfört värde. Differensen är {numberToSv(Math.abs(Math.round(mismatch.deltaCur)))} kr.
                      </p>
                    </>
                  );
                } else if (prevMism && !curMism) {
                  return (
                    <>
                      <p className="text-sm font-medium text-gray-900">
                        Summor balanserar inte {previousYear}
                      </p>
                      <p className="mt-1 text-sm text-gray-700">
                        Beräknat redovisat värde stämmer inte med bokfört värde. Differensen är {numberToSv(Math.abs(Math.round(mismatch.deltaPrev)))} kr.
                      </p>
                    </>
                  );
                } else {
                  return (
                    <>
                      <p className="text-sm font-medium text-gray-900">
                        Summor balanserar inte
                      </p>
                      <p className="mt-1 text-sm text-gray-700">
                        Beräknat redovisat värde stämmer inte med bokfört värde.
                      </p>
                      <ul className="mt-2 text-sm text-gray-900">
                        <li><strong>{fiscalYear}</strong>: Differens {numberToSv(Math.abs(Math.round(mismatch.deltaCur)))} kr</li>
                        <li><strong>{previousYear}</strong>: Differens {numberToSv(Math.abs(Math.round(mismatch.deltaPrev)))} kr</li>
                      </ul>
                    </>
                  );
                }
              })()}
            </div>
            <button
              onClick={() => { setShowValidationMessage(false); setMismatch(m => ({ ...m, open: false })); }}
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

// Eventualförpliktelser editor component
const EventualNote: React.FC<{
  items: NoterItem[];
  heading: string;
  fiscalYear?: number;
  previousYear?: number;
  companyData?: any;
  toggleOn: boolean;
  setToggle: (checked: boolean) => void;
  blockToggles: Record<string, boolean>;
  setBlockToggles: (fn: (prev: Record<string, boolean>) => Record<string, boolean>) => void;
}> = ({ items, heading, fiscalYear, previousYear, companyData, toggleOn, setToggle, blockToggles, setBlockToggles }) => {
  const gridCols = { gridTemplateColumns: "4fr 1fr 1fr" };

  const isFlowVar = (vn?: string) => {
    if (!vn) return false;
    // For EVENTUAL, all variables with names are editable
    return true;
  };

  const byVar = useMemo(() => {
    const m = new Map<string, NoterItem>();
    items.forEach((it) => it.variable_name && m.set(it.variable_name, it));
    return m;
  }, [items]);

  // No BR book value for EVENTUAL - it's not a balance sheet asset calculation
  const brBookValueUBCur = 0;
  const brBookValueUBPrev = 0;

  // Baseline management
  const originalBaselineRef = React.useRef<{cur: Record<string, number>, prev: Record<string, number>}>({cur:{}, prev:{}});
  React.useEffect(() => {
    const cur: Record<string, number> = {};
    const prev: Record<string, number> = {};
    items.forEach(it => {
      const vn = it.variable_name;
      if (!vn) return;
      cur[vn] = it.current_amount ?? 0;
      prev[vn] = it.previous_amount ?? 0;
    });
    originalBaselineRef.current = { cur, prev };
  }, [items]);

  // Local edit state
  const [isEditing, setIsEditing] = useState(false);
  const [editedValues, setEditedValues] = useState<Record<string, number>>({});
  const [editedPrevValues, setEditedPrevValues] = useState<Record<string, number>>({});
  const [committedValues, setCommittedValues] = useState<Record<string, number>>({});
  const [committedPrevValues, setCommittedPrevValues] = useState<Record<string, number>>({});
  const [showValidationMessage, setShowValidationMessage] = useState(false);

  // Sign enforcement - all flexible for EVENTUAL
  const expectedSignFor = (vn?: string): '+' | '-' | null => {
    return null;
  };

  const getVal = React.useCallback((vn: string, year: 'cur' | 'prev') => {
    if (year === 'cur') {
      if (editedValues[vn] !== undefined) return editedValues[vn];
      if (committedValues[vn] !== undefined) return committedValues[vn];
      return byVar.get(vn)?.current_amount ?? 0;
    } else {
      if (editedPrevValues[vn] !== undefined) return editedPrevValues[vn];
      if (committedPrevValues[vn] !== undefined) return committedPrevValues[vn];
      return byVar.get(vn)?.previous_amount ?? 0;
    }
  }, [editedValues, committedValues, editedPrevValues, committedPrevValues, byVar]);

  const readCur = (it: NoterItem) => getVal(it.variable_name!, 'cur');
  const readPrev = (it: NoterItem) => getVal(it.variable_name!, 'prev');

  const visible = useMemo(() => {
    return buildVisibleWithHeadings({
      items,
      toggleOn,
      readCur: (it) => readCur(it),
      readPrev: (it) => readPrev(it),
    });
  }, [items, toggleOn, editedValues, editedPrevValues, committedValues, committedPrevValues]);

  const startEdit = () => {
    setIsEditing(true);
    setToggle?.(true);
  };

  const cancelEdit = () => {
    setIsEditing(false);
    setEditedValues({});
    setEditedPrevValues({});
    setShowValidationMessage(false);
    setToggle?.(false);
  };

  const undoEdit = () => {
    blurAllEditableInputs();
    setEditedValues({});
    setEditedPrevValues({});
    setCommittedValues({ ...originalBaselineRef.current.cur });
    setCommittedPrevValues({ ...originalBaselineRef.current.prev });
    setShowValidationMessage(false);
  };

  const approveEdit = () => {
    // No balance validation for EVENTUAL - just commit the values
    setCommittedValues(prev => ({ ...prev, ...editedValues }));
    setCommittedPrevValues(prev => ({ ...prev, ...editedPrevValues }));
    setEditedValues({});
    setEditedPrevValues({});
    setIsEditing(false);
    setToggle?.(false);
  };

  // Helper functions
  const isSumRow = (it: NoterItem) => it.style === 'S2';
  const isHeading = (it: NoterItem) => isHeadingStyle(it.style);

  const sumGroupAbove = React.useCallback(
    (list: NoterItem[], index: number, year: 'cur' | 'prev') => {
      let sum = 0;
      for (let i = index - 1; i >= 0; i--) {
        const r = list[i];
        if (!r) break;
        if (isHeading(r) || r.style === 'S2') break;
        if (r.variable_name) sum += getVal(r.variable_name, year);
      }
      return sum;
    },
    [getVal]
  );

  const containerRef = React.useRef<HTMLDivElement>(null);

  const focusByOrd = (fromEl: HTMLInputElement, dir: 1 | -1) => {
    const root = containerRef.current;
    if (!root) return;
    const curOrd = Number(fromEl.dataset.ord || '0');
    const nextOrd = curOrd + dir;
    const next = root.querySelector<HTMLInputElement>(
      `input[data-editable-cell="1"][data-ord="${nextOrd}"]`
    );
    if (next) { next.focus(); next.select?.(); }
  };

  const blurAllEditableInputs = () => {
    const root = containerRef.current;
    if (!root) return;
    const inputs = root.querySelectorAll<HTMLInputElement>('input[data-editable-cell="1"]');
    inputs.forEach(inp => inp.blur());
  };

  const pushSignNotice = (e: { label: string; year: string; typed: string; adjusted: string }) => {
    console.log(`Sign forced for ${e.label} (${e.year}): ${e.typed} → ${e.adjusted}`);
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

  return (
    <div ref={containerRef} className="space-y-2 pt-4">
      {/* Header with edit button and visibility toggle only */}
      <div className="flex items-center justify-between border-b pb-1">
        <div className="flex items-center">
          <h3 className={`font-semibold text-lg ${blockToggles['eventual-visibility'] !== true ? 'opacity-35' : ''}`} style={{paddingTop: '7px'}}>
            {heading}
          </h3>
          <button
            onClick={() => isEditing ? cancelEdit() : startEdit()}
            className={`ml-3 w-6 h-6 rounded-full flex items-center justify-center transition-colors ${
              isEditing ? 'bg-blue-600 text-white' : 'bg-gray-200 hover:bg-gray-300 text-gray-600'
            } ${blockToggles['eventual-visibility'] !== true ? 'opacity-35' : ''}`}
            title={isEditing ? 'Avsluta redigering' : 'Redigera värden'}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                    d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
            </svg>
          </button>
          <div className={`ml-2 flex items-center ${blockToggles['eventual-visibility'] !== true ? 'opacity-35' : ''}`} style={{transform: 'scale(0.75)', marginTop: '5px'}}>
            <Switch
              checked={blockToggles['eventual-visibility'] === true} // Default to false (hidden)
              onCheckedChange={(checked) => 
                setBlockToggles(prev => ({ ...prev, ['eventual-visibility']: checked }))
              }
            />
            <span className="ml-2 font-medium" style={{fontSize: '17px'}}>Visa not</span>
          </div>
        </div>
      </div>

      {/* Only show content if visibility toggle is on */}
      {blockToggles['eventual-visibility'] === true && (
        <>
          {/* Column headers */}
          <div className="grid gap-4 text-sm text-muted-foreground border-b pb-1 font-semibold" style={gridCols}>
            <span></span>
            <span className="text-right">{companyData?.currentPeriodEndDate || `${fiscalYear ?? new Date().getFullYear()}-12-31`}</span>
            <span className="text-right">{companyData?.previousPeriodEndDate || `${(previousYear ?? (fiscalYear ? fiscalYear - 1 : new Date().getFullYear() - 1))}-12-31`}</span>
          </div>

          {/* Rows */}
          {(() => {
            let ordCounter = 0;
            return visible.map((it, idx) => {
              const getStyleClasses = (style?: string) => {
                const baseClasses = 'grid gap-4';
                let additionalClasses = '';
                const s = style || 'NORMAL';
                
                const boldStyles = ['H0','H1','H2','H3','S1','S2','S3','TH0','TH1','TH2','TH3','TS1','TS2','TS3'];
                if (boldStyles.includes(s)) {
                  additionalClasses += ' font-semibold';
                }
                
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
              const isHeadingRow = isHeadingStyle(currentStyle);
              const isS2 = isSumRow(it);
              const editable = isEditing && isFlowVar(it.variable_name);
              
              const ordCur  = editable ? ++ordCounter : undefined;
              const ordPrev = editable ? ++ordCounter : undefined;
              
              const curVal = isS2 ? sumGroupAbove(visible, idx, 'cur') : getVal(it.variable_name ?? '', 'cur');
              const prevVal = isS2 ? sumGroupAbove(visible, idx, 'prev') : getVal(it.variable_name ?? '', 'prev');
              
              const gc = getStyleClasses(currentStyle);
              
              return (
                <div 
                  key={`${it.row_id}-${idx}`}
                  className={gc.className}
                  style={gc.style}
                >
                  <span className="text-muted-foreground">{it.row_title}</span>
                  
                  {/* Current year amount */}
                  <span className="text-right font-medium">
                    {isHeadingRow ? '' : (
                      <AmountCell
                        year="cur"
                        varName={it.variable_name!}
                        baseVar={it.variable_name!}
                        label={it.row_title}
                        editable={editable}
                        value={curVal}
                        ord={ordCur}
                        onCommit={(n) => setEditedValues(p => ({ ...p, [it.variable_name!]: n }))}
                        onTabNavigate={(el, dir) => focusByOrd(el, dir)}
                        onSignForced={(e) => pushSignNotice(e)}
                        expectedSignFor={expectedSignFor}
                      />
                    )}
                  </span>
                  
                  {/* Previous year amount */}
                  <span className="text-right font-medium">
                    {isHeadingRow ? '' : (
                      <AmountCell
                        year="prev"
                        varName={`${it.variable_name!}_prev`}
                        baseVar={it.variable_name!}
                        label={it.row_title}
                        editable={editable}
                        value={prevVal}
                        ord={ordPrev}
                        onCommit={(n) => setEditedPrevValues(p => ({ ...p, [it.variable_name!]: n }))}
                        onTabNavigate={(el, dir) => focusByOrd(el, dir)}
                        onSignForced={(e) => pushSignNotice(e)}
                        expectedSignFor={expectedSignFor}
                      />
                    )}
                  </span>
                </div>
              );
            });
          })()}

          {/* Action buttons - only show when editing */}
          {isEditing && (
            <div className="flex justify-between pt-4 border-t border-gray-200">
              <button
                onClick={undoEdit}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
              >
                Ångra
              </button>
              <button
                onClick={approveEdit}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700"
              >
                Godkänn ändringar
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
};

// Ställda säkerheter editor component
const SakerhetNote: React.FC<{
  items: NoterItem[];
  heading: string;
  fiscalYear?: number;
  previousYear?: number;
  companyData?: any;
  toggleOn: boolean;
  setToggle: (checked: boolean) => void;
  blockToggles: Record<string, boolean>;
  setBlockToggles: (fn: (prev: Record<string, boolean>) => Record<string, boolean>) => void;
}> = ({ items, heading, fiscalYear, previousYear, companyData, toggleOn, setToggle, blockToggles, setBlockToggles }) => {
  const gridCols = { gridTemplateColumns: "4fr 1fr 1fr" };

  const isFlowVar = (vn?: string) => {
    if (!vn) return false;
    // For SAKERHET, all variables with names are editable (no IB/UB concept)
    return true;
  };

  const byVar = useMemo(() => {
    const m = new Map<string, NoterItem>();
    items.forEach((it) => it.variable_name && m.set(it.variable_name, it));
    return m;
  }, [items]);

  // No BR book value for SAKERHET - it's not a balance sheet asset calculation
  const brBookValueUBCur = 0;
  const brBookValueUBPrev = 0;

  // Baseline management
  const originalBaselineRef = React.useRef<{cur: Record<string, number>, prev: Record<string, number>}>({cur:{}, prev:{}});
  React.useEffect(() => {
    const cur: Record<string, number> = {};
    const prev: Record<string, number> = {};
    items.forEach(it => {
      const vn = it.variable_name;
      if (!vn) return;
      cur[vn] = it.current_amount ?? 0;
      prev[vn] = it.previous_amount ?? 0;
    });
    originalBaselineRef.current = { cur, prev };
  }, [items]);

  // Local edit state
  const [isEditing, setIsEditing] = useState(false);
  const [editedValues, setEditedValues] = useState<Record<string, number>>({});
  const [editedPrevValues, setEditedPrevValues] = useState<Record<string, number>>({});
  const [committedValues, setCommittedValues] = useState<Record<string, number>>({});
  const [committedPrevValues, setCommittedPrevValues] = useState<Record<string, number>>({});
  const [showValidationMessage, setShowValidationMessage] = useState(false);

  // Sign enforcement - all flexible for SAKERHET (security positions can be any amount)
  const expectedSignFor = (vn?: string): '+' | '-' | null => {
    // All security variables are flexible - can be positive or negative
    return null;
  };

  const getVal = React.useCallback((vn: string, year: 'cur' | 'prev') => {
    if (year === 'cur') {
      if (editedValues[vn] !== undefined) return editedValues[vn];
      if (committedValues[vn] !== undefined) return committedValues[vn];
      return byVar.get(vn)?.current_amount ?? 0;
    } else {
      if (editedPrevValues[vn] !== undefined) return editedPrevValues[vn];
      if (committedPrevValues[vn] !== undefined) return committedPrevValues[vn];
      return byVar.get(vn)?.previous_amount ?? 0;
    }
  }, [editedValues, committedValues, editedPrevValues, committedPrevValues, byVar]);

  const readCur = (it: NoterItem) => getVal(it.variable_name!, 'cur');
  const readPrev = (it: NoterItem) => getVal(it.variable_name!, 'prev');

  const visible = useMemo(() => {
    return buildVisibleWithHeadings({
      items,
      toggleOn,
      readCur: (it) => readCur(it),
      readPrev: (it) => readPrev(it),
    });
  }, [items, toggleOn, editedValues, editedPrevValues, committedValues, committedPrevValues]);

  const startEdit = () => {
    setIsEditing(true);
    setToggle?.(true);
  };

  const cancelEdit = () => {
    setIsEditing(false);
    setEditedValues({});
    setEditedPrevValues({});
    setShowValidationMessage(false);
    setToggle?.(false);
  };

  const undoEdit = () => {
    blurAllEditableInputs();
    setEditedValues({});
    setEditedPrevValues({});
    setCommittedValues({ ...originalBaselineRef.current.cur });
    setCommittedPrevValues({ ...originalBaselineRef.current.prev });
    setShowValidationMessage(false);
  };

  const approveEdit = () => {
    // No balance validation for SAKERHET - just commit the values
    setCommittedValues(prev => ({ ...prev, ...editedValues }));
    setCommittedPrevValues(prev => ({ ...prev, ...editedPrevValues }));
    setEditedValues({});
    setEditedPrevValues({});
    setIsEditing(false);
    setToggle?.(false);
  };

  // Helper functions
  const isSumRow = (it: NoterItem) => it.style === 'S2';
  const isHeading = (it: NoterItem) => isHeadingStyle(it.style);

  const sumGroupAbove = React.useCallback(
    (list: NoterItem[], index: number, year: 'cur' | 'prev') => {
      let sum = 0;
      for (let i = index - 1; i >= 0; i--) {
        const r = list[i];
        if (!r) break;
        if (isHeading(r) || r.style === 'S2') break;
        if (r.variable_name) sum += getVal(r.variable_name, year);
      }
      return sum;
    },
    [getVal]
  );

  const containerRef = React.useRef<HTMLDivElement>(null);

  const focusByOrd = (fromEl: HTMLInputElement, dir: 1 | -1) => {
    const root = containerRef.current;
    if (!root) return;
    const curOrd = Number(fromEl.dataset.ord || '0');
    const nextOrd = curOrd + dir;
    const next = root.querySelector<HTMLInputElement>(
      `input[data-editable-cell="1"][data-ord="${nextOrd}"]`
    );
    if (next) { next.focus(); next.select?.(); }
  };

  const blurAllEditableInputs = () => {
    const root = containerRef.current;
    if (!root) return;
    const nodes = root.querySelectorAll<HTMLInputElement>('input[data-editable-cell="1"]');
    nodes.forEach((el) => el.blur());
  };

  const pushSignNotice = (e: any) => {
    console.log(`Sign forced for ${e.label} (${e.year}): ${e.typed} → ${e.adjusted}`);
  };

  return (
    <div ref={containerRef} className="space-y-2 pt-4">
      {/* Header with both toggles */}
      <div className="flex items-center justify-between border-b pb-1">
        <div className="flex items-center">
          <h3 className={`font-semibold text-lg ${blockToggles['sakerhet-visibility'] !== true ? 'opacity-35' : ''}`} style={{paddingTop: '7px'}}>
            {heading}
          </h3>
          <button
            onClick={() => isEditing ? cancelEdit() : startEdit()}
            className={`ml-3 w-6 h-6 rounded-full flex items-center justify-center transition-colors ${
              isEditing ? 'bg-blue-600 text-white' : 'bg-gray-200 hover:bg-gray-300 text-gray-600'
            } ${blockToggles['sakerhet-visibility'] !== true ? 'opacity-35' : ''}`}
            title={isEditing ? 'Avsluta redigering' : 'Redigera värden'}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                    d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
            </svg>
          </button>
          <div className={`ml-2 flex items-center ${blockToggles['sakerhet-visibility'] !== true ? 'opacity-35' : ''}`} style={{transform: 'scale(0.75)', marginTop: '5px'}}>
            <Switch
              checked={blockToggles['sakerhet-visibility'] === true} // Default to false (hidden)
              onCheckedChange={(checked) => 
                setBlockToggles(prev => ({ ...prev, ['sakerhet-visibility']: checked }))
              }
            />
            <span className="ml-2 font-medium" style={{fontSize: '17px'}}>Visa not</span>
          </div>
        </div>
        <div className={`flex items-center space-x-2 ${blockToggles['sakerhet-visibility'] !== true ? 'opacity-35' : ''}`}>
          <label htmlFor="toggle-sakerhet-rows" className="text-sm font-medium cursor-pointer">
            Visa alla rader
          </label>
          <Switch
            id="toggle-sakerhet-rows"
            checked={toggleOn}
            onCheckedChange={setToggle}
          />
        </div>
      </div>

      {/* Only show content if visibility toggle is on */}
      {blockToggles['sakerhet-visibility'] === true && (
        <>
          {/* Column headers */}
          <div className="grid gap-4 text-sm text-muted-foreground border-b pb-1 font-semibold" style={gridCols}>
            <span></span>
            <span className="text-right">{companyData?.currentPeriodEndDate || `${fiscalYear ?? new Date().getFullYear()}-12-31`}</span>
            <span className="text-right">{companyData?.previousPeriodEndDate || `${(previousYear ?? (fiscalYear ? fiscalYear - 1 : new Date().getFullYear() - 1))}-12-31`}</span>
          </div>

          {/* Rows */}
          {(() => {
            let ordCounter = 0;
            return visible.map((it, idx) => {
          const getStyleClasses = (style?: string) => {
            const baseClasses = 'grid gap-4';
            let additionalClasses = '';
            const s = style || 'NORMAL';
            
            const boldStyles = ['H0','H1','H2','H3','S1','S2','S3','TH0','TH1','TH2','TH3','TS1','TS2','TS3'];
            if (boldStyles.includes(s)) {
              additionalClasses += ' font-semibold';
            }
            
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
          const isHeadingRow = isHeadingStyle(currentStyle);
          const isS2 = isSumRow(it);
          const editable = isEditing && isFlowVar(it.variable_name);
          
          const ordCur  = editable ? ++ordCounter : undefined;
          const ordPrev = editable ? ++ordCounter : undefined;
          
          // For SAKERHET S2 sum, calculate total of main security items (exclude group_ variables)
          const curVal = isS2 
            ? items.filter(r => r.variable_name && !r.variable_name.startsWith('group_') && r.variable_name !== 'sum_stallda_sakerheter')
                   .reduce((sum, r) => sum + getVal(r.variable_name!, 'cur'), 0)
            : getVal(it.variable_name ?? '', 'cur');
          const prevVal = isS2 
            ? items.filter(r => r.variable_name && !r.variable_name.startsWith('group_') && r.variable_name !== 'sum_stallda_sakerheter')
                   .reduce((sum, r) => sum + getVal(r.variable_name!, 'prev'), 0)
            : getVal(it.variable_name ?? '', 'prev');
          
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
              <span className="text-right font-medium">
                {isHeadingRow ? '' : (
                  <AmountCell
                    year="cur"
                    varName={it.variable_name!}
                    baseVar={it.variable_name!}
                    label={it.row_title}
                    editable={editable}
                    value={curVal}
                    ord={ordCur}
                    onCommit={(n) => setEditedValues(p => ({ ...p, [it.variable_name!]: n }))}
                    onTabNavigate={(el, dir) => focusByOrd(el, dir)}
                    onSignForced={(e) => pushSignNotice(e)}
                    expectedSignFor={expectedSignFor}
                  />
                )}
              </span>

              {/* Previous year */}
              <span className="text-right font-medium">
                {isHeadingRow ? '' : (
                  <AmountCell
                    year="prev"
                    varName={`${it.variable_name!}_prev`}
                    baseVar={it.variable_name!}
                    label={it.row_title}
                    editable={editable}
                    value={prevVal}
                    ord={ordPrev}
                    onCommit={(n) => setEditedPrevValues(p => ({ ...p, [it.variable_name!]: n }))}
                    onTabNavigate={(el, dir) => focusByOrd(el, dir)}
                    onSignForced={(e) => pushSignNotice(e)}
                    expectedSignFor={expectedSignFor}
                  />
                )}
              </span>
            </div>
          );
        });
      })()}

      {/* Action buttons - no balance validation needed for SAKERHET */}
      {isEditing && (
        <div className="pt-4 flex justify-between">
          <Button 
            onClick={undoEdit}
            variant="outline"
            className="flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"/>
            </svg>
            Ångra ändringar
          </Button>
          
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
        </>
      )}
    </div>
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

  // BR book value (UB) for both years
  const { brBookValueUBCur, brBookValueUBPrev } = React.useMemo(() => {
    const brData: any[] = companyData?.seFileData?.br_data || [];
    const candidates = [
      "InventarierVerktygInstallationer",
      "Inventarier",
      "InventarierVerktygInst",
    ];
    let cur = 0, prev = 0;

    for (const c of candidates) {
      const hit = brData.find((x: any) => x.variable_name === c);
      if (hit) {
        if (Number.isFinite(hit.current_amount))  cur  = hit.current_amount;
        if (Number.isFinite(hit.previous_amount)) prev = hit.previous_amount;
        if (cur || prev) break;
      }
    }

    // Fallback to note values if BR is missing
    if (!cur)  cur  = byVar.get("red_varde_inventarier")?.current_amount  ?? 0;
    if (!prev) prev = byVar.get("red_varde_inventarier")?.previous_amount ?? 0;

    return { brBookValueUBCur: cur, brBookValueUBPrev: prev };
  }, [companyData, byVar]);

  // Baseline management - save original values for proper undo
  const originalBaselineRef = React.useRef<{cur: Record<string, number>, prev: Record<string, number>}>({cur:{}, prev:{}});
  React.useEffect(() => {
    const cur: Record<string, number> = {};
    const prev: Record<string, number> = {};
    items.forEach(it => {
      const vn = it.variable_name;
      if (!vn) return;
      if (!isFlowVar(vn)) return;                 // baseline bara för flöden
      cur[vn] = it.current_amount ?? 0;
      prev[vn] = it.previous_amount ?? 0;
    });
    originalBaselineRef.current = { cur, prev };
  }, [items]);  // uppdatera baseline om ny SIE/parse kommer in

  // Local edit state (simplified to match FB)
  const [isEditing, setIsEditing] = useState(false);
  const [editedValues, setEditedValues] = useState<Record<string, number>>({});
  const [editedPrevValues, setEditedPrevValues] = useState<Record<string, number>>({});
  const [committedValues, setCommittedValues] = useState<Record<string, number>>({});       // NEW
  const [committedPrevValues, setCommittedPrevValues] = useState<Record<string, number>>({});
  const [mismatch, setMismatch] = useState<{ open: boolean; deltaCur: number; deltaPrev: number }>({
    open: false,
    deltaCur: 0,
    deltaPrev: 0,
  });
  const [showValidationMessage, setShowValidationMessage] = useState(false);


  // Sign enforcement from SQL mapping
  // Optional: inject a real mapping from SQL -> { [variable_name]: '+' | '-' }
  const injectedSignMap: Record<string, '+' | '-'> | undefined = (companyData?.signByVar) || undefined;

  // Heuristic fallback based on actual CSV mapping for INV block
  const heuristicSign = (vn: string): '+' | '-' | null => {
    // Based on variable_mapping_noter_rows (3).csv
    const positiveVars = [
      'arets_inkop_inventarier',
      'aterfor_avskr_fsg_inventarier', 
      'aterfor_nedskr_fsg_inventarier',
      'aterfor_nedskr_inventarier'
    ];
    
    const negativeVars = [
      'arets_fsg_inventarier',
      'arets_avskr_inventarier', 
      'arets_nedskr_inventarier'
    ];
    
    if (positiveVars.includes(vn)) return '+';
    if (negativeVars.includes(vn)) return '-';
    return null; // flexible - can be both + or -
  };

  // Unified accessor
  const expectedSignFor = (vn?: string): '+' | '-' | null => {
    if (!vn) return null;
    return injectedSignMap?.[vn] ?? heuristicSign(vn);
  };

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

  // Single accessor that S2 and "beräknat" use (no live state)
  const getVal = React.useCallback((vn: string, year: 'cur' | 'prev') => {
    if (year === 'cur') {
      if (editedValues[vn] !== undefined) return editedValues[vn];
      if (committedValues[vn] !== undefined) return committedValues[vn];
      return byVar.get(vn)?.current_amount ?? 0;
    } else {
      // VIKTIGT: edited före committed, annars kan du inte skriva 0 efter Godkänn
      if (editedPrevValues[vn] !== undefined) return editedPrevValues[vn];
      if (committedPrevValues[vn] !== undefined) return committedPrevValues[vn];
      return byVar.get(vn)?.previous_amount ?? 0;
    }
  }, [editedValues, committedValues, editedPrevValues, committedPrevValues, byVar]);

  // Helper function to get current value (edited or original) - matching FB
  const getCurrentValue = (variableName: string): number => {
    return getVal(variableName, 'cur');
  };


  // Read current/prev amount, considering edits
  const readCur = (it: NoterItem) => getVal(it.variable_name!, 'cur');
  const readPrev = (it: NoterItem) => getVal(it.variable_name!, 'prev');

  const visible = useMemo(() => {
    return buildVisibleWithHeadings({
      items,
      toggleOn,
      readCur: (it) => readCur(it),
      readPrev: (it) => readPrev(it),
    });
  }, [items, toggleOn, editedValues, editedPrevValues, committedValues, committedPrevValues]);

  // Compute Redovisat värde (beräknat) - year-aware version
  const calcRedovisatVarde = React.useCallback((year: 'cur' | 'prev') => {
    const v = (name: string) => getVal(name, year) || 0;

    const invUB     = v('inventarier_ib') + v('arets_inkop_inventarier') + v('arets_fsg_inventarier') + v('arets_omklass_inventarier');
    const avskrUB   = v('ack_avskr_inventarier_ib') + v('arets_avskr_inventarier') + v('aterfor_avskr_fsg_inventarier') + v('omklass_avskr_inventarier');
    const nedskrUB  = v('ack_nedskr_inventarier_ib') + v('arets_nedskr_inventarier') + v('aterfor_nedskr_inventarier') + v('aterfor_nedskr_fsg_inventarier') + v('omklass_nedskr_inventarier');

    return invUB + avskrUB + nedskrUB;
  }, [getVal]);

  const startEdit = () => {
    setIsEditing(true);
    setToggle?.(true);   // show hidden rows when entering edit
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
    setEditedPrevValues({});
    setMismatch({ open: false, deltaCur: 0, deltaPrev: 0 });
    setShowValidationMessage(false);
    setToggle?.(false);   // hide extra rows like FB
  };

  const undoEdit = () => {
    blurAllEditableInputs();                 // ensure inputs drop focus so they re-seed
    setEditedValues({});
    setEditedPrevValues({});
    setCommittedValues({ ...originalBaselineRef.current.cur });     // resetta godkända (innevarande år)
    setCommittedPrevValues({ ...originalBaselineRef.current.prev }); // resetta godkända (föreg. år)
    setMismatch({ open: false, deltaCur: 0, deltaPrev: 0 });
    setShowValidationMessage(false);
    // Don't change show/hide mode - stay with current toggle state
    // IMPORTANT: do NOT setIsEditing(false); stay in edit mode
  };

  const approveEdit = () => {
    const redCurCalc  = calcRedovisatVarde('cur');
    const redPrevCalc = calcRedovisatVarde('prev');

    const deltaCur  = redCurCalc  - brBookValueUBCur;
    const deltaPrev = redPrevCalc - brBookValueUBPrev;

    const hasMismatch =
      Math.round(deltaCur) !== 0 ||
      Math.round(deltaPrev) !== 0;

    if (hasMismatch) {
      setMismatch({ open: true, deltaCur, deltaPrev }); // store both
      setShowValidationMessage(true);
      return; // stay in edit mode
    }

    // success path:
    setCommittedValues(prev => ({ ...prev, ...editedValues }));
    setCommittedPrevValues(prev => ({ ...prev, ...editedPrevValues }));
    setEditedValues({});
    setEditedPrevValues({});
    setMismatch({ open: false, deltaCur: 0, deltaPrev: 0 });
    setShowValidationMessage(false);
    setIsEditing(false);
    setToggle?.(false); // collapse zero rows after approve
  };


  // Helpers for S2 row calculation
  const isSumRow = (it: NoterItem) => it.style === 'S2';
  const isHeading = (it: NoterItem) => isHeadingStyle(it.style);

  // Sum all non-heading, non-S rows directly ABOVE this S2 row until a heading or start
  const sumGroupAbove = React.useCallback(
    (list: NoterItem[], index: number, year: 'cur' | 'prev') => {
      let sum = 0;
      for (let i = index - 1; i >= 0; i--) {
        const r = list[i];
        if (!r) break;
        if (isHeading(r) || r.style === 'S2') break;
        if (r.variable_name) sum += getVal(r.variable_name, year);
      }
      return sum;
    },
    [getVal]
  );

  // Container ref + tab navigation helper
  const containerRef = React.useRef<HTMLDivElement>(null);

  const focusByOrd = (fromEl: HTMLInputElement, dir: 1 | -1) => {
    const root = containerRef.current;
    if (!root) return;
    const curOrd = Number(fromEl.dataset.ord || '0');
    const nextOrd = curOrd + dir;
    const next = root.querySelector<HTMLInputElement>(
      `input[data-editable-cell="1"][data-ord="${nextOrd}"]`
    );
    if (next) { next.focus(); next.select?.(); }
  };

  const blurAllEditableInputs = () => {
    const root = containerRef.current;
    if (!root) return;
    const nodes = root.querySelectorAll<HTMLInputElement>('input[data-editable-cell="1"]');
    nodes.forEach((el) => el.blur());
  };

  const pushSignNotice = (e: any) => {
    console.log(`Sign forced for ${e.label} (${e.year}): ${e.typed} → ${e.adjusted}`);
  };

  // Helper: get the dynamic S2 subtotal for INVENTARIER UB rows
  const ubSum = React.useCallback((ubVar: string, year: 'cur' | 'prev') => {
    const v = (name: string) => getVal(name, year) || 0;
    const idx = visible.findIndex(r => r.variable_name === ubVar);
    if (idx !== -1 && visible[idx]?.style === 'S2') {
      // Use exactly what the UI shows for that S2 row
      return sumGroupAbove(visible, idx, year);
    }
    // Fallbacks if the UB row isn't visible:
    switch (ubVar) {
      case 'inventarier_ub':
        return v('inventarier_ib') + v('arets_inkop_inventarier') + v('arets_fsg_inventarier') + v('arets_omklass_inventarier');
      case 'ack_avskr_inventarier_ub':
        return v('ack_avskr_inventarier_ib') + v('arets_avskr_inventarier') + v('aterfor_avskr_fsg_inventarier') + v('omklass_avskr_inventarier');
      case 'ack_nedskr_inventarier_ub':
        return v('ack_nedskr_inventarier_ib') + v('arets_nedskr_inventarier') + v('aterfor_nedskr_inventarier') + v('aterfor_nedskr_fsg_inventarier') + v('omklass_nedskr_inventarier');
      default:
        return getVal(ubVar, year);
    }
  }, [visible, sumGroupAbove, getVal]);

  // Sum the actual S2 subtotals for INVENTARIER (no uppskrivningar)
  const redCur  = ['inventarier_ub','ack_avskr_inventarier_ub','ack_nedskr_inventarier_ub']
    .map(n => ubSum(n, 'cur'))
    .reduce((a,b) => a + b, 0);

  const redPrev = ['inventarier_ub','ack_avskr_inventarier_ub','ack_nedskr_inventarier_ub']
    .map(n => ubSum(n, 'prev'))
    .reduce((a,b) => a + b, 0);

  return (
    <div ref={containerRef} className="space-y-2 pt-4">
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
        <span className="text-right">{companyData?.currentPeriodEndDate || `${fiscalYear ?? new Date().getFullYear()}-12-31`}</span>
        <span className="text-right">{companyData?.previousPeriodEndDate || `${(previousYear ?? (fiscalYear ? fiscalYear - 1 : new Date().getFullYear() - 1))}-12-31`}</span>
      </div>

      {/* Rows */}
      {(() => {
        let ordCounter = 0; // for Tab navigation order
        return visible.map((it, idx) => {
        // Use same style system as main Noter component
        const getStyleClasses = (style?: string, isRedovisatVarde = false) => {
          const baseClasses = 'grid gap-4';
          let additionalClasses = '';
          const s = style || 'NORMAL';
          
          // Bold styles
          const boldStyles = ['H0','H1','H2','H3','S1','S2','S3','TH0','TH1','TH2','TH3','TS1','TS2','TS3'];
          if (boldStyles.includes(s)) {
            additionalClasses += ' font-semibold';
          }
          
          // Line styles - but remove bottom border for redovisat värde when editing
          const lineStyles = ['S2','S3','TS2','TS3'];
          if (lineStyles.includes(s)) {
            if (isRedovisatVarde && isEditing) {
              additionalClasses += ' border-t border-gray-200 pt-1 pb-1'; // no bottom border
            } else {
              additionalClasses += ' border-t border-b border-gray-200 pt-1 pb-1';
            }
          }
          
          return {
            className: `${baseClasses}${additionalClasses}`,
            style: { gridTemplateColumns: '4fr 1fr 1fr' }
          };
        };

        const currentStyle = it.style || 'NORMAL';
        const isHeadingRow = isHeadingStyle(currentStyle);
        const isS2 = isSumRow(it);
        
        // Precompute style classes once per row
        const gc = getStyleClasses(currentStyle);

        const isRedVardeRow = it.variable_name === "red_varde_inventarier";
        const editable = isEditing && isFlowVar(it.variable_name);
        
        // assign order numbers only to editable inputs,
        // first current-year (col 2), then previous-year (col 3)
        const ordCur  = editable ? ++ordCounter : undefined;
        const ordPrev = editable ? ++ordCounter : undefined;
        
        // values for display
        const curVal = isRedVardeRow
          ? redCur
          : (isS2 ? sumGroupAbove(visible, idx, 'cur') : getVal(it.variable_name ?? '', 'cur'));
        const prevVal = isRedVardeRow
          ? redPrev
          : (isS2 ? sumGroupAbove(visible, idx, 'prev') : getVal(it.variable_name ?? '', 'prev'));

        const curMismatch  = isEditing && isRedVardeRow && Math.round(redCur)  !== Math.round(brBookValueUBCur);
        const prevMismatch = isEditing && isRedVardeRow && Math.round(redPrev) !== Math.round(brBookValueUBPrev);
        
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
            <span className={`text-right font-medium ${isRedVardeRow && curMismatch ? 'text-red-600 font-bold' : ''}`}>
              {isHeadingRow ? '' : isRedVardeRow
                ? `${numberToSv(curVal)} kr`
                : <AmountCell
                    year="cur"
                    varName={it.variable_name!}
                    baseVar={it.variable_name!}
                    label={it.row_title}
                    editable={editable}
                    value={curVal}
                    ord={ordCur}
                    onCommit={(n) => setEditedValues(p => ({ ...p, [it.variable_name!]: n }))}
                    onTabNavigate={(el, dir) => focusByOrd(el, dir)}
                    onSignForced={(e) => pushSignNotice(e)}
                    expectedSignFor={expectedSignFor}
                  />
              }
            </span>

            {/* Previous year */}
            <span className={`text-right font-medium ${isRedVardeRow && prevMismatch ? 'text-red-600 font-bold' : ''}`}>
              {isHeadingRow ? '' : isRedVardeRow
                ? `${numberToSv(prevVal)} kr`
                : <AmountCell
                    year="prev"
                    varName={`${it.variable_name!}_prev`}
                    baseVar={it.variable_name!}
                    label={it.row_title}
                    editable={editable}
                    value={prevVal}
                    ord={ordPrev}
                    onCommit={(n) => setEditedPrevValues(p => ({ ...p, [it.variable_name!]: n }))}
                    onTabNavigate={(el, dir) => focusByOrd(el, dir)}
                    onSignForced={(e) => pushSignNotice(e)}
                    expectedSignFor={expectedSignFor}
                  />
              }
            </span>
          </div>
        );
        });
      })()}

      {/* Comparison row – only while editing */}
      {isEditing && (
        <div className="grid gap-4 border-t border-b border-gray-200 pt-1 pb-1 font-semibold bg-gray-50/50" style={gridCols}>
          <span className="text-muted-foreground font-semibold">Redovisat värde (bokfört)</span>
          <span className="text-right font-medium">{numberToSv(brBookValueUBCur)} kr</span>
          <span className="text-right font-medium">{numberToSv(brBookValueUBPrev)} kr</span>
        </div>
      )}

      {/* Action buttons at bottom - matching FB pattern */}
      {isEditing && (
        <div className="pt-4 flex justify-between">
          {/* Undo Button - Left */}
          <Button 
            onClick={undoEdit}
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
        <div className="fixed bottom-4 right-4 z-50 bg-white rounded-lg shadow-lg p-4 max-w-sm animate-in slide-in-from-bottom-2">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <svg className="w-5 h-5 text-red-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                      d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </div>
            <div className="ml-3">
              {(() => {
                const curMism = Math.round(mismatch.deltaCur) !== 0;
                const prevMism = Math.round(mismatch.deltaPrev) !== 0;
                
                if (curMism && !prevMism) {
                  return (
                    <>
                      <p className="text-sm font-medium text-gray-900">
                        Summor balanserar inte {fiscalYear}
                      </p>
                      <p className="mt-1 text-sm text-gray-700">
                        Beräknat redovisat värde stämmer inte med bokfört värde. Differensen är {numberToSv(Math.abs(Math.round(mismatch.deltaCur)))} kr.
                      </p>
                    </>
                  );
                } else if (prevMism && !curMism) {
                  return (
                    <>
                      <p className="text-sm font-medium text-gray-900">
                        Summor balanserar inte {previousYear}
                      </p>
                      <p className="mt-1 text-sm text-gray-700">
                        Beräknat redovisat värde stämmer inte med bokfört värde. Differensen är {numberToSv(Math.abs(Math.round(mismatch.deltaPrev)))} kr.
                      </p>
                    </>
                  );
                } else {
                  // Both years have mismatches
                  return (
                    <>
                      <p className="text-sm font-medium text-gray-900">
                        Summor balanserar inte
                      </p>
                      <p className="mt-1 text-sm text-gray-700">
                        Beräknat redovisat värde stämmer inte med bokfört värde.
                      </p>
                      <ul className="mt-2 text-sm text-gray-900">
                        <li><strong>{fiscalYear}</strong>: Differens {numberToSv(Math.abs(Math.round(mismatch.deltaCur)))} kr</li>
                        <li><strong>{previousYear}</strong>: Differens {numberToSv(Math.abs(Math.round(mismatch.deltaPrev)))} kr</li>
                      </ul>
                    </>
                  );
                }
              })()}
            </div>
            <button
              onClick={() => { setShowValidationMessage(false); setMismatch(m => ({ ...m, open: false })); }}
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
                const isEventualVisible = blockToggles[eventualToggleKey] === true;
                if (!isEventualVisible) shouldGetNumber = false;
              }
              
              if (block === 'SAKERHET') {
                const sakerhetToggleKey = `sakerhet-visibility`;
                const isSakerhetVisible = blockToggles[sakerhetToggleKey] === true;
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
            
            // Special handling for Note 1 (Redovisningsprinciper) - with edit functionality
            if (block === 'NOT1') {
              // Find the heading item (row_id 2) and text item (row_id 3)
              const headingItem = blockItems.find(item => item.row_id === 2);
              const textItem = blockItems.find(item => item.row_id === 3);
              
              // Get editable values
              const originalText = textItem?.variable_text || '';
              const originalAvskrtidBygg = noterData.find(item => item.variable_name === 'avskrtid_bygg')?.current_amount || 0;
              const originalAvskrtidMask = noterData.find(item => item.variable_name === 'avskrtid_mask')?.current_amount || 0;
              const originalAvskrtidInv = noterData.find(item => item.variable_name === 'avskrtid_inv')?.current_amount || 0;
              const originalAvskrtidOvriga = noterData.find(item => item.variable_name === 'avskrtid_ovriga')?.current_amount || 0;
              
              // Local edit state for NOT1 - EXACT same pattern as NOT2
              const [isEditingNOT1, setIsEditingNOT1] = useState(false);
              const [editedValues, setEditedValues] = useState<Record<string, number | string>>({});
              const [committedValues, setCommittedValues] = useState<Record<string, number | string>>({});
              const textareaRefNOT1 = React.useRef<HTMLTextAreaElement>(null);
              
              // Track original baseline for proper undo (like other notes)
              const originalBaselineNOT1 = React.useRef<Record<string, number | string>>({});
              React.useEffect(() => {
                originalBaselineNOT1.current = { 
                  'redovisning_principer': originalText,
                  'avskrtid_bygg': originalAvskrtidBygg,
                  'avskrtid_mask': originalAvskrtidMask,
                  'avskrtid_inv': originalAvskrtidInv,
                  'avskrtid_ovriga': originalAvskrtidOvriga
                };
              }, [originalText, originalAvskrtidBygg, originalAvskrtidMask, originalAvskrtidInv, originalAvskrtidOvriga]);
              
              // getVal function - EXACT same as NOT2
              const getVal = (vn: string) => {
                if (editedValues[vn] !== undefined) return editedValues[vn];
                if (committedValues[vn] !== undefined) return committedValues[vn];
                // Fallback to original values
                if (vn === 'redovisning_principer') return originalText;
                if (vn === 'avskrtid_bygg') return originalAvskrtidBygg;
                if (vn === 'avskrtid_mask') return originalAvskrtidMask;
                if (vn === 'avskrtid_inv') return originalAvskrtidInv;
                if (vn === 'avskrtid_ovriga') return originalAvskrtidOvriga;
                return 0;
              };
              
              // Auto-resize textarea when entering edit mode or content changes
              React.useEffect(() => {
                if (isEditingNOT1 && textareaRefNOT1.current) {
                  const textarea = textareaRefNOT1.current;
                  textarea.style.height = 'auto';
                  textarea.style.height = textarea.scrollHeight + 'px';
                }
              }, [isEditingNOT1, editedValues['redovisning_principer'], committedValues['redovisning_principer'], originalText]);
              
              const startEditNOT1 = () => {
                setIsEditingNOT1(true);
              };
              
              const cancelEditNOT1 = () => {
                setIsEditingNOT1(false);
                setEditedValues({});
              };
              
              const undoEditNOT1 = () => {
                // EXACT same as NOT2 - clear edits and reset committed to baseline
                setEditedValues({});
                setCommittedValues({ ...originalBaselineNOT1.current });
                // IMPORTANT: do NOT setIsEditingNOT1(false); stay in edit mode
              };
              
              const approveEditNOT1 = () => {
                // EXACT same as NOT2 - commit edits and close
                setCommittedValues(prev => ({ ...prev, ...editedValues }));
                setEditedValues({});
                setIsEditingNOT1(false);
              };

              // Tab navigation function (like other notes)
              const focusByOrd = (fromEl: HTMLInputElement, dir: 1 | -1) => {
                const curOrd = Number(fromEl.dataset.ord || '0');
                const nextOrd = curOrd + dir;
                const next = document.querySelector<HTMLInputElement>(
                  `input[data-editable-cell="1"][data-ord="${nextOrd}"]`
                );
                if (next) { next.focus(); next.select?.(); }
              };
              
              return (
                <div key={block} className="space-y-4 pt-4">
                  {/* Note 1 heading with edit button */}
                  <div className="flex items-center justify-between border-b pb-1">
                    <div className="flex items-center gap-3">
                      <h3 className="font-semibold text-lg" style={{paddingTop: '7px'}}>{blockHeading}</h3>
                      <button
                        onClick={() => isEditingNOT1 ? cancelEditNOT1() : startEditNOT1()}
                        className={`w-6 h-6 rounded-full flex items-center justify-center transition-colors ${
                          isEditingNOT1 ? 'bg-blue-600 text-white' : 'bg-gray-200 hover:bg-gray-300 text-gray-600'
                        }`}
                        title={isEditingNOT1 ? 'Avsluta redigering' : 'Redigera värden'}
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                                d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
                        </svg>
                      </button>
                    </div>
                  </div>
                  
                  {/* Editable text */}
                  <div className="text-sm leading-relaxed">
                    {isEditingNOT1 ? (
                      <textarea
                        ref={textareaRefNOT1}
                        value={getVal('redovisning_principer') as string}
                        onChange={(e) => {
                          setEditedValues(prev => ({ ...prev, 'redovisning_principer': e.target.value }));
                          // Auto-resize to fit content
                          e.target.style.height = 'auto';
                          e.target.style.height = e.target.scrollHeight + 'px';
                        }}
                        className="w-full p-2 border border-gray-300 rounded-md resize-y"
                        style={{ minHeight: '80px' }}
                        placeholder="Skriv redovisningsprinciper..."
                      />
                    ) : (
                      getVal('redovisning_principer') as string || 'Inga redovisningsprinciper angivna'
                    )}
                  </div>
                  
                  {/* Editable depreciation table */}
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
                            {isEditingNOT1 ? (
                              <AmountCell
                                year="cur"
                                varName="avskrtid_bygg"
                                baseVar="avskrtid_bygg"
                                label="Byggnader & mark"
                                editable={true}
                                value={getVal('avskrtid_bygg') as number}
                                ord={1}
                                onCommit={(n) => setEditedValues(prev => ({ ...prev, 'avskrtid_bygg': n }))}
                                onTabNavigate={(el, dir) => focusByOrd(el, dir)}
                                expectedSignFor={() => null}
                              />
                            ) : (
                              getVal('avskrtid_bygg') !== null ? getVal('avskrtid_bygg') : '-'
                            )}
                          </TableCell>
                        </TableRow>
                        <TableRow>
                          <TableCell className="py-1">Maskiner och andra tekniska anläggningar</TableCell>
                          <TableCell className="text-right py-1">
                            {isEditingNOT1 ? (
                              <AmountCell
                                year="cur"
                                varName="avskrtid_mask"
                                baseVar="avskrtid_mask"
                                label="Maskiner och andra tekniska anläggningar"
                                editable={true}
                                value={getVal('avskrtid_mask') as number}
                                ord={2}
                                onCommit={(n) => setEditedValues(prev => ({ ...prev, 'avskrtid_mask': n }))}
                                onTabNavigate={(el, dir) => focusByOrd(el, dir)}
                                expectedSignFor={() => null}
                              />
                            ) : (
                              getVal('avskrtid_mask') !== null ? getVal('avskrtid_mask') : '-'
                            )}
                          </TableCell>
                        </TableRow>
                        <TableRow>
                          <TableCell className="py-1">Inventarier, verktyg och installationer</TableCell>
                          <TableCell className="text-right py-1">
                            {isEditingNOT1 ? (
                              <AmountCell
                                year="cur"
                                varName="avskrtid_inv"
                                baseVar="avskrtid_inv"
                                label="Inventarier, verktyg och installationer"
                                editable={true}
                                value={getVal('avskrtid_inv') as number}
                                ord={3}
                                onCommit={(n) => setEditedValues(prev => ({ ...prev, 'avskrtid_inv': n }))}
                                onTabNavigate={(el, dir) => focusByOrd(el, dir)}
                                expectedSignFor={() => null}
                              />
                            ) : (
                              getVal('avskrtid_inv') !== null ? getVal('avskrtid_inv') : '-'
                            )}
                          </TableCell>
                        </TableRow>
                        <TableRow>
                          <TableCell className="py-1">Övriga materiella anläggningstillgångar</TableCell>
                          <TableCell className="text-right py-1">
                            {isEditingNOT1 ? (
                              <AmountCell
                                year="cur"
                                varName="avskrtid_ovriga"
                                baseVar="avskrtid_ovriga"
                                label="Övriga materiella anläggningstillgångar"
                                editable={true}
                                value={getVal('avskrtid_ovriga') as number}
                                ord={4}
                                onCommit={(n) => setEditedValues(prev => ({ ...prev, 'avskrtid_ovriga': n }))}
                                onTabNavigate={(el, dir) => focusByOrd(el, dir)}
                                expectedSignFor={() => null}
                              />
                            ) : (
                              getVal('avskrtid_ovriga') !== null ? getVal('avskrtid_ovriga') : '-'
                            )}
                          </TableCell>
                        </TableRow>
                      </TableBody>
                    </Table>
                  </div>

                  {/* Action buttons - only show when editing */}
                  {isEditingNOT1 && (
                    <div className="flex justify-between pt-4 border-t border-gray-200">
                      <Button 
                        onClick={undoEditNOT1}
                        variant="outline"
                        className="flex items-center gap-2"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"/>
                        </svg>
                        Ångra ändringar
                      </Button>
                      
                      <Button 
                        onClick={approveEditNOT1}
                        className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 flex items-center gap-2"
                      >
                        Godkänn ändringar
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 10h-10a8 8 0 00-8 8v2M21 10l-6 6m6-6l-6-6"/>
                        </svg>
                      </Button>
                    </div>
                  )}
                </div>
              );
            }
            
            // Special handling for Note 2 (Medelantalet anställda) - with edit functionality
            if (block === 'NOT2') {
              // Get the ant_anstallda item for edit functionality
              const antAnstallndaItem = blockItems.find(item => item.variable_name === 'ant_anstallda');
              
              // Get employee count from scraped data (first value from "Antal anställda") - RESTORE ORIGINAL LOGIC
              const scrapedEmployeeCount = (companyData as any)?.scraped_company_data?.nyckeltal?.["Antal anställda"]?.[0] || 0;
              
              // Use database values if available, otherwise fallback to scraped data
              const currentValue = antAnstallndaItem?.current_amount || scrapedEmployeeCount;
              const previousValue = antAnstallndaItem?.previous_amount || scrapedEmployeeCount;
              
              // Local edit state for NOT2 - EXACT same pattern as other notes
              const [isEditingNOT2, setIsEditingNOT2] = useState(false);
              const [editedValues, setEditedValues] = useState<Record<string, number>>({});
              const [committedValues, setCommittedValues] = useState<Record<string, number>>({});
              
              // Track original baseline for proper undo (like other notes)
              const originalBaselineNOT2 = React.useRef<Record<string, number>>({});
              React.useEffect(() => {
                originalBaselineNOT2.current = { 'ant_anstallda': currentValue };
              }, [currentValue]);
              
              // getVal function - EXACT same as SakerhetNote
              const getVal = (vn: string) => {
                if (editedValues[vn] !== undefined) return editedValues[vn];
                if (committedValues[vn] !== undefined) return committedValues[vn];
                return currentValue; // fallback to original
              };
              
              const startEditNOT2 = () => {
                setIsEditingNOT2(true);
              };
              
              const cancelEditNOT2 = () => {
                setIsEditingNOT2(false);
                setEditedValues({});
              };
              
              const undoEditNOT2 = () => {
                // EXACT same as SakerhetNote - clear edits and reset committed to baseline
                setEditedValues({});
                setCommittedValues({ ...originalBaselineNOT2.current });
                // IMPORTANT: do NOT setIsEditingNOT2(false); stay in edit mode
              };
              
              const approveEditNOT2 = () => {
                // EXACT same as SakerhetNote - commit edits and close
                setCommittedValues(prev => ({ ...prev, ...editedValues }));
                setEditedValues({});
                setIsEditingNOT2(false);
              };
              
              return (
                <div key={block} className="space-y-2 pt-4">
                  {/* Note 2 heading with edit button */}
                  <div className="flex items-center justify-between border-b pb-1">
                    <div className="flex items-center gap-3">
                      <h3 className="font-semibold text-lg" style={{paddingTop: '7px'}}>{blockHeading}</h3>
                      <button
                        onClick={() => isEditingNOT2 ? cancelEditNOT2() : startEditNOT2()}
                        className={`w-6 h-6 rounded-full flex items-center justify-center transition-colors ${
                          isEditingNOT2 ? 'bg-blue-600 text-white' : 'bg-gray-200 hover:bg-gray-300 text-gray-600'
                        }`}
                        title={isEditingNOT2 ? 'Avsluta redigering' : 'Redigera värden'}
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                                d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
                        </svg>
                      </button>
                    </div>
                  </div>
                  
                  {/* Column Headers - same as BR/RR */}
                  <div className="grid gap-4 text-sm text-muted-foreground border-b pb-1 font-semibold" style={{gridTemplateColumns: '4fr 1fr 1fr'}}>
                    <span></span>
                    <span className="text-right">{companyData?.currentPeriodEndDate || `${fiscalYear || new Date().getFullYear()}-12-31`}</span>
                    <span className="text-right">{companyData?.previousPeriodEndDate || `${(previousYear || (fiscalYear ? fiscalYear - 1 : new Date().getFullYear() - 1))}-12-31`}</span>
                  </div>

                  {/* Employee count row */}
                  <div className="grid gap-4" style={{gridTemplateColumns: '4fr 1fr 1fr'}}>
                    <span className="text-sm">Medelantalet anställda under året</span>
                    {/* Current year - editable when in edit mode */}
                    <span className="text-right text-sm">
                      {isEditingNOT2 ? (
                        <AmountCell
                          year="cur"
                          varName="ant_anstallda"
                          baseVar="ant_anstallda"
                          label="Medelantalet anställda under året"
                          editable={true}
                          value={getVal('ant_anstallda')}
                          ord={1}
                          onCommit={(n) => setEditedValues(prev => ({ ...prev, 'ant_anstallda': n }))}
                          expectedSignFor={() => null}
                        />
                      ) : (
                        getVal('ant_anstallda')
                      )}
                    </span>
                    {/* Previous year - always read-only */}
                    <span className="text-right text-sm">{previousValue}</span>
                  </div>

                  {/* Action buttons - only show when editing */}
                  {isEditingNOT2 && (
                    <div className="flex justify-between pt-4 border-t border-gray-200">
                      <Button 
                        onClick={undoEditNOT2}
                        variant="outline"
                        className="flex items-center gap-2"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"/>
                        </svg>
                        Ångra ändringar
                      </Button>
                      
                      <Button 
                        onClick={approveEditNOT2}
                        className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 flex items-center gap-2"
                      >
                        Godkänn ändringar
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 10h-10a8 8 0 00-8 8v2M21 10l-6 6m6-6l-6-6"/>
                        </svg>
                      </Button>
                    </div>
                  )}
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
            
            // Special handling for EVENTUAL block - use EventualNote component with edit functionality
            if (block === 'EVENTUAL') {
              return (
                <EventualNote
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
                  blockToggles={blockToggles}
                  setBlockToggles={setBlockToggles}
                />
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
            
            // Special handling for MASKIN block - with manual editing capability
            if (block === 'MASKIN') {
              return (
                <MaskinerNote
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
            
            // Special handling for BYGG block - with manual editing capability (includes UPPSKRIVNINGAR)
            if (block === 'BYGG') {
              return (
                <ByggnaderNote
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
            
            // Special handling for MAT block - with manual editing capability
            if (block === 'MAT') {
              return (
                <OvrigaMateriellaNote
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
            
            // Special handling for KONCERN block - with manual editing capability
            if (block === 'KONCERN') {
              return (
                <KoncernNote
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
            
            // Special handling for INTRESSEFTG block - with manual editing capability
            if (block === 'INTRESSEFTG') {
              return (
                <IntresseforetagNote
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
            
            // Special handling for LVP block - with manual editing capability
            if (block === 'LVP') {
              return (
                <LangfristigaVardepapperNote
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
            
            // Special handling for FORDRKONC block - with manual editing capability
            if (block === 'FORDRKONC') {
              return (
                <FordringarKoncernNote
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
            
            // Special handling for FORDRINTRE block - with manual editing capability
            if (block === 'FORDRINTRE') {
              return (
                <FordringarIntresseNote
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
            
            // Special handling for FORDROVRFTG block - with manual editing capability
            if (block === 'FORDROVRFTG') {
              return (
                <FordringarOvrigaNote
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
            
            // Special handling for SAKERHET block - with manual editing capability
            if (block === 'SAKERHET') {
              return (
                <SakerhetNote
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
                  blockToggles={blockToggles}
                  setBlockToggles={setBlockToggles}
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
                  <span className="text-right">{companyData?.currentPeriodEndDate || `${fiscalYear || new Date().getFullYear()}-12-31`}</span>
                  <span className="text-right">{companyData?.previousPeriodEndDate || `${(fiscalYear ? fiscalYear - 1 : new Date().getFullYear() - 1)}-12-31`}</span>
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

