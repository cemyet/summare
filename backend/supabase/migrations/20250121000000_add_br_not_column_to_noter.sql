-- Add br_not column to variable_mapping_noter table
-- This column stores the BR row number where the note number should be placed

ALTER TABLE variable_mapping_noter 
ADD COLUMN br_not INTEGER;

-- Add comment to explain the column
COMMENT ON COLUMN variable_mapping_noter.br_not IS 'BR row number where the note number should be placed in column 2 (note column)';
