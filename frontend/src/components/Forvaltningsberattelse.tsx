'use client';

// Trigger Vercel deployment
import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { formatAmount } from '@/utils/seFileCalculations';

interface FBTableRow {
  id: number;
  label: string;
  aktiekapital: number;
  reservfond: number;
  uppskrivningsfond: number;
  balanserat_resultat: number;
  arets_resultat: number;
  total: number;
}

interface FBVariables {
  [key: string]: number;
}

interface ForvaltningsberattelseProps {
  fbTable: FBTableRow[];
  fbVariables: FBVariables;
  fiscalYear?: number;
  onDataUpdate?: (updates: Partial<any>) => void;
  arets_utdelning?: number;
}

export function Forvaltningsberattelse({
  fbTable, fbVariables, fiscalYear, onDataUpdate, embedded = false, arets_utdelning
}: ForvaltningsberattelseProps & { embedded?: boolean }) {
  const [showAllRows, setShowAllRows] = useState(false);
  const [isEditMode, setIsEditMode] = useState(false);
  const [showAllAfterEdit, setShowAllAfterEdit] = useState(false);
  const [editedValues, setEditedValues] = useState<FBVariables>({});
  const [showValidationMessage, setShowValidationMessage] = useState(false);
  const [recalculatedTable, setRecalculatedTable] = useState<FBTableRow[]>(fbTable);
  const [savedValues, setSavedValues] = useState<FBVariables>({});
  const [draftInputs, setDraftInputs] = useState<Record<string, string>>({});
  const [committedTable, setCommittedTable] = useState<FBTableRow[]>(fbTable);
  
  // NEW: keep the original (pre-manual) baseline forever
  const originalBaselineRef = useRef<FBTableRow[] | null>(null);
  
  // vilken input är i fokus just nu
  const [focusedVar, setFocusedVar] = useState<string | null>(null);

  // Capture the original baseline once
  useEffect(() => {
    if (!originalBaselineRef.current && fbTable && fbTable.length) {
      originalBaselineRef.current = fbTable.map(r => ({ ...r }));
    }
  }, [fbTable]);

  // Keep committed/read-only baseline in sync when backend delivers a new fbTable
  useEffect(() => {
    if (!isEditMode) {
      setCommittedTable(fbTable);
      setRecalculatedTable(fbTable);
    }
  }, [fbTable, isEditMode]);

  // Auto-hide validation message after 5 seconds
  useEffect(() => {
    if (showValidationMessage) {
      const timer = setTimeout(() => {
        setShowValidationMessage(false);
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [showValidationMessage]);

  // Define editable fields based on CSV specification
  const getVariableName = (rowId: number, column: keyof FBTableRow): string | null => {
    const mapping: Record<number, Record<string, string>> = {
      2: { // Utdelning - CSV: balanserat_resultat, arets_resultat editable
        balanserat_resultat: 'fb_balansresultat_utdelning',
        arets_resultat: 'fb_aretsresultat_utdelning'
      },
      3: { // Erhållna aktieägartillskott - CSV: balanserat_resultat editable
        balanserat_resultat: 'fb_balansresultat_erhallna_aktieagartillskott'
      },
      4: { // Återbetalning av aktieägartillskott - CSV: balanserat_resultat, arets_resultat editable
        balanserat_resultat: 'fb_balansresultat_aterbetalda_aktieagartillskott',
        arets_resultat: 'fb_aretsresultat_aterbetalda_aktieagartillskott'
      },
      5: { // Balanseras i ny räkning - CSV: balanserat_resultat, arets_resultat editable
        balanserat_resultat: 'fb_balansresultat_balanseras_nyrakning',
        arets_resultat: 'fb_aretsresultat_balanseras_nyrakning'
      },
      6: { // Förändringar av reservfond - CSV: balanserat_resultat, arets_resultat editable (reservfond not editable)
        balanserat_resultat: 'fb_balansresultat_forandring_reservfond',
        arets_resultat: 'fb_aretsresultat_forandring_reservfond'
      },
      7: { // Fondemission - CSV: uppskrivningsfond, balanserat_resultat, arets_resultat editable
        uppskrivningsfond: 'fb_uppskrfond_fondemission',
        balanserat_resultat: 'fb_balansresultat_fondemission',
        arets_resultat: 'fb_aretsresultat_fondemission'
      },
      8: { // Nyemission - CSV: aktiekapital not editable
        // No editable fields for this row
      },
      9: { // Uppskrivning av anläggningstillgång - CSV: uppskrivningsfond editable
        uppskrivningsfond: 'fb_uppskrfond_uppskr_anltillgangar'
      },
      10: { // Återföring av uppskrivningsfond - CSV: uppskrivningsfond, balanserat_resultat editable
        uppskrivningsfond: 'fb_uppskrfond_aterforing',
        balanserat_resultat: 'fb_balansresultat_uppskrfond_aterforing'
      },
      11: { // Fusionsdifferens - CSV: uppskrivningsfond editable
        uppskrivningsfond: 'fb_uppskrfond_fusionsdifferens'
      },
      12: { // Årets resultat - CSV: arets_resultat editable
        arets_resultat: 'fb_aretsresultat_arets_resultat'
      }
    };
    
    return mapping[rowId]?.[column] || null;
  };

  if (!fbTable || fbTable.length === 0) {
    return null;
  }

  // Helper function to get current value (edited, saved, or original)
  const getCurrentValue = (variableName: string): number => {
    if (editedValues[variableName] !== undefined) {
      return editedValues[variableName];
    }
    if (savedValues[variableName] !== undefined) {
      return savedValues[variableName];
    }
    return fbVariables[variableName] || 0;
  };

  // Helper function to format amounts without decimals and with thousand separator
  const formatAmountForDisplay = (amount: number): string => {
    return Math.round(amount).toLocaleString('sv-SE') + ' kr';
  };

  // Use recalculated table in edit mode, committed baseline otherwise
  const currentTable = isEditMode ? recalculatedTable : committedTable;

  // Helper functions for draft input handling
  const allowDraft = (s: string) => /^-?\d*$/.test(s);        // integers only
  
  // helper: sv-SE tusentalsavgränsare (utan decimaler)
  const formatSvInt = (n: number) =>
    new Intl.NumberFormat('sv-SE', { maximumFractionDigits: 0 }).format(Math.round(n));

  // helper: rensa bort alla mellanrum/nbsp/thin-spaces men behåll minus
  const cleanDigits = (s: string) => (s || '')
    .replace(/\s| |\u00A0|\u202F|,/g, '') // vanliga + NBSP + smalt mellanslag + komma
    .trim();

  const parseDraft = (s: string): number => {
    if (!s) return 0;
    const cleaned = cleanDigits(s);
    const v = parseInt(cleaned, 10);
    return Number.isNaN(v) ? 0 : v;
  };

  const commitDraft = (variableName: string, draft: string) => {
    // Use parseDraft for consistent parsing
    const parsed = parseDraft(draft);
    const newValues = { ...editedValues, [variableName]: parsed };
    setEditedValues(recalculateRow13(newValues));
    setDraftInputs(prev => ({ ...prev, [variableName]: toRaw(parsed) }));
  };

  // Helper: get a row by id from a table
  const getRowById = (table: FBTableRow[], id: number) => table.find(r => r.id === id);

  // Helper: integer equality (what the UI shows)
  const eqInt = (a: unknown, b: unknown) =>
    Math.round(Number(a ?? 0)) === Math.round(Number(b ?? 0));

  const hasDifferences = (): boolean => {
    // Always compare inside the working edit table
    const row13 = getRowById(recalculatedTable, 13);
    const row14 = getRowById(recalculatedTable, 14);
    if (!row13 || !row14) return false;

    return !(
      eqInt(row13.aktiekapital,        row14.aktiekapital) &&
      eqInt(row13.reservfond,          row14.reservfond) &&
      eqInt(row13.uppskrivningsfond,   row14.uppskrivningsfond) &&
      eqInt(row13.balanserat_resultat, row14.balanserat_resultat) &&
      eqInt(row13.arets_resultat,      row14.arets_resultat) &&
      eqInt(row13.total,               row14.total)
    );
  };

  // Helper to deep copy a table
  const cloneTable = (t: FBTableRow[]) => t.map(r => ({ ...r }));
  const toRaw = (n: number) => (n === 0 ? '' : String(Math.round(n)));

  const buildValuesFromTable = (table: FBTableRow[]) => {
    const values: FBVariables = {};
    for (let rowId = 2; rowId <= 12; rowId++) {
      const row = table.find(r => r.id === rowId);
      if (!row) continue;
      (['aktiekapital','reservfond','uppskrivningsfond','balanserat_resultat','arets_resultat'] as (keyof FBTableRow)[])
        .forEach((col) => {
          const varName = getVariableName(rowId, col);
          if (varName) values[varName] = Number(row[col]) || 0;
        });
    }
    return values;
  };

  // NEW: hard reset to original, regardless of saves
  const resetToOriginal = () => {
    const orig = (originalBaselineRef.current && originalBaselineRef.current.length)
      ? originalBaselineRef.current
      : fbTable;

    const resetTable = cloneTable(orig);
    setCommittedTable(resetTable);        // read-only baseline = original
    setRecalculatedTable(resetTable);     // edit working table = original

    const base = buildValuesFromTable(resetTable);
    setSavedValues(base);                 // per-cell values = original
    setEditedValues({});                  // no pending edits
    setDraftInputs(Object.fromEntries(
      Object.entries(base).map(([k, v]) => [k, toRaw(v as number)])
    ));
  };

  // Recalculate entire table from committed baseline + edits
  const recalculateRow13 = (updatedValues: FBVariables) => {
    // Work on a fresh copy of the committed baseline so values persist correctly
    const working = cloneTable(committedTable);

    // Combine previously saved + current edits
    const allValues: FBVariables = { ...savedValues, ...updatedValues };

    // Apply each variable into its proper row/column
    for (const [varName, val] of Object.entries(allValues)) {
      for (let rowId = 2; rowId <= 12; rowId++) {
        // Try each possible editable column
        (['aktiekapital','reservfond','uppskrivningsfond','balanserat_resultat','arets_resultat'] as (keyof FBTableRow)[])
          .forEach((col) => {
            if (getVariableName(rowId, col) === varName) {
              const idx = working.findIndex(r => r.id === rowId);
              if (idx !== -1) {
                const row = { ...working[idx], [col]: val } as FBTableRow;
                // Recompute this row's total for display consistency
                row.total = row.aktiekapital + row.reservfond + row.uppskrivningsfond + row.balanserat_resultat + row.arets_resultat;
                working[idx] = row;
              }
            }
          });
      }
    }

    // Recompute row 13 (Belopp vid årets utgång) from row 1 + rows 2–12 in 'working'
    const row1 = working.find(r => r.id === 1);
    if (!row1) {
      setRecalculatedTable(working);
      return updatedValues;
    }

    const sumCols = { aktiekapital: row1.aktiekapital, reservfond: row1.reservfond,
                      uppskrivningsfond: row1.uppskrivningsfond, balanserat_resultat: row1.balanserat_resultat,
                      arets_resultat: row1.arets_resultat };

    for (let rowId = 2; rowId <= 12; rowId++) {
      const r = working.find(x => x.id === rowId);
      if (r) {
        sumCols.aktiekapital        += r.aktiekapital;
        sumCols.reservfond          += r.reservfond;
        sumCols.uppskrivningsfond   += r.uppskrivningsfond;
        sumCols.balanserat_resultat += r.balanserat_resultat;
        sumCols.arets_resultat      += r.arets_resultat;
      }
    }

    const idx13 = working.findIndex(r => r.id === 13);
    const updated13: FBTableRow = {
      ...(idx13 !== -1 ? working[idx13] : { id: 13, label: 'Belopp vid årets utgång' } as any),
      ...sumCols,
      total: sumCols.aktiekapital + sumCols.reservfond + sumCols.uppskrivningsfond + sumCols.balanserat_resultat + sumCols.arets_resultat
    };
    if (idx13 !== -1) working[idx13] = updated13; else working.push(updated13);

    setRecalculatedTable(working);
    return updatedValues;
  };


  // Helper function to toggle edit mode
  const toggleEditMode = () => {
    if (isEditMode) {
      // Exiting edit mode (canceling changes)
      setIsEditMode(false);
      setEditedValues({});
      setRecalculatedTable(committedTable.map(r => ({ ...r })));
      // Reset to normal view (hide empty rows/columns) when canceling
      setShowAllAfterEdit(false);
    } else {
      // Entering edit mode
      setIsEditMode(true);
      setRecalculatedTable(committedTable.map(r => ({ ...r })));
      const base = buildValuesFromTable(committedTable);
      setSavedValues(base);
      setDraftInputs(Object.fromEntries(
        Object.entries(base).map(([k, v]) => [k, toRaw(v as number)])
      ));
    }
  };

  // Helper function to handle undo
  const handleUndo = () => {
    resetToOriginal(); // always jump to original, even after Godkänn
    // Reset to normal view when undoing
    setShowAllAfterEdit(false);
  };

  // Helper function to handle save
  const handleSave = () => {
    if (hasDifferences()) {
      setShowValidationMessage(true);
      return;
    }
    
    // Here you would typically save the changes to the backend
    console.log('Saving changes:', editedValues);
    console.log('Final table state:', recalculatedTable);
    
    // Merge edited values into saved values
    const newSavedValues = { ...savedValues, ...editedValues };
    
    const committed = cloneTable(recalculatedTable);
    setCommittedTable(committed);
    const base = buildValuesFromTable(committed);
    setSavedValues(base);
    setDraftInputs(Object.fromEntries(Object.entries(base).map(([k, v]) => [k, toRaw(v as number)])));
    
    // (Optional) Bubble up so parent/DB can persist variables & rows
    onDataUpdate?.({ fbVariables: newSavedValues, fbTable: recalculatedTable });
    
    setIsEditMode(false);
    setEditedValues({});
    // Keep all rows/columns visible after successful save
    setShowAllAfterEdit(true);
  };

  // Check which columns have all zero/null values (use recalculated table)
  // Only show columns that have non-zero values (edit mode doesn't affect column visibility)
  const hasNonZeroValues = {
    aktiekapital: currentTable.some(row => row.aktiekapital !== 0),
    reservfond: currentTable.some(row => row.reservfond !== 0),
    uppskrivningsfond: currentTable.some(row => row.uppskrivningsfond !== 0),
    balanserat_resultat: currentTable.some(row => row.balanserat_resultat !== 0),
    arets_resultat: currentTable.some(row => row.arets_resultat !== 0),
    total: currentTable.some(row => row.total !== 0)
  };

  // Function to check if a row should be hidden (all values are zero/null)
  const shouldHideRow = (row: FBTableRow) => {
    // Show "Redovisat värde" row (id 14) only when there are differences or in edit mode
    if (row.id === 14) {
      return !isEditMode && !hasDifferences();
    }
    
    // Priority order: 
    // 1. Edit mode always shows all rows
    if (isEditMode) {
      return false;
    }
    
    // 2. Toggle has priority over showAllAfterEdit
    if (showAllRows) {
      return false; // Toggle ON = show all rows
    }
    
    // 3. If toggle is OFF, hide empty rows (even if showAllAfterEdit is true)
    
    // Always show header rows (IB, UB)
    if (row.id === 1 || row.id === 13) {
      return false;
    }
    
    // Hide row if all values are zero
    return row.aktiekapital === 0 && 
           row.reservfond === 0 && 
           row.uppskrivningsfond === 0 && 
           row.balanserat_resultat === 0 && 
           row.arets_resultat === 0 && 
           row.total === 0;
  };

  // Helper function to render a cell (editable or display)
  const renderCell = (row: FBTableRow, column: keyof FBTableRow, value: number) => {
    // Skip total column and label column
    if (column === 'total' || typeof value !== 'number') return null;
    
    // Check if this specific cell is editable based on CSV specification
    const variableName = getVariableName(row.id, column);
    const isEditable = isEditMode && variableName !== null;
    
    // Check if this is row 13 and there's a difference with row 14
    const isRow13 = row.id === 13;
    const row14 = recalculatedTable.find(r => r.id === 14);
    const hasDifference = isRow13 && row14 && !eqInt(value, (row14 as any)[column]);
    
    if (isEditable && variableName) {
      const currentValue = getCurrentValue(variableName);        // numeriskt
      const draftRaw = draftInputs[variableName] ?? (currentValue ? String(Math.round(currentValue)) : '');
      const display = focusedVar === variableName
        ? draftRaw                                           // rått vid fokus (lätt att skriva -, radera mm)
        : (draftRaw ? formatSvInt(parseDraft(draftRaw)) : ''); // formaterat utanför fokus

      return (
        <input
          type="text"
          inputMode="numeric"
          className="w-full max-w-[108px] px-1 py-0.5 text-sm border border-gray-300 rounded text-right font-normal h-6 bg-white focus:border-gray-400 focus:outline-none"
          value={display}
          onFocus={() => setFocusedVar(variableName)}
          onChange={(e) => {
            // spara rå-värde (utan mellanrum/komma) så minus alltid funkar
            const raw = cleanDigits(e.target.value);
            if (allowDraft(raw)) setDraftInputs(prev => ({ ...prev, [variableName]: raw }));
          }}
          onBlur={(e) => {
            setFocusedVar(null);
            // commit med parsning + omräkning
            commitDraft(variableName, e.target.value);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === 'Tab') {
              commitDraft(variableName, (e.target as HTMLInputElement).value);
            }
          }}
          placeholder="0"
        />
      );
    }
    
    if (value === 0) return '';
    
    const formattedValue = formatAmountForDisplay(value);
    
    if (hasDifference) {
      return (
        <span className="text-red-600 font-bold">
          {formattedValue}
        </span>
      );
    }
    
    return formattedValue;
  };

  // Extract the content that currently sits inside the Card
  const content = (
    <>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-semibold text-muted-foreground pt-1">Förändringar i eget kapital</h2>
          <button
            onClick={toggleEditMode}
            className={`w-6 h-6 rounded-full flex items-center justify-center transition-colors ${
              isEditMode 
                ? 'bg-blue-600 text-white' 
                : 'bg-gray-200 hover:bg-gray-300 text-gray-600'
            }`}
            title={isEditMode ? 'Avsluta redigering' : 'Redigera värden'}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
            </svg>
          </button>
        </div>
        <div className="flex items-center space-x-2">
          <label 
            htmlFor="toggle-show-all-fb" 
            className="text-sm font-medium cursor-pointer"
          >
            Visa alla rader
          </label>
          <Switch
            id="toggle-show-all-fb"
            checked={showAllRows}
            onCheckedChange={setShowAllRows}
          />
        </div>
      </div>
      
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="font-semibold py-1 min-w-[200px] pl-0"></TableHead>
            {hasNonZeroValues.aktiekapital && (
              <TableHead className="font-semibold text-right py-1 min-w-[120px]">Aktiekapital</TableHead>
            )}
            {hasNonZeroValues.reservfond && (
              <TableHead className="font-semibold text-right py-1 min-w-[120px]">Reservfond</TableHead>
            )}
            {hasNonZeroValues.uppskrivningsfond && (
              <TableHead className="font-semibold text-right py-1 min-w-[140px]">
                <div className="text-right">
                  <div>Uppskrivnings</div>
                  <div>fond</div>
                </div>
              </TableHead>
            )}
            {hasNonZeroValues.balanserat_resultat && (
              <TableHead className="font-semibold text-right py-1 min-w-[140px]">
                <div className="text-right">
                  <div>Balanserat</div>
                  <div>resultat</div>
                </div>
              </TableHead>
            )}
            {hasNonZeroValues.arets_resultat && (
              <TableHead className="font-semibold text-right py-1 min-w-[120px]">
                <div className="text-right">
                  <div>Årets</div>
                  <div>resultat</div>
                </div>
              </TableHead>
            )}
            {hasNonZeroValues.total && (
              <TableHead className="font-semibold text-right py-1 min-w-[120px] bg-gray-50">Totalt</TableHead>
            )}
          </TableRow>
        </TableHeader>
        <TableBody>
          {currentTable.filter(row => !shouldHideRow(row)).map((row) => {
            const isHeaderRow = row.id === 13;
            const isSubtotalRow = row.id === 13;
            const isRedovisatVarde = row.id === 14;
            
            return (
              <TableRow 
                key={row.id} 
                className={`${isHeaderRow ? 'bg-gray-50 font-semibold' : ''} ${isSubtotalRow ? 'border-t border-gray-300' : ''} ${isRedovisatVarde ? 'bg-amber-50/10' : ''}`}
              >
                <TableCell className="py-1 text-left pl-0">{row.label}</TableCell>
                {hasNonZeroValues.aktiekapital && (
                  <TableCell className="py-1 text-right">
                    {renderCell(row, 'aktiekapital', row.aktiekapital)}
                  </TableCell>
                )}
                {hasNonZeroValues.reservfond && (
                  <TableCell className="py-1 text-right">
                    {renderCell(row, 'reservfond', row.reservfond)}
                  </TableCell>
                )}
                {hasNonZeroValues.uppskrivningsfond && (
                  <TableCell className="py-1 text-right">
                    {renderCell(row, 'uppskrivningsfond', row.uppskrivningsfond)}
                  </TableCell>
                )}
                {hasNonZeroValues.balanserat_resultat && (
                  <TableCell className="py-1 text-right">
                    {renderCell(row, 'balanserat_resultat', row.balanserat_resultat)}
                  </TableCell>
                )}
                {hasNonZeroValues.arets_resultat && (
                  <TableCell className="py-1 text-right">
                    {renderCell(row, 'arets_resultat', row.arets_resultat)}
                  </TableCell>
                )}
                {hasNonZeroValues.total && (
                  <TableCell className="py-1 text-right font-semibold bg-gray-50">
                    {row.total !== 0 ? formatAmountForDisplay(row.total) : ''}
                  </TableCell>
                )}
              </TableRow>
            );
          })}
        </TableBody>
      </Table>

      {/* Action Buttons in Edit Mode */}
      {isEditMode && (
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
            onClick={handleSave}
            className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 flex items-center gap-2"
          >
            Godkänn ändringar
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 10h-10a8 8 0 00-8 8v2M21 10l-6 6m6-6l-6-6"/>
            </svg>
          </Button>
        </div>
      )}

      {/* Resultatdisposition Section */}
      {(() => {
        // Get current values from row 13 (Belopp vid årets utgång)
        const row13 = currentTable.find(r => r.id === 13);
        const currentBalanserat = row13?.balanserat_resultat || 0;
        const currentArets = row13?.arets_resultat || 0;
        const currentTotal = currentBalanserat + currentArets;
        // Use chat-entered dividend amount if available, otherwise fall back to calculated amount
        const utdelning = arets_utdelning !== undefined ? arets_utdelning : (fbVariables.fb_arets_utdelning || 0);
        
        return (
          <div className="mt-8">
            <h2 className="text-xl font-semibold text-muted-foreground mb-4 pt-1">Resultatdisposition</h2>
            
            <p className="mb-4 text-sm">Styrelsen och VD föreslår att till förfogande stående medel</p>
            
            {/* First Table - Available Funds */}
            <Table className="mb-4 w-1/2">
              <TableBody>
                <TableRow>
                  <TableCell className="py-1">Balanserat resultat</TableCell>
                  <TableCell className="py-1 text-right">
                    {formatAmountForDisplay(currentBalanserat)}
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="py-1">Årets resultat</TableCell>
                  <TableCell className="py-1 text-right">
                    {formatAmountForDisplay(currentArets)}
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="py-1 font-bold">Summa</TableCell>
                  <TableCell className="py-1 text-right font-bold">
                    {formatAmountForDisplay(currentTotal)}
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>

            <p className="mb-4 text-sm">Disponeras enligt följande</p>

            {/* Second Table - Disposition */}
            <Table className="mb-4 w-1/2">
              <TableBody>
                <TableRow>
                  <TableCell className="py-1">Utdelas till aktieägare</TableCell>
                  <TableCell className="py-1 text-right">
                    {formatAmountForDisplay(utdelning)}
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="py-1">Balanseras i ny räkning</TableCell>
                  <TableCell className="py-1 text-right">
                    {formatAmountForDisplay(currentTotal - utdelning)}
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="py-1 font-bold">Summa</TableCell>
                  <TableCell className="py-1 text-right font-bold">
                    {formatAmountForDisplay(currentTotal)}
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>

            {/* Conditional text for dividend policy */}
            {utdelning > 0 && (
              <p className="mt-4 text-sm">
                Styrelsen anser att förslaget är förenligt med försiktighetsregeln i 17 kap. 3 § aktiebolagslagen enligt följande redogörelse. Styrelsens uppfattning är att vinstutdelningen är försvarlig med hänsyn till de krav verksamhetens art, omfattning och risk ställer på storleken på det egna kapitalet, bolagets konsolideringsbehov, likviditet och ställning i övrigt.
              </p>
            )}
          </div>
        );
      })()}

      {/* Toast Notification */}
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
                Belopp vid årets utgång måste stämma överens med redovisat värde. Kolumn som inte balanserar markeras med röd summa.
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
    </>
  );

  // If embedded, return only the content (no outer Card).
  if (embedded) return content;

  // Otherwise keep the current Card wrapper.
  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>
          <h1 className="text-2xl font-bold">Förvaltningsberättelse</h1>
        </CardTitle>
      </CardHeader>
      
      <CardContent>
        {content}
      </CardContent>
    </Card>
  );
}