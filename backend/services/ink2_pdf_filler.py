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

# --- Normalization helpers ---
def _norm(s: str) -> str:
    """Normalize variable name for case-insensitive lookup"""
    if not s:
        return ""
    s = s.strip().replace(" ", "").replace("-", "_")
    return re.sub(r"\u00A0", " ", s).lower()

def _sv_num(x):
    """Accept numbers or Swedish formatted strings like '205 253'"""
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().replace("\u00A0", " ").replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except:
        return None

def build_override_map(company_data: dict) -> dict:
    """Freshest values from the UI across INK2, RR, BR, Noter, FB.
    
    Priority order (later overwrites earlier):
    1. seFileData.ink2_data (original baseline)
    2. ink2Data (latest calculated values including INK4.15, INK4.16)
    3. acceptedInk2Manuals (user manual edits - HIGHEST PRIORITY)
    """
    M: dict = {}

    # 1) INK2 current values from seFileData (original baseline)
    for row in (company_data.get("seFileData") or {}).get("ink2_data", []) or []:
        k, v = row.get("variable_name"), _sv_num(row.get("amount"))
        if k and v is not None:
            M[_norm(k)] = v
    
    # 2) INK2 top-level ink2Data (latest calculated values including INK4.15, INK4.16)
    # This has higher priority than seFileData.ink2_data
    for row in (company_data.get("ink2Data") or []):
        k, v = row.get("variable_name"), _sv_num(row.get("amount"))
        if k and v is not None:
            M[_norm(k)] = v

    # 3) Manual overrides made by the user inside INK2 (HIGHEST PRIORITY - applied last)
    accepted_manuals = company_data.get("acceptedInk2Manuals") or {}
    print(f"🔍 DEBUG acceptedInk2Manuals keys: {list(accepted_manuals.keys())}")
    for k, v in accepted_manuals.items():
        val = _sv_num(v)
        if val is not None:
            M[_norm(k)] = val
            if 'INK4.23' in k or 'INK4.24' in k:
                print(f"🔍 DEBUG Radio button in override map: {k}={val}")

    # 3) RR/BR current values (affects many sums used by INK2)
    se = (company_data.get("seFileData") or {})
    for row in se.get("rr_data", []) or []:
        k, v = row.get("variable_name"), _sv_num(row.get("current_amount"))
        if k and v is not None:
            M[_norm(k)] = v
    for row in se.get("br_data", []) or []:
        k, v = row.get("variable_name"), _sv_num(row.get("current_amount"))
        if k and v is not None:
            M[_norm(k)] = v

    # 4) Noter + FB variables (frequently feed tax/ink2)
    for row in (company_data.get("noterData") or []):
        k, v = row.get("variable_name"), _sv_num(row.get("current_amount"))
        if k and v is not None:
            M[_norm(k)] = v
    for k, v in (company_data.get("fbVariables") or {}).items():
        vv = _sv_num(v)
        if vv is not None:
            M[_norm(k)] = vv

    # 5) Misc tax singletons sometimes used in mappings
    for k in ["inkBeraknadSkatt", "inkBokfordSkatt", "pensionPremier",
              "sarskildLoneskattPension", "sarskildLoneskattPensionCalculated",
              "unusedTaxLossAmount", "justeringSarskildLoneskatt"]:
        if k in company_data:
            v = _sv_num(company_data[k])
            if v is not None:
                M[_norm(k)] = v
    
    # 6) Map chat-injected values to their INK2 variable names
    # unusedTaxLossAmount -> INK4.14a
    # IMPORTANT: Only map if INK4.14a doesn't have a manual override in acceptedInk2Manuals
    accepted_manuals = company_data.get("acceptedInk2Manuals") or {}
    ink4_14a_has_manual = "INK4.14a" in accepted_manuals or "ink4.14a" in accepted_manuals
    
    if "unusedTaxLossAmount" in company_data and not ink4_14a_has_manual:
        v = _sv_num(company_data["unusedTaxLossAmount"])
        if v is not None:
            M[_norm("INK4.14a")] = v
            print(f"✅ Mapped unusedTaxLossAmount to INK4.14a: {v} (no manual override)")
    elif ink4_14a_has_manual:
        print(f"ℹ️ Skipping unusedTaxLossAmount mapping - INK4.14a has manual override in acceptedInk2Manuals")

    return M

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
    # Meta fields
    "organization_number": ["org_nr", "orgnr", "organisationsnummer", "orgNumber", "PersOrgNr"],
    "start_date": ["fiscal_year_start", "period_from", "from_date"],
    "end_date": ["fiscal_year_end", "period_to", "to_date"],
    
    # Tax aliases
    "INK4.9(+)": ["ink4_9_plus", "aterforing_periodiseringsfond_current_year"],
    "INK4.10(-)": ["ink4_10_minus", "avsattning_periodiseringsfond_current_year"],
    "INK4.13(+)": ["ink4_13_plus"],
    "INK4.13(-)": ["ink4_13_minus"],
}


def get_meta_value(company_data: Dict[str, Any], key: str) -> str:
    """
    Get a meta value from company_data with alias fallback.
    Checks multiple locations: top-level, seFileData.company_info, and aliases.
    
    Args:
        company_data: Company data dictionary
        key: Key to look up
        
    Returns:
        Value or empty string
    """
    # Try exact key first at top level (handles both camelCase and snake_case)
    if key in company_data and company_data[key]:
        return str(company_data[key])
    
    # Try nested seFileData.company_info
    se_data = company_data.get('seFileData', {})
    company_info = se_data.get('company_info', {})
    if key in company_info and company_info[key]:
        return str(company_info[key])
    
    # Try aliases at top level first
    for alias in ALIASES.get(key, []):
        if alias in company_data and company_data[alias]:
            return str(company_data[alias])
    
    # Try aliases in nested company_info
    for alias in ALIASES.get(key, []):
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


class VarResolver:
    """Universal variable resolver that prefers client overrides, then DB values."""
    
    def __init__(self, rr_data: List[Dict], br_data: List[Dict], ink2_data: List[Dict], company_data: Dict):
        """
        Args:
            rr_data: Pre-loaded RR data from DB
            br_data: Pre-loaded BR data from DB
            ink2_data: Pre-loaded INK2 data from DB
            company_data: Live company data from client (for overrides)
        """
        self.rr_data = rr_data
        self.br_data = br_data
        self.ink2_data = ink2_data
        self.ov = build_override_map(company_data)  # freshest stuff from UI
        self.cache = {}
        
    def get(self, name: str) -> Optional[float]:
        """
        Get variable value with override-first precedence.
        
        Args:
            name: Variable name
            
        Returns:
            Value as float or None
        """
        # Check cache first
        if name in self.cache:
            return self.cache[name]
        
        # 1) UI override map (freshest)
        key = _norm(name)
        if key in self.ov:
            val = self.ov[key]
            self.cache[name] = val
            return val
        
        for alt in ALIASES.get(name, []):
            k2 = _norm(alt)
            if k2 in self.ov:
                val = self.ov[k2]
                self.cache[name] = val
                return val
        
        # 2) DB fallback (last stored in RR/BR/INK2)
        names_to_try = [name] + ALIASES.get(name, [])
        
        for n in names_to_try:
            # Search in RR data
            for item in self.rr_data:
                if item.get('variable_name') == n:
                    value = item.get('current_amount')
                    if value is not None:
                        try:
                            float_value = float(value)
                            self.cache[name] = float_value
                            return float_value
                        except (ValueError, TypeError):
                            pass
            
            # Search in BR data
            for item in self.br_data:
                if item.get('variable_name') == n:
                    value = item.get('current_amount')
                    if value is not None:
                        try:
                            float_value = float(value)
                            self.cache[name] = float_value
                            return float_value
                        except (ValueError, TypeError):
                            pass
            
            # Search in INK2 data
            for item in self.ink2_data:
                if item.get('variable_name') == n:
                    value = item.get('amount')
                    if value is not None:
                        try:
                            float_value = float(value)
                            self.cache[name] = float_value
                            return float_value
                        except (ValueError, TypeError):
                            pass
        
        return None


def eval_mapping(expr: str, R: VarResolver) -> Optional[float]:
    """
    Evaluate a variable mapping expression with conditional support.
    Supports: A + B + INK4.9(+)
              X (IF>0)   Y (IF<0)   (conditions only when there's a space before '(')
    
    Args:
        expr: Expression to evaluate
        R: VarResolver instance
        
    Returns:
        Computed value or None
    """
    parts = split_top_level_plus(expr)
    if not parts:
        return None
    
    total, seen = 0.0, False
    for piece in parts:
        m = COND_RE.match(piece)
        if m:
            name, cond = m.group("name").strip(), m.group("cond").upper()
            v = R.get(name)
            if v is None:
                continue
            if cond in ("IF>0", "IF>=0") and v > 0:
                total += v
                seen = True
            elif cond in ("IF<0", "IF<=0") and v < 0:
                total += abs(v)
                seen = True
        else:
            v = R.get(piece.strip())  # keeps INK4.9(+) intact
            if v is None:
                continue
            total += v
            seen = True
    
    return total if seen else None


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


def fill_ink2_with_pymupdf(pdf_bytes: bytes, assignments: Dict[str, str], company_data: Dict[str, Any] = None) -> bytes:
    """
    Fill INK2 PDF form using PyMuPDF (generates appearance streams + flattens).
    
    Args:
        pdf_bytes: Template PDF bytes
        assignments: Dict mapping logical names ('2.17', '3.12(+)', etc.) to values
        company_data: Optional company data for extracting org number
        
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
    
    # Extract organization number variants if company_data provided
    if company_data:
        import re
        ci = (company_data.get("seFileData") or {}).get("company_info") or {}
        raw_org = ci.get("organization_number") or company_data.get("organizationNumber") or ""
        digits = re.sub(r"\D", "", str(raw_org))  # '5566103643'
        dashed = f"{digits[:6]}-{digits[6:]}" if len(digits) == 10 else raw_org
        
        # Add org number to assignments under all common aliases (use dashed format)
        org_specials = {
            "org_nr": dashed,
            "org_nr#0": dashed,
            "organization_number": dashed,
            "organisationsnummer": dashed,
            "orgnr": dashed,
            "PersOrgNr": dashed,
            "PersOrgNr#0": dashed,
        }
        
        # Write org number specials directly
        print(f"🔍 Writing org number: digits={digits}, dashed={dashed}")
        for logical_name, value in org_specials.items():
            if not value:
                continue
            pdf_name = to_pdf_field_name(logical_name, style)
            key = normalize_field_name(pdf_name)
            hits = widgets_by_name.get(key, [])
            print(f"🔍 org debug: {logical_name} → {pdf_name} → '{key}' → hits: {len(hits)}")
            for page, widget in hits:
                try:
                    widget.field_value = str(value)
                    widget.update()
                    print(f"✅ org_nr → {logical_name} = {value}")
                except Exception as e:
                    print(f"⚠️  Error setting org {logical_name}: {e}")
        
        # Safety net: auto-probe any field with "org" in name and set to dashed format
        if dashed:
            print(f"🔍 Safety net: Probing all fields containing 'org'...")
            org_count = 0
            for key, widgets in widgets_by_name.items():
                if "org" in key:
                    for page, widget in widgets:
                        try:
                            widget.field_value = dashed
                            widget.update()
                            org_count += 1
                            print(f"✅ Safety net: {key} = {dashed}")
                        except Exception as e:
                            print(f"⚠️  Safety net error on {key}: {e}")
            print(f"🔍 Safety net wrote org number to {org_count} fields")
    
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
    
    def __init__(self, organization_number: str, fiscal_year: int, rr_data: List[Dict] = None, br_data: List[Dict] = None, ink2_data: List[Dict] = None, company_data: Dict = None):
        """
        Initialize the PDF filler
        
        Args:
            organization_number: Organization number for the company
            fiscal_year: Fiscal year for the data
            rr_data: Pre-loaded RR data (optional, will fetch from DB if not provided)
            br_data: Pre-loaded BR data (optional, will fetch from DB if not provided)
            ink2_data: Pre-loaded INK2 data (optional, will fetch from DB if not provided)
            company_data: Live company data from client (overrides DB values)
        """
        self.organization_number = organization_number
        self.fiscal_year = fiscal_year
        self.form_mappings = []
        self.company_data = company_data or {}
        
        # Create universal resolver (override-first, then DB)
        self.resolver = VarResolver(
            rr_data or [],
            br_data or [],
            ink2_data or [],
            self.company_data
        )
        
        # Log a sample of overrides for validation
        if self.resolver.ov:
            sample = {k: self.resolver.ov[k] for k in list(self.resolver.ov.keys())[:8]}
            print(f"🔎 OVERRIDE SAMPLE: {sample}")
        else:
            print("⚠️  No overrides found in company_data")
        
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
        Fetch the value of a variable using the universal resolver.
        Precedence: client overrides > DB values
        
        Args:
            variable_name: Name of the variable to fetch
            
        Returns:
            The value as a float, or None if not found
        """
        return self.resolver.get(variable_name)
    
    def _parse_variable_mapping(self, mapping: str) -> Optional[float]:
        """
        Parse a variable mapping and return the computed value using universal resolver.
        Uses eval_mapping with override-first lookup.
        
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
        
        return eval_mapping(mapping.strip(), self.resolver)
    
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
        
        # Rule: Don't inject 0 values - leave field empty instead
        if value == 0:
            return ''
        
        # IMPORTANT: All values in INK2 form should be positive (absolute values)
        # The form itself handles signs with +/- indicators
        value = abs(value)
        
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
        
        # Debug: Show top-level keys in company_data
        print(f"🔍 DEBUG: company_data keys: {list(company_data.keys())}")
        if 'seFileData' in company_data:
            se_data = company_data['seFileData']
            print(f"🔍 DEBUG: seFileData keys: {list(se_data.keys())}")
            if 'company_info' in se_data:
                company_info = se_data['company_info']
                print(f"🔍 DEBUG: company_info keys: {list(company_info.keys())}")
                print(f"🔍 DEBUG: company_info values: {company_info}")
        
        # Current date and time for framställning
        now = datetime.now()
        special_values['DatFramst'] = now.strftime('%Y-%m-%d')  # YYYY-MM-DD format
        special_values['TidFramst'] = now.strftime('%H:%M:%S')  # HH:MM:SS format
        special_values['date'] = now.strftime('%Y-%m-%d')  # YYYY-MM-DD format
        
        # System info
        system_info = get_meta_value(company_data, 'system_info')
        if not system_info:
            system_info = get_meta_value(company_data, 'SystemInfo')
        if not system_info:
            system_info = 'Summare AI - Årsredovisningssystem'
        special_values['SystemInfo'] = system_info
        special_values['system_info'] = system_info
        
        # Organization number with alias fallback (multiple lookup attempts)
        # Try snake_case first
        org_nr = get_meta_value(company_data, 'organization_number')
        print(f"🔍 DEBUG: get_meta_value('organization_number') = {org_nr}")
        
        # Try camelCase (frontend format)
        if not org_nr:
            org_nr = get_meta_value(company_data, 'organizationNumber')
            print(f"🔍 DEBUG: get_meta_value('organizationNumber') = {org_nr}")
        
        # Try other variants
        if not org_nr:
            org_nr = get_meta_value(company_data, 'org_nr')
            print(f"🔍 DEBUG: get_meta_value('org_nr') = {org_nr}")
        if not org_nr:
            org_nr = get_meta_value(company_data, 'PersOrgNr')
            print(f"🔍 DEBUG: get_meta_value('PersOrgNr') = {org_nr}")
        
        # Fallback to constructor parameter
        if not org_nr and self.organization_number:
            org_nr = self.organization_number
            print(f"🔍 DEBUG: Using self.organization_number = {org_nr}")
        
        if org_nr:
            # Format with dash (556610-3643) for display in PDF
            import re
            org_digits = re.sub(r"\D", "", str(org_nr))
            org_formatted = f"{org_digits[:6]}-{org_digits[6:]}" if len(org_digits) == 10 else str(org_nr)
            
            special_values['organization_number'] = org_formatted
            special_values['org_nr'] = org_formatted
            special_values['PersOrgNr'] = org_formatted
            special_values['orgnr'] = org_formatted
            special_values['organisationsnummer'] = org_formatted
            print(f"✅ Organization number set: {org_formatted}")
        else:
            print("❌ Organization number not found in company_data or self.organization_number")
        
        # Fiscal year dates with alias fallback - convert YYYYMMDD to YYYY-MM-DD
        start = get_meta_value(company_data, 'start_date')
        if start:
            # Convert YYYYMMDD to YYYY-MM-DD format
            start_str = str(start)
            if len(start_str) == 8 and start_str.isdigit():
                start_formatted = f"{start_str[:4]}-{start_str[4:6]}-{start_str[6:8]}"
            else:
                start_formatted = start_str  # Already formatted or invalid
            special_values['start_date'] = start_formatted
            special_values['fiscal_year_start'] = start_formatted
            print(f"✅ Start date set: {start_formatted}")
        
        end = get_meta_value(company_data, 'end_date')
        if end:
            # Convert YYYYMMDD to YYYY-MM-DD format
            end_str = str(end)
            if len(end_str) == 8 and end_str.isdigit():
                end_formatted = f"{end_str[:4]}-{end_str[4:6]}-{end_str[6:8]}"
            else:
                end_formatted = end_str  # Already formatted or invalid
            special_values['end_date'] = end_formatted
            special_values['fiscal_year_end'] = end_formatted
            print(f"✅ End date set: {end_formatted}")
        
        print(f"📋 Special values created: {list(special_values.keys())}")
        
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
        
        # Create case-insensitive lookup for special values
        special_values_lower = {k.lower(): v for k, v in special_values.items()}
        
        # Prepare assignments (logical name -> value)
        assignments = {}
        
        for mapping in self.form_mappings:
            form_field_raw = mapping.get('form_field')
            variable_map = mapping.get('variable_map')
            field_type = mapping.get('type')
            
            if not form_field_raw or not variable_map:
                continue
            
            # Check if this is a special value (exact match first)
            if variable_map in special_values:
                assignments[form_field_raw] = special_values[variable_map]
                print(f"✅ Special value: {form_field_raw} = {variable_map} = {special_values[variable_map]}")
                continue
            
            # Check case-insensitive
            variable_map_lower = variable_map.lower()
            if variable_map_lower in special_values_lower:
                assignments[form_field_raw] = special_values_lower[variable_map_lower]
                print(f"✅ Special value (case-insensitive): {form_field_raw} = {variable_map} = {special_values_lower[variable_map_lower]}")
                continue
            
            # Check if any alias of this variable_map exists in special_values
            found_in_special = False
            for alias in ALIASES.get(variable_map, []):
                if alias in special_values:
                    assignments[form_field_raw] = special_values[alias]
                    print(f"✅ Special value (via alias): {form_field_raw} = {variable_map} → {alias} = {special_values[alias]}")
                    found_in_special = True
                    break
                elif alias.lower() in special_values_lower:
                    assignments[form_field_raw] = special_values_lower[alias.lower()]
                    print(f"✅ Special value (via alias, case-insensitive): {form_field_raw} = {variable_map} → {alias} = {special_values_lower[alias.lower()]}")
                    found_in_special = True
                    break
            
            if found_in_special:
                continue
            
            # Parse the variable mapping (looks in RR/BR/INK2 data)
            value = self._parse_variable_mapping(variable_map)
            
            if value is not None:
                formatted_value = self._format_value_for_field(value, field_type, form_field_raw)
                if formatted_value:  # Only assign non-empty values
                    assignments[form_field_raw] = formatted_value
        
        # OVERRIDE: 4.3a should always equal Skatt på årets resultat from RR (row 277)
        # This is the calculated tax that should be reported
        skatt_arets_resultat = self.resolver.get('SkattAretsResultat')
        if skatt_arets_resultat is not None:
            # Skatt på årets resultat is stored as negative in RR, but we want positive in form
            formatted_skatt = self._format_value_for_field(skatt_arets_resultat, 'number', '4.3a')
            if formatted_skatt:
                assignments['4.3a'] = formatted_skatt
                print(f"✅ OVERRIDE: 4.3a (Skatt på årets resultat) = {formatted_skatt} (from RR SkattAretsResultat)")
        
        # SPECIAL HANDLING: INK4.23a/23b radio buttons (Uppdragstagare)
        # When Ja selected: INK4.23a=1, INK4.23b=0 → PDF: 23a=Yes, 23b=Off
        # When Nej selected: INK4.23a=0, INK4.23b=1 → PDF: 23a=Off, 23b=Yes
        ink4_23a_value = self.resolver.get('INK4.23a')
        ink4_23b_value = self.resolver.get('INK4.23b')
        
        print(f"🔍 DEBUG INK4.23a/b values: 23a={ink4_23a_value}, 23b={ink4_23b_value}")
        
        if ink4_23a_value == 1:
            # Ja selected
            assignments['23a'] = 'Yes'
            assignments['23b'] = 'Off'
            print(f"✅ INK4.23a/b radio: Ja selected (INK4.23a=1, INK4.23b=0 → 23a=Yes, 23b=Off)")
        elif ink4_23b_value == 1:
            # Nej selected
            assignments['23a'] = 'Off'
            assignments['23b'] = 'Yes'
            print(f"✅ INK4.23a/b radio: Nej selected (INK4.23a=0, INK4.23b=1 → 23a=Off, 23b=Yes)")
        else:
            # Default to "Nej" (23b checked)
            assignments['23a'] = 'Off'
            assignments['23b'] = 'Yes'
            print(f"✅ INK4.23a/b radio: Default to Nej (23a=Off, 23b=Yes)")
        
        # SPECIAL HANDLING: INK4.24a/24b radio buttons (Revision)
        # When Ja selected: INK4.24a=1, INK4.24b=0 → PDF: 24a=Yes, 24b=Off
        # When Nej selected: INK4.24a=0, INK4.24b=1 → PDF: 24a=Off, 24b=Yes
        ink4_24a_value = self.resolver.get('INK4.24a')
        ink4_24b_value = self.resolver.get('INK4.24b')
        
        print(f"🔍 DEBUG INK4.24a/b values: 24a={ink4_24a_value}, 24b={ink4_24b_value}")
        
        if ink4_24a_value == 1:
            # Ja selected
            assignments['24a'] = 'Yes'
            assignments['24b'] = 'Off'
            print(f"✅ INK4.24a/b radio: Ja selected (INK4.24a=1, INK4.24b=0 → 24a=Yes, 24b=Off)")
        elif ink4_24b_value == 1:
            # Nej selected
            assignments['24a'] = 'Off'
            assignments['24b'] = 'Yes'
            print(f"✅ INK4.24a/b radio: Nej selected (INK4.24a=0, INK4.24b=1 → 24a=Off, 24b=Yes)")
        else:
            # Default to "Nej" (24b checked)
            assignments['24a'] = 'Off'
            assignments['24b'] = 'Yes'
            print(f"✅ INK4.24a/b radio: Default to Nej (24a=Off, 24b=Yes)")
        
        # Load template PDF
        with open(pdf_path, 'rb') as f:
            template_bytes = f.read()
        
        # Fill using PyMuPDF (generates appearance streams + flattens)
        filled_pdf = fill_ink2_with_pymupdf(template_bytes, assignments, company_data)
        
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
    # IMPORTANT: Try ink2Data first (has latest manual edits), then fall back to seFileData.ink2_data
    ink2_data = company_data.get('ink2Data') or company_data.get('seFileData', {}).get('ink2_data', [])
    
    print(f"📊 INK2 PDF Filler - RR items: {len(rr_data)}, BR items: {len(br_data)}, INK2 items: {len(ink2_data)}")
    print(f"📊 INK2 data source: {'ink2Data (with manual edits)' if company_data.get('ink2Data') else 'seFileData.ink2_data (original)'}")
    
    # Create filler and fill the form (pass company_data for overrides)
    filler = INK2PdfFiller(organization_number, fiscal_year, rr_data, br_data, ink2_data, company_data)
    filled_pdf = filler.fill_pdf_form(pdf_template_path, company_data)
    
    return filled_pdf

