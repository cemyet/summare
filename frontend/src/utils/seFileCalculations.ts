// SE File calculation utilities - simplified for database-driven parser
// Most calculations are now handled by the backend database parser

export interface SEData {
  // Legacy interface - kept for backward compatibility
  accountBalances?: Record<string, number>;
  sruMapping?: Record<string, string>;
  incomeStatement?: Array<{account: string, amount: number, description?: string}>;
  balanceSheet?: Array<{account: string, amount: number, description?: string, type?: string}>;
  
  // New database-driven parser format
  rr_data?: Array<{
    id: string;
    label: string;
    current_amount: number | null;
    previous_amount: number | null;
    level: number;
    section: string;
    bold?: boolean;
    style?: string;
    block_group?: string;
    always_show?: boolean;
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
    style?: string;
    block_group?: string;
    always_show?: boolean;
  }>;
  company_info?: {
    organization_number?: string;
    fiscal_year?: number;
    company_name?: string;
    location?: string;
    date?: string;
  };
}

// Format amount for display
export function formatAmount(amount: number | null, rowId?: string): string {
  if (amount === null || amount === undefined) {
    return '';
  }
  
  return new Intl.NumberFormat('sv-SE', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

// Legacy functions - kept for backward compatibility but deprecated
export function calculateRRSums(seData: SEData): Array<{ID: string, Rubrik: string, summa: number}> {
  console.warn('calculateRRSums is deprecated - use database-driven parser instead');
  return [];
}

export function extractKeyMetrics(seData: SEData) {
  console.warn('extractKeyMetrics is deprecated - use database-driven parser instead');
  return null;
}