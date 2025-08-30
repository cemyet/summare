#!/usr/bin/env python3
"""
Test INK_sarskild_loneskatt calculation
"""
import sys
import os

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from services.database_parser import DatabaseParser
    
    print("🧪 Testing INK_sarskild_loneskatt calculation...")
    
    # Initialize parser
    parser = DatabaseParser()
    
    # Test with dummy data
    current_accounts = {
        '7410': 62628,  # pension_premier
        '7531': 0,      # sarskild_loneskatt_pension (booked)
    }
    
    rr_data = [
        {'variable_name': 'SkattAretsResultat', 'current_amount': 50000}
    ]
    
    br_data = []
    
    # Test 1: No adjustment (justering_sarskild_loneskatt = 0)
    print("\n1. Testing with no pension tax adjustment:")
    ink2_data = parser.parse_ink2_data(current_accounts, 2024, rr_data, br_data)
    
    sarskild_row = next((item for item in ink2_data if item.get('variable_name') == 'INK_sarskild_loneskatt'), None)
    
    if sarskild_row:
        print(f"   ✅ INK_sarskild_loneskatt found: {sarskild_row['amount']}")
        print(f"   Row details: {sarskild_row}")
    else:
        print("   ❌ INK_sarskild_loneskatt NOT found in results")
    
    # Test 2: With adjustment
    print("\n2. Testing with pension tax adjustment (15194 kr):")
    manual_amounts = {'justering_sarskild_loneskatt': 15194}
    
    ink2_data_with_adjustment = parser.parse_ink2_data_with_overrides(
        current_accounts, 2024, rr_data, br_data, manual_amounts
    )
    
    sarskild_row_adj = next((item for item in ink2_data_with_adjustment if item.get('variable_name') == 'INK_sarskild_loneskatt'), None)
    
    if sarskild_row_adj:
        print(f"   ✅ INK_sarskild_loneskatt found: {sarskild_row_adj['amount']}")
        print(f"   Row details: {sarskild_row_adj}")
    else:
        print("   ❌ INK_sarskild_loneskatt NOT found in results")
    
    # Show all variables with 'sarskild' in name
    print("\n3. All variables with 'sarskild' in name:")
    all_sarskild = [item for item in ink2_data_with_adjustment if 'sarskild' in item.get('variable_name', '').lower()]
    for item in all_sarskild:
        print(f"   - {item.get('variable_name')}: {item.get('amount')} (show_amount: {item.get('show_amount')})")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
