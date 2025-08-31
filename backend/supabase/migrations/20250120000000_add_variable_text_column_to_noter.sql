-- Add variable_text column to variable_mapping_noter table
-- This column stores descriptive text content for notes

ALTER TABLE variable_mapping_noter 
ADD COLUMN variable_text TEXT;

-- Add comment to explain the column
COMMENT ON COLUMN variable_mapping_noter.variable_text IS 'Descriptive text content for notes, used for explanatory text sections';
