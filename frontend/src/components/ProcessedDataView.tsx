import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { Building2, Calendar, FileText, Download } from 'lucide-react';

interface ProcessedDataViewProps {
  data: {
    organizationNumber?: string;
    fiscalYear: number;
    fiscalYearMinus1?: number;
    fiscalYearString: string;
    endDate: string;
    // New database-driven parser format
    rr_data?: Array<{
      id: string;
      label: string;
      current_amount: number | null;
      previous_amount: number | null;
      level: number;
      section: string;
      bold?: boolean;
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
    }>;
    // Legacy format (fallback)
    incomeStatementYear0?: Array<{
      id: string;
      label: string;
      amount: number | null;
      level: number;
      section: string;
      bold?: boolean;
    }>;
    incomeStatementYearMinus1?: Array<{
      id: string;
      label: string;
      amount: number | null;
      level: number;
      section: string;
      bold?: boolean;
    }>;
    balanceSheetYear0?: Array<{
      id: string;
      label: string;
      amount: number;
      level: number;
      section: string;
      type: 'asset' | 'liability' | 'equity';
      bold?: boolean;
    }>;
    balanceSheetYearMinus1?: Array<{
      id: string;
      label: string;
      amount: number;
      level: number;
      section: string;
      type: 'asset' | 'liability' | 'equity';
      bold?: boolean;
    }>;
    // Legacy fallback
    incomeStatement?: Array<{
      account: string;
      amount: number;
      description: string;
    }>;
    balanceSheet?: Array<{
      account: string;
      amount: number;
      description: string;
      type: 'asset' | 'liability' | 'equity';
    }>;
  };
  reportId: string;
}

export function ProcessedDataView({ data, reportId }: ProcessedDataViewProps) {
  const formatAmount = (amount: number | null) => {
    if (amount === null) {
      return ''; // Return empty string for null amounts (headers)
    }
    return new Intl.NumberFormat('sv-SE', {
      style: 'currency',
      currency: 'SEK',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const generatePDF = async () => {
    // TODO: Implement PDF generation

  };

  // Helper function to normalize data to new format
  const normalizeItem = (item: any) => {
    if (item.current_amount !== undefined) {
      // Already in new format
      return item;
    } else if (item.amount !== undefined) {
      // Old format - convert to new format
      return {
        ...item,
        current_amount: item.amount,
        previous_amount: null
      };
    }
    return item;
  };

  // Use new data format or fallback to legacy
  const incomeStatementYear0 = (data.rr_data || data.incomeStatementYear0 || data.incomeStatement?.map(item => ({
    id: item.account,
    label: item.description,
    current_amount: item.amount,
    previous_amount: null,
    level: 1,
    section: 'Legacy',
    bold: false
  })) || []).map(normalizeItem);
  
  const incomeStatementYearMinus1 = (data.incomeStatementYearMinus1 || []).map(normalizeItem);
  
  const balanceSheetYear0 = (data.br_data || data.balanceSheetYear0 || data.balanceSheet?.map(item => ({
    id: item.account,
    label: item.description,
    current_amount: item.amount,
    previous_amount: null,
    level: 1,
    section: 'Legacy',
    type: item.type,
    bold: false
  })) || []).map(normalizeItem);
  
  const balanceSheetYearMinus1 = (data.balanceSheetYearMinus1 || []).map(normalizeItem);

  // Group balance sheet items by type for both years
  const assetsYear0 = balanceSheetYear0.filter(item => item.type === 'asset');
  const liabilitiesYear0 = balanceSheetYear0.filter(item => item.type === 'liability');
  const equityYear0 = balanceSheetYear0.filter(item => item.type === 'equity');
  
  const assetsYearMinus1 = balanceSheetYearMinus1.filter(item => item.type === 'asset');
  const liabilitiesYearMinus1 = balanceSheetYearMinus1.filter(item => item.type === 'liability');
  const equityYearMinus1 = balanceSheetYearMinus1.filter(item => item.type === 'equity');

  return (
    <div className="space-y-6">
      {/* Header */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Building2 className="w-5 h-5" />
            Företagsinformation
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {data.organizationNumber && (
              <div>
                <p className="text-sm text-muted-foreground">Organisationsnummer</p>
                <p className="font-medium">{data.organizationNumber}</p>
              </div>
            )}
            <div>
              <p className="text-sm text-muted-foreground">Räkenskapsår</p>
              <p className="font-medium">{data.fiscalYear} / {data.fiscalYearMinus1 || data.fiscalYear - 1}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Slutdatum</p>
              <p className="font-medium">{data.endDate}</p>
            </div>
          </div>
          
          <div className="flex justify-end">
            <Button onClick={generatePDF} className="gap-2">
              <Download className="w-4 h-4" />
              Generera PDF-rapport
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Income Statement */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="w-5 h-5" />
            Resultaträkning
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* Header row */}
            <div className="grid grid-cols-3 gap-4 font-semibold text-sm text-muted-foreground border-b pb-2">
              <div>Beskrivning</div>
              <div className="text-right">{data.fiscalYear}</div>
              <div className="text-right flex items-center justify-end gap-2">
                {data.fiscalYearMinus1 || data.fiscalYear - 1}
                {incomeStatementYearMinus1.length > 0 ? (
                  <Badge variant="secondary" className="text-xs">({incomeStatementYearMinus1.length} rader)</Badge>
                ) : (
                  <Badge variant="destructive" className="text-xs">(Ingen data)</Badge>
                )}
              </div>
            </div>
            
            {/* Income statement rows */}
            {incomeStatementYear0.map((item, index) => {
              const itemYearMinus1 = incomeStatementYearMinus1.find(i => i.id === item.id);
              return (
                <div key={index} className={`grid grid-cols-3 gap-4 py-2 ${item.bold ? 'font-bold border-t' : ''}`}>
                  <div className={`${item.level > 0 ? 'pl-4' : ''}`}>
                    <p className={item.bold ? "font-bold" : ""}>{item.label}</p>
                  </div>
                  <div className="text-right">
                    {item.current_amount !== null ? (
                      <Badge variant={item.current_amount >= 0 ? "default" : "destructive"}>
                        {formatAmount(item.current_amount)}
                      </Badge>
                    ) : (
                      <span className="text-muted-foreground">-</span>
                    )}
                  </div>
                  <div className="text-right">
                    {itemYearMinus1 && itemYearMinus1.current_amount !== null ? (
                      <Badge variant={itemYearMinus1.current_amount >= 0 ? "default" : "destructive"}>
                        {formatAmount(itemYearMinus1.current_amount)}
                      </Badge>
                    ) : (
                      <span className="text-muted-foreground">-</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Balance Sheet */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calendar className="w-5 h-5" />
            Balansräkning
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Header row */}
          <div className="grid grid-cols-3 gap-4 font-semibold text-sm text-muted-foreground border-b pb-2">
            <div>Beskrivning</div>
            <div className="text-right">{data.fiscalYear}</div>
            <div className="text-right">{data.fiscalYearMinus1 || data.fiscalYear - 1}</div>
          </div>
          
          {/* Assets */}
          {assetsYear0.length > 0 && (
            <div>
              <h4 className="font-semibold mb-3 text-primary">Tillgångar</h4>
              <div className="space-y-2">
                {assetsYear0.map((item, index) => {
                  const itemYearMinus1 = assetsYearMinus1.find(i => i.id === item.id);
                  return (
                    <div key={index} className={`grid grid-cols-3 gap-4 py-2 ${item.bold ? 'font-bold border-t' : ''}`}>
                      <div className={`${item.level > 0 ? 'pl-4' : ''}`}>
                        <p className={item.bold ? "font-bold" : ""}>{item.label}</p>
                      </div>
                      <div className="text-right">
                        <Badge variant="outline">
                          {formatAmount(item.current_amount)}
                        </Badge>
                      </div>
                      <div className="text-right">
                        <Badge variant="outline">
                          {formatAmount(itemYearMinus1?.current_amount || 0)}
                        </Badge>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {assetsYear0.length > 0 && (liabilitiesYear0.length > 0 || equityYear0.length > 0) && (
            <Separator />
          )}

          {/* Liabilities */}
          {liabilitiesYear0.length > 0 && (
            <div>
              <h4 className="font-semibold mb-3 text-primary">Skulder</h4>
              <div className="space-y-2">
                {liabilitiesYear0.map((item, index) => {
                  const itemYearMinus1 = liabilitiesYearMinus1.find(i => i.id === item.id);
                  return (
                    <div key={index} className={`grid grid-cols-3 gap-4 py-2 ${item.bold ? 'font-bold border-t' : ''}`}>
                      <div className={`${item.level > 0 ? 'pl-4' : ''}`}>
                        <p className={item.bold ? "font-bold" : ""}>{item.label}</p>
                      </div>
                      <div className="text-right">
                        <Badge variant="outline">
                          {formatAmount(item.current_amount)}
                        </Badge>
                      </div>
                      <div className="text-right">
                        <Badge variant="outline">
                          {formatAmount(itemYearMinus1?.current_amount || 0)}
                        </Badge>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {liabilitiesYear0.length > 0 && equityYear0.length > 0 && <Separator />}

          {/* Equity */}
          {equityYear0.length > 0 && (
            <div>
              <h4 className="font-semibold mb-3 text-primary">Eget kapital</h4>
              <div className="space-y-2">
                {equityYear0.map((item, index) => {
                  const itemYearMinus1 = equityYearMinus1.find(i => i.id === item.id);
                  return (
                    <div key={index} className={`grid grid-cols-3 gap-4 py-2 ${item.bold ? 'font-bold border-t' : ''}`}>
                      <div className={`${item.level > 0 ? 'pl-4' : ''}`}>
                        <p className={item.bold ? "font-bold" : ""}>{item.label}</p>
                      </div>
                      <div className="text-right">
                        <Badge variant="outline">
                          {formatAmount(item.current_amount)}
                        </Badge>
                      </div>
                      <div className="text-right">
                        <Badge variant="outline">
                          {formatAmount(itemYearMinus1?.current_amount || 0)}
                        </Badge>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}