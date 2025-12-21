-- ============================================================================
-- Add user_reclassifications column to annual_report_data table
-- ============================================================================
-- Run this SQL in your Supabase SQL editor.
-- ============================================================================

-- Add column for storing user's manual account reclassifications
-- Structure: JSONB array of {account_id, from_row_id, to_row_id, balance_current, balance_previous}
ALTER TABLE annual_report_data 
ADD COLUMN IF NOT EXISTS user_reclassifications JSONB DEFAULT '[]'::jsonb;

-- Create index for the new column
CREATE INDEX IF NOT EXISTS idx_annual_report_reclassifications 
ON annual_report_data USING gin(user_reclassifications);

-- ============================================================================
-- Example of user_reclassifications structure:
-- [
--   {
--     "account_id": "1219",
--     "from_row_id": 322,
--     "to_row_id": 321,
--     "balance_current": -35870,
--     "balance_previous": -30000
--   }
-- ]
-- ============================================================================
