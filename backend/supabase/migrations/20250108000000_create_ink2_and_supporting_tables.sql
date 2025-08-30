-- Create INK2 tax calculation tables and supporting structures
-- This adds tax calculation functionality with simpler structure than RR/BR

-- Table 1: Variable Mapping for INK2 (Tax calculations)
CREATE TABLE variable_mapping_ink2 (
  id SERIAL PRIMARY KEY,
  row_id INTEGER NOT NULL,
  row_title TEXT NOT NULL,
  accounts_included TEXT, -- Simplified: only one column for included accounts
  calculation_formula TEXT, -- Formula for calculated values, may reference global variables
  always_show BOOLEAN NOT NULL DEFAULT FALSE, -- Show row regardless of amount
  show_tag BOOLEAN NOT NULL DEFAULT FALSE, -- Show SHOW tag for account details popup
  variable_name TEXT NOT NULL, -- Variable name for the amount
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  
  UNIQUE(row_id)
);

-- Table 2: Global Variables for calculations
CREATE TABLE global_variables (
  id SERIAL PRIMARY KEY,
  variable_name TEXT NOT NULL UNIQUE, -- e.g., 'statslaneranta'
  variable_value DECIMAL(15,4) NOT NULL, -- The numeric value
  description TEXT, -- Description of what this variable represents
  fiscal_year INTEGER, -- Year this value applies to (if year-specific)
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Table 3: Accounts lookup table for account text descriptions
CREATE TABLE accounts_table (
  id SERIAL PRIMARY KEY,
  account_id INTEGER NOT NULL UNIQUE, -- Account number (e.g., 6072, 6992)
  account_text TEXT NOT NULL, -- Account description
  account_category TEXT, -- Optional categorization
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Enable RLS
ALTER TABLE variable_mapping_ink2 ENABLE ROW LEVEL SECURITY;
ALTER TABLE global_variables ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts_table ENABLE ROW LEVEL SECURITY;

-- Create policies (following same pattern as RR/BR tables)
CREATE POLICY "Anyone can view INK2 mappings" ON variable_mapping_ink2 FOR SELECT USING (true);
CREATE POLICY "Anyone can insert INK2 mappings" ON variable_mapping_ink2 FOR INSERT WITH CHECK (true);
CREATE POLICY "Anyone can update INK2 mappings" ON variable_mapping_ink2 FOR UPDATE USING (true);

CREATE POLICY "Anyone can view global variables" ON global_variables FOR SELECT USING (true);
CREATE POLICY "Anyone can insert global variables" ON global_variables FOR INSERT WITH CHECK (true);
CREATE POLICY "Anyone can update global variables" ON global_variables FOR UPDATE USING (true);

CREATE POLICY "Anyone can view accounts" ON accounts_table FOR SELECT USING (true);
CREATE POLICY "Anyone can insert accounts" ON accounts_table FOR INSERT WITH CHECK (true);
CREATE POLICY "Anyone can update accounts" ON accounts_table FOR UPDATE USING (true);

-- Create triggers for automatic timestamp updates
CREATE TRIGGER update_variable_mapping_ink2_updated_at
BEFORE UPDATE ON variable_mapping_ink2
FOR EACH ROW
EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_global_variables_updated_at
BEFORE UPDATE ON global_variables
FOR EACH ROW
EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_accounts_table_updated_at
BEFORE UPDATE ON accounts_table
FOR EACH ROW
EXECUTE FUNCTION public.update_updated_at_column();

-- Create indexes for better performance
CREATE INDEX idx_variable_mapping_ink2_row_id ON variable_mapping_ink2(row_id);
CREATE INDEX idx_variable_mapping_ink2_variable_name ON variable_mapping_ink2(variable_name);
CREATE INDEX idx_global_variables_variable_name ON global_variables(variable_name);
CREATE INDEX idx_global_variables_fiscal_year ON global_variables(fiscal_year);
CREATE INDEX idx_accounts_table_account_id ON accounts_table(account_id);

-- Insert some sample global variables (can be updated later)
INSERT INTO global_variables (variable_name, variable_value, description) VALUES
('statslaneranta', 3.0, 'Statslåneränta för skatteberäkningar'),
('grundavdrag', 24300, 'Grundavdrag för inkomstskatt'),
('forvaltningsavgift', 0.5, 'Förvaltningsavgift i procent');

-- Insert some common account descriptions (can be expanded)
INSERT INTO accounts_table (account_id, account_text, account_category) VALUES
(6072, 'Representation ej avdragsgill', 'Kostnader'),
(6992, 'Ej avdragsgill kostnad', 'Kostnader'),
(6993, 'Lämnade bidrag och gåvor', 'Kostnader'),
(7622, 'Sjukvårdsförsäkring, avdragsgill', 'Personalförmåner'),
(7623, 'Sjukvårdsförsäkring, ej avdragsgill', 'Personalförmåner'),
(7632, 'Personalrepresentation, ej avdragsgill', 'Personalförmåner'),
(8423, 'Räntekostnader för skatter och avgifter', 'Finansiella kostnader');
