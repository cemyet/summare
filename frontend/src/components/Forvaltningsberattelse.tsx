'use client';

import { Card } from "@/components/ui/card";
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
    <Card className="p-6 mt-6">
      <h2 className="text-xl font-bold mb-4">
        Förvaltningsberättelse - Förändring i eget kapital
      </h2>
      
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b-2 border-gray-300">
              <th className="text-left py-2 px-3 font-semibold min-w-[200px]"></th>
              <th className="text-right py-2 px-3 font-semibold min-w-[120px]">Aktiekapital</th>
              <th className="text-right py-2 px-3 font-semibold min-w-[120px]">Reservfond</th>
              <th className="text-right py-2 px-3 font-semibold min-w-[140px]">Uppskrivningsfond</th>
              <th className="text-right py-2 px-3 font-semibold min-w-[140px]">Balanserat resultat</th>
              <th className="text-right py-2 px-3 font-semibold min-w-[120px]">Årets resultat</th>
              <th className="text-right py-2 px-3 font-semibold min-w-[120px] border-l-2 border-gray-300">Totalt</th>
            </tr>
          </thead>
          <tbody>
            {fbTable.map((row) => {
              const isHeaderRow = row.id === 1 || row.id === 13 || row.id === 14;
              const isSubtotalRow = row.id === 13;
              
              return (
                <tr 
                  key={row.id} 
                  className={`border-b border-gray-200 ${isHeaderRow ? 'bg-gray-50 font-semibold' : ''} ${isSubtotalRow ? 'border-t-2 border-gray-400' : ''}`}
                >
                  <td className="py-2 px-3 text-left">{row.label}</td>
                  <td className="py-2 px-3 text-right font-mono">{row.aktiekapital !== 0 ? formatAmount(row.aktiekapital) : ''}</td>
                  <td className="py-2 px-3 text-right font-mono">{row.reservfond !== 0 ? formatAmount(row.reservfond) : ''}</td>
                  <td className="py-2 px-3 text-right font-mono">{row.uppskrivningsfond !== 0 ? formatAmount(row.uppskrivningsfond) : ''}</td>
                  <td className="py-2 px-3 text-right font-mono">{row.balanserat_resultat !== 0 ? formatAmount(row.balanserat_resultat) : ''}</td>
                  <td className="py-2 px-3 text-right font-mono">{row.arets_resultat !== 0 ? formatAmount(row.arets_resultat) : ''}</td>
                  <td className="py-2 px-3 text-right font-mono border-l-2 border-gray-300 font-semibold">{row.total !== 0 ? formatAmount(row.total) : ''}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="mt-4 text-sm text-gray-600">
        <p>Tabellen visar förändringarna i eget kapital under räkenskapsåret {fiscalYear ? fiscalYear : 'aktuellt år'}.</p>
        
        {fbVariables.fb_balansresultat_utdelning && fbVariables.fb_balansresultat_utdelning < 0 && (
          <div className="mt-2 p-3 bg-blue-50 rounded-md">
            <p className="font-medium text-blue-800">Utdelning: {formatAmount(Math.abs(fbVariables.fb_balansresultat_utdelning))} kr</p>
          </div>
        )}
        
        {fbVariables.fb_balansresultat_erhallna_aktieagartillskott && fbVariables.fb_balansresultat_erhallna_aktieagartillskott > 0 && (
          <div className="mt-2 p-3 bg-green-50 rounded-md">
            <p className="font-medium text-green-800">Erhållna aktieägartillskott: {formatAmount(fbVariables.fb_balansresultat_erhallna_aktieagartillskott)} kr</p>
          </div>
        )}
        
        {fbVariables.fb_uppskrfond_aterforing && fbVariables.fb_uppskrfond_aterforing < 0 && (
          <div className="mt-2 p-3 bg-orange-50 rounded-md">
            <p className="font-medium text-orange-800">Återföring av uppskrivningsfond: {formatAmount(Math.abs(fbVariables.fb_uppskrfond_aterforing))} kr</p>
          </div>
        )}
      </div>
    </Card>
  );
}