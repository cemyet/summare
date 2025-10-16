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
    
    def __init__(self, organization_number: str, fiscal_year: int, rr_data: List[Dict] = None, br_data: List[Dict] = None, ink2_data: List[Dict] = None):
        """
        Initialize the PDF filler
        
        Args:
            organization_number: Organization number for the company
            fiscal_year: Fiscal year for the data
            rr_data: Pre-loaded RR data (optional, will fetch from DB if not provided)
            br_data: Pre-loaded BR data (optional, will fetch from DB if not provided)
            ink2_data: Pre-loaded INK2 data (optional, will fetch from DB if not provided)
        """
        self.organization_number = organization_number
        self.fiscal_year = fiscal_year
        self.form_mappings = []
        self.variable_values = {}
        
        # Store pre-loaded data or prepare to fetch from DB
        self.rr_data = rr_data or []
        self.br_data = br_data or []
        self.ink2_data = ink2_data or []
        
    def _load_form_mappings(self):
        """Load form field mappings from ink2_form table"""
        try:
            response = supabase.table('ink2_form').select('*').order('Id').execute()
            self.form_mappings = response.data
            print(f"✅ Loaded {len(self.form_mappings)} form field mappings")
        except Exception as e:
            print(f"❌ Error loading form mappings: {e}")
            raise
    
    def _fetch_variable_value(self, variable_name: str) -> Optional[float]:
        """
        Fetch the value of a variable from pre-loaded data
        Checks RR, BR, and INK2 data
        
        Args:
            variable_name: Name of the variable to fetch
            
        Returns:
            The value as a float, or None if not found
        """
        # Try to get from cached values first
        if variable_name in self.variable_values:
            return self.variable_values[variable_name]
        
        # Search in RR data
        for item in self.rr_data:
            if item.get('variable_name') == variable_name:
                value = item.get('current_amount')
                if value is not None:
                    try:
                        float_value = float(value)
                        self.variable_values[variable_name] = float_value
                        return float_value
                    except (ValueError, TypeError):
                        pass
        
        # Search in BR data
        for item in self.br_data:
            if item.get('variable_name') == variable_name:
                value = item.get('current_amount')
                if value is not None:
                    try:
                        float_value = float(value)
                        self.variable_values[variable_name] = float_value
                        return float_value
                    except (ValueError, TypeError):
                        pass
        
        # Search in INK2 data
        for item in self.ink2_data:
            if item.get('variable_name') == variable_name:
                value = item.get('amount')
                if value is not None:
                    try:
                        float_value = float(value)
                        self.variable_values[variable_name] = float_value
                        return float_value
                    except (ValueError, TypeError):
                        pass
        
        print(f"⚠️  Variable {variable_name} not found in any data")
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


def generate_filled_ink2_pdf(organization_number: str, fiscal_year: int, company_data: Dict[str, Any]) -> bytes:
    """
    Main function to generate a filled INK2 PDF
    
    Args:
        organization_number: Company organization number
        fiscal_year: Fiscal year for the data
        company_data: Dictionary with company information including rr_data, br_data, ink2_data
        
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
    
    # Extract data from company_data
    rr_data = company_data.get('seFileData', {}).get('rr_data', [])
    br_data = company_data.get('seFileData', {}).get('br_data', [])
    ink2_data = company_data.get('seFileData', {}).get('ink2_data', []) or company_data.get('ink2Data', [])
    
    print(f"📊 INK2 PDF Filler - RR items: {len(rr_data)}, BR items: {len(br_data)}, INK2 items: {len(ink2_data)}")
    
    # Create filler and fill the form
    filler = INK2PdfFiller(organization_number, fiscal_year, rr_data, br_data, ink2_data)
    filled_pdf = filler.fill_pdf_form(pdf_template_path, company_data)
    
    return filled_pdf

