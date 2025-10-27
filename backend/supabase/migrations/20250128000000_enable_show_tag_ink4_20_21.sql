-- Enable show_tag for INK4.20 and INK4.21 to display VISA (SHOW) button with account details
-- This allows users to see which accounts contribute to shareholder loans and pension costs

-- Update INK4.20 (Lån från aktieägare vid räkenskapsårets utgång)
-- Shows accounts 2393 and 2893 when they have balances
UPDATE variable_mapping_ink2 
SET show_tag = true
WHERE variable_name = 'INK4.20';

-- Update INK4.21 (Pensionskostnader)
-- Shows account 7410 (and any future pension accounts) when they have balances
UPDATE variable_mapping_ink2 
SET show_tag = true
WHERE variable_name = 'INK4.21';

