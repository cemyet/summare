'use client';

import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Switch } from '@/components/ui/switch';
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

  if (!fbTable || fbTable.length === 0) {
    return null;
  }

  // Check which columns have all zero/null values
  const hasNonZeroValues = {
    aktiekapital: showAllRows || fbTable.some(row => row.aktiekapital !== 0),
    reservfond: showAllRows || fbTable.some(row => row.reservfond !== 0),
    uppskrivningsfond: showAllRows || fbTable.some(row => row.uppskrivningsfond !== 0),
    balanserat_resultat: showAllRows || fbTable.some(row => row.balanserat_resultat !== 0),
    arets_resultat: showAllRows || fbTable.some(row => row.arets_resultat !== 0),
    total: showAllRows || fbTable.some(row => row.total !== 0)
  };

  // Function to check if a row should be hidden (all values are zero/null)
  const shouldHideRow = (row: FBTableRow) => {
    // Show all rows if toggle is on
    if (showAllRows) {
      return false;
    }
    
    // Always show header rows (IB, UB, Redovisat värde)
    if (row.id === 1 || row.id === 13 || row.id === 14) {
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

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>
          <h1 className="text-2xl font-bold">Förvaltningsberättelse</h1>
          <div className="flex items-center justify-between mt-2">
            <h2 className="text-lg font-semibold text-muted-foreground">Förändring i eget kapital</h2>
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
              <TableHead className="font-semibold py-1 min-w-[200px]"></TableHead>
              {hasNonZeroValues.aktiekapital && (
                <TableHead className="font-semibold text-right py-1 min-w-[120px]">Aktiekapital</TableHead>
              )}
              {hasNonZeroValues.reservfond && (
                <TableHead className="font-semibold text-right py-1 min-w-[120px]">Reservfond</TableHead>
              )}
              {hasNonZeroValues.uppskrivningsfond && (
                <TableHead className="font-semibold text-right py-1 min-w-[140px]">
                  <div className="text-center">
                    <div>Uppskrivnings-</div>
                    <div>fond</div>
                  </div>
                </TableHead>
              )}
              {hasNonZeroValues.balanserat_resultat && (
                <TableHead className="font-semibold text-right py-1 min-w-[140px]">Balanserat resultat</TableHead>
              )}
              {hasNonZeroValues.arets_resultat && (
                <TableHead className="font-semibold text-right py-1 min-w-[120px]">Årets resultat</TableHead>
              )}
              {hasNonZeroValues.total && (
                <TableHead className="font-semibold text-right py-1 min-w-[120px] border-l-2 border-gray-300">Totalt</TableHead>
              )}
            </TableRow>
          </TableHeader>
          <TableBody>
            {fbTable.filter(row => !shouldHideRow(row)).map((row) => {
              const isHeaderRow = row.id === 1 || row.id === 13 || row.id === 14;
              const isSubtotalRow = row.id === 13;
              
              return (
                <TableRow 
                  key={row.id} 
                  className={`${isHeaderRow ? 'bg-gray-50 font-semibold' : ''} ${isSubtotalRow ? 'border-t-2 border-gray-400' : ''}`}
                >
                  <TableCell className="py-1 text-left">{row.label}</TableCell>
                  {hasNonZeroValues.aktiekapital && (
                    <TableCell className="py-1 text-right">
                      {row.aktiekapital !== 0 ? formatAmount(row.aktiekapital) : ''}
                    </TableCell>
                  )}
                  {hasNonZeroValues.reservfond && (
                    <TableCell className="py-1 text-right">
                      {row.reservfond !== 0 ? formatAmount(row.reservfond) : ''}
                    </TableCell>
                  )}
                  {hasNonZeroValues.uppskrivningsfond && (
                    <TableCell className="py-1 text-right">
                      {row.uppskrivningsfond !== 0 ? formatAmount(row.uppskrivningsfond) : ''}
                    </TableCell>
                  )}
                  {hasNonZeroValues.balanserat_resultat && (
                    <TableCell className="py-1 text-right">
                      {row.balanserat_resultat !== 0 ? formatAmount(row.balanserat_resultat) : ''}
                    </TableCell>
                  )}
                  {hasNonZeroValues.arets_resultat && (
                    <TableCell className="py-1 text-right">
                      {row.arets_resultat !== 0 ? formatAmount(row.arets_resultat) : ''}
                    </TableCell>
                  )}
                  {hasNonZeroValues.total && (
                    <TableCell className="py-1 text-right border-l-2 border-gray-300 font-semibold">
                      {row.total !== 0 ? formatAmount(row.total) : ''}
                    </TableCell>
                  )}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}