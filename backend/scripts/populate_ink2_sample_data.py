#!/usr/bin/env python3
"""
Populate INK2 tables with sample data to test the tax calculation functionality
"""

import os
from supabase import create_client
from dotenv import load_dotenv

def main():
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    
    if not url or not key:
        print("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY/ANON_KEY")
        return
    
    client = create_client(url, key)
    
    # Sample global variables
    global_variables = [
        {
            "variable_name": "statslaneranta",
            "variable_value": 3.0,
            "description": "Statslåneränta för skatteberäkningar"
        },
        {
            "variable_name": "grundavdrag",
            "variable_value": 24300,
            "description": "Grundavdrag för inkomstskatt"
        },
        {
            "variable_name": "forvaltningsavgift",
            "variable_value": 0.5,
            "description": "Förvaltningsavgift i procent"
        }
    ]
    
    # Sample accounts
    accounts = [
        {"account_id": 6072, "account_text": "Representation ej avdragsgill", "account_category": "Kostnader"},
        {"account_id": 6992, "account_text": "Ej avdragsgill kostnad", "account_category": "Kostnader"},
        {"account_id": 6993, "account_text": "Lämnade bidrag och gåvor", "account_category": "Kostnader"},
        {"account_id": 7622, "account_text": "Sjukvårdsförsäkring, avdragsgill", "account_category": "Personalförmåner"},
        {"account_id": 7623, "account_text": "Sjukvårdsförsäkring, ej avdragsgill", "account_category": "Personalförmåner"},
        {"account_id": 7632, "account_text": "Personalrepresentation, ej avdragsgill", "account_category": "Personalförmåner"},
        {"account_id": 8423, "account_text": "Räntekostnader för skatter och avgifter", "account_category": "Finansiella kostnader"}
    ]
    
    # Sample INK2 mappings based on your screenshot
    ink2_mappings = [
        {
            "row_id": 1,
            "row_title": "Resultat före skatt",
            "accounts_included": None,  # This would be calculated from RR data
            "calculation_formula": "SumAretsResultat",  # Reference to RR variable
            "always_show": True,
            "show_tag": False,
            "variable_name": "ResultatForeSkatt"
        },
        {
            "row_id": 2,
            "row_title": "4.3c Andra bokförda kostnader (+)",
            "accounts_included": "6072;6992",
            "calculation_formula": None,
            "always_show": False,
            "show_tag": True,
            "variable_name": "AndraBokfordaKostnader"
        },
        {
            "row_id": 3,
            "row_title": "4.5c Andra bokförda intäkter (-)",
            "accounts_included": "7622",
            "calculation_formula": None,
            "always_show": False,
            "show_tag": True,
            "variable_name": "AndraBokfordaIntakter"
        },
        {
            "row_id": 4,
            "row_title": "4.6a Beräknad schablonintäkt på kvarvarande periodiseringsfonder vid beskattningsårets ingång (+)",
            "accounts_included": None,
            "calculation_formula": "periodiseringsfonder * statslaneranta / 100",
            "always_show": True,
            "show_tag": False,
            "variable_name": "SchablonintaktPeriodiseringsfonder"
        },
        {
            "row_id": 5,
            "row_title": "4.14a Outnyttjat underskott från fg. år",
            "accounts_included": None,
            "calculation_formula": None,
            "always_show": True,
            "show_tag": False,
            "variable_name": "OutnyttjatUnderskott"
        },
        {
            "row_id": 6,
            "row_title": "Skattemässigt resultat",
            "accounts_included": None,
            "calculation_formula": None,
            "always_show": True,
            "show_tag": False,
            "variable_name": "SkattemassigResultat"
        },
        {
            "row_id": 7,
            "row_title": "Beräknad skatt (20,6%)",
            "accounts_included": None,
            "calculation_formula": "SkattemassigResultat * 0.206",
            "always_show": True,
            "show_tag": False,
            "variable_name": "BeraknadSkatt"
        }
    ]
    
    try:
        # Insert global variables
        print("📊 Inserting global variables...")
        client.table("global_variables").upsert(global_variables, on_conflict="variable_name").execute()
        print(f"✅ Inserted {len(global_variables)} global variables")
        
        # Insert accounts
        print("📋 Inserting accounts...")
        client.table("accounts_table").upsert(accounts, on_conflict="account_id").execute()
        print(f"✅ Inserted {len(accounts)} accounts")
        
        # Insert INK2 mappings
        print("🏛️ Inserting INK2 mappings...")
        client.table("variable_mapping_ink2").upsert(ink2_mappings, on_conflict="row_id").execute()
        print(f"✅ Inserted {len(ink2_mappings)} INK2 mappings")
        
        print("\n🎉 Sample data inserted successfully!")
        print("Now try uploading an SE file to see the tax calculations working.")
        
    except Exception as e:
        print(f"❌ Error inserting data: {e}")

if __name__ == "__main__":
    main()
