"""
INK2 PDF Form Filler Service
Populates the INK2_form.pdf with data from the database based on ink2_form table mappings
"""

import os
import re
from typing import Dict, Any, Optional, List, Tuple
from io import BytesIO
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.generic import TextStringObject, NameObject, BooleanObject
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

# Regex for conditional expressions (space before parenthesis required)
COND_RE = re.compile(r"^\s*(?P<name>.+?)\s+\((?P<cond>IF[<>]=?0|IF[<>]0)\)\s*$", re.I)

# Variable name aliases for DB lookup
ALIASES = {
    # Meta fields (expanded with more variants)
    "organization_number": ["org_nr", "orgnr", "PersOrgNr", "orgNumber", "organisationsnummer"],
    "start_date": ["fiscal_year_start", "period_from", "from_date", "startDate"],
    "end_date": ["fiscal_year_end", "period_to", "to_date", "endDate"],
    "DatFramst": ["date", "framstallningsdatum", "current_date"],
    "TidFramst": ["time", "framstallningstid", "current_time"],
    "SystemInfo": ["system_info"],
    
    # Periodiseringsfonder (both ways for compatibility)
    "aterforing_periodiseringsfond_current_year": ["INK4.9(+)", "ink4_9_plus"],
    "avsattning_periodiseringsfond_current_year": ["INK4.10(-)", "ink4_10_minus"],
    "INK4.9(+)": ["aterforing_periodiseringsfond_current_year", "ink4_9_plus"],
    "INK4.10(-)": ["avsattning_periodiseringsfond_current_year", "ink4_10_minus"],
    
    # Överavskrivningar
    "INK4.13(+)": ["aterforing_overavskrivningar_current_year", "ink4_13_plus"],
    "INK4.13(-)": ["avsattning_overavskrivningar_current_year", "ink4_13_minus"],
}


def get_meta_value(company_data: Dict[str, Any], key: str) -> str:
    """
    Get a meta value from company_data with alias fallback.
    
    Args:
        company_data: Company data dictionary
        key: Key to look up
        
    Returns:
        Value or empty string
    """
    # Try exact key first
    if key in company_data and company_data[key]:
        return str(company_data[key])
    
    # Try nested seFileData
    se_data = company_data.get('seFileData', {})
    company_info = se_data.get('company_info', {})
    if key in company_info and company_info[key]:
        return str(company_info[key])
    
    # Try aliases
    for alias in ALIASES.get(key, []):
        if alias in company_data and company_data[alias]:
            return str(company_data[alias])
        if alias in company_info and company_info[alias]:
            return str(company_info[alias])
    
    return ""


def split_top_level_plus(expr: str) -> List[str]:
    """
    Split expression on '+' but only at top level (not inside parentheses).
    This keeps variable names like INK4.9(+) intact.
    
    Args:
        expr: Expression to split (e.g., "A+B", "INK4.9(+)+INK4.10(-)")
        
    Returns:
        List of parts
    """
    parts, buf, depth = [], [], 0
    for ch in expr or "":
        if ch == "(":
            depth += 1
            buf.append(ch)
        elif ch == ")":
            depth = max(0, depth - 1)
            buf.append(ch)
        elif ch == "+" and depth == 0:
            # Top-level plus - split here
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    
    if buf:
        parts.append("".join(buf).strip())
    
    return [p for p in parts if p]


def detect_name_style(widget_names: set) -> str:
    """
    Detect the naming style used by the PDF form.
    
    Args:
        widget_names: Set of raw field names from the PDF
        
    Returns:
        'prefixed' if names like '2.1', '3.12(+)' are used
        'colon' if names like '1:', '12(+):' are used
        'raw' otherwise
    """
    # If we see names like '2.1', '3.12(+)', etc., use them as-is
    if any(n.startswith("2.") or n.startswith("3.") or n.startswith("4.") for n in widget_names):
        return "prefixed"
    # If we see '12:' / '12(+):' style, use colon mapping
    if any(n.endswith(":") for n in widget_names):
        return "colon"
    return "raw"


def to_pdf_field_name(form_field: str, style: str = "prefixed") -> str:
    """
    Convert logical names from ink2_form table to actual /T names in INK2_form.pdf.
    Adapts based on the detected PDF naming style.
    
    Args:
        form_field: Logical field name from database (e.g., '2.17', '3.12(+)', '4.6d')
        style: Naming style ('prefixed', 'colon', or 'raw')
        
    Returns:
        Actual PDF widget name
    """
    s = (form_field or "").strip()
    s = SUFFIX_RE.sub("", s)  # Strip any #0 or [0] suffixes
    
    if style == "prefixed":
        # Keep '2.17', '3.12(+)', '4.6d' exactly as-is
        return s
    
    if style == "colon":
        # Map to colon style: '2.17' -> '17:', '3.12(+)' -> '12(+):'
        if s.startswith(("2.", "3.", "4.")):
            rest = s[2:]
            # Checkboxes on p.4 have plain names like 23a/23b (no colon)
            if rest in {"23a", "23b", "24a", "24b"}:
                return rest
            return f"{rest}:"
    
    # raw style: return as-is
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


def normalize_field_name(name: str) -> str:
    """Normalize field name for case-insensitive matching (strip #0, trailing :)"""
    s = SUFFIX_RE.sub("", (name or "").strip())
    s = s.rstrip(":")
    return s.lower()


def fill_ink2_with_pymupdf(pdf_bytes: bytes, assignments: Dict[str, str]) -> bytes:
    """
    Fill INK2 PDF form using PyMuPDF (generates appearance streams + flattens).
    
    Args:
        pdf_bytes: Template PDF bytes
        assignments: Dict mapping logical names ('2.17', '3.12(+)', etc.) to values
        
    Returns:
        Filled and flattened PDF bytes
    """
    if not HAS_PYMUPDF:
        raise RuntimeError("PyMuPDF is required for INK2 PDF filling")
    
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    # Build set of raw field names to detect the naming style
    raw_names = set()
    widgets_by_name = {}
    
    for page in doc:
        for widget in page.widgets():
            # PyMuPDF exposes widget.field_name (widget /T) and widget.field_label (parent /T)
            raw = widget.field_name or widget.field_label or ""
            if not raw:
                continue
            
            raw_names.add(raw.strip())
            
            # Create key variants (with/without trailing colon, #0 suffix)
            # Normalize handles #0 and : removal
            base = normalize_field_name(raw)
            key_variants = {
                base,
                normalize_field_name(raw + ":"),
                normalize_field_name(raw[:-1] if raw.endswith(":") else raw),
            }
            
            for key in key_variants:
                widgets_by_name.setdefault(key, []).append((page, widget))
    
    # Detect naming style from raw field names
    style = detect_name_style(raw_names)
    print(f"📄 PyMuPDF found {len(widgets_by_name)} unique form fields, style: {style}")
    
    # Debug: show first 30 field names
    sample_keys = sorted(list(widgets_by_name.keys()))[:30]
    print(f"📋 Sample field names in index: {sample_keys}")
    
    # Assign all values
    filled_count = 0
    not_found_count = 0
    
    for logical_name, value in assignments.items():
        # Convert logical name to PDF field name using detected style
        pdf_name = to_pdf_field_name(logical_name, style)
        normalized = normalize_field_name(pdf_name)
        hits = widgets_by_name.get(normalized, [])
        
        # Debug first few lookups
        if filled_count + not_found_count < 5:
            print(f"🔍 DEBUG: {logical_name} → {pdf_name} → normalized: '{normalized}' → hits: {len(hits)}")
        
        # Special-case the four checkboxes on page 4
        is_checkbox = pdf_name in ("23a", "23b", "24a", "24b")
        
        if not hits:
            not_found_count += 1
            print(f"⚠️  {logical_name} → {pdf_name} not found")
            continue
        
        for page, widget in hits:
            try:
                if is_checkbox:
                    # Set checkbox state
                    widget.button_set(bool(value in (True, 1, "Yes", "/Yes", "On")))
                else:
                    # Set text value; PyMuPDF will create the appearance stream
                    widget.field_value = str(value)
                
                widget.update()  # Force appearance generation for this widget
                # NOTE: page.reload() removed - doesn't exist in this PyMuPDF version
                
            except Exception as e:
                print(f"⚠️  Error setting {logical_name}: {e}")
                continue
        
        filled_count += 1
        print(f"✅ {logical_name} → {pdf_name} = {value}")
    
    # Flatten so values are baked into page content for any viewer
    flat_doc = fitz.open("pdf", doc.convert_to_pdf())
    out_bytes = flat_doc.write()
    flat_doc.close()
    doc.close()
    
    print(f"✅ PDF form filled with PyMuPDF: {filled_count} fields set, {not_found_count} not found, flattened")
    return out_bytes


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
        Fetch the value of a variable from pre-loaded data with alias resolution.
        Checks RR, BR, and INK2 data
        
        Args:
            variable_name: Name of the variable to fetch
            
        Returns:
            The value as a float, or None if not found
        """
        # Try to get from cached values first
        if variable_name in self.variable_values:
            return self.variable_values[variable_name]
        
        # Try exact name first, then aliases
        names_to_try = [variable_name] + ALIASES.get(variable_name, [])
        
        for name in names_to_try:
            # Search in RR data
            for item in self.rr_data:
                if item.get('variable_name') == name:
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
                if item.get('variable_name') == name:
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
                if item.get('variable_name') == name:
                    value = item.get('amount')
                    if value is not None:
                        try:
                            float_value = float(value)
                            self.variable_values[variable_name] = float_value
                            return float_value
                        except (ValueError, TypeError):
                            pass
        
        # Not found even with aliases
        if len(names_to_try) > 1:
            print(f"⚠️  Variable {variable_name} (tried aliases: {names_to_try[1:]}) not found in any data")
        else:
            print(f"⚠️  Variable {variable_name} not found in any data")
        return None
    
    def _parse_variable_mapping(self, mapping: str) -> Optional[float]:
        """
        Parse a variable mapping and return the computed value.
        Uses parenthesis-aware splitting to preserve names like INK4.9(+).
        
        Handles:
        - Single variable: "Nettoomsattning" or "INK4.10(-)"
        - Sum of variables: "MaskinerAndraTekniskaAnlagg+InventarierVerktyg+OvrMatAnlTillgangar"
        - Conditional: "ForandringLager (IF>0)" or "ForandringLager (IF<0)" (space before parenthesis)
        
        Args:
            mapping: The variable mapping string from variable_map column
            
        Returns:
            Computed value or None
        """
        if not mapping or mapping.strip() == '':
            return None
        
        mapping = mapping.strip()
        
        # Parse into tokens (handles conditionals and sums)
        # Split on top-level '+' only (preserves INK4.9(+) as single token)
        parts = split_top_level_plus(mapping)
        
        if len(parts) == 0:
            return None
        
        # If multiple parts, it's a sum
        if len(parts) > 1:
            total = 0.0
            found_any = False
            
            for part in parts:
                value = self._parse_single_token(part)
                if value is not None:
                    total += value
                    found_any = True
            
            return total if found_any else None
        
        # Single token (may have condition)
        return self._parse_single_token(parts[0])
    
    def _parse_single_token(self, token: str) -> Optional[float]:
        """
        Parse a single token (variable name with optional condition).
        
        Args:
            token: Single token like "Nettoomsattning", "INK4.9(+)", or "ForandringLager (IF>0)"
            
        Returns:
            Computed value or None
        """
        # Check for conditional (IF>0) or (IF<0) - ONLY if there's whitespace before '('
        match = COND_RE.match(token)
        if match:
            variable_name = match.group("name").strip()
            condition = match.group("cond").upper()
            
            # Get the value
            value = self._fetch_variable_value(variable_name)
            
            if value is None:
                return None
            
            # Apply condition
            if condition in ("IF>0", "IF>=0") and value > 0:
                return value
            elif condition in ("IF<0", "IF<=0") and value < 0:
                return abs(value)  # Return absolute value for negative display
            else:
                return None  # Condition not met
        
        # No condition - just fetch the variable (including names with (+) or (-))
        return self._fetch_variable_value(token)
    
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
        Uses get_meta_value for robust lookup with aliases.
        
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
        special_values['date'] = now.strftime('%Y-%m-%d')
        
        # System info
        special_values['SystemInfo'] = 'Summare AI - Årsredovisningssystem'
        
        # Organization number with alias fallback
        org_nr = get_meta_value(company_data, 'organization_number')
        if not org_nr and self.organization_number:
            org_nr = self.organization_number
        if org_nr:
            special_values['organization_number'] = org_nr.replace('-', '')
            special_values['org_nr'] = org_nr.replace('-', '')
            special_values['PersOrgNr'] = org_nr.replace('-', '')
        
        # Fiscal year dates with alias fallback
        start = get_meta_value(company_data, 'start_date')
        if start:
            special_values['start_date'] = start
            special_values['fiscal_year_start'] = start
        
        end = get_meta_value(company_data, 'end_date')
        if end:
            special_values['end_date'] = end
            special_values['fiscal_year_end'] = end
        
        return special_values
    
    
    def fill_pdf_form(self, pdf_path: str, company_data: Dict[str, Any]) -> bytes:
        """
        Fill the INK2 PDF form with data using PyMuPDF (generates appearance streams)
        
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
        
        # Prepare assignments (logical name -> value)
        assignments = {}
        
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
        
        # Load template PDF
        with open(pdf_path, 'rb') as f:
            template_bytes = f.read()
        
        # Fill using PyMuPDF (generates appearance streams + flattens)
        filled_pdf = fill_ink2_with_pymupdf(template_bytes, assignments)
        
        return filled_pdf


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

