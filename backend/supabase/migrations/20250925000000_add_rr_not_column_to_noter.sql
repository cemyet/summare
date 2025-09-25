-- Add rr_not column to variable_mapping_noter table
-- This mirrors the br_not column approach that works perfectly for BR
-- This column stores the RR row number where the note number should be placed

ALTER TABLE variable_mapping_noter 
ADD COLUMN rr_not INTEGER;

-- Add comment to explain the column
COMMENT ON COLUMN variable_mapping_noter.rr_not IS 'RR row number where the note number should be placed in column 2 (note column)';

-- Set the mapping for NOT2 -> Personalkostnader (RR row 252)
-- This mirrors how BR mappings work
UPDATE variable_mapping_noter 
SET rr_not = 252 
WHERE block = 'NOT2';
