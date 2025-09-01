import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Switch } from '@/components/ui/switch';

interface NoterItem {
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
}

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
  const getVisibleItems = (blockItems: NoterItem[]) => {
    return blockItems.filter(item => {
      if (item.always_show) return true;
      if (!item.always_show) {
        // Show if has non-zero amounts OR toggle is on
        const hasNonZeroAmount = (item.current_amount !== 0 && item.current_amount !== null) || 
                                 (item.previous_amount !== 0 && item.previous_amount !== null);
        const toggleIsOn = item.toggle_show && blockToggles[item.block];
        return hasNonZeroAmount || toggleIsOn;
      }
      return false;
    });
  };

  const AccountDetailsDialog = ({ item }: { item: NoterItem }) => (
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
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{item.row_title} - Kontodetaljer</DialogTitle>
        </DialogHeader>
        <div className="mt-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Konto</TableHead>
                <TableHead>Kontotext</TableHead>
                <TableHead className="text-right">{fiscalYear || new Date().getFullYear()}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {item.account_details?.map((detail, index) => (
                <TableRow key={index}>
                  <TableCell className="font-mono">{detail.account_id}</TableCell>
                  <TableCell>{detail.account_text}</TableCell>
                  <TableCell className="text-right font-mono">
                    {formatAmountWithDecimals(detail.balance)}
                  </TableCell>
                </TableRow>
              ))}
              {(!item.account_details || item.account_details.length === 0) && (
                <TableRow>
                  <TableCell colSpan={3} className="text-center text-gray-500">
                    Inga konton med saldo hittades
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </DialogContent>
    </Dialog>
  );

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>
          Noter
        </CardTitle>

      </CardHeader>
      
      <CardContent>
        <div className="space-y-6">
          {blocks.map(block => {
            const blockItems = groupedItems[block];
            const visibleItems = getVisibleItems(blockItems);
            
            if (visibleItems.length === 0) return null;

            // Hide specific blocks if all amounts are zero
            const blocksToHideIfZero = ['KONCERN', 'INTRESSEFTG', 'BYGG', 'MASKIN', 'INV', 'MAT', 'LVP'];
            if (blocksToHideIfZero.includes(block)) {
              const hasNonZeroAmount = blockItems.some(item => 
                (item.current_amount !== 0 && item.current_amount !== null) || 
                (item.previous_amount !== 0 && item.previous_amount !== null)
              );
              if (!hasNonZeroAmount) return null;
            }
            
            // Get first row title for block heading
            const firstRowTitle = blockItems[0]?.row_title || block;
            const blockHeading = `Not ${firstRowTitle}`;
            
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
                          <TableHead className="font-semibold py-2">Anläggningstillgångar</TableHead>
                          <TableHead className="font-semibold text-right py-2">År</TableHead>
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
                        
                        {/* Add moderbolag text after row 534 if moderbolag exists */}
                        {item.row_id === 534 && moderbolag && (
                          <div className="text-sm leading-relaxed mt-2 mb-2 -ml-4">
                            Företaget är ett dotterbolag till {moderbolag} med organisationsnummer {moderbolagOrgnr} med säte i {sate}, som upprättar koncernredovisning.
                          </div>
                        )}
                      </React.Fragment>
                    );
                  })}
                </div>
              );
            }
            
            // Special handling for EVENTUAL block - no toggle, but keep standard layout
            if (block === 'EVENTUAL') {
              return (
                <div key={block} className="space-y-2 pt-4">
                  {/* EVENTUAL heading without toggle */}
                  <div className="border-b pb-1">
                    <h3 className="font-semibold text-lg" style={{paddingTop: '7px'}}>{blockHeading}</h3>
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
          })}
          
          {blocks.every(block => getVisibleItems(groupedItems[block]).length === 0) && (
            <div className="text-center text-gray-500 py-4">
              Inga noter att visa. Aktivera sektioner ovan för att se detaljer.
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
