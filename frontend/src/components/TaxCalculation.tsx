import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Switch } from '@/components/ui/switch';

interface TaxCalculationItem {
  row_id: number;
  row_title: string;
  amount: number;
  variable_name: string;
  show_tag: boolean;
  accounts_included: string;
  always_show?: boolean | null;
  account_details?: Array<{
    account_id: string;
    account_text: string;
    balance: number;
  }>;
}

interface TaxCalculationProps {
  ink2Data: TaxCalculationItem[];
  fiscalYear?: number;
  onContinue: () => void;
}

export function TaxCalculation({ ink2Data, fiscalYear, onContinue }: TaxCalculationProps) {
  const [selectedItem, setSelectedItem] = useState<TaxCalculationItem | null>(null);
  const [showAllRows, setShowAllRows] = useState(false);

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

  // Filter items based on always_show logic and toggle state
  const getVisibleItems = () => {
    return ink2Data.filter(item => {
      // always_show = true: always show
      if (item.always_show === true) return true;
      
      // always_show = false: never show
      if (item.always_show === false) return false;
      
      // always_show = null/undefined: show if amount != 0 OR toggle is on
      if (item.always_show === null || item.always_show === undefined) {
        if (item.amount !== 0) return true;
        return showAllRows;
      }
      
      return false;
    });
  };

  const visibleItems = getVisibleItems();

  const AccountDetailsDialog = ({ item }: { item: TaxCalculationItem }) => (
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
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            🏛️ Skatteberäkning
            <span className="text-sm font-normal text-gray-600">
              ({visibleItems.length} av {ink2Data.length} poster)
            </span>
          </CardTitle>
          <div className="flex items-center space-x-2">
            <label 
              htmlFor="toggle-show-all-tax" 
              className="text-sm font-medium cursor-pointer"
            >
              Visa alla rader
            </label>
            <Switch
              id="toggle-show-all-tax"
              checked={showAllRows}
              onCheckedChange={setShowAllRows}
            />
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-1">
          {visibleItems.map((item, index) => (
            <div 
              key={index} 
              className="flex items-center justify-between py-2 border-b border-gray-100 last:border-b-0"
            >
              <div className="flex items-center">
                <span className="text-sm">{item.row_title}</span>
                {item.show_tag && item.account_details && (
                  <AccountDetailsDialog item={item} />
                )}
              </div>
              <span className="font-mono text-sm text-right min-w-[100px]">
                {formatAmount(item.amount)}
              </span>
            </div>
          ))}
          
          {visibleItems.length === 0 && ink2Data.length > 0 && (
            <div className="text-center py-8 text-gray-500">
              <p>Inga rader att visa med nuvarande inställningar</p>
              <p className="text-xs mt-1">Aktivera "Visa alla rader" för att se alla poster</p>
            </div>
          )}
          
          {ink2Data.length === 0 && (
            <div className="text-center py-8 text-gray-500">
              <p>Inga skatteberäkningar tillgängliga</p>
              <p className="text-xs mt-1">Kontrollera att INK2 mappings finns i databasen</p>
            </div>
          )}
        </div>
        
        <div className="mt-6 pt-4 border-t border-gray-200">
          <div className="text-xs text-gray-500 mb-4">
            Endast de vanligaste skattemässiga justeringarna visas. Fullständiga justeringar kan göras i INK2S-blanketten före inlämning i steg 7.
          </div>
          
          <Button 
            onClick={onContinue}
            className="w-full"
          >
            Fortsätt till utdelning
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
