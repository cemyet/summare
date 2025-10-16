"""
INK2 PDF Form Filler Service
Populates the INK2_form.pdf with data from the database based on ink2_form table mappings
"""

import os
import re
from typing import Dict, Any, Optional, List, Tuple
from io import BytesIO
from PyPDF2 import PdfReader, PdfWriter
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime

try:
    import fitz  # PyMuPDF for flattening
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False
    print("⚠️  PyMuPDF not available, PDF flattening will be skipped")

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

# Regex to strip Acrobat suffixes like #0, #1, [0], [1]
SUFFIX_RE = re.compile(r"(#\d+|\[\d+\])$")


def to_pdf_field_name(form_field: str) -> str:
    """
    Convert logical names from ink2_form table to actual /T names in INK2_form.pdf.
    
    Page 1 (Balance sheet): '2.17' -> '2.17' (unchanged)
    Page 2 (Income statement): '3.2' -> '2:', '3.23(+)' -> '23(+):'
    Page 3 (Tax adjustments): '4.6d' -> '6d:', '4.23a' -> '23a'
    
    Args:
        form_field: Logical field name from database (e.g., '3.12(+)', '4.6d')
        
    Returns:
        Actual PDF widget name
    """
    s = (form_field or "").strip()
    s = SUFFIX_RE.sub("", s)  # Strip any #0 or [0] suffixes
    
    # Page 2: Income statement fields (3.x) -> remove '3.' prefix, add ':'
    if s.startswith("3."):
        rest = s[2:]  # '2', '23(+)', '12(-)'
        return f"{rest}:"
    
    # Page 3: Tax adjustment fields (4.x) -> remove '4.' prefix, add ':'
    if s.startswith("4."):
        rest = s[2:]  # '6d', '23a', '15'
        # Checkbox fields (23a, 23b, 24a, 24b) don't have colon
        if rest in ['23a', '23b', '24a', '24b']:
            return rest
        return f"{rest}:"
    
    # Page 1: Balance sheet fields (2.x), special fields (date, org_nr, etc.)
    return s


def format_number_swedish(value: float) -> str:
    """
    Format number with Swedish conventions: space for thousands, no decimals
    Examples: 1234567 -> '1 234 567', 0 -> '0'
    """
    if value == 0:
        return '0'
    
    # Format with thousands separator
    return f"{int(round(value)):,}".replace(",", " ")


def build_widget_index(reader: PdfReader) -> Dict[str, List[Tuple[int, Any]]]:
    """
    Build an index of all form widgets in the PDF by their /T (field name).
    
    Returns:
        Dictionary mapping field names to list of (page_index, widget_object) tuples
    """
    by_name = {}
    for page_idx, page in enumerate(reader.pages):
        annots = page.get("/Annots", None)
        if not annots:
            continue
        
        # Resolve indirect object if needed
        if hasattr(annots, 'get_object'):
            annots = annots.get_object()
        
        # Now annots should be a list/array
        if not isinstance(annots, (list, tuple)):
            print(f"⚠️  Unexpected annots type on page {page_idx}: {type(annots)}")
            continue
        
        for annot_ref in annots:
            try:
                obj = annot_ref.get_object()
                name = obj.get("/T")
                if not name:
                    continue
                by_name.setdefault(name, []).append((page_idx, obj))
            except Exception as e:
                print(f"⚠️  Error reading annotation on page {page_idx}: {e}")
                continue
    return by_name


def set_pdf_value(widget_index: Dict[str, List[Tuple[int, Any]]], pdf_name: str, value: str) -> bool:
    """
    Set the value of a PDF form field by updating its widget /V property.
    
    Args:
        widget_index: Widget index from build_widget_index
        pdf_name: PDF field name (e.g., '12(+):')
        value: Value to set
        
    Returns:
        True if field was found and updated, False otherwise
    """
    hits = widget_index.get(pdf_name, [])
    if not hits:
        return False
    
    for _, widget in hits:
        widget.update({"/V": value})
    
    return True


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
    
    def _format_value_for_field(self, value: Optional[float], field_type: str = None, form_field: str = None) -> str:
        """
        Format a value for insertion into a PDF form field
        
        Args:
            value: The numeric value
            field_type: Optional field type hint
            form_field: Field name for checkbox detection
            
        Returns:
            Formatted string
        """
        if value is None:
            return ''
        
        # Checkbox fields (4.23a, 4.23b, 4.24a, 4.24b) expect Yes/Off
        if form_field and any(form_field.endswith(x) for x in ['23a', '23b', '24a', '24b']):
            # These are checkbox fields
            return 'Yes' if value else 'Off'
        
        # Numeric fields: format with Swedish thousands separator (space)
        return format_number_swedish(value)
    
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
    
    
    def fill_pdf_form(self, pdf_path: str, company_data: Dict[str, Any]) -> bytes:
        """
        Fill the INK2 PDF form with data using robust widget-based approach
        
        Args:
            pdf_path: Path to the INK2_form.pdf template
            company_data: Dictionary with company information
            
        Returns:
            Bytes of the filled and flattened PDF
        """
        # Load form mappings
        self._load_form_mappings()
        
        # Get special values
        special_values = self._get_special_values(company_data)
        
        # Read the PDF and build widget index
        reader = PdfReader(pdf_path)
        widget_index = build_widget_index(reader)
        
        print(f"📄 PDF has {len(widget_index)} unique form fields")
        
        # Create writer and copy pages
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        
        # Carry AcroForm and set NeedAppearances
        if "/Root" in reader.trailer and reader.trailer["/Root"].get("/AcroForm"):
            acro = reader.trailer["/Root"].get("/AcroForm").get_object()
            acro.update({"/NeedAppearances": True})
            writer._root_object.update({"/AcroForm": acro})
        
        # Prepare assignments (logical name -> value)
        assignments = {}
        filled_count = 0
        not_found_count = 0
        
        for mapping in self.form_mappings:
            form_field_raw = mapping.get('form_field')
            variable_map = mapping.get('variable_map')
            field_type = mapping.get('type')
            
            if not form_field_raw or not variable_map:
                continue
            
            # Check if this is a special value
            if variable_map in special_values:
                assignments[form_field_raw] = special_values[variable_map]
                continue
            
            # Parse the variable mapping
            value = self._parse_variable_mapping(variable_map)
            
            if value is not None:
                formatted_value = self._format_value_for_field(value, field_type, form_field_raw)
                assignments[form_field_raw] = formatted_value
        
        # Set values using widget index
        for logical_name, text_value in assignments.items():
            # Convert logical name to PDF field name
            pdf_name = to_pdf_field_name(logical_name)
            
            # Set the value
            ok = set_pdf_value(widget_index, pdf_name, str(text_value))
            
            if ok:
                filled_count += 1
                print(f"✅ {logical_name} → {pdf_name} = {text_value}")
            else:
                not_found_count += 1
                print(f"⚠️  Field '{logical_name}' → '{pdf_name}' not found in PDF")
        
        # Write to bytes
        output = BytesIO()
        writer.write(output)
        raw_pdf = output.getvalue()
        
        # Flatten with PyMuPDF if available
        if HAS_PYMUPDF:
            try:
                doc = fitz.open(stream=raw_pdf, filetype="pdf")
                for page in doc:
                    page.flatten_annots()
                flattened = doc.write()
                doc.close()
                print(f"✅ PDF form filled successfully: {filled_count} fields set, {not_found_count} not found, flattened")
                return flattened
            except Exception as e:
                print(f"⚠️  Could not flatten PDF: {e}")
                print(f"✅ PDF form filled successfully: {filled_count} fields set, {not_found_count} not found (not flattened)")
                return raw_pdf
        else:
            print(f"✅ PDF form filled successfully: {filled_count} fields set, {not_found_count} not found (not flattened)")
            return raw_pdf


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

