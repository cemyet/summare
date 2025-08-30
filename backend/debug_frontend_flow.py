#!/usr/bin/env python3
"""
Debug the frontend recalculation flow by simulating the exact API call
"""
import sys
import os
import json

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from services.database_parser import DatabaseParser
    
    print("🔍 Debugging frontend recalculation flow...")
    
    # Simulate the exact API call from triggerPensionTaxRecalculation
    # This is what the frontend should be sending
    api_data = {
        'current_accounts': {
            '7410': 62628,  # pension_premier
            '7531': 0,      # sarskild_loneskatt_pension (booked)
            # Add more accounts from your actual SE file
            '8999': -553622.39,  # Results account
        },
        'fiscal_year': 2024,
        'rr_data': [
            {'variable_name': 'SkattAretsResultat', 'current_amount': 0},
            {'variable_name': 'SumAretsResultat', 'current_amount': 553622.39}
        ],
        'br_data': [],
        'manual_amounts': {},  # No manual edits, just pension tax adjustment
        'justering_sarskild_loneskatt': 15194  # The pension tax adjustment
    }
    
    print("\n1. Simulating API call with data:")
    print(f"   justering_sarskild_loneskatt: {api_data['justering_sarskild_loneskatt']}")
    
    # Initialize parser
    parser = DatabaseParser()
    
    # Extract the parameters as the API endpoint does
    current_accounts = api_data.get('current_accounts', {})
    fiscal_year = api_data.get('fiscal_year')
    rr_data = api_data.get('rr_data', [])
    br_data = api_data.get('br_data', [])
    manual_amounts = api_data.get('manual_amounts', {})
    justering_sarskild_loneskatt = api_data.get('justering_sarskild_loneskatt', 0)
    
    # Add pension tax adjustment to manual amounts if provided (as per API logic)
    if justering_sarskild_loneskatt != 0:
        manual_amounts['justering_sarskild_loneskatt'] = justering_sarskild_loneskatt
        print(f"   Added to manual_amounts: {manual_amounts}")
    
    # Call the recalculation method
    ink2_data = parser.parse_ink2_data_with_overrides(
        current_accounts, 
        fiscal_year, 
        rr_data, 
        br_data, 
        manual_amounts
    )
    
    print(f"\n2. API Response:")
    print(f"   Total rows: {len(ink2_data)}")
    
    # Find the INK_sarskild_loneskatt row
    sarskild_row = next((item for item in ink2_data if item.get('variable_name') == 'INK_sarskild_loneskatt'), None)
    
    if sarskild_row:
        print("   ✅ INK_sarskild_loneskatt found!")
        print(f"   Amount: {sarskild_row.get('amount')}")
        print(f"   Row: {json.dumps(sarskild_row, indent=6)}")
        
        # Check visibility logic
        amount = sarskild_row.get('amount')
        show_amount = sarskild_row.get('show_amount')
        always_show = sarskild_row.get('always_show')
        
        print(f"\n3. Frontend visibility check:")
        print(f"   amount: {amount} != 0? {amount != 0}")
        print(f"   show_amount: {show_amount}")
        print(f"   always_show: {always_show}")
        
        # Frontend logic from AnnualReportPreview.tsx
        should_show = False
        
        if show_amount == 'NEVER':
            should_show = False
            reason = "show_amount is NEVER"
        elif always_show == True:
            should_show = True
            reason = "always_show is True"
        elif always_show == False:
            should_show = False
            reason = "always_show is False"
        elif amount != None and amount != 0 and amount != -0:
            should_show = True
            reason = "amount is non-zero"
        else:
            should_show = False
            reason = "amount is zero/null and always_show is null"
            
        print(f"   Should show: {should_show} ({reason})")
        
    else:
        print("   ❌ INK_sarskild_loneskatt NOT found!")
        
        # Show all rows to debug
        print("\n   All returned rows:")
        for i, row in enumerate(ink2_data):
            var_name = row.get('variable_name', 'UNKNOWN')
            amount = row.get('amount', 'NONE')
            print(f"     {i+1}. {var_name}: {amount}")
    
    # Test: Find what other pension-related variables exist
    print(f"\n4. All pension/sarskild related variables:")
    pension_vars = [row for row in ink2_data if any(keyword in row.get('variable_name', '').lower() for keyword in ['pension', 'sarskild', 'loneskatt'])]
    for var in pension_vars:
        print(f"   - {var.get('variable_name')}: {var.get('amount')}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
