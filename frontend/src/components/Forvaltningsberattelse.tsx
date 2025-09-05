'use client';

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
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
  if (!fbTable || fbTable.length === 0) {
    return null;
  }


  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>
          <h1 className="text-2xl font-bold">Förvaltningsberättelse</h1>
          <h2 className="text-lg font-semibold text-muted-foreground mt-2">Förändring i eget kapital</h2>
        </CardTitle>
      </CardHeader>
      
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="font-semibold py-1 min-w-[200px]"></TableHead>
              <TableHead className="font-semibold text-right py-1 min-w-[120px]">Aktiekapital</TableHead>
              <TableHead className="font-semibold text-right py-1 min-w-[120px]">Reservfond</TableHead>
              <TableHead className="font-semibold text-right py-1 min-w-[140px]">Uppskrivningsfond</TableHead>
              <TableHead className="font-semibold text-right py-1 min-w-[140px]">Balanserat resultat</TableHead>
              <TableHead className="font-semibold text-right py-1 min-w-[120px]">Årets resultat</TableHead>
              <TableHead className="font-semibold text-right py-1 min-w-[120px] border-l-2 border-gray-300">Totalt</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {fbTable.map((row) => {
              const isHeaderRow = row.id === 1 || row.id === 13 || row.id === 14;
              const isSubtotalRow = row.id === 13;
              
              return (
                <TableRow 
                  key={row.id} 
                  className={`${isHeaderRow ? 'bg-gray-50 font-semibold' : ''} ${isSubtotalRow ? 'border-t-2 border-gray-400' : ''}`}
                >
                  <TableCell className="py-1 text-left">{row.label}</TableCell>
                  <TableCell className="py-1 text-right">
                    {row.aktiekapital !== 0 ? formatAmount(row.aktiekapital) : ''}
                  </TableCell>
                  <TableCell className="py-1 text-right">
                    {row.reservfond !== 0 ? formatAmount(row.reservfond) : ''}
                  </TableCell>
                  <TableCell className="py-1 text-right">
                    {row.uppskrivningsfond !== 0 ? formatAmount(row.uppskrivningsfond) : ''}
                  </TableCell>
                  <TableCell className="py-1 text-right">
                    {row.balanserat_resultat !== 0 ? formatAmount(row.balanserat_resultat) : ''}
                  </TableCell>
                  <TableCell className="py-1 text-right">
                    {row.arets_resultat !== 0 ? formatAmount(row.arets_resultat) : ''}
                  </TableCell>
                  <TableCell className="py-1 text-right border-l-2 border-gray-300 font-semibold">
                    {row.total !== 0 ? formatAmount(row.total) : ''}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}