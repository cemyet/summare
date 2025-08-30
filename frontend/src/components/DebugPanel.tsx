import React from 'react';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Card, CardContent } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';

interface DebugInfo {
  // SE File parsing
  se_file_lines_count?: number;
  res_lines_found?: number;
  ub_lines_found?: number;
  ib_lines_found?: number;
  year0_lines_parsed?: number;
  year_minus1_lines_parsed?: number;
  sample_se_lines?: any[];
  has_rar_line?: boolean;
  has_res_lines?: boolean;
  has_ub_lines?: boolean;
  has_ib_lines?: boolean;
  has_sru_lines?: boolean;
  
  // Income Statement
  year0_income_statement_length?: number;
  year_minus1_income_statement_length?: number;
  year_minus1_income_statement_with_amounts_count?: number;
  
  // Balance Sheet
  year0_balance_sheet_length?: number;
  year_minus1_balance_sheet_length?: number;
  year_minus1_balance_sheet_with_amounts_count?: number;
  year0_balance_sheet_details?: any[];
  year_minus1_balance_sheet_details?: any[];
  
  // Accounts
  year0_accounts_sample?: [string, number][];
  year_minus1_accounts_sample?: [string, number][];
  
  // SRU Mappings
  sru_mappings_count?: number;
  sru_mappings_sample?: [string, string][];
  
  // EKS specific
  eks_calculation_debug?: {
    ek_value: number;
    s_value: number;
    eks_value: number;
    total_assets: number;
  };
}

interface DebugPanelProps {
  debugInfo: DebugInfo;
}

export function DebugPanel({ debugInfo }: DebugPanelProps) {
  if (!debugInfo || Object.keys(debugInfo).length === 0) {
    return (
      <div className="p-4">
        <h3 className="text-sm font-semibold mb-2">🐛 Debug Panel</h3>
        <p className="text-xs text-muted-foreground">No debug data available. Upload an SE file to see debugging information.</p>
      </div>
    );
  }

  const formatAmount = (amount: number) => {
    return new Intl.NumberFormat('sv-SE', {
      style: 'currency',
      currency: 'SEK',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  return (
    <ScrollArea className="h-full">
      <Card>
        <CardContent className="space-y-4 text-sm">
          {/* SE File Parsing */}
          <div>
            <h4 className="font-semibold mb-2">📄 SE File Parsing</h4>
            <div className="space-y-1">
              <div className="flex justify-between">
                <span>Total lines:</span>
                <Badge variant="outline">{debugInfo.se_file_lines_count || 0}</Badge>
              </div>
              <div className="flex justify-between">
                <span>RES lines:</span>
                <Badge variant={debugInfo.has_res_lines ? "default" : "destructive"}>
                  {debugInfo.res_lines_found || 0}
                </Badge>
              </div>
              <div className="flex justify-between">
                <span>UB lines:</span>
                <Badge variant={debugInfo.has_ub_lines ? "default" : "destructive"}>
                  {debugInfo.ub_lines_found || 0}
                </Badge>
              </div>
              <div className="flex justify-between">
                <span>IB lines:</span>
                <Badge variant={debugInfo.has_ib_lines ? "default" : "destructive"}>
                  {debugInfo.ib_lines_found || 0}
                </Badge>
              </div>
              <div className="flex justify-between">
                <span>SRU lines:</span>
                <Badge variant={debugInfo.has_sru_lines ? "default" : "destructive"}>
                  {debugInfo.sru_mappings_count || 0}
                </Badge>
              </div>
            </div>
          </div>

          <Separator />

          {/* Balance Sheet */}
          <div>
            <h4 className="font-semibold mb-2">💰 Balance Sheet</h4>
            <div className="space-y-1">
              <div className="flex justify-between">
                <span>Year 0 rows:</span>
                <Badge variant="outline">{debugInfo.year0_balance_sheet_length || 0}</Badge>
              </div>
              <div className="flex justify-between">
                <span>Year -1 rows:</span>
                <Badge variant="outline">{debugInfo.year_minus1_balance_sheet_length || 0}</Badge>
              </div>
              <div className="flex justify-between">
                <span>Year -1 with amounts:</span>
                <Badge variant="outline">{debugInfo.year_minus1_balance_sheet_with_amounts_count || 0}</Badge>
              </div>
            </div>
          </div>

          {/* EKS Calculation Debug */}
          {debugInfo.eks_calculation_debug && (
            <>
              <Separator />
              <div>
                <h4 className="font-semibold mb-2">🔍 EKS Calculation</h4>
                <div className="space-y-1">
                  <div className="flex justify-between">
                    <span>EK (Equity):</span>
                    <span className="font-mono">{formatAmount(debugInfo.eks_calculation_debug.ek_value)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>S (Liabilities):</span>
                    <span className="font-mono">{formatAmount(debugInfo.eks_calculation_debug.s_value)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>EKS (Total):</span>
                    <span className="font-mono">{formatAmount(debugInfo.eks_calculation_debug.eks_value)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>T (Assets):</span>
                    <span className="font-mono">{formatAmount(debugInfo.eks_calculation_debug.total_assets)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Balance:</span>
                    <Badge variant={Math.abs(debugInfo.eks_calculation_debug.eks_value - debugInfo.eks_calculation_debug.total_assets) < 1 ? "default" : "destructive"}>
                      {formatAmount(debugInfo.eks_calculation_debug.eks_value - debugInfo.eks_calculation_debug.total_assets)}
                    </Badge>
                  </div>
                </div>
              </div>
            </>
          )}

          {/* Account Samples */}
          {debugInfo.year0_accounts_sample && debugInfo.year0_accounts_sample.length > 0 && (
            <>
              <Separator />
              <div>
                <h4 className="font-semibold mb-2">📊 Year 0 Accounts (Sample)</h4>
                <div className="space-y-1 max-h-32 overflow-y-auto">
                  {debugInfo.year0_accounts_sample.map(([account, amount]) => (
                    <div key={account} className="flex justify-between text-xs">
                      <span className="font-mono">{account}:</span>
                      <span className="font-mono">{formatAmount(amount)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* Balance Sheet Details */}
          {debugInfo.year0_balance_sheet_details && debugInfo.year0_balance_sheet_details.length > 0 && (
            <>
              <Separator />
              <div>
                <h4 className="font-semibold mb-2">📋 Balance Sheet Details</h4>
                <div className="space-y-1 max-h-32 overflow-y-auto">
                  {debugInfo.year0_balance_sheet_details.map((item) => (
                    <div key={item.id} className="text-xs">
                      <div className="flex justify-between">
                        <span className="font-mono">{item.id}:</span>
                        <span className="font-mono">{formatAmount(item.amount || 0)}</span>
                      </div>
                      {item.calculation && (
                        <div className="text-xs text-muted-foreground ml-2">
                          {item.calculation}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

        </CardContent>
      </Card>
    </ScrollArea>
  );
} // Trigger deploy
