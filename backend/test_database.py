#!/usr/bin/env python3
"""
Test script to check database connection and INK_sarskild_loneskatt row
"""
import sys
import os

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from services.supabase_database import db
    
    print("🔍 Testing Supabase database connection...")
    
    # Test 1: Check if INK_sarskild_loneskatt row exists
    print("\n1. Checking if INK_sarskild_loneskatt exists...")
    exists = db.check_ink_sarskild_loneskatt_exists()
    print(f"   Result: {'✅ EXISTS' if exists else '❌ NOT FOUND'}")
    
    if exists:
        # Get the mapping details
        mapping = db.get_ink_sarskild_loneskatt_mapping()
        print("   Mapping details:")
        for key, value in mapping.items():
            print(f"     {key}: {value}")
    
    # Test 2: Get all INK2 mappings to see row count
    print("\n2. Getting all INK2 mappings...")
    mappings = db.get_ink2_mappings()
    print(f"   Total INK2 mappings: {len(mappings)}")
    
    # Show INK_sarskild_loneskatt specifically
    sarskild_rows = [m for m in mappings if 'sarskild' in m.get('variable_name', '').lower()]
    print(f"   Rows with 'sarskild' in name: {len(sarskild_rows)}")
    for row in sarskild_rows:
        print(f"     - {row.get('variable_name')}: {row.get('row_title')}")
    
    # Test 3: Get global variables
    print("\n3. Getting global variables...")
    globals_vars = db.get_global_variables()
    print(f"   Total global variables: {len(globals_vars)}")
    
    # Look for sarskild_loneskatt rate
    sarskild_rate = [g for g in globals_vars if 'sarskild' in g.get('variable_name', '').lower()]
    print(f"   Sarskild loneskatt rate variables: {len(sarskild_rate)}")
    for var in sarskild_rate:
        print(f"     - {var.get('variable_name')}: {var.get('value')}")
    
    print("\n✅ Database connection test completed!")
    
except Exception as e:
    print(f"❌ Database connection failed: {e}")
    print("\nMake sure SUPABASE_URL and SUPABASE_ANON_KEY are set in environment variables.")
    sys.exit(1)
