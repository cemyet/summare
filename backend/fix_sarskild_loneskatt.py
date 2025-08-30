#!/usr/bin/env python3
"""
Fix the INK_sarskild_loneskatt row configuration
"""
import sys
import os

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from services.supabase_database import db
    
    print("🔧 Fixing INK_sarskild_loneskatt configuration...")
    
    # Current state
    print("\n📋 Current configuration:")
    mapping = db.get_ink_sarskild_loneskatt_mapping()
    for key, value in mapping.items():
        print(f"   {key}: {value}")
    
    # Fix the configuration
    print("\n🔧 Updating configuration...")
    
    updates = {
        'show_amount': 'TRUE',  # Should show the amount
        'is_calculated': 'FALSE',  # Not calculated, uses adjustment value
        'calculation_formula': 'justering_sarskild_loneskatt',  # Remove the negative sign
        'always_show': None,  # Show only if amount != 0
        'style': 'NORMAL',  # Change from TNORMAL to NORMAL
        'block': 'INK4',  # Make sure it's in INK4 block
        'header': 'FALSE'  # Not a header
    }
    
    success = db.update_table(
        'variable_mapping_ink2',
        updates,
        {'variable_name': 'INK_sarskild_loneskatt'}
    )
    
    if success:
        print("✅ Configuration updated successfully!")
        
        # Show new configuration
        print("\n📋 New configuration:")
        mapping = db.get_ink_sarskild_loneskatt_mapping()
        for key, value in mapping.items():
            print(f"   {key}: {value}")
    else:
        print("❌ Failed to update configuration")
    
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
