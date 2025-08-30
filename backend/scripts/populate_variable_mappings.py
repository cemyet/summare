#!/usr/bin/env python3
"""
Script to populate variable mapping tables from Excel files
This converts the Excel structures to database tables
"""

import pandas as pd
import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

def parse_account_ranges(account_str):
    """Parse account ranges from string format"""
    if pd.isna(account_str) or account_str == "":
        return None
    return str(account_str)

def parse_boolean(value):
    """Parse boolean values from Excel"""
    if pd.isna(value):
        return False
    if isinstance(value, str):
        return value.upper() == "TRUE"
    return bool(value)

def populate_rr_mappings():
    """Populate RR variable mappings from Excel"""
    print("Loading RR Excel file...")
    
    # Read the Excel file
    df = pd.read_excel('/Users/cem/Desktop/Tabell_RR.xlsx')
    
    print(f"Found {len(df)} rows in RR file")
    
    # Process each row
    for index, row in df.iterrows():
        try:
            data = {
                'row_id': int(row['ID']) if pd.notna(row['ID']) else None,
                'row_title': str(row['Radrubrik']) if pd.notna(row['Radrubrik']) else '',
                'accounts_included_start': int(row['Accounts\nincluded int. start']) if pd.notna(row['Accounts\nincluded int. start']) else None,
                'accounts_included_end': int(row['Accounts\nincluded int. end']) if pd.notna(row['Accounts\nincluded int. end']) else None,
                'accounts_included': parse_account_ranges(row['Accounts\nincluded']),
                'accounts_excluded_start': int(row['Accounts\nexcluded int. start']) if pd.notna(row['Accounts\nexcluded int. start']) else None,
                'accounts_excluded_end': int(row['Accounts\nexcluded int. end']) if pd.notna(row['Accounts\nexcluded int. end']) else None,
                'accounts_excluded': parse_account_ranges(row['Accounts\nexcluded']),
                'show_amount': parse_boolean(row['Amount']),
                'style': str(row['Style']) if pd.notna(row['Style']) else 'NORMAL',
                'variable_name': str(row['Variabelnamn']) if pd.notna(row['Variabelnamn']) else '',
                'element_name': str(row['Elementnamn']) if pd.notna(row['Elementnamn']) else None,
                'is_calculated': parse_boolean(row['Calculate']),
                'calculation_formula': str(row['Calculation formula']) if pd.notna(row['Calculation formula']) else None,
                'is_abstract': parse_boolean(row['Abstrakt']),
                'data_type': str(row['Datatyp']) if pd.notna(row['Datatyp']) else None,
                'balance_type': str(row['Saldo']) if pd.notna(row['Saldo']) else None,
                'show_in_shortened': parse_boolean(row['Forkort\nad']),
                'period_type': str(row['Periodtyp']) if pd.notna(row['Periodtyp']) else None
            }
            
            # Skip rows without row_id
            if data['row_id'] is None:
                continue
                
            # Insert into database
            result = supabase.table('variable_mapping_rr').upsert(data).execute()
            print(f"Inserted RR row {data['row_id']}: {data['row_title']}")
            
        except Exception as e:
            print(f"Error processing RR row {index}: {e}")
            continue

def populate_br_mappings():
    """Populate BR variable mappings from Excel"""
    print("Loading BR Excel file...")
    
    # Read the Excel file
    df = pd.read_excel('/Users/cem/Desktop/Tabell_BR.xlsx')
    
    print(f"Found {len(df)} rows in BR file")
    
    # Process each row
    for index, row in df.iterrows():
        try:
            data = {
                'row_id': int(row['ID']) if pd.notna(row['ID']) else None,
                'row_title': str(row['Radrubrik']) if pd.notna(row['Radrubrik']) else '',
                'accounts_included_start': int(row['Accounts\nincluded int. start']) if pd.notna(row['Accounts\nincluded int. start']) else None,
                'accounts_included_end': int(row['Accounts\nincluded int. end']) if pd.notna(row['Accounts\nincluded int. end']) else None,
                'accounts_included': parse_account_ranges(row['Accounts\nincluded']),
                'accounts_excluded_start': int(row['Accounts\nexcluded int. start']) if pd.notna(row['Accounts\nexcluded int. start']) else None,
                'accounts_excluded_end': int(row['Accounts\nexcluded int. end']) if pd.notna(row['Accounts\nexcluded int. end']) else None,
                'accounts_excluded': parse_account_ranges(row['Accounts\nexcluded']),
                'show_amount': parse_boolean(row['Amount']),
                'style': str(row['Style']) if pd.notna(row['Style']) else 'NORMAL',
                'variable_name': str(row['Variabelnamn']) if pd.notna(row['Variabelnamn']) else '',
                'element_name': str(row['Elementnamn']) if pd.notna(row['Elementnamn']) else None,
                'is_calculated': parse_boolean(row['Calculate']),
                'calculation_formula': str(row['Calculation formula']) if pd.notna(row['Calculation formula']) else None,
                'is_abstract': parse_boolean(row['Abstrakt']),
                'data_type': str(row['Datatyp']) if pd.notna(row['Datatyp']) else None,
                'balance_type': str(row['Saldo']) if pd.notna(row['Saldo']) else None,
                'show_in_shortened': parse_boolean(row['Forkort\nad']),
                'period_type': str(row['Periodtyp']) if pd.notna(row['Periodtyp']) else None
            }
            
            # Skip rows without row_id
            if data['row_id'] is None:
                continue
                
            # Insert into database
            result = supabase.table('variable_mapping_br').upsert(data).execute()
            print(f"Inserted BR row {data['row_id']}: {data['row_title']}")
            
        except Exception as e:
            print(f"Error processing BR row {index}: {e}")
            continue

def main():
    """Main function to populate both tables"""
    print("Starting variable mapping population...")
    
    try:
        # Populate RR mappings
        print("\n=== Populating RR Mappings ===")
        populate_rr_mappings()
        
        # Populate BR mappings
        print("\n=== Populating BR Mappings ===")
        populate_br_mappings()
        
        print("\n=== Population Complete ===")
        
        # Show summary
        rr_count = supabase.table('variable_mapping_rr').select('*').execute()
        br_count = supabase.table('variable_mapping_br').select('*').execute()
        
        print(f"RR mappings: {len(rr_count.data)} rows")
        print(f"BR mappings: {len(br_count.data)} rows")
        
    except Exception as e:
        print(f"Error in main: {e}")

if __name__ == "__main__":
    main()
