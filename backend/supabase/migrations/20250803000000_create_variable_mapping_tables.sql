-- Create variable mapping tables for RR and BR structures
-- This replaces the hardcoded BR_STRUCTURE and RR_STRUCTURE with database-driven approach

-- Table 1: Variable Mapping for RR (Resultaträkning)
CREATE TABLE variable_mapping_rr (
  id SERIAL PRIMARY KEY,
  row_id INTEGER NOT NULL,
  row_title TEXT NOT NULL,
  accounts_included_start INTEGER,
  accounts_included_end INTEGER,
  accounts_included TEXT, -- Additional accounts (e.g., "8113;8118" or "4910-4931")
  accounts_excluded_start INTEGER,
  accounts_excluded_end INTEGER,
  accounts_excluded TEXT, -- Additional excluded accounts
  show_amount BOOLEAN NOT NULL DEFAULT FALSE,
  style TEXT NOT NULL, -- H0, H1, H2, NORMAL, S3, etc.
  variable_name TEXT NOT NULL, -- Variable name for the amount
  element_name TEXT, -- Bolagsverket element name
  is_calculated BOOLEAN NOT NULL DEFAULT FALSE,
  calculation_formula TEXT, -- Formula for calculated values
  is_abstract BOOLEAN NOT NULL DEFAULT FALSE,
  data_type TEXT, -- xbrli:monetaryItemType, etc.
  balance_type TEXT, -- DEBIT/CREDIT
  show_in_shortened BOOLEAN NOT NULL DEFAULT FALSE,
  period_type TEXT, -- DURATION/INSTANT
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  
  UNIQUE(row_id)
);

-- Table 2: Variable Mapping for BR (Balansräkning)
CREATE TABLE variable_mapping_br (
  id SERIAL PRIMARY KEY,
  row_id INTEGER NOT NULL,
  row_title TEXT NOT NULL,
  accounts_included_start INTEGER,
  accounts_included_end INTEGER,
  accounts_included TEXT, -- Additional accounts (e.g., "8113;8118" or "4910-4931")
  accounts_excluded_start INTEGER,
  accounts_excluded_end INTEGER,
  accounts_excluded TEXT, -- Additional excluded accounts
  show_amount BOOLEAN NOT NULL DEFAULT FALSE,
  style TEXT NOT NULL, -- H0, H1, H2, NORMAL, S3, etc.
  variable_name TEXT NOT NULL, -- Variable name for the amount
  element_name TEXT, -- Bolagsverket element name
  is_calculated BOOLEAN NOT NULL DEFAULT FALSE,
  calculation_formula TEXT, -- Formula for calculated values
  is_abstract BOOLEAN NOT NULL DEFAULT FALSE,
  data_type TEXT, -- xbrli:monetaryItemType, etc.
  balance_type TEXT, -- DEBIT/CREDIT
  show_in_shortened BOOLEAN NOT NULL DEFAULT FALSE,
  period_type TEXT, -- DURATION/INSTANT
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  
  UNIQUE(row_id)
);

-- Table 3: Financial Data Storage (replaces JSON-based approach)
CREATE TABLE financial_data (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID REFERENCES companies(id),
  fiscal_year INTEGER NOT NULL,
  report_type TEXT NOT NULL CHECK (report_type IN ('RR', 'BR')),
  
  -- Dynamic columns will be added based on variable names from mapping tables
  -- This table will be populated with actual financial values
  
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  
  UNIQUE(company_id, fiscal_year, report_type)
);

-- Enable RLS
ALTER TABLE variable_mapping_rr ENABLE ROW LEVEL SECURITY;
ALTER TABLE variable_mapping_br ENABLE ROW LEVEL SECURITY;
ALTER TABLE financial_data ENABLE ROW LEVEL SECURITY;

-- Create policies
CREATE POLICY "Anyone can view variable mappings" ON variable_mapping_rr FOR SELECT USING (true);
CREATE POLICY "Anyone can view variable mappings" ON variable_mapping_br FOR SELECT USING (true);
CREATE POLICY "Anyone can view financial data" ON financial_data FOR SELECT USING (true);

CREATE POLICY "Anyone can create variable mappings" ON variable_mapping_rr FOR INSERT WITH CHECK (true);
CREATE POLICY "Anyone can create variable mappings" ON variable_mapping_br FOR INSERT WITH CHECK (true);
CREATE POLICY "Anyone can create financial data" ON financial_data FOR INSERT WITH CHECK (true);

CREATE POLICY "Anyone can update variable mappings" ON variable_mapping_rr FOR UPDATE USING (true);
CREATE POLICY "Anyone can update variable mappings" ON variable_mapping_br FOR UPDATE USING (true);
CREATE POLICY "Anyone can update financial data" ON financial_data FOR UPDATE USING (true);

-- Create triggers for automatic timestamp updates
CREATE TRIGGER update_variable_mapping_rr_updated_at
BEFORE UPDATE ON variable_mapping_rr
FOR EACH ROW
EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_variable_mapping_br_updated_at
BEFORE UPDATE ON variable_mapping_br
FOR EACH ROW
EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_financial_data_updated_at
BEFORE UPDATE ON financial_data
FOR EACH ROW
EXECUTE FUNCTION public.update_updated_at_column();

-- Create indexes for better performance
CREATE INDEX idx_variable_mapping_rr_row_id ON variable_mapping_rr(row_id);
CREATE INDEX idx_variable_mapping_br_row_id ON variable_mapping_br(row_id);
CREATE INDEX idx_variable_mapping_rr_variable_name ON variable_mapping_rr(variable_name);
CREATE INDEX idx_variable_mapping_br_variable_name ON variable_mapping_br(variable_name);
CREATE INDEX idx_financial_data_company_year ON financial_data(company_id, fiscal_year);
CREATE INDEX idx_financial_data_report_type ON financial_data(report_type);
