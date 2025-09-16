-- Add toggle_show column to variable_mapping_ink2 table
-- This enables toggle-specific visibility for tax calculation rows

ALTER TABLE variable_mapping_ink2 
ADD COLUMN toggle_show BOOLEAN NOT NULL DEFAULT FALSE;

-- Add comment to explain the column
COMMENT ON COLUMN variable_mapping_ink2.toggle_show IS 'Show only when toggle is enabled - overrides always_show logic when toggle is ON';
