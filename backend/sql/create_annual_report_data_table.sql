-- ============================================================================
-- SQL Schema for Annual Report Data Storage (Mina Sidor Feature)
-- ============================================================================
-- Run this SQL in your Supabase SQL editor to create the required table.
-- This table stores all annual report data after payment for the Mina Sidor feature.
-- ============================================================================

-- Create the annual_report_data table
CREATE TABLE IF NOT EXISTS annual_report_data (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    
    -- Company identification
    organization_number VARCHAR(20) NOT NULL,
    company_name VARCHAR(255),
    
    -- Fiscal year period
    fiscal_year_start DATE NOT NULL,
    fiscal_year_end DATE NOT NULL,
    
    -- Report sections (stored as JSONB for flexibility)
    fb_data JSONB,           -- Förvaltningsberättelse data (fb_variables, fb_table)
    rr_data JSONB,           -- Resultaträkning data (array of row items)
    br_data JSONB,           -- Balansräkning data (array of row items)
    noter_data JSONB,        -- Noter data (array of note items)
    ink2_data JSONB,         -- INK2 skatteberäkning data (array of row items)
    signering_data JSONB,    -- Signering data (board members, dates, etc.)
    company_data JSONB,      -- Full company data object (variables, settings, etc.)
    
    -- Status tracking
    status VARCHAR(50) DEFAULT 'draft',  -- draft, submitted, signed, completed
    
    -- Audit fields
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Unique constraint: one report per company per fiscal year
    CONSTRAINT unique_company_fiscal_year UNIQUE (organization_number, fiscal_year_start, fiscal_year_end)
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_annual_report_org_number ON annual_report_data(organization_number);
CREATE INDEX IF NOT EXISTS idx_annual_report_fiscal_year ON annual_report_data(fiscal_year_end DESC);
CREATE INDEX IF NOT EXISTS idx_annual_report_status ON annual_report_data(status);
CREATE INDEX IF NOT EXISTS idx_annual_report_updated ON annual_report_data(updated_at DESC);

-- Enable Row Level Security (RLS) if needed
ALTER TABLE annual_report_data ENABLE ROW LEVEL SECURITY;

-- Create a policy that allows all operations for authenticated users
-- Adjust this based on your security requirements
CREATE POLICY "Allow all operations on annual_report_data" ON annual_report_data
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- ============================================================================
-- Sample Queries for Reference
-- ============================================================================

-- Get all reports for a specific organization:
-- SELECT * FROM annual_report_data WHERE organization_number = '5569876543' ORDER BY fiscal_year_end DESC;

-- Get the most recent report for an organization:
-- SELECT * FROM annual_report_data WHERE organization_number = '5569876543' ORDER BY fiscal_year_end DESC LIMIT 1;

-- Get all reports for a user (requires joining with users table):
-- SELECT ard.* FROM annual_report_data ard
-- JOIN users u ON ard.organization_number = ANY(u.organization_number)
-- WHERE u.username = 'user@example.com'
-- ORDER BY ard.fiscal_year_end DESC;

-- ============================================================================
-- Notes on JSONB Structure
-- ============================================================================
-- 
-- fb_data example:
-- {
--   "fb_variables": {"oms1": 1000000, "ref1": 50000, ...},
--   "fb_table": [{row_data}, {row_data}, ...]
-- }
--
-- rr_data example:
-- [{row_id: 240, variable_name: "ResultatrakningHeader", current_amount: 0, ...}, ...]
--
-- br_data example:
-- [{row_id: 310, variable_name: "BalansrakningHeader", current_amount: 0, ...}, ...]
--
-- noter_data example:
-- [{row_id: 502, variable_name: "NoterHeader", ...}, ...]
--
-- ink2_data example:
-- [{row_id: 0, variable_name: "INKa", current_amount: 0, ...}, ...]
--
-- signering_data example:
-- {
--   "boardMembers": [{name: "Anna Andersson", personalNumber: "851201-1234", ...}],
--   "date": "2024-12-17",
--   "location": "Stockholm"
-- }
--
-- company_data example:
-- {
--   "result": 100000,
--   "dividend": "utdelning",
--   "customDividend": 50000,
--   "inkBeraknadSkatt": 20600,
--   ...
-- }

