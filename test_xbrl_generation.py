#!/usr/bin/env python3
"""Quick script to generate XBRL document to desktop for testing"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from services.xbrl_generator import generate_xbrl_instance_document
import json

# Load test company data (you may need to adjust this path)
# This should match the format from your API endpoint
test_data = {
    "fiscal_year": 2024,
    "organization_number": "5566103643",
    "company_name": "Holtback Yeter Consulting AB",
    "seFileData": {
        "company_info": {
            "company_name": "Holtback Yeter Consulting AB",
            "organization_number": "5566103643",
            "fiscal_year": 2024,
            "start_date": "2024-01-01",
            "end_date": "2024-12-31"
        }
    }
}

# Try to load actual data if available
try:
    # Check if there's a recent test data file
    test_files = [
        'backend/test_data.json',
        'test_company_data.json'
    ]
    
    for test_file in test_files:
        if os.path.exists(test_file):
            with open(test_file, 'r') as f:
                loaded_data = json.load(f)
                if loaded_data:
                    test_data = loaded_data
                    print(f"Loaded data from {test_file}")
                    break
except Exception as e:
    print(f"Could not load test data file: {e}")
    print("Using minimal test data")

try:
    # Generate XBRL document
    print("Generating XBRL document...")
    xbrl_bytes = generate_xbrl_instance_document(test_data)
    
    # Write to desktop
    output_path = "/Users/cemyeter/Desktop/arsredovisning (32).xhtml"
    with open(output_path, 'wb') as f:
        f.write(xbrl_bytes)
    
    print(f"Successfully generated: {output_path}")
    print(f"File size: {len(xbrl_bytes):,} bytes")
    
except Exception as e:
    print(f"Error generating XBRL: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)



