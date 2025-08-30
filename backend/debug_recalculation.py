#!/usr/bin/env python3
"""
Debug the recalculation with pension tax adjustment
"""
import sys
import os

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from services.database_parser import DatabaseParser
    
    print("🔍 Debugging INK2 recalculation with pension tax adjustment...")
    
    # Initialize parser
    parser = DatabaseParser()
    
    # Simulate the exact scenario from your screenshot
    current_accounts = {
        '7410': 62628,  # pension_premier 
        '7531': 0,      # sarskild_loneskatt_pension (booked = 0)
    }
    
    # Sample RR data with tax result
    rr_data = [
        {'variable_name': 'SkattAretsResultat', 'current_amount': 0},
        {'variable_name': 'SumAretsResultat', 'current_amount': 553622.39}
    ]
    
    br_data = []
    
    # Test with pension tax adjustment = 15194
    manual_amounts = {'justering_sarskild_loneskatt': 15194}
    
    print("\n1. Testing recalculation with pension tax adjustment...")
    print(f"   Manual amounts: {manual_amounts}")
    
    ink2_data = parser.parse_ink2_data_with_overrides(
        current_accounts, 2024, rr_data, br_data, manual_amounts
    )
    
    print(f"\n2. Total INK2 rows returned: {len(ink2_data)}")
    
    # Look specifically for INK_sarskild_loneskatt
    sarskild_rows = [item for item in ink2_data if 'sarskild' in item.get('variable_name', '').lower()]
    
    print(f"\n3. Rows with 'sarskild' in name: {len(sarskild_rows)}")
    for row in sarskild_rows:
        print(f"   Variable: {row.get('variable_name')}")
        print(f"   Amount: {row.get('amount')}")
        print(f"   Show amount: {row.get('show_amount')}")
        print(f"   Always show: {row.get('always_show')}")
        print(f"   Row title: {row.get('row_title')}")
        print(f"   Full row: {row}")
        print()
    
    # Check the exact INK_sarskild_loneskatt row
    ink_sarskild = next((item for item in ink2_data if item.get('variable_name') == 'INK_sarskild_loneskatt'), None)
    
    if ink_sarskild:
        print("✅ INK_sarskild_loneskatt found in results!")
        print(f"   Amount: {ink_sarskild.get('amount')}")
        print(f"   Show amount: {ink_sarskild.get('show_amount')}")
        print(f"   Always show: {ink_sarskild.get('always_show')}")
    else:
        print("❌ INK_sarskild_loneskatt NOT found in results!")
        
        # Let's check what variables are being processed
        print("\n🔍 All variables processed:")
        for item in ink2_data:
            var_name = item.get('variable_name', 'UNKNOWN')
            amount = item.get('amount', 'NONE')
            print(f"   {var_name}: {amount}")
    
    # Test the visibility logic
    print("\n4. Testing visibility logic...")
    if ink_sarskild:
        amount = ink_sarskild.get('amount')
        show_amount = ink_sarskild.get('show_amount')
        always_show = ink_sarskild.get('always_show')
        
        print(f"   Amount: {amount} (type: {type(amount)})")
        print(f"   Show amount: {show_amount} (type: {type(show_amount)})")
        print(f"   Always show: {always_show} (type: {type(always_show)})")
        
        # Simulate frontend visibility logic
        should_show = False
        
        if show_amount == 'NEVER' or show_amount == False:
            should_show = False
            print("   → Hidden: show_amount is NEVER/False")
        elif always_show == True or always_show == 'TRUE':
            should_show = True
            print("   → Shown: always_show is True")
        elif always_show == False or always_show == 'FALSE':
            should_show = False
            print("   → Hidden: always_show is False")
        elif amount != 0 and amount != -0 and amount is not None:
            should_show = True
            print("   → Shown: amount is non-zero")
        else:
            should_show = False
            print("   → Hidden: amount is zero/null and always_show is null")
            
        print(f"   FINAL VISIBILITY: {'SHOW' if should_show else 'HIDE'}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
