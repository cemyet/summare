"""
INK2 PDF Form Filler Service
Populates the INK2_form.pdf with data from the database based on ink2_form table mappings
"""

import os
import re
from typing import Dict, Any, Optional, List
from io import BytesIO
from PyPDF2 import PdfReader, PdfWriter
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(supabase_url, supabase_key)


class INK2PdfFiller:
    """Service to fill INK2 PDF form with data from database"""
    
    def __init__(self, session_id: str, organization_number: str):
        """
        Initialize the PDF filler
        
        Args:
            session_id: Session ID to fetch data for
            organization_number: Organization number for the company
        """
        self.session_id = session_id
        self.organization_number = organization_number
        self.form_mappings = []
        self.variable_values = {}
        
    def _load_form_mappings(self):
        """Load form field mappings from ink2_form table"""
        try:
            response = supabase.table('ink2_form').select('*').order('id').execute()
            self.form_mappings = response.data
            print(f"✅ Loaded {len(self.form_mappings)} form field mappings")
        except Exception as e:
            print(f"❌ Error loading form mappings: {e}")
            raise
    
    def _fetch_variable_value(self, variable_name: str) -> Optional[float]:
        """
        Fetch the last stored value of a variable from the database
        Checks RR, BR, and INK2 tables
        
        Args:
            variable_name: Name of the variable to fetch
            
        Returns:
            The value as a float, or None if not found
        """
        # Try to get from cached values first
        if variable_name in self.variable_values:
            return self.variable_values[variable_name]
        
        # Check each table for the variable
        tables_to_check = [
            ('rr_data', 'variable_name'),
            ('br_data', 'variable_name'),
            ('ink2_data', 'variable_name')
        ]
        
        for table_name, column_name in tables_to_check:
            try:
                response = supabase.table(table_name)\
                    .select('value')\
                    .eq('session_id', self.session_id)\
                    .eq(column_name, variable_name)\
                    .order('updated_at', desc=True)\
                    .limit(1)\
                    .execute()
                
                if response.data and len(response.data) > 0:
                    value = response.data[0].get('value')
                    if value is not None:
                        # Convert to float
                        try:
                            float_value = float(value)
                            self.variable_values[variable_name] = float_value
                            return float_value
                        except (ValueError, TypeError):
                            print(f"⚠️  Could not convert value to float for {variable_name}: {value}")
                            return None
            except Exception as e:
                print(f"⚠️  Error checking table {table_name} for {variable_name}: {e}")
                continue
        
        print(f"⚠️  Variable {variable_name} not found in any table")
        return None
    
    def _parse_variable_mapping(self, mapping: str) -> Optional[float]:
        """
        Parse a variable mapping and return the computed value
        
        Handles:
        - Single variable: "Nettoomsattning"
        - Sum of variables: "MaskinerAndraTekniskaAnlagg+InventarierVerktyg+OvrMatAnlTillgangar"
        - Conditional: "ForandringLager (IF>0)" or "ForandringLager (IF<0)"
        
        Args:
            mapping: The variable mapping string from variable_map column
            
        Returns:
            Computed value or None
        """
        if not mapping or mapping.strip() == '':
            return None
        
        mapping = mapping.strip()
        
        # Check for conditional (IF>0) or (IF<0)
        conditional_match = re.search(r'(.+?)\s*\(IF([><])0\)', mapping)
        if conditional_match:
            variable_expr = conditional_match.group(1).strip()
            condition = conditional_match.group(2)  # '>' or '<'
            
            # Get the value
            value = self._parse_variable_mapping(variable_expr)
            
            if value is None:
                return None
            
            # Apply condition
            if condition == '>' and value > 0:
                return value
            elif condition == '<' and value < 0:
                return abs(value)  # Return absolute value for negative display
            else:
                return None  # Condition not met
        
        # Check for sum of variables (contains +)
        if '+' in mapping:
            parts = [part.strip() for part in mapping.split('+')]
            total = 0.0
            found_any = False
            
            for part in parts:
                value = self._fetch_variable_value(part)
                if value is not None:
                    total += value
                    found_any = True
            
            return total if found_any else None
        
        # Single variable
        return self._fetch_variable_value(mapping)
    
    def _format_value_for_field(self, value: Optional[float], field_type: str = None) -> str:
        """
        Format a value for insertion into a PDF form field
        
        Args:
            value: The numeric value
            field_type: Optional field type hint
            
        Returns:
            Formatted string
        """
        if value is None:
            return ''
        
        # For numeric fields, format as integer (no decimals)
        if field_type and 'Numeriskt' in field_type:
            return str(int(round(value)))
        
        # Default: format as integer
        return str(int(round(value)))
    
    def _get_special_values(self, company_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Get special values that need custom logic (dates, org number, etc.)
        
        Args:
            company_data: Company data dictionary
            
        Returns:
            Dictionary of field names to values
        """
        special_values = {}
        
        # Current date and time for framställning
        now = datetime.now()
        special_values['DatFramst'] = now.strftime('%Y-%m-%d')
        special_values['TidFramst'] = now.strftime('%H:%M')
        
        # System info
        special_values['SystemInfo'] = 'Summare AI - Årsredovisningssystem'
        
        # Organization number
        if self.organization_number:
            special_values['organization_number'] = self.organization_number.replace('-', '')
        
        # Fiscal year dates
        if company_data.get('start_date'):
            special_values['start_date'] = company_data['start_date']
        if company_data.get('end_date'):
            special_values['end_date'] = company_data['end_date']
        
        return special_values
    
    def _normalize_form_field_name(self, form_field: str) -> str:
        """
        Normalize form field name - simply strips #0 suffix if present
        The form_field column already matches the exact PDF field names
        
        Args:
            form_field: Field name from database (e.g., "date#0", "2.1", "3.2(+)")
            
        Returns:
            Normalized field name for PDF
        """
        if not form_field:
            return ""
        
        # Strip #0 or #1 suffix (e.g., "date#0" → "date", "org_nr#0" → "org_nr")
        # The rest of the field name (like "2.1", "3.2(+)", "4.3a") is already correct
        if '#' in form_field:
            form_field = form_field.split('#')[0]
        
        return form_field
    
    def fill_pdf_form(self, pdf_path: str, company_data: Dict[str, Any]) -> bytes:
        """
        Fill the INK2 PDF form with data
        
        Args:
            pdf_path: Path to the INK2_form.pdf template
            company_data: Dictionary with company information
            
        Returns:
            Bytes of the filled PDF
        """
        # Load form mappings
        self._load_form_mappings()
        
        # Get special values
        special_values = self._get_special_values(company_data)
        
        # Read the PDF
        reader = PdfReader(pdf_path)
        writer = PdfWriter()
        
        # Copy all pages
        for page in reader.pages:
            writer.add_page(page)
        
        # Get available PDF fields for validation
        pdf_fields = reader.get_fields()
        available_field_names = set(pdf_fields.keys()) if pdf_fields else set()
        print(f"📄 PDF has {len(available_field_names)} form fields")
        
        # Prepare field updates
        field_updates = {}
        
        for mapping in self.form_mappings:
            form_field_raw = mapping.get('form_field')
            variable_map = mapping.get('variable_map')
            field_type = mapping.get('type')
            
            if not form_field_raw or not variable_map:
                continue
            
            # Normalize the field name (just strips #0 suffix, everything else is exact)
            form_field = self._normalize_form_field_name(form_field_raw)
            
            if not form_field:
                continue
            
            # Check if field exists in PDF
            if form_field not in available_field_names:
                print(f"⚠️  Field '{form_field}' (from '{form_field_raw}') not found in PDF")
                continue
            
            # Check if this is a special value
            if variable_map in special_values:
                field_updates[form_field] = special_values[variable_map]
                print(f"✅ {form_field} = {special_values[variable_map]} (special)")
                continue
            
            # Parse the variable mapping
            value = self._parse_variable_mapping(variable_map)
            
            if value is not None:
                formatted_value = self._format_value_for_field(value, field_type)
                field_updates[form_field] = formatted_value
                print(f"✅ {form_field} = {formatted_value} (from {variable_map})")
            else:
                print(f"⚠️  {form_field} - no value found for {variable_map}")
        
        # Update form fields
        if field_updates:
            writer.update_page_form_field_values(
                writer.pages[0],  # Assuming form fields are on the first page (update all pages if needed)
                field_updates
            )
            
            # Also try to update all pages if there are multiple
            for i in range(len(writer.pages)):
                try:
                    writer.update_page_form_field_values(
                        writer.pages[i],
                        field_updates
                    )
                except Exception as e:
                    print(f"⚠️  Could not update fields on page {i}: {e}")
        
        # Flatten the form (make it non-editable) - optional
        # for page in writer.pages:
        #     page.compress_content_streams()
        
        # Write to bytes
        output = BytesIO()
        writer.write(output)
        output.seek(0)
        
        print(f"✅ PDF form filled successfully with {len(field_updates)} fields")
        
        return output.getvalue()


def generate_filled_ink2_pdf(session_id: str, organization_number: str, company_data: Dict[str, Any]) -> bytes:
    """
    Main function to generate a filled INK2 PDF
    
    Args:
        session_id: Session ID for data retrieval
        organization_number: Company organization number
        company_data: Dictionary with company information
        
    Returns:
        Bytes of the filled PDF
    """
    # Path to the INK2 form template
    pdf_template_path = os.path.join(
        os.path.dirname(__file__),
        '..',
        '..',
        'frontend',
        'public',
        'INK2_form.pdf'
    )
    
    if not os.path.exists(pdf_template_path):
        raise FileNotFoundError(f"INK2 form template not found at {pdf_template_path}")
    
    # Create filler and fill the form
    filler = INK2PdfFiller(session_id, organization_number)
    filled_pdf = filler.fill_pdf_form(pdf_template_path, company_data)
    
    return filled_pdf

