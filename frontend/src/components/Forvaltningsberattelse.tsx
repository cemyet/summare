'use client';

import React, { useState } from 'react';
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
}

export function Forvaltningsberattelse({ fbTable, fbVariables, fiscalYear }: ForvaltningsberattelseProps) {
  const [showAllRows, setShowAllRows] = useState(false);
  const [isEditMode, setIsEditMode] = useState(false);
  const [editedValues, setEditedValues] = useState<FBVariables>({});
  const [showValidationMessage, setShowValidationMessage] = useState(false);
  const [recalculatedTable, setRecalculatedTable] = useState<FBTableRow[]>(fbTable);

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
      6: { // Förändringar av reservfond - CSV: reservfond, balanserat_resultat, arets_resultat editable
        reservfond: 'fb_reservfond_change',
        balanserat_resultat: 'fb_balansresultat_forandring_reservfond',
        arets_resultat: 'fb_aretsresultat_forandring_reservfond'
      },
      7: { // Fondemission - CSV: uppskrivningsfond, balanserat_resultat, arets_resultat editable
        uppskrivningsfond: 'fb_uppskrfond_fondemission',
        balanserat_resultat: 'fb_balansresultat_fondemission',
        arets_resultat: 'fb_aretsresultat_fondemission'
      },
      8: { // Nyemission - CSV: aktiekapital editable
        aktiekapital: 'fb_aktiekapital_nyemission'
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

  // Helper function to get current value (edited or original)
  const getCurrentValue = (variableName: string): number => {
    return editedValues[variableName] !== undefined ? editedValues[variableName] : fbVariables[variableName] || 0;
  };

  // Helper function to format amounts without decimals and with thousand separator
  const formatAmountForDisplay = (amount: number): string => {
    if (amount === 0) return '';
    return Math.round(amount).toLocaleString('sv-SE');
  };

  // Use recalculated table in edit mode, original table otherwise
  const currentTable = isEditMode ? recalculatedTable : fbTable;

  // Helper function to check if there are differences between row 13 and 14
  const hasDifferences = (): boolean => {
    const row13 = currentTable.find(row => row.id === 13);
    const row14 = currentTable.find(row => row.id === 14);
    if (!row13 || !row14) return false;

    return (
      Math.abs(row13.aktiekapital - row14.aktiekapital) > 0.01 ||
      Math.abs(row13.reservfond - row14.reservfond) > 0.01 ||
      Math.abs(row13.uppskrivningsfond - row14.uppskrivningsfond) > 0.01 ||
      Math.abs(row13.balanserat_resultat - row14.balanserat_resultat) > 0.01 ||
      Math.abs(row13.arets_resultat - row14.arets_resultat) > 0.01 ||
      Math.abs(row13.total - row14.total) > 0.01
    );
  };

  // Helper function to recalculate row 13 totals dynamically
  const recalculateRow13 = (updatedValues: FBVariables) => {
    // Start with original table values
    const originalRow13 = fbTable.find(row => row.id === 13);
    if (!originalRow13) return updatedValues;

    // Calculate new totals by adding all the changes
    let newAktiekapital = fbVariables['fb_aktiekaptial_ib'] || 0;
    let newReservfond = fbVariables['fb_reservfond_ib'] || 0;
    let newUppskrivningsfond = fbVariables['fb_uppskrfond_ib'] || 0;
    let newBalanseratResultat = fbVariables['fb_balansresultat_ib'] || 0;
    let newAretsResultat = fbVariables['fb_aretsresultat_ib'] || 0;

    // Add all the changes from edited values
    Object.entries(updatedValues).forEach(([variableName, value]) => {
      // Map each variable to its column and add to the appropriate total
      if (variableName.includes('aktiekapital')) {
        newAktiekapital += value;
      } else if (variableName.includes('reservfond')) {
        newReservfond += value;
      } else if (variableName.includes('uppskrfond')) {
        newUppskrivningsfond += value;
      } else if (variableName.includes('balansresultat')) {
        newBalanseratResultat += value;
      } else if (variableName.includes('aretsresultat')) {
        newAretsResultat += value;
      }
    });

    // Update the table with new calculated values
    const updatedTable = recalculatedTable.map(row => {
      if (row.id === 13) {
        return {
          ...row,
          aktiekapital: newAktiekapital,
          reservfond: newReservfond,
          uppskrivningsfond: newUppskrivningsfond,
          balanserat_resultat: newBalanseratResultat,
          arets_resultat: newAretsResultat,
          total: newAktiekapital + newReservfond + newUppskrivningsfond + newBalanseratResultat + newAretsResultat
        };
      }
      return row;
    });

    setRecalculatedTable(updatedTable);
    return updatedValues;
  };

  // Helper function to handle input changes (real-time)
  const handleInputChange = (variableName: string, value: string) => {
    const numValue = parseFloat(value) || 0;
    const newValues = {
      ...editedValues,
      [variableName]: numValue
    };
    setEditedValues(recalculateRow13(newValues));
  };

  // Helper function to handle input blur (when user leaves field)
  const handleInputBlur = (variableName: string, value: string) => {
    const numValue = parseFloat(value) || 0;
    const newValues = {
      ...editedValues,
      [variableName]: numValue
    };
    setEditedValues(recalculateRow13(newValues));
  };

  // Helper function to handle keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>, variableName: string) => {
    if (e.key === 'Enter' || e.key === 'Tab') {
      // Commit the current value and move to next field
      const target = e.target as HTMLInputElement;
      handleInputBlur(variableName, target.value);
      
      if (e.key === 'Enter') {
        e.preventDefault();
        // Find next input field and focus it
        const inputs = document.querySelectorAll('input[type="number"]');
        const currentIndex = Array.from(inputs).indexOf(target);
        const nextInput = inputs[currentIndex + 1] as HTMLInputElement;
        if (nextInput) {
          nextInput.focus();
          nextInput.select();
        }
      }
    }
  };

  // Helper function to toggle edit mode
  const toggleEditMode = () => {
    if (isEditMode) {
      // Exiting edit mode
      setIsEditMode(false);
      setEditedValues({});
      setShowAllRows(false);
      setRecalculatedTable(fbTable); // Reset to original table
    } else {
      // Entering edit mode
      setIsEditMode(true);
      setShowAllRows(true);
      setRecalculatedTable(fbTable); // Start with original table
    }
  };

  // Helper function to handle undo
  const handleUndo = () => {
    setEditedValues({});
    setIsEditMode(false);
    setShowAllRows(false);
    setRecalculatedTable(fbTable); // Reset to original table
  };

  // Helper function to handle save
  const handleSave = () => {
    if (hasDifferences()) {
      setShowValidationMessage(true);
      setTimeout(() => setShowValidationMessage(false), 5000);
      return;
    }
    
    // Here you would typically save the changes to the backend
    console.log('Saving changes:', editedValues);
    console.log('Final table state:', recalculatedTable);
    setIsEditMode(false);
    setEditedValues({});
    setShowAllRows(false);
    // Keep the recalculatedTable as it represents the saved state
  };

  // Check which columns have all zero/null values (use recalculated table)
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
    
    // Show all rows if toggle is on
    if (showAllRows) {
      return false;
    }
    
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
    
    // Check if this is row 14 and there's a difference with row 13
    const isDifferenceRow = row.id === 14;
    const row13 = fbTable.find(r => r.id === 13);
    const hasDifference = isDifferenceRow && row13 && Math.abs(row13[column] - value) > 0.01;
    
    if (isEditable && variableName) {
      const currentValue = getCurrentValue(variableName);
      return (
        <input
          type="number"
          className="w-full max-w-[96px] px-1 py-0.5 text-sm border border-gray-300 rounded text-right font-normal h-6 bg-white [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none focus:border-gray-400 focus:outline-none"
          value={currentValue || ''}
          onChange={(e) => handleInputChange(variableName, e.target.value)}
          onBlur={(e) => handleInputBlur(variableName, e.target.value)}
          onKeyDown={(e) => handleKeyDown(e, variableName)}
          step="1"
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

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>
          <h1 className="text-2xl font-bold">Förvaltningsberättelse</h1>
          <div className="flex items-center justify-between mt-2">
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-semibold text-muted-foreground">Förändringar i eget kapital</h2>
              <button
                onClick={toggleEditMode}
                className={`w-6 h-6 rounded-full flex items-center justify-center transition-colors ${
                  isEditMode 
                    ? 'bg-blue-600 text-white' 
                    : 'bg-gray-200 hover:bg-gray-300 text-gray-600'
                }`}
                title={isEditMode ? 'Avsluta redigering' : 'Redigera värden'}
              >
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
        </CardTitle>
      </CardHeader>
      
      <CardContent>
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
              Godkänn och uppdatera ändringar
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 10h-10a8 8 0 00-8 8v2M21 10l-6 6m6-6l-6-6"/>
              </svg>
            </Button>
          </div>
        )}

        {/* Validation Message */}
        {showValidationMessage && (
          <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-center">
              <svg className="w-5 h-5 text-red-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
              <span className="text-red-800 font-medium">
                Belopp vid årets utgång måste stämma överens med redovisat värde
              </span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}