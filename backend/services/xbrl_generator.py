"""
XBRL Instance Document Generator
Generates XBRL instance documents for Swedish financial reporting
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import Dict, List, Any, Optional
from datetime import datetime
import uuid


class XBRLGenerator:
    """Generate XBRL instance documents from parsed financial data"""
    
    # XBRL namespaces (updated to match Bolagsverket iXBRL standard)
    NAMESPACES = {
        'iso4217': 'http://www.xbrl.org/2003/iso4217',
        'ixt': 'http://www.xbrl.org/inlineXBRL/transformation/2010-04-20',
        'xlink': 'http://www.w3.org/1999/xlink',
        'link': 'http://www.xbrl.org/2003/linkbase',
        'xbrli': 'http://www.xbrl.org/2003/instance',
        'ix': 'http://www.xbrl.org/2013/inlineXBRL',
        'se-gen-base': 'http://www.taxonomier.se/se/fr/gen-base/2021-10-31',
        'se-cd-base': 'http://www.taxonomier.se/se/fr/cd-base/2021-10-31',
        'se-bol-base': 'http://www.bolagsverket.se/se/fr/comp-base/2020-12-01',
        'se-misc-base': 'http://www.taxonomier.se/se/fr/misc-base/2017-09-30',
        'se-gaap-ext': 'http://www.taxonomier.se/se/fr/gaap/gaap-ext/2021-10-31',
        'se-mem-base': 'http://www.taxonomier.se/se/fr/mem-base/2021-10-31',
        'se-k2-type': 'http://www.taxonomier.se/se/fr/k2/datatype',
    }
    
    # Note number to note ID pattern mapping for note references
    # Maps note number -> (from_id, to_id_pattern)
    NOTE_REFERENCE_MAPPING = {
        '2': {
            'from_id': 'personalkostnader-rr',
            'to_id_pattern': 'notmedelantaletanstallda-ref-id1',
            'label': 'Medelantalet anställda'
        },
        '3': {
            'from_id': 'byggnadermark-br',
            'to_id_pattern': 'notbyggnadermark-ref',
            'label': 'Byggnader och mark'
        },
        '4': {
            'from_id': 'maskinerandratekniskaanlaggningar-br',
            'to_id_pattern': 'notmaskinerandratekniskaanlaggningar-ref',
            'label': 'Maskiner och andra tekniska anläggningar'
        },
        '5': {
            'from_id': 'inventarierverktyginstallationer-br',
            'to_id_pattern': 'notinventarierverktyginstallationer-ref',
            'label': 'Inventarier, verktyg och installationer'
        },
    }
    
    def __init__(self):
        self.contexts = {}
        self.units = {}
        self.facts = []
        self.context_counter = 0
        self.unit_counter = 0
        self.note_references = []  # Track note references for tuple generation
    
    def _get_namespace_prefix(self, namespace: str) -> str:
        """Get namespace prefix from full namespace URL"""
        namespace_map = {
            'se-gen-base': 'se-gen-base',
            'se-cd-base': 'se-cd-base',
            'se-gaap-ext': 'se-gaap-ext',
            'se-mem-base': 'se-mem-base',
        }
        return namespace_map.get(namespace, 'se-gen-base')
    
    def _get_or_create_context(self, period_type: str, start_date: Optional[str] = None, 
                               end_date: Optional[str] = None, instant_date: Optional[str] = None,
                               is_current: bool = True, context_id: Optional[str] = None) -> str:
        """Get or create a context ID for the given period with semantic naming
        
        Args:
            period_type: 'duration' or 'instant'
            start_date: Start date for duration contexts
            end_date: End date for duration contexts
            instant_date: Instant date for instant contexts
            is_current: True for current year (period0/balans0), False for previous (period1/balans1)
            context_id: Optional manual context ID (e.g., 'period2', 'balans2')
        """
        if period_type == 'duration':
            key = f"duration_{start_date}_{end_date}"
            # Use semantic IDs: period0 for current year, period1 for previous (rule 2.16.5)
            if not context_id:
                context_id = "period0" if is_current else "period1"
        else:
            key = f"instant_{instant_date}"
            # Use semantic IDs: balans0 for current year end, balans1 for previous (rule 2.16.7)
            if not context_id:
                context_id = "balans0" if is_current else "balans1"
        
        if key not in self.contexts:
            self.contexts[key] = {
                'id': context_id,
                'period_type': period_type,
                'start_date': start_date,
                'end_date': end_date,
                'instant_date': instant_date
            }
        return self.contexts[key]['id']
    
    def _get_or_create_unit(self, unit_type: str = 'SEK') -> str:
        """Get or create a unit ID for the given type
        
        Args:
            unit_type: 'SEK' for currency, 'procent' for percentages, etc.
        """
        # Use semantic IDs per Bolagsverket pattern
        if unit_type == 'SEK':
            unit_id = 'SEK'
        elif unit_type == 'procent':
            unit_id = 'procent'
        else:
            unit_id = unit_type
        
        if unit_id not in self.units:
            self.units[unit_id] = {
                'id': unit_id,
                'type': unit_type
            }
        return unit_id
    
    def _format_date(self, date_str: str) -> str:
        """Format date string to XBRL format (YYYY-MM-DD)"""
        if not date_str:
            return None
        # Handle various date formats
        if len(date_str) == 8 and date_str.isdigit():
            # YYYYMMDD format
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        # Try to parse other formats
        try:
            dt = datetime.strptime(date_str, '%Y-%m-%d')
            return dt.strftime('%Y-%m-%d')
        except:
            return date_str
    
    def _format_monetary_value(self, value: Optional[float], for_display: bool = False) -> str:
        """Format monetary value for XBRL or display"""
        if value is None:
            return "0"
        if for_display:
            # Format with thousand separators (space), NO decimals for HTML display
            # Match PDF format: "1 936 366" not "1 936 365,77"
            return f"{int(round(value)):,}".replace(',', ' ')
        # XBRL uses string representation of numbers (integers)
        return str(int(round(value)))
    
    def _format_decimal_value(self, value: Optional[float], decimals: int = 2) -> str:
        """Format decimal value for XBRL"""
        if value is None:
            return "0"
        return f"{value:.{decimals}f}"
    
    def add_fact(self, element_name: str, namespace: str, value: Any, 
                 period_type: str, start_date: Optional[str] = None,
                 end_date: Optional[str] = None, instant_date: Optional[str] = None,
                 data_type: str = 'monetaryItemType', unit_ref: Optional[str] = None,
                 context_ref: Optional[str] = None, is_current: bool = True,
                 decimals: Optional[str] = None, in_thousands: bool = False):
        """Add a fact to the XBRL document"""
        # Get or create context
        if not context_ref:
            context_ref = self._get_or_create_context(period_type, start_date, end_date, instant_date, is_current)
        
        # Get or create unit (only for monetary items)
        if not unit_ref and data_type == 'monetaryItemType':
            unit_ref = self._get_or_create_unit('SEK')
        elif data_type != 'monetaryItemType':
            unit_ref = None  # No unit for non-monetary items
        
        # Determine decimals for monetary items
        if decimals is None and data_type == 'monetaryItemType':
            # Default: "-3" for thousands (Tkr), "0" for full amounts (kr)
            decimals = "-3" if in_thousands else "0"
        
        # Format value based on data type
        if data_type == 'monetaryItemType':
            formatted_value = self._format_monetary_value(value)
        elif data_type in ['decimalItemType', 'pureItemType']:
            formatted_value = self._format_decimal_value(value)
        elif data_type == 'dateItemType':
            formatted_value = self._format_date(str(value)) if value else None
        else:
            formatted_value = str(value) if value else ""
        
        if formatted_value is None or formatted_value == "":
            return  # Skip empty facts
        
        fact = {
            'element_name': element_name,
            'namespace': namespace,
            'value': formatted_value,
            'context_ref': context_ref,
            'unit_ref': unit_ref,
            'data_type': data_type,
            'decimals': decimals  # Add decimals to fact storage
        }
        self.facts.append(fact)
    
    def generate_xbrl_document(self, company_data: Dict[str, Any]) -> str:
        """Generate complete Inline XBRL (iXBRL) document as XHTML"""
        # Extract company info
        company_info = company_data.get('seFileData', {}).get('company_info', {})
        fiscal_year = company_data.get('fiscal_year') or company_info.get('fiscal_year')
        start_date = company_info.get('start_date')
        end_date = company_info.get('end_date')
        
        # Format dates
        if start_date:
            start_date = self._format_date(start_date)
        if end_date:
            end_date = self._format_date(end_date)
        
        # Pre-create all contexts (period0-3, balans0-3) per Bolagsverket pattern
        # This ensures all contexts are defined in ix:resources
        if fiscal_year and start_date and end_date:
            # Period 0 (current year)
            self._get_or_create_context('duration', start_date, end_date, is_current=True, context_id='period0')
            self._get_or_create_context('instant', instant_date=end_date, is_current=True, context_id='balans0')
            
            # Period 1 (previous year)
            prev_year = fiscal_year - 1
            period1_start = f"{prev_year}-01-01"
            period1_end = f"{prev_year}-12-31"
            self._get_or_create_context('duration', period1_start, period1_end, is_current=False, context_id='period1')
            self._get_or_create_context('instant', instant_date=period1_end, is_current=False, context_id='balans1')
            
            # Period 2 (two years ago)
            prev_year_2 = fiscal_year - 2
            period2_start = f"{prev_year_2}-01-01"
            period2_end = f"{prev_year_2}-12-31"
            self._get_or_create_context('duration', period2_start, period2_end, is_current=False, context_id='period2')
            self._get_or_create_context('instant', instant_date=period2_end, is_current=False, context_id='balans2')
            
            # Period 3 (three years ago)
            prev_year_3 = fiscal_year - 3
            period3_start = f"{prev_year_3}-01-01"
            period3_end = f"{prev_year_3}-12-31"
            self._get_or_create_context('duration', period3_start, period3_end, is_current=False, context_id='period3')
            self._get_or_create_context('instant', instant_date=period3_end, is_current=False, context_id='balans3')
        
        # Pre-create units (SEK, procent, antal-anstallda) per Bolagsverket pattern
        self._get_or_create_unit('SEK')
        self._get_or_create_unit('procent')
        self._get_or_create_unit('antal-anstallda')
        
        # Create root HTML element for Inline XBRL
        root = ET.Element('html')
        root.set('xmlns', 'http://www.w3.org/1999/xhtml')
        
        # Add all namespace declarations
        for prefix, uri in self.NAMESPACES.items():
            root.set(f'xmlns:{prefix}', uri)
        
        # Create head element
        head = ET.SubElement(root, 'head')
        
        # Charset MUST be first meta
        meta_charset = ET.SubElement(head, 'meta')
        meta_charset.set('charset', 'UTF-8')
        
        # Add meta tags
        meta_program = ET.SubElement(head, 'meta')
        meta_program.set('name', 'programvara')
        meta_program.set('content', 'Summare')
        
        meta_version = ET.SubElement(head, 'meta')
        meta_version.set('name', 'programversion')
        meta_version.set('content', '1.0')
        
        # Roboto web font to match PDF typography
        font_link = ET.SubElement(head, 'link')
        font_link.set('rel', 'stylesheet')
        font_link.set('href', 'https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap')
        
        # Add title
        company_name = (company_data.get('company_name') 
                       or company_data.get('companyName')
                       or company_info.get('company_name')
                       or 'Bolag')
        org_number = (company_data.get('organization_number')
                     or company_data.get('organizationNumber')
                     or company_info.get('organization_number')
                     or '')
        title_text = f"{org_number} {company_name} - Årsredovisning"
        title = ET.SubElement(head, 'title')
        title.text = title_text
        
        # Add CSS styles (defined in _get_css_styles)
        style = ET.SubElement(head, 'style')
        style.set('type', 'text/css')
        style.text = self._get_css_styles()
        
        # Create body element
        body = ET.SubElement(root, 'body')
        
        # Create hidden div for iXBRL content (Bolagsverket pattern)
        hidden_div = ET.SubElement(body, 'div')
        hidden_div.set('style', 'display:none')
        
        # <ix:header> encloses hidden facts, references and resources
        ix_header = ET.SubElement(hidden_div, 'ix:header')
        
        # ix:hidden – non-visible facts (document metadata, duplicates, etc.)
        ix_hidden = ET.SubElement(ix_header, 'ix:hidden')
        
        # ix:references – schemaRef to K2 AB RISBS 2024 taxonomy
        ix_references = ET.SubElement(ix_header, 'ix:references')
        schema_ref = ET.SubElement(ix_references, 'link:schemaRef')
        schema_ref.set('xlink:type', 'simple')
        schema_ref.set(
            'xlink:href',
            'http://www.taxonomier.se/se/fr/gaap/k2-all/ab/risbs/2024-09-12/se-k2-ab-risbs-2024-09-12.xsd'
        )
        
        # ix:resources – contexts and units live here in Inline XBRL
        ix_resources = ET.SubElement(ix_header, 'ix:resources')
        
        # NOTE: RR/BR/FB/Noter financial data will be tagged INLINE in presentation
        # Only document metadata goes in hidden section
        
        # Add general info metadata facts
        self._add_general_info_facts(company_data, start_date, end_date)
        
        # Process Signature info
        self._add_signature_facts(company_data, end_date)
        
        # ------------------------------------------------------------------
        # Contexts and units: must be children of <ix:resources>
        # ------------------------------------------------------------------
        org_number_clean = (company_info.get('organization_number', '') or
                           company_data.get('organization_number', '') or
                           company_data.get('organizationNumber', '')).replace('-', '')
        
        # Add all contexts to ix:resources
        for context_key, context_info in self.contexts.items():
            context_element = ET.SubElement(ix_resources, 'xbrli:context')
            context_element.set('id', context_info['id'])
            
            entity = ET.SubElement(context_element, 'xbrli:entity')
            identifier = ET.SubElement(entity, 'xbrli:identifier')
            identifier.set('scheme', 'http://www.bolagsverket.se/se/organisationsnummer')
            identifier.text = org_number_clean
            
            period = ET.SubElement(context_element, 'xbrli:period')
            if context_info['period_type'] == 'duration':
                start_elem = ET.SubElement(period, 'xbrli:startDate')
                start_elem.text = context_info['start_date']
                end_elem = ET.SubElement(period, 'xbrli:endDate')
                end_elem.text = context_info['end_date']
            else:
                instant_elem = ET.SubElement(period, 'xbrli:instant')
                instant_elem.text = context_info['instant_date']
        
        # Add units to ix:resources (matching Bolagsverket example)
        for unit_id, unit_info in self.units.items():
            unit_element = ET.SubElement(ix_resources, 'xbrli:unit')
            unit_element.set('id', unit_id)
            measure = ET.SubElement(unit_element, 'xbrli:measure')
            
            # Different measure formats for different unit types
            unit_type = unit_info.get('type', unit_id)
            if unit_type == 'SEK':
                measure.text = 'iso4217:SEK'
            elif unit_type == 'procent':
                measure.text = 'xbrli:pure'
            elif unit_type == 'antal-anstallda':
                measure.text = 'se-k2-type:AntalAnstallda'
            else:
                # Generic format
                measure.text = f'xbrli:{unit_type}'
        
        # ------------------------------------------------------------------
        # Hidden facts in ix:hidden (metadata, enums, duplicates)
        # ------------------------------------------------------------------
        # NOTE: we no longer generate a custom <ixt:transform> element here.
        # Bolagsverket's examples rely on the standard inline XBRL
        # transformation registry, so we just use the "format" attribute on
        # ix:nonFraction facts (e.g. format="ixt:numdotdecimal").
        
        # Add required metadata tags first (Swedish XBRL requirements)
        period0_ref = 'period0'
        
        # Language
        meta_lang = ET.SubElement(ix_hidden, 'ix:nonNumeric')
        meta_lang.set('name', 'se-cd-base:SprakHandlingUpprattadList')
        meta_lang.set('contextRef', period0_ref)
        meta_lang.text = 'se-mem-base:SprakSvenskaMember'
        
        # Country
        meta_country = ET.SubElement(ix_hidden, 'ix:nonNumeric')
        meta_country.set('name', 'se-cd-base:LandForetagetsSateList')
        meta_country.set('contextRef', period0_ref)
        meta_country.text = 'se-mem-base:LandSverigeMember'
        
        # Currency
        meta_currency = ET.SubElement(ix_hidden, 'ix:nonNumeric')
        meta_currency.set('name', 'se-cd-base:RedovisningsvalutaHandlingList')
        meta_currency.set('contextRef', period0_ref)
        meta_currency.text = 'se-mem-base:ValutaSvenskaKronorMember'
        
        # Amount format (normal form, not thousands)
        meta_format = ET.SubElement(ix_hidden, 'ix:nonNumeric')
        meta_format.set('name', 'se-cd-base:BeloppsformatList')
        meta_format.set('contextRef', period0_ref)
        meta_format.text = 'se-mem-base:BeloppsformatNormalformMember'
        
        # Financial report type
        meta_report = ET.SubElement(ix_hidden, 'ix:nonNumeric')
        meta_report.set('name', 'se-gen-base:FinansiellRapportList')
        meta_report.set('contextRef', period0_ref)
        meta_report.text = 'se-mem-base:FinansiellRapportStyrelsenVerkstallandeDirektorenAvgerArsredovisningMember'
        
        # Fiscal year first day
        meta_start = ET.SubElement(ix_hidden, 'ix:nonNumeric')
        meta_start.set('name', 'se-cd-base:RakenskapsarForstaDag')
        meta_start.set('contextRef', period0_ref)
        meta_start.text = start_date
        
        # Fiscal year last day
        meta_end = ET.SubElement(ix_hidden, 'ix:nonNumeric')
        meta_end.set('name', 'se-cd-base:RakenskapsarSistaDag')
        meta_end.set('contextRef', period0_ref)
        meta_end.text = end_date
        
        # Organization number
        meta_org = ET.SubElement(ix_hidden, 'ix:nonNumeric')
        meta_org.set('name', 'se-cd-base:Organisationsnummer')
        meta_org.set('contextRef', period0_ref)
        meta_org.text = company_data.get('organization_number', '') or company_data.get('organizationNumber', '') or org_number
        
        # NOTE: All monetary and display facts are now tagged INLINE in presentation
        # No hidden monetary facts needed
        
        # ------------------------------------------------------------------
        # Generate visible HTML content matching PDF structure
        # ------------------------------------------------------------------
        self._generate_visible_content(body, company_data, start_date, end_date, fiscal_year)
        
        # ------------------------------------------------------------------
        # Generate note reference tuples (Notkoppling) in hidden section
        # ------------------------------------------------------------------
        self._generate_note_reference_tuples(ix_hidden)
        
        # Convert to pretty XML string with UTF-8 encoding
        rough_string = ET.tostring(root, encoding='unicode')
        reparsed = minidom.parseString(rough_string)
        # Generate XML with proper UTF-8 declaration
        xml_bytes = reparsed.toprettyxml(indent="  ", encoding='UTF-8')
        xml_string = xml_bytes.decode('UTF-8')
        
        # Format the opening <html> tag with proper line breaks and tabs
        # Replace the compact html opening tag with formatted version
        html_open_start = xml_string.find('<html')
        html_open_end = xml_string.find('>', html_open_start)
        
        if html_open_start != -1 and html_open_end != -1:
            # Build the properly formatted opening tag
            formatted_html_open = '''<html xmlns="http://www.w3.org/1999/xhtml" 
\txmlns:iso4217="http://www.xbrl.org/2003/iso4217" 
\txmlns:ixt="http://www.xbrl.org/inlineXBRL/transformation/2010-04-20" 
\txmlns:xlink="http://www.w3.org/1999/xlink" 
\txmlns:link="http://www.xbrl.org/2003/linkbase" 
\txmlns:xbrli="http://www.xbrl.org/2003/instance" 
\txmlns:ix="http://www.xbrl.org/2013/inlineXBRL" 
\txmlns:se-gen-base="http://www.taxonomier.se/se/fr/gen-base/2021-10-31"
\txmlns:se-cd-base="http://www.taxonomier.se/se/fr/cd-base/2021-10-31"
\txmlns:se-bol-base="http://www.bolagsverket.se/se/fr/comp-base/2020-12-01"
\txmlns:se-misc-base="http://www.taxonomier.se/se/fr/misc-base/2017-09-30"
\t  xmlns:se-gaap-ext="http://www.taxonomier.se/se/fr/gaap/gaap-ext/2021-10-31"
\t  xmlns:se-mem-base="http://www.taxonomier.se/se/fr/mem-base/2021-10-31"
\txmlns:se-k2-type="http://www.taxonomier.se/se/fr/k2/datatype">'''
            
            xml_string = xml_string[:html_open_start] + formatted_html_open + xml_string[html_open_end+1:]
        
        return xml_string
    
    def _get_css_styles(self) -> str:
        """Return CSS styles matching PDF generator"""
        return """
/* Base reset */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body {
  height: 100%;
  width: 100%;
}

body {
  font-family: "Roboto", Arial, sans-serif;
  font-size: 10pt;
  line-height: 1.2;
  color: #000000;
  background-color: #f5f5f5;
}

/* Page container */
@media screen {
  .ar-page0, .ar-page1, .ar-page2, .ar-page3, .ar-page4, 
  .ar-page5, .ar-page6, .ar-page7, .ar-page8 {
    width: 210mm;
    min-height: 297mm;
    margin: 10mm auto;
    padding: 54pt 68pt 68pt 68pt;
    background-color: #ffffff;
    box-shadow: 0 0 10px rgba(0,0,0,0.1);
  }
  
  .ar-page-noter {
    width: 210mm;
    min-height: 297mm;
    margin: 10mm auto;
    padding: 54pt 68pt 68pt 68pt;
    background-color: #ffffff;
    box-shadow: 0 0 10px rgba(0,0,0,0.1);
  }
}

@media print {
  @page {
    size: A4;
    margin: 0;
  }
  
  body {
    background-color: #ffffff;
    margin: 0;
    padding: 0;
  }
  
  .ar-page0, .ar-page1, .ar-page2, .ar-page3, .ar-page4,
  .ar-page5, .ar-page6, .ar-page7, .ar-page8 {
    width: 210mm;
    height: 297mm;
    margin: 0;
    padding: 54pt 68pt 68pt 68pt;
    box-shadow: none;
    page-break-after: always;
  }
  
  .ar-page8 {
    page-break-after: auto;
  }
  
  .ar-page-noter {
    width: 210mm;
    height: 297mm;
    margin: 0;
    padding: 54pt 68pt 68pt 68pt;
    box-shadow: none;
    page-break-after: always;
  }
  
  div[style*="page-break-inside: avoid"] {
    page-break-inside: avoid;
  }
  
  .H1 {
    page-break-after: avoid;
  }
  
  table {
    page-break-inside: auto;
  }
}

/* Typography */

        /* H0 - Main section titles */
        .H0 {
          font-family: "Roboto", Arial, sans-serif;
          font-weight: 500;
          font-size: 16pt;
          margin-top: 0pt;
          margin-bottom: 18pt;
          line-height: 1.2;
        }

/* H1 - Subsection headings */
.H1 {
  font-family: "Roboto", Arial, sans-serif;
  font-weight: 500;
  font-size: 12pt;
  margin-top: 18pt;
  margin-bottom: 0pt;
  line-height: 1.2;
}

/* H2 - Major headings */
.H2 {
  font-family: "Roboto", Arial, sans-serif;
  font-weight: 500;
  font-size: 15pt;
  margin-top: 18pt;
  margin-bottom: 0pt;
  line-height: 1.2;
}

        /* H2 in tables */
        .H2-table {
          font-family: "Roboto", Arial, sans-serif;
          font-weight: 500;
          font-size: 11pt;
          line-height: 1.2;
          margin-top: 0;
          margin-bottom: 0;
        }

        /* H3 in tables */
        .H3-table {
          font-family: "Roboto", Arial, sans-serif;
          font-weight: 500;
          font-size: 10pt;
          line-height: 1.2;
          margin-top: 0;
          margin-bottom: 0;
        }

        /* Body text */
        .P {
          font-family: "Roboto", Arial, sans-serif;
          font-weight: normal;
          font-size: 10pt;
          line-height: 12pt;
          margin-top: 0pt;
          margin-bottom: 0pt;
        }

/* Small text */
.SMALL {
  font-family: "Roboto", Arial, sans-serif;
  font-weight: normal;
  font-size: 8pt;
  margin-top: 0pt;
  margin-bottom: 0pt;
  line-height: 1.2;
}

/* Cover page styles */
.cover-center {
  text-align: center;
  font-size: 10pt;
  line-height: 1.2;
}

.cover-title {
  text-align: center;
  font-size: 24pt;
  font-weight: 500;
  line-height: 27.6pt;
}

.cover-subtitle {
  text-align: center;
  font-size: 16pt;
  font-weight: 500;
  line-height: 18.4pt;
}

.cover-label {
  text-align: center;
  font-size: 14pt;
  line-height: 1.2;
}

        /* Table styles */
        table {
          border-collapse: collapse;
          width: 100%;
          margin-top: 0pt;
          margin-bottom: 0pt;
        }

        td, th {
          vertical-align: top;
          padding: 0;
        }

        /* RR/BR table - header with underline */
        .table-header {
          border-collapse: collapse;
          width: 16.5cm;
          table-layout: fixed;
          border-bottom: 0.5pt solid rgba(0, 0, 0, 0.7);
          margin-bottom: 6pt;
        }

        /* RR/BR table - data rows */
        .table-data {
          border-collapse: collapse;
          width: 16.5cm;
          table-layout: fixed;
        }

        /* Header cells */
        .th-label {
          vertical-align: bottom;
          width: 9cm;
          padding-bottom: 4pt;
        }

        .th-note {
          vertical-align: bottom;
          width: 2cm;
          padding-bottom: 4pt;
          text-align: center;
        }

        .th-year {
          vertical-align: bottom;
          width: 2.5cm;
          padding-bottom: 4pt;
          text-align: right;
        }

        .th-spacing {
          vertical-align: bottom;
          width: 0.5cm;
          padding-bottom: 4pt;
        }

        /* Text with semibold for headers */
        .P-bold {
          font-family: "Roboto", Arial, sans-serif;
          font-weight: 500;
          font-size: 10pt;
          line-height: 12pt;
          margin-top: 0pt;
          margin-bottom: 0pt;
        }

        /* Amount columns */
        .amount-right {
          text-align: right;
          font-size: 10pt;
          font-weight: normal;
          margin-top: 0;
          margin-bottom: 0;
        }

        .amount-right-bold {
          text-align: right;
          font-size: 10pt;
          font-weight: 700;
          margin-top: 0;
          margin-bottom: 0;
        }

        .amount-center {
          text-align: center;
          font-size: 10pt;
          margin-top: 0;
          margin-bottom: 0;
        }

        /* Sum rows */
        .sum-label {
          font-family: "Roboto", Arial, sans-serif;
          font-weight: 500;
          font-size: 10pt;
          line-height: 1.2;
          margin-top: 0;
          margin-bottom: 0;
        }

        .sum-amount {
          text-align: right;
          font-family: "Roboto", Arial, sans-serif;
          font-weight: 500;
          font-size: 10pt;
          line-height: 1.2;
          margin-top: 0;
          margin-bottom: 0;
        }

        /* Utility classes */
        .text-center {
          text-align: center;
        }

        .text-right {
          text-align: right;
        }

        .text-left {
          text-align: left;
        }

        /* Header table styling */
        .header-underline {
          border-bottom: 0.5pt solid rgba(0, 0, 0, 0.7);
          padding-bottom: 6pt;
          margin-bottom: 6pt;
        }

        /* Table cell styles for RR/BR */
        .td-label {
          vertical-align: top;
          width: 9cm;
        }

        .td-label-colspan {
          vertical-align: top;
          /* No width - spans full table */
        }

        .td-note {
          vertical-align: top;
          width: 2cm;
          text-align: center;
        }

        .td-amount {
          vertical-align: top;
          width: 2.5cm;
          text-align: right;
        }

        .td-spacing {
          vertical-align: top;
          width: 0.5cm;
        }

        .td-label-indent {
          vertical-align: top;
          width: 9cm;
          padding-left: 12pt;
        }

        .td-label-sum {
          vertical-align: top;
          width: 9cm;
          font-weight: 500;
        }

        /* Padding utilities */
        .pt-2 {
          padding-top: 2pt;
        }

        .pt-8 {
          padding-top: 8pt;
        }

        .pt-18 {
          padding-top: 18pt;
        }

        .pb-10 {
          padding-bottom: 10pt;
        }

        .pb-12 {
          padding-bottom: 12pt;
        }

        .pt-8-pb-12 {
          padding-top: 8pt;
          padding-bottom: 12pt;
        }

        /* Border utilities */
        .border-top {
          border-top: 0.5pt solid rgba(0, 0, 0, 0.7);
        }

        .border-bottom {
          border-bottom: 0.5pt solid rgba(0, 0, 0, 0.7);
        }

        /* Noter table styles - Semantic approach */
        .noter-table {
          border-collapse: collapse;
          width: 15.1cm;
          table-layout: fixed;
          margin-top: 10pt;
        }

        .noter-table-depr {
          border-collapse: collapse;
          width: 12cm;
          margin-top: 10pt;
        }

        /* Main noter table cells */
        .noter-header-label {
          vertical-align: top;
          width: 9.5cm;
          padding-bottom: 4pt;
          border-bottom: 0.5pt solid rgba(0, 0, 0, 0.2);
        }

        .noter-header-amount {
          vertical-align: top;
          width: 2.8cm;
          text-align: right;
          padding-bottom: 4pt;
          border-bottom: 0.5pt solid rgba(0, 0, 0, 0.2);
        }

        .noter-data-label {
          vertical-align: top;
          width: 9.5cm;
          padding-top: 2pt;
        }

        .noter-data-amount {
          vertical-align: top;
          width: 2.8cm;
          text-align: right;
          padding-top: 2pt;
        }

        .noter-section-label {
          vertical-align: top;
          width: 9.5cm;
          padding-top: 10pt;
        }

        .noter-section-amount {
          vertical-align: top;
          width: 2.8cm;
          text-align: right;
          padding-top: 10pt;
        }

        /* Depreciation table cells */
        .noter-depr-header-label {
          vertical-align: top;
          width: 10cm;
          padding-bottom: 4pt;
          border-bottom: 0.5pt solid rgba(0, 0, 0, 0.2);
        }

        .noter-depr-header-amount {
          vertical-align: top;
          width: 2cm;
          text-align: right;
          padding-bottom: 4pt;
          border-bottom: 0.5pt solid rgba(0, 0, 0, 0.2);
        }

        .noter-depr-data-label {
          vertical-align: top;
          width: 10cm;
          padding-top: 2pt;
        }

        .noter-depr-data-amount {
          vertical-align: top;
          width: 2cm;
          text-align: right;
          padding-top: 2pt;
        }

        /* Text styles for noter */
        .noter-text {
          margin: 0;
        }

        .noter-text-bold {
          margin: 0;
          font-weight: 500;
        }

        .noter-text-header {
          margin: 0;
          font-size: 9pt;
          font-weight: 500;
        }

        .noter-text-paragraph {
          margin-top: 10pt;
        }

        /* Page break utilities */
        .pagebreak-before {
          page-break-before: always;
        }

        /* Note container styling */
        .note-container {
          page-break-inside: avoid;
          page-break-before: auto;
          margin-top: 32pt;
        }

        /* Margin utilities */
        .mt-0 {
          margin-top: 0pt;
        }

        .mt-10 {
          margin-top: 10pt;
        }

        /* FB (Förvaltningsberättelse) table styles */
        
        /* Flerårsöversikt table */
        .fb-flerars-table {
          border-collapse: collapse;
          width: 16cm;
          table-layout: fixed;
          margin-top: 6pt;
          margin-bottom: 27pt;
        }

        .fb-flerars-th-label {
          vertical-align: bottom;
          width: 7cm;
          padding-bottom: 4pt;
          border-bottom: 0.5pt solid rgba(0, 0, 0, 0.7);
        }

        .fb-flerars-th-year {
          vertical-align: bottom;
          width: 3cm;
          padding-bottom: 4pt;
          text-align: right;
          border-bottom: 0.5pt solid rgba(0, 0, 0, 0.7);
        }

        .fb-flerars-td-label {
          vertical-align: top;
          width: 7cm;
          padding-top: 2pt;
        }

        .fb-flerars-td-amount {
          vertical-align: top;
          width: 3cm;
          text-align: right;
          padding-top: 2pt;
        }

        /* Förändringar i eget kapital table */
        .fb-ek-table {
          border-collapse: collapse;
          width: 459.0pt;
          table-layout: fixed;
          margin-top: 6pt;
          margin-bottom: 27pt;
        }

        .fb-ek-th-label {
          vertical-align: bottom;
          width: 160pt;
          padding-bottom: 4pt;
          border-bottom: 0.5pt solid rgba(0, 0, 0, 0.7);
        }

        .fb-ek-th-col {
          vertical-align: bottom;
          width: 59.8pt;
          padding-bottom: 4pt;
          text-align: right;
          border-bottom: 0.5pt solid rgba(0, 0, 0, 0.7);
        }

        .fb-ek-td-label {
          vertical-align: top;
          width: 160pt;
          padding-top: 2pt;
        }

        .fb-ek-td-amount {
          vertical-align: top;
          width: 59.8pt;
          text-align: right;
          padding-top: 2pt;
        }

        /* Resultatdisposition table */
        .fb-resdisp-table {
          border-collapse: collapse;
          width: 300pt;
          table-layout: fixed;
          margin-top: 6pt;
          margin-bottom: 27pt;
        }

        .fb-resdisp-td-label {
          vertical-align: top;
          width: 150pt;
        }

        .fb-resdisp-td-amount {
          vertical-align: top;
          width: 150pt;
          text-align: right;
        }

        .fb-spacer-row {
          height: 10pt;
        }

        /* P text with margin reset (used in FB tables) */
        .P-no-margin {
          font-family: "Roboto", Arial, sans-serif;
          font-weight: normal;
          font-size: 10pt;
          line-height: 12pt;
          margin-top: 0;
          margin-bottom: 0;
        }

        .P-no-margin-bold {
          font-family: "Roboto", Arial, sans-serif;
          font-weight: 500;
          font-size: 10pt;
          line-height: 12pt;
          margin-top: 0;
          margin-bottom: 0;
        }

        /* FB section and cover page specific styles */
        .fb-ek-td-amount-bold {
          vertical-align: top;
          width: 59.8pt;
          text-align: right;
          padding-top: 2pt;
          font-weight: 500;
        }

        .fb-resdisp-td-amount-bold {
          vertical-align: top;
          width: 150pt;
          text-align: right;
          font-weight: 500;
        }

        .cover-title-spaced {
          text-align: center;
          font-size: 24pt;
          font-weight: 500;
          line-height: 27.6pt;
          margin-top: 0;
          margin-bottom: 4pt;
        }

        .cover-subtitle-spaced {
          text-align: center;
          font-size: 16pt;
          font-weight: 500;
          line-height: 18.4pt;
          margin-top: 0;
          margin-bottom: 4pt;
        }

        .cover-center-org {
          text-align: center;
          font-size: 10pt;
          line-height: 1.2;
          margin-top: 0;
          margin-bottom: 24pt;
          font-size: 16pt;
        }

        .cover-label-spaced {
          text-align: center;
          font-size: 14pt;
          line-height: 1.2;
          margin-top: 0;
          margin-bottom: 3pt;
        }

        .cover-center-dates {
          text-align: center;
          font-size: 14pt;
          line-height: 1.2;
          margin-top: 0;
          margin-bottom: 0;
        }

        .H0-spaced-bottom {
          font-family: "Roboto", Arial, sans-serif;
          font-weight: 500;
          font-size: 16pt;
          margin-top: 0pt;
          margin-bottom: 18pt;
          line-height: 1.2;
        }

        .H1-spaced-top {
          font-family: "Roboto", Arial, sans-serif;
          font-weight: 500;
          font-size: 12pt;
          margin-top: 18pt;
          margin-bottom: 0pt;
          line-height: 1.2;
        }

        .H1-no-margin-top {
          font-family: "Roboto", Arial, sans-serif;
          font-weight: 500;
          font-size: 12pt;
          margin-top: 0pt;
          margin-bottom: 0pt;
          line-height: 1.2;
        }

        .P-spaced-bottom {
          font-family: "Roboto", Arial, sans-serif;
          font-weight: normal;
          font-size: 10pt;
          line-height: 12pt;
          margin-top: 0pt;
          margin-bottom: 27pt;
        }
        """
    
    def _num(self, v):
        """Convert value to float, handling bools, None, empty strings"""
        try:
            if isinstance(v, bool): return 0.0
            if v is None or v == "": return 0.0
            if isinstance(v, (int, float)): return float(v)
            s = str(v).replace(" ", "").replace("\u00A0", "").replace(",", ".")
            return float(s) if s else 0.0
        except Exception:
            return 0.0
    
    def _create_inline_xbrl_element(self, parent: ET.Element, element_name: str, 
                                   value: float, context_ref: str, 
                                   is_negative_display: bool = False) -> ET.Element:
        """Create inline XBRL element with proper formatting (following Bolagsverket example)
        
        Args:
            parent: Parent ET.Element to attach to
            element_name: Qualified element name (e.g. 'se-gen-base:Nettoomsattning')
            value: Numeric value (will be formatted with space as thousands separator)
            context_ref: Context reference (e.g. 'period0', 'balans0')
            is_negative_display: If True and value is negative, prepend '-' before tag
        
        Returns:
            The created ix:nonFraction element
        """
        # Format value for display (space as thousands separator)
        formatted_value = self._format_monetary_value(abs(value), for_display=True)
        
        # If value is negative and displayed with minus sign, add it before the tag
        if is_negative_display and value < 0:
            if parent.text:
                parent.text += '-'
            else:
                parent.text = '-'
        
        # Create ix:nonFraction element
        ix_elem = ET.SubElement(parent, 'ix:nonFraction')
        ix_elem.set('contextRef', context_ref)
        ix_elem.set('name', element_name)
        ix_elem.set('unitRef', 'SEK')
        ix_elem.set('decimals', 'INF')
        ix_elem.set('scale', '0')
        ix_elem.set('format', 'ixt:numspacecomma')
        
        # Add sign attribute if value is negative and displayed with minus
        if is_negative_display and value < 0:
            ix_elem.set('sign', '-')
        
        # Set text to formatted value (always positive display value)
        ix_elem.text = formatted_value
        
        return ix_elem
    
    def _should_show_row(self, row: Dict[str, Any], data: List[Dict[str, Any]], section: str = 'rr') -> bool:
        """Apply show/hide logic matching PDF generation"""
        # Always show if always_show is True
        if row.get('always_show'):
            return True
        
        # Check if row has note_number (show even if zero)
        has_note = row.get('note_number') is not None and row.get('note_number') != ''
        if has_note:
            return True
        
        # Check if this is a heading or sum row
        label = row.get('label', '')
        style = row.get('style', '')
        is_heading = style in ['H0', 'H1', 'H2', 'H3', 'H4']
        is_sum = style in ['S1', 'S2', 'S3', 'S4'] or label.startswith('Summa ')
        
        # Headings and sums are shown if their block has content
        if is_heading or is_sum:
            block_group = row.get('block_group', '')
            if block_group:
                return self._block_has_content(block_group, data, section)
            return True
        
        # For data rows: show if has non-zero amounts
        curr = self._num(row.get('current_amount', 0))
        prev = self._num(row.get('previous_amount', 0))
        return curr != 0 or prev != 0
    
    def _block_has_content(self, block_group: str, data: List[Dict[str, Any]], section: str) -> bool:
        """Check if block group has any non-zero content"""
        if not block_group:
            return True
        
        for row in data:
            if row.get('block_group') != block_group:
                continue
            
            # Skip headings and sums
            label = row.get('label', '')
            style = row.get('style', '')
            is_heading = style in ['H0', 'H1', 'H2', 'H3', 'H4']
            is_sum = style in ['S1', 'S2', 'S3', 'S4'] or label.startswith('Summa ')
            
            if is_heading or is_sum:
                continue
            
            # Check if this row has non-zero amount or always_show
            if row.get('always_show'):
                return True
            curr = self._num(row.get('current_amount', 0))
            prev = self._num(row.get('previous_amount', 0))
            if curr != 0 or prev != 0:
                return True
        
        return False
    
    def _add_note_reference(self, note_number: str, from_id: str, to_id_pattern: str):
        """Add a note reference for tuple generation in hidden section
        
        Args:
            note_number: Note number (e.g., "2", "3", "4")
            from_id: ID of the element in financial statement (e.g., 'personalkostnader-rr')
            to_id_pattern: ID pattern of the note element (e.g., 'notmedelantaletanstallda-ref-id1')
        """
        self.note_references.append({
            'note_number': note_number,
            'from_id': from_id,
            'to_id_pattern': to_id_pattern
        })
    
    def _generate_note_reference_tuples(self, ix_hidden: ET.Element):
        """Generate note reference tuples (Notkoppling) per Bolagsverket pattern
        
        Creates tuples for both period0 and period1 for each note reference.
        """
        tuple_counter = 1
        for ref in self.note_references:
            note_num = ref['note_number']
            from_id = ref['from_id']
            to_id_pattern = ref['to_id_pattern']
            
            # Add comment for readability
            comment = ET.Comment(f" Notkoppling för not {note_num} ")
            ix_hidden.append(comment)
            
            # Period 0 (current year)
            tuple_id_0 = f"not-ref-tabell-id{tuple_counter}-ar-0"
            
            # Tuple declaration
            tuple_0 = ET.SubElement(ix_hidden, 'ix:tuple')
            tuple_0.set('name', 'se-misc-base:ReferensInstansDokumentTuple')
            tuple_0.set('tupleID', tuple_id_0)
            
            # Note number
            ref_namn_0 = ET.SubElement(ix_hidden, 'ix:nonNumeric')
            ref_namn_0.set('name', 'se-misc-base:ReferensInstansDokumentNamn')
            ref_namn_0.set('contextRef', 'period0')
            ref_namn_0.set('order', '1.0')
            ref_namn_0.set('tupleRef', tuple_id_0)
            ref_namn_0.text = note_num
            
            # From reference
            ref_fran_0 = ET.SubElement(ix_hidden, 'ix:nonNumeric')
            ref_fran_0.set('name', 'se-misc-base:ReferensInstansDokumentFran')
            ref_fran_0.set('contextRef', 'period0')
            ref_fran_0.set('order', '2.0')
            ref_fran_0.set('tupleRef', tuple_id_0)
            ref_fran_0.text = f"#xpointer(//*/*[@id='{from_id}-ar-0'])"
            
            # To reference
            ref_till_0 = ET.SubElement(ix_hidden, 'ix:nonNumeric')
            ref_till_0.set('name', 'se-misc-base:ReferensInstansDokumentTill')
            ref_till_0.set('contextRef', 'period0')
            ref_till_0.set('order', '3.0')
            ref_till_0.set('tupleRef', tuple_id_0)
            ref_till_0.text = f"#xpointer(//*/*[starts-with(@id,'{to_id_pattern}-ar-0')])"
            
            # Type
            ref_typ_0 = ET.SubElement(ix_hidden, 'ix:nonNumeric')
            ref_typ_0.set('name', 'se-misc-base:ReferensInstansDokumentTyp')
            ref_typ_0.set('contextRef', 'period0')
            ref_typ_0.set('order', '4.0')
            ref_typ_0.set('tupleRef', tuple_id_0)
            ref_typ_0.text = 'ANNUALREPORT_DISCLOSURE_REF'
            
            # Period 1 (previous year)
            tuple_id_1 = f"not-ref-tabell-id{tuple_counter}-ar-1"
            
            # Tuple declaration
            tuple_1 = ET.SubElement(ix_hidden, 'ix:tuple')
            tuple_1.set('name', 'se-misc-base:ReferensInstansDokumentTuple')
            tuple_1.set('tupleID', tuple_id_1)
            
            # Note number
            ref_namn_1 = ET.SubElement(ix_hidden, 'ix:nonNumeric')
            ref_namn_1.set('name', 'se-misc-base:ReferensInstansDokumentNamn')
            ref_namn_1.set('contextRef', 'period1')
            ref_namn_1.set('order', '1.0')
            ref_namn_1.set('tupleRef', tuple_id_1)
            ref_namn_1.text = note_num
            
            # From reference
            ref_fran_1 = ET.SubElement(ix_hidden, 'ix:nonNumeric')
            ref_fran_1.set('name', 'se-misc-base:ReferensInstansDokumentFran')
            ref_fran_1.set('contextRef', 'period1')
            ref_fran_1.set('order', '2.0')
            ref_fran_1.set('tupleRef', tuple_id_1)
            ref_fran_1.text = f"#xpointer(//*/*[@id='{from_id}-ar-1'])"
            
            # To reference
            ref_till_1 = ET.SubElement(ix_hidden, 'ix:nonNumeric')
            ref_till_1.set('name', 'se-misc-base:ReferensInstansDokumentTill')
            ref_till_1.set('contextRef', 'period1')
            ref_till_1.set('order', '3.0')
            ref_till_1.set('tupleRef', tuple_id_1)
            ref_till_1.text = f"#xpointer(//*/*[starts-with(@id,'{to_id_pattern}-ar-1')])"
            
            # Type
            ref_typ_1 = ET.SubElement(ix_hidden, 'ix:nonNumeric')
            ref_typ_1.set('name', 'se-misc-base:ReferensInstansDokumentTyp')
            ref_typ_1.set('contextRef', 'period1')
            ref_typ_1.set('order', '4.0')
            ref_typ_1.set('tupleRef', tuple_id_1)
            ref_typ_1.text = 'ANNUALREPORT_DISCLOSURE_REF'
            
            tuple_counter += 1
    
    def _get_context_refs(self, fiscal_year: int, period_type: str = 'duration') -> tuple:
        """Get contextRef IDs for current and previous year with semantic naming
        
        Per Bolagsverket rules:
        - Rule 2.16.5: Duration periods named "period0" (current), "period1" (previous)
        - Rule 2.16.7: Balance dates named "balans0" (current), "balans1" (previous)
        """
        if period_type == 'duration':
            return ('period0', 'period1')
        else:
            return ('balans0', 'balans1')
    
    def _generate_visible_content(self, body: ET.Element, company_data: Dict[str, Any], 
                                 start_date: Optional[str], end_date: Optional[str], fiscal_year: Optional[int]):
        """Generate visible HTML content matching PDF structure"""
        company_info = company_data.get('seFileData', {}).get('company_info', {})
        company_name = (company_data.get('company_name') 
                       or company_data.get('companyName')
                       or company_info.get('company_name')
                       or 'Bolag')
        org_number = (company_data.get('organization_number')
                     or company_data.get('organizationNumber')
                     or company_info.get('organization_number')
                     or '')
        prev_year = fiscal_year - 1 if fiscal_year else 0
        
        # All contexts already created in generate_xbrl_document
        # Just reference them directly
        period0_ref = 'period0'
        period1_ref = 'period1'
        period2_ref = 'period2'
        period3_ref = 'period3'
        balans0_ref = 'balans0'
        balans1_ref = 'balans1'
        balans2_ref = 'balans2'
        balans3_ref = 'balans3'
        
        # Unit refs (already created in generate_xbrl_document)
        unit_ref = 'SEK'
        procent_unit_ref = 'procent'
        
        # Page 0: Cover page
        self._render_cover_page(body, company_name, org_number, fiscal_year, start_date, end_date, 'period0')
        
        # Page 1: Förvaltningsberättelse
        self._render_forvaltningsberattelse(body, company_data, company_name, org_number, fiscal_year, prev_year, unit_ref)
        
        # Page 2: Resultaträkning
        self._render_resultatrakning(body, company_data, company_name, org_number, fiscal_year, prev_year, 'period0', 'period1', unit_ref)
        
        # Page 3: Balansräkning (Tillgångar)
        self._render_balansrakning_tillgangar(body, company_data, company_name, org_number, fiscal_year, prev_year, 'balans0', 'balans1', unit_ref)
        
        # Page 4: Balansräkning (Eget kapital och skulder)
        self._render_balansrakning_skulder(body, company_data, company_name, org_number, fiscal_year, prev_year, 'balans0', 'balans1', unit_ref)
        
        # Page 5+: Noter
        self._render_noter(body, company_data, company_name, org_number, fiscal_year, prev_year, 'period0', 'period1', 'balans0', 'balans1', unit_ref)
    
    def _render_cover_page(self, body: ET.Element, company_name: str, org_number: str, 
                          fiscal_year: Optional[int], start_date: Optional[str], end_date: Optional[str],
                          period0_ref: str):
        """Render cover page (mirror PDF generator exactly)"""
        page0 = ET.SubElement(body, 'div')
        page0.set('class', 'ar-page0')
        
        # Top spacing: 16 line breaks = 192pt (PDF: Spacer(1, 16 * 12))
        p_top_space = ET.SubElement(page0, 'p')
        p_top_space.set('style', 'margin-top: 192pt; margin-bottom: 0;')
        p_top_space.text = ''
        
        # "Årsredovisning" - 18pt semibold, centered (PDF: fontSize=18, fontName='Roboto-Medium', spaceAfter=0, leading=18)
        p_title = ET.SubElement(page0, 'p')
        p_title.set('class', 'cover-title-spaced')
        p_title.text = 'Årsredovisning'
        
        # Company name - 16pt semibold, centered (with XBRL tag)
        p_name = ET.SubElement(page0, 'p')
        p_name.set('class', 'cover-subtitle-spaced')
        ix_name = ET.SubElement(p_name, 'ix:nonNumeric')
        ix_name.set('name', 'se-cd-base:ForetagetsNamn')
        ix_name.set('contextRef', period0_ref)
        ix_name.text = company_name
        
        # Organization number - 16pt normal, centered (with XBRL tag)
        p_org = ET.SubElement(page0, 'p')
        p_org.set('class', 'cover-center-org')
        ix_org = ET.SubElement(p_org, 'ix:nonNumeric')
        ix_org.set('name', 'se-cd-base:Organisationsnummer')
        ix_org.set('contextRef', period0_ref)
        # Keep hyphen for display (e.g. 556610-3643)
        org_num_str = str(org_number)
        if '-' not in org_num_str and len(org_num_str) == 10:
            org_num_str = org_num_str[:6] + '-' + org_num_str[6:]
        ix_org.text = org_num_str
        
        # "avseende perioden" - 12pt normal, centered
        p_period_label = ET.SubElement(page0, 'p')
        p_period_label.set('class', 'cover-label-spaced')
        p_period_label.text = 'avseende perioden'
        
        # Fiscal period dates - 14pt normal, centered
        p_dates = ET.SubElement(page0, 'p')
        p_dates.set('class', 'cover-center-dates')
        period_text = f"{start_date} - {end_date}"
        p_dates.text = period_text
        
    
    def _render_forvaltningsberattelse(self, body: ET.Element, company_data: Dict[str, Any],
                                      company_name: str, org_number: str, fiscal_year: Optional[int],
                                      prev_year: int, unit_ref: str):
        """Render Förvaltningsberättelse section with proper FB mapping"""
        page1 = ET.SubElement(body, 'div')
        page1.set('class', 'pagebreak_before ar-page1')
        
        # Main heading "Förvaltningsberättelse" with spacing
        p_fb_title = ET.SubElement(page1, 'p')
        p_fb_title.set('class', 'H0-spaced-bottom')
        p_fb_title.text = 'Förvaltningsberättelse'
        
        # Get company and FB data
        scraped_company_data = company_data.get('scraped_company_data', {})
        fb_variables = company_data.get('fbVariables', {})
        fb_table = company_data.get('fbTable', [])
        
        # Load FB mappings from Supabase
        try:
            from supabase import create_client
            import os
            from dotenv import load_dotenv
            load_dotenv()
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_ANON_KEY")
            if supabase_url and supabase_key:
                supabase = create_client(supabase_url, supabase_key)
                fb_mappings_response = supabase.table('variable_mapping_fb').select('*').execute()
                fb_mappings = fb_mappings_response.data
            else:
                fb_mappings = []
        except:
            fb_mappings = []
        
        # Section: Verksamheten
        verksamhet_text = company_data.get('verksamhetContent')
        if not verksamhet_text:
            # Build from scraped data (mirrors PDF generator logic)
            verksamhetsbeskrivning = (scraped_company_data.get('verksamhetsbeskrivning') or 
                                     scraped_company_data.get('Verksamhetsbeskrivning') or '').strip()
            sate = (scraped_company_data.get('säte') or 
                   scraped_company_data.get('sate') or 
                   scraped_company_data.get('Säte') or '').strip()
            moderbolag = (scraped_company_data.get('moderbolag') or 
                         scraped_company_data.get('Moderbolag') or '').strip()
            moderbolag_orgnr = (scraped_company_data.get('moderbolag_orgnr') or 
                               scraped_company_data.get('ModerbolagOrgNr') or '').strip()
            
            verksamhet_text = verksamhetsbeskrivning
            if sate:
                verksamhet_text += (' ' if verksamhet_text else '') + f"Bolaget har sitt säte i {sate}."
            if moderbolag:
                moder_sate = (scraped_company_data.get('moderbolag_säte') or 
                             scraped_company_data.get('moderbolag_sate') or sate).strip()
                verksamhet_text += f" Bolaget är dotterbolag till {moderbolag}"
                if moderbolag_orgnr:
                    verksamhet_text += f" med organisationsnummer {moderbolag_orgnr}"
                verksamhet_text += f", som har sitt säte i {moder_sate or sate}."
            
            if not verksamhet_text:
                verksamhet_text = "Bolaget bedriver verksamhet enligt bolagsordningen."
        
        # Verksamheten section
        p_h_verksamhet = ET.SubElement(page1, 'p')
        p_h_verksamhet.set('class', 'H1-spaced-top')
        p_h_verksamhet.text = 'Verksamheten'
        
        p_verksamhet = ET.SubElement(page1, 'p')
        p_verksamhet.set('class', 'P-spaced-bottom')
        # Add XBRL tagging for Verksamheten text
        ix_verksamhet = ET.SubElement(p_verksamhet, 'ix:nonNumeric')
        ix_verksamhet.set('name', 'se-gen-base:AllmantVerksamheten')
        ix_verksamhet.set('contextRef', 'period0')
        ix_verksamhet.text = verksamhet_text
        
        # Väsentliga händelser
        vasentliga_text = company_data.get('vasentligaHandelser')
        if not vasentliga_text:
            vasentliga_text = "Inga väsentliga händelser under året."
        
        p_h_vasentliga = ET.SubElement(page1, 'p')
        p_h_vasentliga.set('class', 'H1-no-margin-top')
        p_h_vasentliga.text = 'Väsentliga händelser under räkenskapsåret'
        
        p_vasentliga = ET.SubElement(page1, 'p')
        p_vasentliga.set('class', 'P-spaced-bottom')
        # Add XBRL tagging for Väsentliga händelser text
        ix_vasentliga = ET.SubElement(p_vasentliga, 'ix:nonNumeric')
        ix_vasentliga.set('name', 'se-gen-base:VasentligaHandelserUnderRakenskapsaret')
        ix_vasentliga.set('contextRef', 'period0')
        ix_vasentliga.text = vasentliga_text
        
        # Flerårsöversikt - render with proper logic
        self._render_flerarsoversikt_xbrl(page1, company_data, fiscal_year, prev_year, fb_variables, fb_mappings, unit_ref)
        
        # Förändringar i eget kapital - render with show/hide logic
        self._render_forandringar_eget_kapital_xbrl(page1, fb_table, fiscal_year, prev_year, fb_variables, fb_mappings, 'balans0', 'balans1', 'period0', unit_ref)
        
        # Resultatdisposition - render with proper formatting
        self._render_resultatdisposition_xbrl(page1, fb_table, company_data, fb_mappings, 'balans0', unit_ref)
    
    def _render_flerarsoversikt_xbrl(self, page: ET.Element, company_data: dict, fiscal_year: int, prev_year: int,
                                     fb_variables: dict, fb_mappings: list, unit_ref: str) -> None:
        """Render Flerårsöversikt table with 3 years"""
        p_heading = ET.SubElement(page, 'p')
        p_heading.set('class', 'H1-no-margin-top')
        p_heading.text = 'Flerårsöversikt'
        
        p_tkr = ET.SubElement(page, 'p')
        p_tkr.set('class', 'SMALL')
        p_tkr.text = 'Belopp i tkr'
        
        # Build FB mappings dict by variable name
        fb_mappings_dict = {}
        for mapping in fb_mappings:
            var_str = mapping.get('variable', '')
            if var_str:
                # Split multiple variables (oms1;oms2;oms3;oms4)
                vars_list = [v.strip() for v in var_str.split(';') if v.strip()]
                for var_name in vars_list:
                    fb_mappings_dict[var_name] = {
                        'element_name': mapping.get('elementname', ''),
                        'data_type': mapping.get('datatyp', ''),
                        'period_type': mapping.get('periodtyp', ''),
                        'namespace': 'se-gen-base'  # Hardcoded from tillhor column
                    }
        
        # Get flerårsöversikt data
        flerars = company_data.get('flerarsoversikt', {})
        
        # Build years list (3 years: fiscal_year, prev_year, prev_year-1)
        years = [str(fiscal_year), str(prev_year), str(prev_year - 1)]
        
        # Helper to get variable value
        def get_var(var_names):
            if isinstance(var_names, str):
                var_names = [v.strip() for v in var_names.split(';')]
            for var in var_names:
                if var in fb_variables:
                    val = fb_variables[var]
                    return self._num(val) if val is not None else 0
            return 0
        
        # Get scraped nyckeltal as fallback
        scraped = company_data.get('scraped_company_data', {})
        nyckeltal = scraped.get('nyckeltal', {})
        
        def get_scraped_values(key_variants):
            for key in key_variants:
                arr = nyckeltal.get(key)
                if arr and isinstance(arr, list):
                    return [self._num(x) for x in arr[:3]]
            return [0, 0, 0]
        
        # Build rows with proper variable mapping from CSV
        # oms1;oms2;oms3 -> current, prev, prev-1
        rows_data = []
        
        # Nettoomsättning (row 31 in CSV) - variable: oms1;oms2;oms3
        oms_vals = [get_var('oms1'), get_var('oms2'), get_var('oms3')]
        if all(v == 0 for v in oms_vals):
            scraped_oms = get_scraped_values(['Omsättning', 'Total omsättning', 'omsättning'])
            oms_vals = scraped_oms
        rows_data.append(('Nettoomsättning', oms_vals, False, ['oms1', 'oms2', 'oms3']))
        
        # Resultat efter finansiella poster (row 34) - variable: ref1;ref2;ref3
        ref_vals = [get_var('ref1'), get_var('ref2'), get_var('ref3')]
        if all(v == 0 for v in ref_vals):
            scraped_ref = get_scraped_values(['Resultat efter finansnetto', 'Resultat efter finansiella poster'])
            ref_vals = scraped_ref
        rows_data.append(('Resultat efter finansiella poster', ref_vals, False, ['ref1', 'ref2', 'ref3']))
        
        # Balansomslutning (row 39) - variable: bal1;bal2;bal3
        bal_vals = [get_var('bal1'), get_var('bal2'), get_var('bal3')]
        if all(v == 0 for v in bal_vals):
            scraped_bal = get_scraped_values(['Summa tillgångar', 'Balansomslutning'])
            bal_vals = scraped_bal
        rows_data.append(('Balansomslutning', bal_vals, False, ['bal1', 'bal2', 'bal3']))
        
        # Soliditet (row 41) - percentage - variable: sol1;sol2;sol3
        sol_vals = [get_var('sol1'), get_var('sol2'), get_var('sol3')]
        if all(v == 0 for v in sol_vals):
            scraped_sol = get_scraped_values(['Soliditet'])
            sol_vals = scraped_sol
        rows_data.append(('Soliditet (%)', sol_vals, True, ['sol1', 'sol2', 'sol3']))  # True = percentage
        
        # Create table
        table = ET.SubElement(page, 'table')
        table.set('class', 'fb-flerars-table')
        
        # Header row
        tr_header = ET.SubElement(table, 'tr')
        td_label_h = ET.SubElement(tr_header, 'td')
        td_label_h.set('class', 'fb-flerars-th-label')
        # Empty
        
        for year in years:
            td_year = ET.SubElement(tr_header, 'td')
            td_year.set('class', 'fb-flerars-th-year')
            p_year = ET.SubElement(td_year, 'p')
            p_year.set('class', 'P-no-margin-bold')
            p_year.text = year
        
        # Data rows
        for label, values, is_percentage, var_names in rows_data:
            tr = ET.SubElement(table, 'tr')
            
            # Label
            td_label = ET.SubElement(tr, 'td')
            td_label.set('class', 'fb-flerars-td-label')
            p_label = ET.SubElement(td_label, 'p')
            p_label.set('class', 'P')
            p_label.text = label
            
            # Values (3 years: current, prev, prev-1)
            # Tag all 3 years with XBRL if contexts are available
            for idx, val in enumerate(values):
                td_val = ET.SubElement(tr, 'td')
                td_val.set('class', 'fb-flerars-td-amount')
                
                # Get XBRL mapping for this variable
                var_name = var_names[idx] if idx < len(var_names) else None
                mapping = fb_mappings_dict.get(var_name) if var_name else None
                
                # Determine contextRef based on year index and period type
                # All contexts (period0-3, balans0-3) are pre-defined
                context_ref = None
                if idx == 0:  # Current year (2024)
                    context_ref = 'period0' if mapping and mapping.get('period_type') == 'DURATION' else 'balans0'
                elif idx == 1:  # Previous year (2023)
                    context_ref = 'period1' if mapping and mapping.get('period_type') == 'DURATION' else 'balans1'
                elif idx == 2:  # Third year (2022)
                    context_ref = 'period2' if mapping and mapping.get('period_type') == 'DURATION' else 'balans2'
                
                # Apply XBRL tagging if mapping and context exist
                if mapping and context_ref:
                    element_name = f"{mapping['namespace']}:{mapping['element_name']}"
                    data_type = mapping.get('data_type', '')
                    
                    if data_type == 'xbrli:monetaryItemType':
                        # Monetary value
                        formatted_val = self._format_monetary_value(abs(val), for_display=True)
                        if val < 0:
                            td_val.text = '- '
                        
                        ix_elem = ET.SubElement(td_val, 'ix:nonFraction')
                        ix_elem.set('contextRef', context_ref)
                        ix_elem.set('name', element_name)
                        ix_elem.set('unitRef', 'SEK')
                        ix_elem.set('decimals', 'INF')
                        ix_elem.set('scale', '0')
                        ix_elem.set('format', 'ixt:numspacecomma')
                        if val < 0:
                            ix_elem.set('sign', '-')
                        ix_elem.text = formatted_val
                    elif data_type == 'xbrli:pureItemType':
                        # Soliditet percentage - Rule 2.12.1: MUST use scale="-2"
                        # Display value in percent (e.g., "28"), scale=-2 means actual value is 0.28
                        # Per Bolagsverket: use unitRef="procent" (xbrli:pure measure)
                        ix_elem = ET.SubElement(td_val, 'ix:nonFraction')
                        ix_elem.set('contextRef', context_ref)
                        ix_elem.set('name', element_name)
                        ix_elem.set('unitRef', 'procent')  # Use procent unit (xbrli:pure)
                        ix_elem.set('decimals', 'INF')  # Exact value
                        ix_elem.set('scale', '-2')  # Value is 100 times smaller (28 -> 0.28)
                        ix_elem.set('format', 'ixt:numdotdecimal')  # Decimal format with dot
                        # Display as percentage value without % symbol (e.g., "28")
                        ix_elem.text = str(int(round(val)))
                    else:
                        # Fallback: plain text in <p>
                        p_val = ET.SubElement(td_val, 'p')
                        p_val.set('class', 'P-no-margin')
                        if is_percentage:
                            # Per Bolagsverket rule 2.12.1: show percentage value without % symbol
                            p_val.text = str(int(round(val)))
                        else:
                            p_val.text = self._format_monetary_value(val, for_display=True)
                else:
                    # No XBRL tagging (third year or no mapping): plain text in <p>
                    p_val = ET.SubElement(td_val, 'p')
                    p_val.set('class', 'P-no-margin')
                    if is_percentage:
                        # Per Bolagsverket rule 2.12.1: show percentage value without % symbol
                        p_val.text = str(int(round(val)))
                    else:
                        p_val.text = self._format_monetary_value(val, for_display=True)
    
    def _render_forandringar_eget_kapital_xbrl(self, page: ET.Element, fb_table: list, fiscal_year: int, 
                                               prev_year: int, fb_variables: dict, fb_mappings: list,
                                               balans0_ref: str, balans1_ref: str, period0_ref: str, unit_ref: str) -> None:
        """Render Förändringar i eget kapital table with column/row filtering"""
        if not fb_table or len(fb_table) == 0:
            return
        
        p_heading = ET.SubElement(page, 'p')
        p_heading.set('class', 'H1-no-margin-top')
        p_heading.text = 'Förändringar i eget kapital'
        
        # Build FB mappings dict by (radrubrik, block) for Förändringar i eget kapital
        # Map: block (column) → {radrubrik (row label) → mapping data}
        fb_mappings_by_block = {}
        for mapping in fb_mappings:
            radrubrik = mapping.get('radrubrik', '')
            block = mapping.get('block', '')
            
            # Only process mappings for equity changes blocks
            if block in ['AKTIEKAPITAL', 'RESERVFOND', 'UPPSKRIVNINGSFOND', 
                        'BALANSERATRESULTAT', 'ARETSRESULTAT', 'TOTALTEGETKAPITAL']:
                if block not in fb_mappings_by_block:
                    fb_mappings_by_block[block] = {}
                
                fb_mappings_by_block[block][radrubrik] = {
                    'element_name': mapping.get('elementname', ''),
                    'data_type': mapping.get('datatyp', ''),
                    'period_type': mapping.get('periodtyp', ''),
                    'namespace': 'se-gen-base'
                }
        
        # Map column names to block names for lookup
        col_to_block = {
            'aktiekapital': 'AKTIEKAPITAL',
            'reservfond': 'RESERVFOND',
            'uppskrivningsfond': 'UPPSKRIVNINGSFOND',
            'balanserat_resultat': 'BALANSERATRESULTAT',
            'arets_resultat': 'ARETSRESULTAT',
            'total': 'TOTALTEGETKAPITAL'
        }
        
        # Column definitions
        cols = ['aktiekapital', 'reservfond', 'uppskrivningsfond', 'balanserat_resultat', 'arets_resultat', 'total']
        col_labels = ['Aktie\nkapital', 'Reserv\nfond', 'Uppskr.\nfond', 'Balanserat\nresultat', 'Årets\nresultat', 'Totalt']
        
        # Determine which columns have non-zero values
        col_has_data = {}
        for col in cols:
            col_has_data[col] = any(self._num(row.get(col, 0)) != 0 for row in fb_table)
        
        # Build visible columns list
        visible_cols = [col for col in cols if col_has_data[col]]
        visible_labels = [col_labels[cols.index(col)] for col in visible_cols]
        
        if not visible_cols:
            return  # All columns are zero
        
        # Build table data, filtering out all-zero rows and "Redovisat värde"
        table_data = []
        utgaende_rows_idx = []  # Track "utgång" rows for semibold styling
        
        for row in fb_table:
            label = row.get('label', '')
            
            # Skip "Redovisat värde" rows completely
            if 'Redovisat' in label:
                continue
            
            row_values = [self._num(row.get(col, 0)) for col in visible_cols]
            
            # Skip rows where all visible columns are zero (except IB/UB rows)
            if not any(v != 0 for v in row_values):
                if not ('Ingående' in label or 'Utgående' in label or 'utgång' in label.lower()):
                    continue
            
            table_data.append((label, row_values))
            
            # Track if this row should be semibold (contains "utgång" or "Utgående")
            if 'utgång' in label.lower() or 'Utgående' in label:
                utgaende_rows_idx.append(len(table_data) - 1)
        
        if len(table_data) == 0:
            return  # No data to show
        
        # Create table
        table = ET.SubElement(page, 'table')
        table.set('class', 'fb-ek-table')
        
        # Header row
        tr_header = ET.SubElement(table, 'tr')
        td_label_h = ET.SubElement(tr_header, 'td')
        td_label_h.set('class', 'fb-ek-th-label')
        # Empty
        
        for col_label in visible_labels:
            td_col = ET.SubElement(tr_header, 'td')
            td_col.set('class', 'fb-ek-th-col')
            # Handle multi-line headers
            lines = col_label.split('\n')
            for line in lines:
                p_line = ET.SubElement(td_col, 'p')
                p_line.set('class', 'P-no-margin-bold')
                p_line.text = line
        
        # Data rows
        for idx, (label, values) in enumerate(table_data):
            tr = ET.SubElement(table, 'tr')
            is_utgaende = idx in utgaende_rows_idx
            
            # Label
            td_label = ET.SubElement(tr, 'td')
            td_label.set('class', 'fb-ek-td-label')
            p_label = ET.SubElement(td_label, 'p')
            if is_utgaende:
                p_label.set('class', 'P-no-margin-bold')
            else:
                p_label.set('class', 'P-no-margin')
            p_label.text = label
            
            # Values
            for col_idx, val in enumerate(values):
                td_val = ET.SubElement(tr, 'td')
                # Add semibold styling for utgående rows
                if is_utgaende:
                    td_val.set('class', 'fb-ek-td-amount-bold')
                else:
                    td_val.set('class', 'fb-ek-td-amount')
                
                # Get the column name and block for XBRL mapping
                col_name = visible_cols[col_idx] if col_idx < len(visible_cols) else None
                block_name = col_to_block.get(col_name) if col_name else None
                
                # Try to find XBRL mapping for this cell (row label + column/block)
                mapping = None
                if block_name and block_name in fb_mappings_by_block:
                    # Try exact match first
                    mapping = fb_mappings_by_block[block_name].get(label)
                    # If not found, try partial match (for rows like "Ingående" vs "Belopp vid årets ingång")
                    if not mapping:
                        for radrubrik, data in fb_mappings_by_block[block_name].items():
                            if ('ingång' in label.lower() and 'ingång' in radrubrik.lower()) or \
                               ('utgång' in label.lower() and 'utgång' in radrubrik.lower()):
                                mapping = data
                                break
                
                # Determine contextRef based on row type and period type
                context_ref = None
                if mapping:
                    period_type = mapping.get('period_type', '')
                    if 'ingång' in label.lower() or 'Ingående' in label:
                        # Opening balance: INSTANT, balans1_ref (previous year end)
                        context_ref = balans1_ref
                    elif 'utgång' in label.lower() or 'Utgående' in label:
                        # Closing balance: INSTANT, balans0_ref (current year end)
                        context_ref = balans0_ref
                    else:
                        # Transaction during period: use DURATION or INSTANT based on mapping
                        context_ref = period0_ref if period_type == 'DURATION' else balans0_ref
                
                # Apply XBRL tagging if mapping found
                if mapping and context_ref and val != 0:
                    formatted_val = self._format_monetary_value(abs(val), for_display=True)
                    if val < 0:
                        td_val.text = '- '
                    
                    ix_elem = ET.SubElement(td_val, 'ix:nonFraction')
                    ix_elem.set('contextRef', context_ref)
                    ix_elem.set('name', f"{mapping['namespace']}:{mapping['element_name']}")
                    ix_elem.set('unitRef', 'SEK')
                    ix_elem.set('decimals', 'INF')
                    ix_elem.set('scale', '0')
                    ix_elem.set('format', 'ixt:numspacecomma')
                    if val < 0:
                        ix_elem.set('sign', '-')
                    ix_elem.text = formatted_val
                else:
                    # No XBRL tagging: plain text in <p>
                    p_val = ET.SubElement(td_val, 'p')
                    if is_utgaende:
                        p_val.set('class', 'P-no-margin-bold')
                    else:
                        p_val.set('class', 'P-no-margin')
                    p_val.text = self._format_monetary_value(val, for_display=True)
    
    def _render_resultatdisposition_xbrl(self, page: ET.Element, fb_table: list, company_data: dict,
                                        fb_mappings: list, balans0_ref: str, unit_ref: str) -> None:
        """Render Resultatdisposition section"""
        arets_utdelning = self._num(company_data.get('arets_utdelning', 0))
        
        if not fb_table:
            return
        
        # Build FB mappings dict by radrubrik (row label) for Resultatdisposition section
        fb_mappings_dict = {}
        for mapping in fb_mappings:
            radrubrik = mapping.get('radrubrik', '')
            block = mapping.get('block', '')
            if block == 'RESULTATDISPOSITION' and radrubrik:
                fb_mappings_dict[radrubrik] = {
                    'element_name': mapping.get('elementname', ''),
                    'data_type': mapping.get('datatyp', ''),
                    'period_type': mapping.get('periodtyp', ''),
                    'namespace': 'se-gen-base'
                }
        
        # Find UB row (Redovisat värde or Utgående or last row)
        ub_row = None
        for row in fb_table:
            if 'Redovisat' in row.get('label', '') or 'Utgående' in row.get('label', ''):
                ub_row = row
                break
        
        if not ub_row:
            ub_row = fb_table[-1] if fb_table else {}
        
        # Get balanserat resultat and årets resultat from UB row
        balanserat = self._num(ub_row.get('balanserat_resultat', 0))
        arets_res = self._num(ub_row.get('arets_resultat', 0))
        summa = balanserat + arets_res
        
        if summa == 0 and arets_utdelning == 0:
            return  # Nothing to report
        
        p_heading = ET.SubElement(page, 'p')
        p_heading.set('class', 'H1-no-margin-top')
        p_heading.text = 'Resultatdisposition'
        
        p_intro = ET.SubElement(page, 'p')
        p_intro.set('class', 'P')
        p_intro.text = 'Styrelsen och VD föreslår att till förfogande stående medel'
        
        # Create table
        table = ET.SubElement(page, 'table')
        table.set('class', 'fb-resdisp-table')
        # Add margin-bottom only if no dividend text will follow (checked below)
        if arets_utdelning != 0:
            table.set('style', 'margin-bottom: 0;')  # Override default when dividend follows
        
        # Available funds
        if balanserat != 0:
            tr = ET.SubElement(table, 'tr')
            td_label = ET.SubElement(tr, 'td')
            td_label.set('class', 'fb-resdisp-td-label')
            p_label = ET.SubElement(td_label, 'p')
            p_label.set('class', 'P-no-margin')
            p_label.text = 'Balanserat resultat'
            
            td_val = ET.SubElement(tr, 'td')
            td_val.set('class', 'fb-resdisp-td-amount')
            
            # Apply XBRL tagging for Balanserat resultat
            mapping = fb_mappings_dict.get('Balanserat resultat')
            if mapping:
                formatted_val = self._format_monetary_value(abs(balanserat), for_display=True)
                if balanserat < 0:
                    td_val.text = '- '
                
                ix_elem = ET.SubElement(td_val, 'ix:nonFraction')
                ix_elem.set('contextRef', balans0_ref)
                ix_elem.set('name', f"{mapping['namespace']}:{mapping['element_name']}")
                ix_elem.set('unitRef', 'SEK')
                ix_elem.set('decimals', 'INF')
                ix_elem.set('scale', '0')
                ix_elem.set('format', 'ixt:numspacecomma')
                if balanserat < 0:
                    ix_elem.set('sign', '-')
                ix_elem.text = formatted_val
            else:
                p_val = ET.SubElement(td_val, 'p')
                p_val.set('class', 'P-no-margin')
                p_val.text = self._format_monetary_value(balanserat, for_display=True)
        
        if arets_res != 0:
            tr = ET.SubElement(table, 'tr')
            td_label = ET.SubElement(tr, 'td')
            td_label.set('class', 'fb-resdisp-td-label')
            p_label = ET.SubElement(td_label, 'p')
            p_label.set('class', 'P-no-margin')
            p_label.text = 'Årets resultat'
            
            td_val = ET.SubElement(tr, 'td')
            td_val.set('class', 'fb-resdisp-td-amount')
            
            # Apply XBRL tagging for Årets resultat
            mapping = fb_mappings_dict.get('Årets resultat')
            if mapping:
                formatted_val = self._format_monetary_value(abs(arets_res), for_display=True)
                if arets_res < 0:
                    td_val.text = '- '
                
                ix_elem = ET.SubElement(td_val, 'ix:nonFraction')
                ix_elem.set('contextRef', balans0_ref)
                ix_elem.set('name', f"{mapping['namespace']}:{mapping['element_name']}")
                ix_elem.set('unitRef', 'SEK')
                ix_elem.set('decimals', 'INF')
                ix_elem.set('scale', '0')
                ix_elem.set('format', 'ixt:numspacecomma')
                if arets_res < 0:
                    ix_elem.set('sign', '-')
                ix_elem.text = formatted_val
            else:
                p_val = ET.SubElement(td_val, 'p')
                p_val.set('class', 'P-no-margin')
                p_val.text = self._format_monetary_value(arets_res, for_display=True)
        
        # First Summa row
        tr = ET.SubElement(table, 'tr')
        td_label = ET.SubElement(tr, 'td')
        td_label.set('class', 'fb-resdisp-td-label')
        p_label = ET.SubElement(td_label, 'p')
        p_label.set('class', 'P-no-margin-bold')
        p_label.text = 'Summa'
        
        td_val = ET.SubElement(tr, 'td')
        td_val.set('class', 'fb-resdisp-td-amount-bold')
        
        # Apply XBRL tagging for first Summa (FrittEgetKapital)
        mapping = fb_mappings_dict.get('Summa')
        if mapping and mapping['element_name'] == 'FrittEgetKapital':
            formatted_val = self._format_monetary_value(abs(summa), for_display=True)
            if summa < 0:
                td_val.text = '- '
            
            ix_elem = ET.SubElement(td_val, 'ix:nonFraction')
            ix_elem.set('contextRef', balans0_ref)
            ix_elem.set('name', f"{mapping['namespace']}:{mapping['element_name']}")
            ix_elem.set('unitRef', 'SEK')
            ix_elem.set('decimals', 'INF')
            ix_elem.set('scale', '0')
            ix_elem.set('format', 'ixt:numspacecomma')
            if summa < 0:
                ix_elem.set('sign', '-')
            ix_elem.text = formatted_val
        else:
            p_val = ET.SubElement(td_val, 'p')
            p_val.set('class', 'P')
            p_val.set('style', 'margin-top: 0; margin-bottom: 0; font-weight: 500;')
            p_val.text = self._format_monetary_value(summa, for_display=True)
        
        # Empty row for spacing
        tr_empty = ET.SubElement(table, 'tr')
        td_empty1 = ET.SubElement(tr_empty, 'td')
        td_empty1.set('class', 'fb-spacer-row')
        td_empty2 = ET.SubElement(tr_empty, 'td')
        td_empty2.set('class', 'fb-spacer-row')
        
        # Disposition header
        tr = ET.SubElement(table, 'tr')
        td_label = ET.SubElement(tr, 'td')
        td_label.set('class', 'fb-resdisp-td-label')
        p_label = ET.SubElement(td_label, 'p')
        p_label.set('class', 'P-no-margin')
        p_label.text = 'Disponeras enligt följande'
        td_empty = ET.SubElement(tr, 'td')
        
        # Utdelas till aktieägare
        tr = ET.SubElement(table, 'tr')
        td_label = ET.SubElement(tr, 'td')
        td_label.set('class', 'fb-resdisp-td-label')
        p_label = ET.SubElement(td_label, 'p')
        p_label.set('class', 'P-no-margin')
        p_label.text = 'Utdelas till aktieägare'
        
        td_val = ET.SubElement(tr, 'td')
        td_val.set('class', 'fb-resdisp-td-amount')
        
        # Apply XBRL tagging for Vinstutdelning
        mapping = fb_mappings_dict.get('Vinstutdelning ')  # Note: space in CSV
        if not mapping:
            mapping = fb_mappings_dict.get('Vinstutdelning')
        if mapping:
            formatted_val = self._format_monetary_value(abs(arets_utdelning), for_display=True)
            if arets_utdelning < 0:
                td_val.text = '- '
            
            ix_elem = ET.SubElement(td_val, 'ix:nonFraction')
            ix_elem.set('contextRef', balans0_ref)
            ix_elem.set('name', f"{mapping['namespace']}:{mapping['element_name']}")
            ix_elem.set('unitRef', 'SEK')
            ix_elem.set('decimals', 'INF')
            ix_elem.set('scale', '0')
            ix_elem.set('format', 'ixt:numspacecomma')
            if arets_utdelning < 0:
                ix_elem.set('sign', '-')
            ix_elem.text = formatted_val
        else:
            p_val = ET.SubElement(td_val, 'p')
            p_val.set('class', 'P-no-margin')
            p_val.text = self._format_monetary_value(arets_utdelning, for_display=True)
        
        # Balanseras i ny räkning
        balanseras = summa - arets_utdelning
        tr = ET.SubElement(table, 'tr')
        td_label = ET.SubElement(tr, 'td')
        td_label.set('class', 'fb-resdisp-td-label')
        p_label = ET.SubElement(td_label, 'p')
        p_label.set('class', 'P-no-margin')
        p_label.text = 'Balanseras i ny räkning'
        
        td_val = ET.SubElement(tr, 'td')
        td_val.set('class', 'fb-resdisp-td-amount')
        
        # Apply XBRL tagging for Balanseras i ny räkning
        mapping = fb_mappings_dict.get('Balanseras i ny räkning')
        if mapping:
            formatted_val = self._format_monetary_value(abs(balanseras), for_display=True)
            if balanseras < 0:
                td_val.text = '- '
            
            ix_elem = ET.SubElement(td_val, 'ix:nonFraction')
            ix_elem.set('contextRef', balans0_ref)
            ix_elem.set('name', f"{mapping['namespace']}:{mapping['element_name']}")
            ix_elem.set('unitRef', 'SEK')
            ix_elem.set('decimals', 'INF')
            ix_elem.set('scale', '0')
            ix_elem.set('format', 'ixt:numspacecomma')
            if balanseras < 0:
                ix_elem.set('sign', '-')
            ix_elem.text = formatted_val
        else:
            p_val = ET.SubElement(td_val, 'p')
            p_val.set('class', 'P-no-margin')
            p_val.text = self._format_monetary_value(balanseras, for_display=True)
        
        # Final Summa row
        tr = ET.SubElement(table, 'tr')
        td_label = ET.SubElement(tr, 'td')
        td_label.set('class', 'fb-resdisp-td-label')
        p_label = ET.SubElement(td_label, 'p')
        p_label.set('class', 'P-no-margin-bold')
        p_label.text = 'Summa'
        
        td_val = ET.SubElement(tr, 'td')
        td_val.set('class', 'fb-resdisp-td-amount-bold')
        
        # Apply XBRL tagging for final Summa (ForslagDisposition)
        # Need to find the Summa mapping with ForslagDisposition element
        mapping = None
        for radrubrik, data in fb_mappings_dict.items():
            if radrubrik == 'Summa' and data['element_name'] == 'ForslagDisposition':
                mapping = data
                break
        
        if mapping:
            formatted_val = self._format_monetary_value(abs(summa), for_display=True)
            if summa < 0:
                td_val.text = '- '
            
            ix_elem = ET.SubElement(td_val, 'ix:nonFraction')
            ix_elem.set('contextRef', balans0_ref)
            ix_elem.set('name', f"{mapping['namespace']}:{mapping['element_name']}")
            ix_elem.set('unitRef', 'SEK')
            ix_elem.set('decimals', 'INF')
            ix_elem.set('scale', '0')
            ix_elem.set('format', 'ixt:numspacecomma')
            if summa < 0:
                ix_elem.set('sign', '-')
            ix_elem.text = formatted_val
        else:
            p_val = ET.SubElement(td_val, 'p')
            p_val.set('class', 'P-no-margin-bold')
            p_val.text = self._format_monetary_value(summa, for_display=True)
        
        # Add dividend policy text if utdelning > 0 (this is the LAST element - add space AFTER)
        if arets_utdelning > 0:
            p_policy = ET.SubElement(page, 'p')
            p_policy.set('class', 'P')
            p_policy.set('style', 'margin-top: 18pt; margin-bottom: 27pt;')  # Space AFTER last element (75% of doubled)
            dividend_text = ("Styrelsen anser att förslaget är förenligt med försiktighetsregeln "
                            "i 17 kap. 3 § aktiebolagslagen enligt följande redogörelse. Styrelsens "
                            "uppfattning är att vinstutdelningen är försvarlig med hänsyn till de krav "
                            "verksamhetens art, omfattning och risk ställer på storleken på det egna "
                            "kapitalet, bolagets konsolideringsbehov, likviditet och ställning i övrigt.")
            p_policy.text = dividend_text
    
    def _render_resultatrakning(self, body: ET.Element, company_data: Dict[str, Any],
                                company_name: str, org_number: str, fiscal_year: Optional[int],
                                prev_year: int, period0_ref: str, period1_ref: str, unit_ref: str):
        """Render Resultaträkning section"""
        page2 = ET.SubElement(body, 'div')
        page2.set('class', 'pagebreak_before ar-page2')
        
        # Header with title
        p_title = ET.SubElement(page2, 'p')
        p_title.set('class', 'H0')
        p_title.text = 'Resultaträkning'
        
        # Column headers table (with underline)
        header_table = ET.SubElement(page2, 'table')
        header_table.set('class', 'table-header')
        tr_header = ET.SubElement(header_table, 'tr')
        
        # Label column
        td_label = ET.SubElement(tr_header, 'td')
        td_label.set('class', 'th-label')
        
        # Note column
        td_not = ET.SubElement(tr_header, 'td')
        td_not.set('class', 'th-note')
        p_not = ET.SubElement(td_not, 'p')
        p_not.set('class', 'P-bold')
        p_not.text = 'Not'
        
        # Current year column
        td_year1 = ET.SubElement(tr_header, 'td')
        td_year1.set('class', 'th-year')
        p_year1_start = ET.SubElement(td_year1, 'p')
        p_year1_start.set('class', 'P-bold')
        p_year1_start.text = f'{fiscal_year}-01-01' if fiscal_year else ''
        p_year1_end = ET.SubElement(td_year1, 'p')
        p_year1_end.set('class', 'P-bold')
        p_year1_end.text = f'-{fiscal_year}-12-31' if fiscal_year else ''
        
        # Spacing column
        td_spacing_h = ET.SubElement(tr_header, 'td')
        td_spacing_h.set('class', 'th-spacing')
        
        # Previous year column
        td_year2 = ET.SubElement(tr_header, 'td')
        td_year2.set('class', 'th-year')
        p_year2_start = ET.SubElement(td_year2, 'p')
        p_year2_start.set('class', 'P-bold')
        p_year2_start.text = f'{prev_year}-01-01' if prev_year else ''
        p_year2_end = ET.SubElement(td_year2, 'p')
        p_year2_end.set('class', 'P-bold')
        p_year2_end.text = f'-{prev_year}-12-31' if prev_year else ''
        
        # RR table
        rr_data_raw = (company_data.get('rrData') or 
                      company_data.get('rrRows') or 
                      company_data.get('seFileData', {}).get('rr_data', []))
        
        if rr_data_raw:
            rr_table = ET.SubElement(page2, 'table')
            rr_table.set('class', 'table-data')
            
            # Define column widths explicitly for proper colspan behavior
            colgroup = ET.SubElement(rr_table, 'colgroup')
            ET.SubElement(colgroup, 'col', style='width: 9cm')     # Label column
            ET.SubElement(colgroup, 'col', style='width: 2cm')     # Note column
            ET.SubElement(colgroup, 'col', style='width: 2.5cm')   # Current year
            ET.SubElement(colgroup, 'col', style='width: 0.5cm')   # Spacing
            ET.SubElement(colgroup, 'col', style='width: 2.5cm')   # Previous year
            
            # Load RR mappings for element names
            try:
                from supabase import create_client
                import os
                from dotenv import load_dotenv
                load_dotenv()
                supabase_url = os.getenv("SUPABASE_URL")
                supabase_key = os.getenv("SUPABASE_ANON_KEY")
                if supabase_url and supabase_key:
                    supabase = create_client(supabase_url, supabase_key)
                    rr_mappings_response = supabase.table('variable_mapping_rr').select('variable_name,element_name').execute()
                    rr_mappings_dict = {m['variable_name']: m for m in rr_mappings_response.data if m.get('variable_name')}
                else:
                    rr_mappings_dict = {}
            except:
                rr_mappings_dict = {}
            
            # Filter and render RR rows (mirroring PDF generator logic)
            seen_rorelseresultat = False
            for row in rr_data_raw:
                # NOTE: Do NOT filter by show_tag - PDF generator ignores this field
                # Only filter by amounts, always_show, block_group logic, and note_number
                
                label = row.get('label', '')
                block_group = row.get('block_group', '')
                
                # Skip "Resultaträkning" heading (duplicate - we have it as top heading)
                if label == 'Resultaträkning':
                    continue
                
                # Skip first occurrence of "Rörelseresultat" (duplicate)
                if label == 'Rörelseresultat':
                    if not seen_rorelseresultat:
                        seen_rorelseresultat = True
                        continue
                
                # Determine if heading or sum based on style field (better than label matching)
                style = row.get('style', '')
                is_heading = style in ['H0', 'H1', 'H2', 'H3', 'H4']
                is_sum = style in ['S1', 'S2', 'S3', 'S4'] or label.startswith('Summa ')
                
                # Block hiding logic: if this row belongs to a block, check if block has content
                if block_group and not self._block_has_content(block_group, rr_data_raw, 'rr'):
                    continue
                
                # For heading rows: always show (with empty amounts)
                # For other rows: show if has amounts OR always_show OR is_sum OR has note_number
                if not is_heading:
                    has_note = row.get('note_number') is not None and row.get('note_number') != ''
                    if not row.get('always_show') and not is_sum and not has_note:
                        curr = self._num(row.get('current_amount', 0))
                        prev = self._num(row.get('previous_amount', 0))
                        if curr == 0 and prev == 0:
                            continue
                
                # Get note number
                note = str(row.get('note_number', '')) if row.get('note_number') else ''
                if 'Personalkostnader' in label or 'personalkostnader' in label.lower():
                    note = '2'
                
                # Create table row with proper spacing
                tr = ET.SubElement(rr_table, 'tr')
                
                # Add ID to row if it has a note (for note reference linking)
                if note and note in self.NOTE_REFERENCE_MAPPING:
                    mapping = self.NOTE_REFERENCE_MAPPING[note]
                    # Add ID for current year (ar-0) - we'll add this to the label cell
                    row_id = f"{mapping['from_id']}-ar-0"
                    # Track this note reference
                    self._add_note_reference(note, mapping['from_id'], mapping['to_id_pattern'])
                
                # Add row spacing based on type (matching PDF spacing)
                row_class = ''
                if label == 'Årets resultat':
                    row_class = 'pt-18'  # Extra space before final result
                elif is_sum:
                    row_class = 'pb-10'  # 10pt space after sum rows
                elif is_heading:
                    row_class = 'pt-2'  # Small space before headings
                
                # For heading rows: use colspan to span entire table (no empty cells needed)
                if is_heading:
                    td_label = ET.SubElement(tr, 'td')
                    if row_class:
                        td_label.set('class', f'td-label-colspan {row_class}')
                    else:
                        td_label.set('class', 'td-label-colspan')
                    td_label.set('colspan', '5')
                    p_label = ET.SubElement(td_label, 'p')
                    p_label.set('class', 'H3-table')
                    p_label.text = label
                    continue  # Skip to next row, don't create other cells
                
                # For non-heading rows: create all cells
                # Label column
                td_label = ET.SubElement(tr, 'td')
                if row_class:
                    td_label.set('class', f'td-label {row_class}')
                else:
                    td_label.set('class', 'td-label')
                p_label = ET.SubElement(td_label, 'p')
                if is_sum:
                    p_label.set('class', 'sum-label')
                else:
                    p_label.set('class', 'P')
                p_label.text = label
                
                # Note column
                td_note = ET.SubElement(tr, 'td')
                if note and row_class:  # Only add padding if there's content
                    td_note.set('class', f'td-note {row_class}')
                else:
                    td_note.set('class', 'td-note')
                if note:  # Only add <p> if there's content
                    p_note = ET.SubElement(td_note, 'p')
                    p_note.set('class', 'P')
                    p_note.text = note
                
                # Current year amount
                td_curr = ET.SubElement(tr, 'td')
                if row_class:
                    td_curr.set('class', f'td-amount {row_class}')
                else:
                    td_curr.set('class', 'td-amount')
                # Add semibold styling for sum rows
                if is_sum:
                    td_curr.set('style', 'font-weight: 500;')
                
                curr_val = self._num(row.get('current_amount', 0))
                prev_val = self._num(row.get('previous_amount', 0))
                # Show amount if: non-zero, OR other year has value, OR always_show, OR has note
                if curr_val != 0 or prev_val != 0 or row.get('always_show') or note:
                    variable_name = row.get('variable_name')
                    if variable_name and variable_name in rr_mappings_dict:
                        mapping = rr_mappings_dict[variable_name]
                        element_name = mapping.get('element_name')
                        # All RR elements are in se-gen-base namespace
                        element_qname = f'se-gen-base:{element_name}'
                        
                        # For negative values, add minus sign before XBRL tag
                        if curr_val < 0: td_curr.text = '- '
                        ix_curr = ET.SubElement(td_curr, 'ix:nonFraction')
                        ix_curr.set('contextRef', period0_ref)
                        ix_curr.set('name', element_qname)
                        # Add ID if this row has a note (for note reference linking)
                        if note and note in self.NOTE_REFERENCE_MAPPING:
                            mapping_note = self.NOTE_REFERENCE_MAPPING[note]
                            ix_curr.set('id', f"{mapping_note['from_id']}-ar-0")
                            # Track this note reference (only add once per note)
                            if not any(ref['note_number'] == note for ref in self.note_references):
                                self._add_note_reference(note, mapping_note['from_id'], mapping_note['to_id_pattern'])
                        ix_curr.set('unitRef', 'SEK')
                        ix_curr.set('decimals', 'INF')
                        ix_curr.set('scale', '0')
                        ix_curr.set('format', 'ixt:numspacecomma')
                        ix_curr.text = self._format_monetary_value(abs(curr_val), for_display=True)
                    else:
                        # Fallback to plain text
                        td_curr.text = self._format_monetary_value(curr_val, for_display=True)
                
                # Spacing column (always empty, never needs padding)
                td_spacing = ET.SubElement(tr, 'td')
                td_spacing.set('class', 'td-spacing')
                
                # Previous year amount
                td_prev = ET.SubElement(tr, 'td')
                if row_class:
                    td_prev.set('class', f'td-amount {row_class}')
                else:
                    td_prev.set('class', 'td-amount')
                # Add semibold styling for sum rows
                if is_sum:
                    td_prev.set('style', 'font-weight: 500;')
                
                # prev_val already calculated above for current year logic
                # Show amount if: non-zero, OR other year has value, OR always_show, OR has note
                if prev_val != 0 or curr_val != 0 or row.get('always_show') or note:
                    variable_name = row.get('variable_name')
                    if variable_name and variable_name in rr_mappings_dict:
                        mapping = rr_mappings_dict[variable_name]
                        element_name = mapping.get('element_name')
                        # All RR elements are in se-gen-base namespace
                        element_qname = f'se-gen-base:{element_name}'
                        
                        # For negative values, add minus sign before XBRL tag
                        if prev_val < 0: td_prev.text = '- '
                        ix_prev = ET.SubElement(td_prev, 'ix:nonFraction')
                        ix_prev.set('contextRef', period1_ref)
                        ix_prev.set('name', element_qname)
                        # Add ID if this row has a note (for note reference linking)
                        if note and note in self.NOTE_REFERENCE_MAPPING:
                            mapping_note = self.NOTE_REFERENCE_MAPPING[note]
                            ix_prev.set('id', f"{mapping_note['from_id']}-ar-1")
                        ix_prev.set('unitRef', 'SEK')
                        ix_prev.set('decimals', 'INF')
                        ix_prev.set('scale', '0')
                        ix_prev.set('format', 'ixt:numspacecomma')
                        ix_prev.text = self._format_monetary_value(abs(prev_val), for_display=True)
                    else:
                        # Fallback to plain text
                        td_prev.text = self._format_monetary_value(prev_val, for_display=True)
    
    def _render_balansrakning_tillgangar(self, body: ET.Element, company_data: Dict[str, Any],
                                         company_name: str, org_number: str, fiscal_year: Optional[int],
                                         prev_year: int, balans0_ref: str, balans1_ref: str, unit_ref: str):
        """Render Balansräkning (Tillgångar) section"""
        page3 = ET.SubElement(body, 'div')
        page3.set('class', 'pagebreak_before ar-page3')
        
        # Header with title
        p_title = ET.SubElement(page3, 'p')
        p_title.set('class', 'H0')
        p_title.text = 'Balansräkning'
        
        # Column headers table (with underline) - must match data table structure EXACTLY
        header_table = ET.SubElement(page3, 'table')
        header_table.set('class', 'table-header')
        tr_header = ET.SubElement(header_table, 'tr')
        
        # Label column
        td_label = ET.SubElement(tr_header, 'td')
        td_label.set('class', 'th-label')
        
        # Note column
        td_not = ET.SubElement(tr_header, 'td')
        td_not.set('class', 'th-note')
        p_not = ET.SubElement(td_not, 'p')
        p_not.set('class', 'P-bold')
        p_not.text = 'Not'
        
        # Current year column
        td_year1 = ET.SubElement(tr_header, 'td')
        td_year1.set('class', 'th-year')
        p_year1 = ET.SubElement(td_year1, 'p')
        p_year1.set('class', 'P-bold')
        p_year1.text = f'{fiscal_year}-12-31' if fiscal_year else ''
        
        # Spacing column
        td_spacing_h = ET.SubElement(tr_header, 'td')
        td_spacing_h.set('class', 'th-spacing')
        
        # Previous year column
        td_year2 = ET.SubElement(tr_header, 'td')
        td_year2.set('class', 'th-year')
        p_year2 = ET.SubElement(td_year2, 'p')
        p_year2.set('class', 'P-bold')
        p_year2.text = f'{prev_year}-12-31' if prev_year else ''
        
        # BR table (assets only)
        br_data_raw = (company_data.get('brData') or 
                      company_data.get('brRows') or 
                      company_data.get('seFileData', {}).get('br_data', []))
        
        # Load BR mappings
        try:
            from supabase import create_client
            import os
            from dotenv import load_dotenv
            load_dotenv()
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_ANON_KEY")
            if supabase_url and supabase_key:
                supabase = create_client(supabase_url, supabase_key)
                br_mappings_response = supabase.table('variable_mapping_br').select('row_title,variable_name,element_name,data_type,period_type').execute()
                # Create dual-key mapping: by variable_name AND by row_title
                br_mappings_dict = {}
                for m in br_mappings_response.data:
                    if m.get('variable_name'):
                        br_mappings_dict[m['variable_name']] = m
                    if m.get('row_title'):
                        br_mappings_dict[m['row_title']] = m
                print(f"✓ Loaded {len(br_mappings_response.data)} BR mappings from database")
            else:
                print("⚠ Warning: No Supabase credentials - BR XBRL tags will be skipped")
                br_mappings_dict = {}
        except Exception as e:
            print(f"⚠ Warning: Failed to load BR mappings - {str(e)}")
            import traceback
            traceback.print_exc()
            br_mappings_dict = {}
        
        if br_data_raw:
            br_table = ET.SubElement(page3, 'table')
            br_table.set('class', 'table-data')
            
            # Define column widths explicitly for proper colspan behavior
            colgroup = ET.SubElement(br_table, 'colgroup')
            ET.SubElement(colgroup, 'col', style='width: 9cm')     # Label column
            ET.SubElement(colgroup, 'col', style='width: 2cm')     # Note column
            ET.SubElement(colgroup, 'col', style='width: 2.5cm')   # Current year
            ET.SubElement(colgroup, 'col', style='width: 0.5cm')   # Spacing
            ET.SubElement(colgroup, 'col', style='width: 2.5cm')   # Previous year
            
            # Filter assets only
            br_assets = [r for r in br_data_raw if r.get('type') == 'asset']
            
            for row in br_assets:
                # NOTE: Do NOT filter by show_tag - PDF generator ignores this field
                # Only filter by amounts, always_show, block_group logic, and note_number
                
                label = row.get('label', '').strip()
                block_group = row.get('block_group', '')
                
                # Skip "Tillgångar" top-level heading
                if label == 'Tillgångar':
                    continue
                
                # Skip equity/liability headings
                if label in ['Eget kapital och skulder', 'Eget kapital', 'Bundet eget kapital', 'Fritt eget kapital', 'Tecknat men ej inbetalt kapital']:
                    continue
                
                # Determine if heading or sum based on style field (better than label matching)
                style = row.get('style', '')
                is_h2_heading = style == 'H2'
                is_h1_heading = style in ['H1', 'H3']  # H1 and H3 are treated the same in BR
                is_heading = is_h2_heading or is_h1_heading
                is_sum = style in ['S1', 'S2', 'S3', 'S4'] or label.startswith('Summa ')
                
                # Block hiding logic: if this row belongs to a block, check if block has content
                if block_group and not self._block_has_content(block_group, br_assets, 'br'):
                    continue
                
                # For heading rows: always show (with empty amounts)
                # For other rows: show if has amounts OR always_show OR is_sum OR has note_number
                if not is_heading:
                    has_note = row.get('note_number') is not None and row.get('note_number') != ''
                    if not row.get('always_show') and not is_sum and not has_note:
                        curr = self._num(row.get('current_amount', 0))
                        prev = self._num(row.get('previous_amount', 0))
                        if curr == 0 and prev == 0:
                            continue
                
                # Get note number
                note = str(row.get('note_number', '')) if row.get('note_number') else ''
                
                # Create table row with proper spacing (matching PDF BR spacing)
                tr = ET.SubElement(br_table, 'tr')
                
                # Add row spacing based on type
                # BR_H2_SPACE_BEFORE = 8pt, BR_H2_SPACE_AFTER = 12pt, sum spacing = 10pt
                row_class = ''
                if is_heading:
                    if style in ['H2', 'H0']:
                        row_class = 'pt-8-pb-12'  # 8pt before and 12pt after H2 headings
                    else:
                        row_class = 'pt-2'  # Small space before H1/H3
                elif is_sum:
                    row_class = 'pb-10'  # 10pt space after sums
                
                # For heading rows: use colspan to span entire table (no empty cells needed)
                if is_heading:
                    td_label = ET.SubElement(tr, 'td')
                    if row_class:
                        td_label.set('class', f'td-label-colspan {row_class}')
                    else:
                        td_label.set('class', 'td-label-colspan')
                    td_label.set('colspan', '5')
                    p_label = ET.SubElement(td_label, 'p')
                    if style in ['H2', 'H0']:
                        p_label.set('class', 'H2-table')
                    else:
                        p_label.set('class', 'H3-table')
                    p_label.text = label
                    continue  # Skip to next row, don't create other cells
                
                # For non-heading rows: create all cells
                # Label column
                td_label = ET.SubElement(tr, 'td')
                if row_class:
                    td_label.set('class', f'td-label {row_class}')
                else:
                    td_label.set('class', 'td-label')
                p_label = ET.SubElement(td_label, 'p')
                if is_sum:
                    p_label.set('class', 'sum-label')
                else:
                    p_label.set('class', 'P')
                p_label.text = label
                
                # Note column
                td_note = ET.SubElement(tr, 'td')
                if note and row_class:  # Only add padding if there's content
                    td_note.set('class', f'td-note {row_class}')
                else:
                    td_note.set('class', 'td-note')
                if note:  # Only add <p> if there's content
                    p_note = ET.SubElement(td_note, 'p')
                    p_note.set('class', 'P')
                    p_note.text = note
                
                # Current year amount
                td_curr = ET.SubElement(tr, 'td')
                if row_class:
                    td_curr.set('class', f'td-amount {row_class}')
                else:
                    td_curr.set('class', 'td-amount')
                # Add semibold styling for sum rows
                if is_sum:
                    td_curr.set('style', 'font-weight: 500;')
                
                if not is_heading:
                    curr_val = self._num(row.get('current_amount', 0))
                    prev_val = self._num(row.get('previous_amount', 0))
                    # Show amount if: non-zero, OR other year has value, OR always_show, OR has note
                    if curr_val != 0 or prev_val != 0 or row.get('always_show') or note:
                        # Try matching by variable_name first, then by label (row_title)
                        variable_name = row.get('variable_name')
                        mapping = None
                        if variable_name and variable_name in br_mappings_dict:
                            mapping = br_mappings_dict[variable_name]
                        elif label and label in br_mappings_dict:
                            mapping = br_mappings_dict[label]
                        
                        if mapping:
                            element_name = mapping.get('element_name')
                            # BR always uses se-gen-base namespace
                            element_qname = f'se-gen-base:{element_name}'
                            
                            # For negative values, add minus sign before XBRL tag
                            if curr_val < 0: td_curr.text = '- '
                            ix_curr = ET.SubElement(td_curr, 'ix:nonFraction')
                            ix_curr.set('contextRef', balans0_ref)
                            ix_curr.set('name', element_qname)
                            # Add ID if this row has a note (for note reference linking)
                            if note and note in self.NOTE_REFERENCE_MAPPING:
                                mapping_note = self.NOTE_REFERENCE_MAPPING[note]
                                ix_curr.set('id', f"{mapping_note['from_id']}-ar-0")
                                # Track this note reference (only add once per note)
                                if not any(ref['note_number'] == note for ref in self.note_references):
                                    self._add_note_reference(note, mapping_note['from_id'], mapping_note['to_id_pattern'])
                            ix_curr.set('unitRef', 'SEK')
                            ix_curr.set('decimals', 'INF')
                            ix_curr.set('scale', '0')
                            ix_curr.set('format', 'ixt:numspacecomma')
                            ix_curr.text = self._format_monetary_value(abs(curr_val), for_display=True)
                        else:
                            # Fallback to plain text
                            td_curr.text = self._format_monetary_value(curr_val, for_display=True)
                
                # Spacing column (always empty, never needs padding)
                td_spacing = ET.SubElement(tr, 'td')
                td_spacing.set('class', 'td-spacing')
                
                # Previous year amount
                td_prev = ET.SubElement(tr, 'td')
                if row_class:
                    td_prev.set('class', f'td-amount {row_class}')
                else:
                    td_prev.set('class', 'td-amount')
                # Add semibold styling for sum rows
                if is_sum:
                    td_prev.set('style', 'font-weight: 500;')
                
                if not is_heading:
                    # prev_val already calculated above for current year logic
                    # Show amount if: non-zero, OR other year has value, OR always_show, OR has note
                    if prev_val != 0 or curr_val != 0 or row.get('always_show') or note:
                        # Try matching by variable_name first, then by label (row_title)
                        variable_name = row.get('variable_name')
                        mapping = None
                        if variable_name and variable_name in br_mappings_dict:
                            mapping = br_mappings_dict[variable_name]
                        elif label and label in br_mappings_dict:
                            mapping = br_mappings_dict[label]
                        
                        if mapping:
                            element_name = mapping.get('element_name')
                            # BR always uses se-gen-base namespace
                            element_qname = f'se-gen-base:{element_name}'
                            
                            # For negative values, add minus sign before XBRL tag
                            if prev_val < 0: td_prev.text = '- '
                            ix_prev = ET.SubElement(td_prev, 'ix:nonFraction')
                            ix_prev.set('contextRef', balans1_ref)
                            ix_prev.set('name', element_qname)
                            # Add ID if this row has a note (for note reference linking)
                            if note and note in self.NOTE_REFERENCE_MAPPING:
                                mapping_note = self.NOTE_REFERENCE_MAPPING[note]
                                ix_prev.set('id', f"{mapping_note['from_id']}-ar-1")
                            ix_prev.set('unitRef', 'SEK')
                            ix_prev.set('decimals', 'INF')
                            ix_prev.set('scale', '0')
                            ix_prev.set('format', 'ixt:numspacecomma')
                            ix_prev.text = self._format_monetary_value(abs(prev_val), for_display=True)
                        else:
                            # Fallback to plain text
                            td_prev.text = self._format_monetary_value(prev_val, for_display=True)
                
                # Final spacing column (not needed, handled by table layout)
    
    def _render_balansrakning_skulder(self, body: ET.Element, company_data: Dict[str, Any],
                                     company_name: str, org_number: str, fiscal_year: Optional[int],
                                     prev_year: int, balans0_ref: str, balans1_ref: str, unit_ref: str):
        """Render Balansräkning (Eget kapital och skulder) section"""
        page4 = ET.SubElement(body, 'div')
        page4.set('class', 'pagebreak_before ar-page4')
        
        # Header with title (same as assets page)
        p_title = ET.SubElement(page4, 'p')
        p_title.set('class', 'H0')
        p_title.text = 'Balansräkning'
        
        # Column headers table (with underline) - must match data table structure EXACTLY
        header_table = ET.SubElement(page4, 'table')
        header_table.set('class', 'table-header')
        tr_header = ET.SubElement(header_table, 'tr')
        
        # Label column
        td_label = ET.SubElement(tr_header, 'td')
        td_label.set('class', 'th-label')
        
        # Note column
        td_not = ET.SubElement(tr_header, 'td')
        td_not.set('class', 'th-note')
        p_not = ET.SubElement(td_not, 'p')
        p_not.set('class', 'P-bold')
        p_not.text = 'Not'
        
        # Current year column
        td_year1 = ET.SubElement(tr_header, 'td')
        td_year1.set('class', 'th-year')
        p_year1 = ET.SubElement(td_year1, 'p')
        p_year1.set('class', 'P-bold')
        p_year1.text = f'{fiscal_year}-12-31' if fiscal_year else ''
        
        # Spacing column
        td_spacing_h = ET.SubElement(tr_header, 'td')
        td_spacing_h.set('class', 'th-spacing')
        
        # Previous year column
        td_year2 = ET.SubElement(tr_header, 'td')
        td_year2.set('class', 'th-year')
        p_year2 = ET.SubElement(td_year2, 'p')
        p_year2.set('class', 'P-bold')
        p_year2.text = f'{prev_year}-12-31' if prev_year else ''
        
        # BR table (equity and liabilities)
        br_data_raw = (company_data.get('brData') or 
                      company_data.get('brRows') or 
                      company_data.get('seFileData', {}).get('br_data', []))
        
        # Load BR mappings
        try:
            from supabase import create_client
            import os
            from dotenv import load_dotenv
            load_dotenv()
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_ANON_KEY")
            if supabase_url and supabase_key:
                supabase = create_client(supabase_url, supabase_key)
                br_mappings_response = supabase.table('variable_mapping_br').select('row_title,variable_name,element_name,data_type,period_type').execute()
                # Create dual-key mapping: by variable_name AND by row_title
                br_mappings_dict = {}
                for m in br_mappings_response.data:
                    if m.get('variable_name'):
                        br_mappings_dict[m['variable_name']] = m
                    if m.get('row_title'):
                        br_mappings_dict[m['row_title']] = m
                print(f"✓ Loaded {len(br_mappings_response.data)} BR mappings from database")
            else:
                print("⚠ Warning: No Supabase credentials - BR XBRL tags will be skipped")
                br_mappings_dict = {}
        except Exception as e:
            print(f"⚠ Warning: Failed to load BR mappings - {str(e)}")
            import traceback
            traceback.print_exc()
            br_mappings_dict = {}
        
        if br_data_raw:
            br_table = ET.SubElement(page4, 'table')
            br_table.set('class', 'table-data')
            
            # Define column widths explicitly for proper colspan behavior
            colgroup = ET.SubElement(br_table, 'colgroup')
            ET.SubElement(colgroup, 'col', style='width: 9cm')     # Label column
            ET.SubElement(colgroup, 'col', style='width: 2cm')     # Note column
            ET.SubElement(colgroup, 'col', style='width: 2.5cm')   # Current year
            ET.SubElement(colgroup, 'col', style='width: 0.5cm')   # Spacing
            ET.SubElement(colgroup, 'col', style='width: 2.5cm')   # Previous year
            
            # Filter equity and liabilities OR headings (H0-H3) - matching PDF logic
            # This ensures "Eget kapital", "Bundet eget kapital", etc. are included
            def _is_br_heading(item):
                return item.get('style') in ['H0', 'H1', 'H2', 'H3']
            
            br_equity_liabilities = [
                r for r in br_data_raw 
                if r.get('type') in ['equity', 'liability'] or _is_br_heading(r)
            ]
            
            # Headings that must NOT appear on equity & liabilities page
            HIDE_HEADINGS_BR_EQ = {
                'Balansräkning', 'Tillgångar', 'Tecknat men ej inbetalt kapital',
                'Anläggningstillgångar', 'Omsättningstillgångar',
                'Eget kapital och skulder',  # top-level page-1 heading, not here
            }
            
            # Force specific headings to H1 style (10pt) - matching PDF logic
            FORCE_H1_EQ = {
                'Kortfristiga skulder', 'Långfristiga skulder', 'Avsättningar',
                'Bundet eget kapital', 'Fritt eget kapital'
            }
            
            for row in br_equity_liabilities:
                # NOTE: Do NOT filter by show_tag - PDF generator ignores this field
                # Only filter by amounts, always_show, block_group logic, and note_number
                
                label = row.get('label', '').strip()
                
                # Hide specific headings that don't belong on equity/liabilities page
                if label in HIDE_HEADINGS_BR_EQ:
                    continue
                
                block_group = row.get('block_group', '')
                
                # Determine if heading or sum based on style field (better than label matching)
                style = row.get('style', '')
                
                # Force specific headings to H1 style (10pt semibold) - matching PDF logic
                if label in FORCE_H1_EQ:
                    style = 'H1'
                
                is_h2_heading = style == 'H2'
                is_h1_heading = style in ['H1', 'H3']  # H1 and H3 are treated the same in BR
                is_heading = is_h2_heading or is_h1_heading
                is_sum = style in ['S1', 'S2', 'S3', 'S4'] or label.startswith('Summa ')
                
                # Block hiding logic: if this row belongs to a block, check if block has content
                if block_group and not self._block_has_content(block_group, br_equity_liabilities, 'br'):
                    continue
                
                # For heading rows: always show (with empty amounts)
                # For other rows: show if has amounts OR always_show OR is_sum OR has note_number
                if not is_heading:
                    has_note = row.get('note_number') is not None and row.get('note_number') != ''
                    if not row.get('always_show') and not is_sum and not has_note:
                        curr = self._num(row.get('current_amount', 0))
                        prev = self._num(row.get('previous_amount', 0))
                        if curr == 0 and prev == 0:
                            continue
                
                # Get note number
                note = str(row.get('note_number', '')) if row.get('note_number') else ''
                
                # Create table row with proper spacing (matching PDF BR spacing)
                tr = ET.SubElement(br_table, 'tr')
                
                # Add row spacing based on type
                # BR_H2_SPACE_BEFORE = 8pt, BR_H2_SPACE_AFTER = 12pt, sum spacing = 10pt
                row_class = ''
                if is_heading:
                    if style in ['H2', 'H0']:
                        row_class = 'pt-8-pb-12'  # 8pt before and 12pt after H2 headings
                    else:
                        row_class = 'pt-2'  # Small space before H1/H3
                elif is_sum:
                    row_class = 'pb-10'  # 10pt space after sums
                
                # For heading rows: use colspan to span entire table (no empty cells needed)
                if is_heading:
                    td_label = ET.SubElement(tr, 'td')
                    if row_class:
                        td_label.set('class', f'td-label-colspan {row_class}')
                    else:
                        td_label.set('class', 'td-label-colspan')
                    td_label.set('colspan', '5')
                    p_label = ET.SubElement(td_label, 'p')
                    if style in ['H2', 'H0']:
                        p_label.set('class', 'H2-table')
                    else:
                        p_label.set('class', 'H3-table')
                    p_label.text = label
                    continue  # Skip to next row, don't create other cells
                
                # For non-heading rows: create all cells
                # Label column
                td_label = ET.SubElement(tr, 'td')
                if row_class:
                    td_label.set('class', f'td-label {row_class}')
                else:
                    td_label.set('class', 'td-label')
                p_label = ET.SubElement(td_label, 'p')
                if is_sum:
                    p_label.set('class', 'sum-label')
                else:
                    p_label.set('class', 'P')
                p_label.text = label
                
                # Note column
                td_note = ET.SubElement(tr, 'td')
                if note and row_class:  # Only add padding if there's content
                    td_note.set('class', f'td-note {row_class}')
                else:
                    td_note.set('class', 'td-note')
                if note:  # Only add <p> if there's content
                    p_note = ET.SubElement(td_note, 'p')
                    p_note.set('class', 'P')
                    p_note.text = note
                
                # Current year amount
                td_curr = ET.SubElement(tr, 'td')
                if row_class:
                    td_curr.set('class', f'td-amount {row_class}')
                else:
                    td_curr.set('class', 'td-amount')
                # Add semibold styling for sum rows
                if is_sum:
                    td_curr.set('style', 'font-weight: 500;')
                
                if not is_heading:
                    curr_val = self._num(row.get('current_amount', 0))
                    prev_val = self._num(row.get('previous_amount', 0))
                    # Show amount if: non-zero, OR other year has value, OR always_show, OR has note
                    if curr_val != 0 or prev_val != 0 or row.get('always_show') or note:
                        # Try matching by variable_name first, then by label (row_title)
                        variable_name = row.get('variable_name')
                        mapping = None
                        if variable_name and variable_name in br_mappings_dict:
                            mapping = br_mappings_dict[variable_name]
                        elif label and label in br_mappings_dict:
                            mapping = br_mappings_dict[label]
                        
                        if mapping:
                            element_name = mapping.get('element_name')
                            # BR always uses se-gen-base namespace
                            element_qname = f'se-gen-base:{element_name}'
                            
                            # For negative values, add minus sign before XBRL tag
                            if curr_val < 0: td_curr.text = '- '
                            ix_curr = ET.SubElement(td_curr, 'ix:nonFraction')
                            ix_curr.set('contextRef', balans0_ref)
                            ix_curr.set('name', element_qname)
                            # Add ID if this row has a note (for note reference linking)
                            if note and note in self.NOTE_REFERENCE_MAPPING:
                                mapping_note = self.NOTE_REFERENCE_MAPPING[note]
                                ix_curr.set('id', f"{mapping_note['from_id']}-ar-0")
                                # Track this note reference (only add once per note)
                                if not any(ref['note_number'] == note for ref in self.note_references):
                                    self._add_note_reference(note, mapping_note['from_id'], mapping_note['to_id_pattern'])
                            ix_curr.set('unitRef', 'SEK')
                            ix_curr.set('decimals', 'INF')
                            ix_curr.set('scale', '0')
                            ix_curr.set('format', 'ixt:numspacecomma')
                            ix_curr.text = self._format_monetary_value(abs(curr_val), for_display=True)
                        else:
                            # Fallback to plain text
                            td_curr.text = self._format_monetary_value(curr_val, for_display=True)
                
                # Spacing column
                td_spacing = ET.SubElement(tr, 'td')
                td_spacing.set('class', 'td-spacing')
                
                # Previous year amount
                td_prev = ET.SubElement(tr, 'td')
                if row_class:
                    td_prev.set('class', f'td-amount {row_class}')
                else:
                    td_prev.set('class', 'td-amount')
                # Add semibold styling for sum rows
                if is_sum:
                    td_prev.set('style', 'font-weight: 500;')
                
                if not is_heading:
                    # prev_val already calculated above for current year logic
                    # Show amount if: non-zero, OR other year has value, OR always_show, OR has note
                    if prev_val != 0 or curr_val != 0 or row.get('always_show') or note:
                        # Try matching by variable_name first, then by label (row_title)
                        variable_name = row.get('variable_name')
                        mapping = None
                        if variable_name and variable_name in br_mappings_dict:
                            mapping = br_mappings_dict[variable_name]
                        elif label and label in br_mappings_dict:
                            mapping = br_mappings_dict[label]
                        
                        if mapping:
                            element_name = mapping.get('element_name')
                            # BR always uses se-gen-base namespace
                            element_qname = f'se-gen-base:{element_name}'
                            
                            # For negative values, add minus sign before XBRL tag
                            if prev_val < 0: td_prev.text = '- '
                            ix_prev = ET.SubElement(td_prev, 'ix:nonFraction')
                            ix_prev.set('contextRef', balans1_ref)
                            ix_prev.set('name', element_qname)
                            # Add ID if this row has a note (for note reference linking)
                            if note and note in self.NOTE_REFERENCE_MAPPING:
                                mapping_note = self.NOTE_REFERENCE_MAPPING[note]
                                ix_prev.set('id', f"{mapping_note['from_id']}-ar-1")
                            ix_prev.set('unitRef', 'SEK')
                            ix_prev.set('decimals', 'INF')
                            ix_prev.set('scale', '0')
                            ix_prev.set('format', 'ixt:numspacecomma')
                            ix_prev.text = self._format_monetary_value(abs(prev_val), for_display=True)
                        else:
                            # Fallback to plain text
                            td_prev.text = self._format_monetary_value(prev_val, for_display=True)
                
                # Final spacing column (not needed, handled by table layout)
    
    def _is_heading_style_noter(self, style: str) -> bool:
        """Check if style is a heading style"""
        return style in ['H0', 'H1', 'H2', 'H3', 'H4']
    
    def _is_s2_noter(self, style: str) -> bool:
        """Check if style is S2 (subtotal)"""
        return style == 'S2'
    
    def _is_subtotal_trigger_noter(self, style: str) -> bool:
        """Check if this is a subtotal trigger (S2/TS2)"""
        return style in ['S2', 'TS2']
    
    def _is_sum_line_noter(self, style: str) -> bool:
        """Check if this is a sum line style"""
        return style in ['S1', 'S2', 'S3', 'TS1', 'TS2', 'TS3']
    
    def _has_nonzero_content_noter(self, rows: List[Dict[str, Any]]) -> bool:
        """Check if any row has non-zero amounts"""
        for row in rows:
            curr = self._num(row.get('current_amount', 0))
            prev = self._num(row.get('previous_amount', 0))
            if curr != 0 or prev != 0:
                return True
        return False
    
    def _build_visible_with_headings_noter(self, items: List[Dict[str, Any]], toggle_on: bool = False) -> List[Dict[str, Any]]:
        """Apply visibility logic with heading/subtotal triggers (mirrors PDF build_visible_with_headings_pdf)"""
        # Pass 1: base visibility (row itself is visible?)
        base_visible = []
        for it in items:
            if it.get("always_show"):
                base_visible.append(it)
                continue
            cur = self._num(it.get("current_amount", 0))
            prev = self._num(it.get("previous_amount", 0))
            if cur != 0 or prev != 0 or (it.get("toggle_show") is True and toggle_on):
                base_visible.append(it)
        
        base_ids = {it.get("row_id") for it in base_visible}
        
        # Rows allowed to TRIGGER headings/subtotals (content rows only)
        triggers = []
        for it in items:
            if self._is_sum_line_noter(it.get("style")):
                continue
            if it.get("always_show"):
                continue
            cur = self._num(it.get("current_amount", 0))
            prev = self._num(it.get("previous_amount", 0))
            if cur != 0 or prev != 0 or (it.get("toggle_show") is True and toggle_on):
                triggers.append(it)
        trigger_ids = {it.get("row_id") for it in triggers}
        
        # Pass 2: add H2/H3 headings + S2/TS2 subtotals based on nearby trigger rows
        out = []
        n = len(items)
        for i, it in enumerate(items):
            rid = it.get("row_id")
            
            # Already visible? keep it.
            if rid in base_ids:
                out.append(it)
                continue
            
            sty = it.get("style")
            
            # Headings (H2/H3): show if ANY following trigger row until next heading is present
            if self._is_heading_style_noter(sty):
                show = False
                j = i + 1
                while j < n:
                    nxt = items[j]
                    if self._is_heading_style_noter(nxt.get("style")):
                        break
                    if nxt.get("row_id") in trigger_ids:
                        show = True
                        break
                    j += 1
                if show:
                    out.append(it)
                    continue
            
            # Subtotals (S2/TS2): show if ANY preceding trigger row until previous heading/S2 is present
            if self._is_subtotal_trigger_noter(sty):
                show = False
                j = i - 1
                while j >= 0:
                    prv = items[j]
                    if self._is_heading_style_noter(prv.get("style")) or self._is_subtotal_trigger_noter(prv.get("style")):
                        break
                    if prv.get("row_id") in trigger_ids:
                        show = True
                        break
                    j -= 1
                if show:
                    out.append(it)
        
        return out
    
    def _collect_visible_note_blocks_xbrl(self, blocks: Dict[str, List[Dict[str, Any]]], 
                                          company_data: Dict[str, Any],
                                          toggle_on: bool = False,
                                          block_toggles: Optional[Dict[str, Any]] = None) -> List[tuple]:
        """Collect visible note blocks and assign note numbers (mirrors PDF _collect_visible_note_blocks)"""
        block_toggles = block_toggles or {}
        scraped_data = company_data.get('scraped_company_data', {})
        
        # Block title mapping
        block_title_map = {
            'NOT1': 'Redovisningsprinciper',
            'NOT2': 'Medelantalet anställda',
            'KONCERN': 'Andelar i koncernföretag',
            'INTRESSEFTG': 'Andelar i intresseföretag och gemensamt styrda företag',
            'BYGG': 'Byggnader och mark',
            'MASKIN': 'Maskiner och andra tekniska anläggningar',
            'INV': 'Inventarier, verktyg och installationer',
            'MAT': 'Övriga materiella anläggningstillgångar',
            'LVP': 'Andra långfristiga värdepappersinnehav',
            'FORDRKONC': 'Fordringar hos koncernföretag',
            'FORDRINTRE': 'Fordringar hos intresseföretag och gemensamt styrda företag',
            'OVRIGAFTG': 'Ägarintressen i övriga företag',
            'FORDROVRFTG': 'Fordringar hos övriga företag som det finns ett ägarintresse i',
            'EVENTUAL': 'Eventualförpliktelser',
            'SAKERHET': 'Ställda säkerheter',
            'OVRIGA': 'Övriga upplysningar',
        }
        
        # Fixed note numbers
        NOTE_NUM_FIXED = {
            'Redovisningsprinciper': 1,
            'Medelantalet anställda': 2,
            'NOT1': 1,
            'NOT2': 2,
        }
        
        # Always show notes
        ALWAYS_SHOW_NOTES = {'Redovisningsprinciper', 'Medelantalet anställda', 'NOT1', 'NOT2'}
        
        collected = []
        
        # Note order (mirrors PDF)
        note_order = [
            'NOT1', 'NOT2',
            'BYGG', 'MASKIN', 'INV', 'MAT',
            'KONCERN', 'INTRESSEFTG',
            'FORDRKONC', 'FORDRINTRE',
            'OVRIGAFTG', 'FORDROVRFTG',
            'LVP',
            'SAKERHET', 'EVENTUAL',
            'OVRIGA',
        ]
        
        # Process in order
        remaining_blocks = [b for b in blocks.keys() if b not in note_order]
        ordered_blocks = [b for b in note_order if b in blocks] + sorted(remaining_blocks)
        
        for block_name in ordered_blocks:
            if block_name not in blocks:
                continue
            
            items = blocks[block_name]
            block_title = block_title_map.get(block_name, block_name)
            
            # Special handling for NOT2 (mirror PDF generator logic)
            if block_name == 'NOT2':
                # Extract employee count - prioritize noter data
                emp_current = 0
                emp_previous = 0
                
                # Look for source item (priority order: variable_name match, then row_title match)
                src = None
                if items:
                    # First pass: Look for variable_name match
                    for r in items:
                        vn = r.get("variable_name", "")
                        if vn in {"ant_anstallda", "medelantal_anstallda_under_aret"}:
                            src = r
                            break
                    
                    # Second pass: Look for row_title match
                    if not src:
                        for r in items:
                            rt = (r.get("row_title") or "").lower()
                            if "medelantalet anställda under året" in rt or rt == "medelantalet anställda":
                                if r.get("variable_name") or r.get("current_amount") or r.get("previous_amount"):
                                    src = r
                                    break
                    
                    # Last resort: first item
                    if not src:
                        src = items[0]
                    
                    if src:
                        emp_current = self._num(src.get('current_amount', 0))
                        emp_previous = self._num(src.get('previous_amount', 0))
                
                # Fallback to scraped data for missing values (check each independently)
                if emp_previous == 0:
                    # Try scraped data for previous year
                    emp_previous = self._num(
                        scraped_data.get('medeltal_anstallda') or 
                        scraped_data.get('medeltal_anstallda_prev') or
                        scraped_data.get('employees') or
                        company_data.get("employees", 0)
                    )
                
                if emp_current == 0:
                    # Try scraped data for current year, fallback to previous
                    emp_current = self._num(scraped_data.get('medeltal_anstallda_cur') or emp_previous)
                
                # Force single row with canonical variable name
                items = [{
                    "row_id": 1,
                    "row_title": "Medelantalet anställda under året",
                    "current_amount": emp_current,
                    "previous_amount": emp_previous,
                    "style": "NORMAL",
                    "variable_name": "ant_anstallda",
                    "always_show": True,
                    "toggle_show": False,
                }]
            
            # Check block type
            is_ovriga = (block_name == 'OVRIGA')
            is_eventual = (block_name == 'EVENTUAL')
            is_sakerhet = (block_name == 'SAKERHET')
            
            # EVENTUAL/SAKERHET require explicit toggle
            if is_eventual or is_sakerhet:
                toggle_key = 'eventual-visibility' if is_eventual else 'sakerhet-visibility'
                block_visible = bool(block_toggles.get(toggle_key, False))
                if not block_visible:
                    continue
            
            # OVRIGA visibility
            if is_ovriga:
                moderbolag = scraped_data.get('moderbolag')
                ovriga_visible = bool(block_toggles.get('ovriga-visibility', False))
                if not ovriga_visible and not moderbolag:
                    # Check for content
                    has_content = any(
                        (it.get('variable_text') and it.get('variable_text').strip()) or
                        self._num(it.get('current_amount', 0)) != 0 or
                        self._num(it.get('previous_amount', 0)) != 0
                        for it in items
                    )
                    if not has_content:
                        continue
            
            # Force always_show for NOT1/NOT2
            force_always = (block_name in ALWAYS_SHOW_NOTES or block_title in ALWAYS_SHOW_NOTES)
            if force_always:
                for it in items:
                    it["always_show"] = True
            
            # For OVRIGA, force always_show for text items
            if is_ovriga:
                for it in items:
                    if it.get('variable_text') and str(it.get('variable_text')).strip():
                        it["always_show"] = True
            
            # Apply visibility logic
            visible = self._build_visible_with_headings_noter(items, toggle_on=toggle_on)
            
            # Skip rows before first heading (except for NOT1/NOT2, SAKERHET, EVENTUAL, OVRIGA)
            if block_name not in ['NOT1', 'NOT2'] and not (is_eventual or is_sakerhet or is_ovriga):
                pruned = []
                seen_heading = False
                for r in visible:
                    if self._is_heading_style_noter(r.get("style")):
                        seen_heading = True
                        pruned.append(r)
                    elif seen_heading:
                        pruned.append(r)
                visible = pruned
            
            # Skip if no visible items (unless forced)
            if not visible:
                if not force_always:
                    continue
            
            # Skip if no non-zero content (unless forced or OVRIGA with toggle)
            if not force_always and not (is_ovriga and block_toggles.get('ovriga-visibility')):
                if not self._has_nonzero_content_noter(visible):
                    continue
            
            collected.append((block_name, block_title, visible))
        
        # Assign note numbers
        result = []
        next_no = 3
        for block_name, block_title, visible in collected:
            if block_name in NOTE_NUM_FIXED:
                note_number = NOTE_NUM_FIXED[block_name]
            elif block_title in NOTE_NUM_FIXED:
                note_number = NOTE_NUM_FIXED[block_title]
            else:
                note_number = next_no
                next_no += 1
            
            result.append((block_name, block_title, note_number, visible))
        
        return result
    
    def _render_noter(self, body: ET.Element, company_data: Dict[str, Any],
                     company_name: str, org_number: str, fiscal_year: Optional[int],
                     prev_year: int, period0_ref: str, period1_ref: str,
                     balans0_ref: str, balans1_ref: str, unit_ref: str):
        """Render Noter section mirroring PDF generator logic"""
        # Create a flexible page container for Noter (no fixed height, allows natural pagination)
        page5 = ET.SubElement(body, 'div')
        page5.set('class', 'pagebreak_before ar-page-noter pagebreak-before')
        
        # Noter title
        p_title = ET.SubElement(page5, 'p')
        p_title.set('class', 'H0')
        p_title.text = 'Noter'
        
        # Load noter data and mappings
        noter_data_raw = (company_data.get('noterData') or
                         company_data.get('noter_data') or
                         company_data.get('seFileData', {}).get('noter_data', []))
        
        noter_toggle_on = company_data.get('noterToggleOn', False)
        noter_block_toggles = company_data.get('noterBlockToggles', {})
        
        # Load noter mappings from variable_mapping_noter
        try:
            from supabase import create_client
            import os
            from dotenv import load_dotenv
            import traceback
            load_dotenv()
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_ANON_KEY")
            if supabase_url and supabase_key:
                supabase = create_client(supabase_url, supabase_key)
                # Select item_name, Datatyp, period_type from variable_mapping_noter
                noter_mappings_response = supabase.table('variable_mapping_noter').select('variable_name,item_name,Datatyp,period_type').execute()
                noter_mappings_dict = {m['variable_name']: m for m in noter_mappings_response.data if m.get('variable_name')}
                print(f"✓ Loaded {len(noter_mappings_dict)} Noter mappings")
            else:
                noter_mappings_dict = {}
        except Exception as e:
            print(f"⚠ Warning: Failed to load Noter mappings - {e}")
            traceback.print_exc()
            noter_mappings_dict = {}
        
        # Group notes by block
        blocks = {}
        for note in noter_data_raw:
            block = note.get('block') or 'OVRIGA'
            if block not in blocks:
                blocks[block] = []
            blocks[block].append(note)
        
        # Collect and filter blocks with note numbers
        rendered_blocks = self._collect_visible_note_blocks_xbrl(blocks, company_data, noter_toggle_on, noter_block_toggles)
        
        # Render each block with pagination (create new pages as needed)
        current_page = page5
        page_note_count = 0
        page_counter = 5
        
        for idx, (block_name, block_title, note_number, visible_items) in enumerate(rendered_blocks):
            # Estimate if we need a new page (rough heuristic)
            # NOT1 is large, others vary. Create new page after 2-3 notes or if NOT1 would be 2nd+ on page
            if page_note_count > 0 and (
                (block_name == 'NOT1' and page_note_count >= 1) or  # NOT1 needs its own page if not first
                (page_note_count >= 3)  # Or after 3 notes
            ):
                # Create new page
                page_counter += 1
                current_page = ET.SubElement(body, 'div')
                current_page.set('class', 'pagebreak_before ar-page-noter pagebreak-before')
                page_note_count = 0
            
            # Render note on current page
            self._render_note_block_xbrl(current_page, block_name, block_title, note_number, visible_items, 
                                        company_data, fiscal_year, prev_year, period0_ref, period1_ref,
                                        balans0_ref, balans1_ref, unit_ref, noter_mappings_dict)
            page_note_count += 1
    
    def _render_note_block_xbrl(self, page: ET.Element, block_name: str, block_title: str,
                                note_number: int, visible_items: List[Dict[str, Any]], company_data: Dict[str, Any],
                                fiscal_year: int, prev_year: int, period0_ref: str, period1_ref: str,
                                balans0_ref: str, balans1_ref: str, unit_ref: str, noter_mappings_dict: Dict[str, Any]):
        """Render a single note block with proper XBRL tagging (mirrors PDF _render_note_block)"""
        
        # Format note title
        title = block_title.replace(" – ", " ").replace(" - ", " ").replace("–", " ").replace("-", " ")
        title = " ".join(title.split())  # Clean multiple spaces
        
        # Create a container div for the note (to keep it together and control page breaks)
        note_container = ET.SubElement(page, 'div')
        note_container.set('class', 'note-container')
        
        # Note title (H1 heading - no extra spacing since container has margin-top)
        # Per Bolagsverket: heading gets simple id="note-{number}" format
        p_heading = ET.SubElement(note_container, 'p')
        p_heading.set('class', 'H1 mt-0')
        p_heading.set('id', f'note-{note_number}')  # Simple format for navigation
        p_heading.text = f'Not {note_number}  {title}'
        
        # Find the note reference pattern for this note (for ix:nonFraction IDs)
        note_id_base = None
        for ref_note_num, ref_data in self.NOTE_REFERENCE_MAPPING.items():
            if str(note_number) == ref_note_num:
                note_id_base = ref_data['to_id_pattern']
                break
        
        # Counter for unique IDs within this note (id1, id2, id3, etc.)
        value_counter = {'count': 1}
        
        #Special handling for NOT1 (Redovisningsprinciper - text + depreciation table)
        if block_name == 'NOT1':
            # Render text paragraphs with XBRL tagging
            for note in visible_items:
                text = note.get('variable_text', note.get('row_title', ''))
                variable_name = note.get('variable_name', '')
                
                if text:
                    p_text = ET.SubElement(note_container, 'p')
                    p_text.set('class', 'P noter-text-paragraph')
                    
                    # Add XBRL tagging for text content
                    mapping = noter_mappings_dict.get(variable_name)
                    if mapping:
                        element_name = mapping.get('item_name')
                        if element_name:
                            ix_text = ET.SubElement(p_text, 'ix:nonNumeric')
                            ix_text.set('name', f'se-gen-base:{element_name}')
                            ix_text.set('contextRef', period0_ref)
                            ix_text.text = text
                        else:
                            p_text.text = text
                    else:
                        p_text.text = text
            
            # Build depreciation table
            noter_data = company_data.get('noterData', [])
            avskrtid_bygg = next((self._num(item.get('current_amount', 0)) for item in noter_data if item.get('variable_name') == 'avskrtid_bygg'), 0)
            avskrtid_mask = next((self._num(item.get('current_amount', 0)) for item in noter_data if item.get('variable_name') == 'avskrtid_mask'), 0)
            avskrtid_inv = next((self._num(item.get('current_amount', 0)) for item in noter_data if item.get('variable_name') == 'avskrtid_inv'), 0)
            avskrtid_ovriga = next((self._num(item.get('current_amount', 0)) for item in noter_data if item.get('variable_name') == 'avskrtid_ovriga'), 0)
            
            table = ET.SubElement(note_container, 'table')
            table.set('class', 'noter-table-depr')
            
            # Header row
            tr_h = ET.SubElement(table, 'tr')
            td_h1 = ET.SubElement(tr_h, 'td')
            td_h1.set('class', 'noter-depr-header-label')
            p_h1 = ET.SubElement(td_h1, 'p')
            p_h1.set('class', 'P noter-text-bold')
            p_h1.text = 'Anläggningstillgångar'
            
            td_h2 = ET.SubElement(tr_h, 'td')
            td_h2.set('class', 'noter-depr-header-amount')
            p_h2 = ET.SubElement(td_h2, 'p')
            p_h2.set('class', 'P noter-text-bold')
            p_h2.text = 'År'
            
            # Data rows with XBRL tagging for depreciation periods
            depr_items = [
                ('Byggnader & mark', avskrtid_bygg, 'avskr-princip-bygg'),
                ('Maskiner och andra tekniska anläggningar', avskrtid_mask, 'avskr-princip-mask'),
                ('Inventarier, verktyg och installationer', avskrtid_inv, 'avskr-princip-inv'),
                ('Övriga materiella anläggningstillgångar', avskrtid_ovriga, 'avskr-princip-ovriga'),
            ]
            
            for label, val, tuple_id in depr_items:
                tr = ET.SubElement(table, 'tr')
                td1 = ET.SubElement(tr, 'td')
                td1.set('class', 'noter-depr-data-label')
                p1 = ET.SubElement(td1, 'p')
                p1.set('class', 'P noter-text')
                p1.text = label
                
                td2 = ET.SubElement(tr, 'td')
                td2.set('class', 'noter-depr-data-amount')
                
                # Add XBRL tagging for depreciation period (year value)
                val_text = f"{int(val)} år" if val else '0 år'
                ix_period = ET.SubElement(td2, 'ix:nonNumeric')
                ix_period.set('contextRef', period0_ref)
                ix_period.set('name', 'se-gen-base:AvskrivningsprincipMateriellAnlaggningstillgangNyttjandeperiod')
                ix_period.set('order', '2.0')
                ix_period.set('tupleRef', tuple_id)
                ix_period.text = val_text
            
            return
        
        # Special handling for OVRIGA (text note with moderbolag)
        if block_name == 'OVRIGA':
            scraped_data = company_data.get('scraped_company_data', {})
            moderbolag = scraped_data.get('moderbolag')
            
            # Check for variable_text from items with XBRL tagging
            has_text = False
            for item in visible_items:
                variable_text = item.get('variable_text', '').strip()
                variable_name = item.get('variable_name', '')
                
                if variable_text:
                    p_text = ET.SubElement(note_container, 'p')
                    p_text.set('class', 'P noter-text-paragraph')
                    
                    # Add XBRL tagging for text content
                    mapping = noter_mappings_dict.get(variable_name)
                    if mapping:
                        element_name = mapping.get('item_name')
                        if element_name:
                            ix_text = ET.SubElement(p_text, 'ix:nonNumeric')
                            ix_text.set('name', f'se-gen-base:{element_name}')
                            ix_text.set('contextRef', period0_ref)
                            ix_text.text = variable_text
                        else:
                            p_text.text = variable_text
                    else:
                        p_text.text = variable_text
                    has_text = True
            
            # If no variable_text but moderbolag exists, render it (with XBRL tag)
            if not has_text and moderbolag:
                moderbolag_orgnr = scraped_data.get('moderbolag_orgnr', '')
                sate = scraped_data.get('säte', '')
                moder_sate = scraped_data.get('moderbolag_säte', sate)
                
                text = f"Bolaget är dotterbolag till {moderbolag}"
                if moderbolag_orgnr:
                    text += f" med organisationsnummer {moderbolag_orgnr}"
                text += f", som har sitt säte i {moder_sate}."
                
                p_text = ET.SubElement(note_container, 'p')
                p_text.set('class', 'P noter-text-paragraph')
                
                # Tag with NotUpplysningModerforetag
                ix_text = ET.SubElement(p_text, 'ix:nonNumeric')
                ix_text.set('name', 'se-gen-base:NotUpplysningModerforetag')
                ix_text.set('contextRef', period0_ref)
                ix_text.text = text
            
            return
        
        # For NOT2 and other notes, render as table
        # Determine header row (dates or years for NOT2)
        if block_name == 'NOT2':
            header_col1 = ''
            header_col2 = str(fiscal_year)
            header_col3 = str(prev_year)
        else:
            cur_end = company_data.get("currentPeriodEndDate") or f"{fiscal_year}-12-31"
            prev_end = company_data.get("previousPeriodEndDate") or f"{prev_year}-12-31"
            header_col1 = ''
            header_col2 = cur_end
            header_col3 = prev_end
        
        # Build table using semantic CSS classes
        table = ET.SubElement(note_container, 'table')
        table.set('class', 'noter-table')
        
        # Header row
        tr_header = ET.SubElement(table, 'tr')
        td_h1 = ET.SubElement(tr_header, 'td')
        td_h1.set('class', 'noter-header-label')
        p_h1 = ET.SubElement(td_h1, 'p')
        p_h1.set('class', 'P noter-text-header')
        p_h1.text = header_col1
        
        td_h2 = ET.SubElement(tr_header, 'td')
        td_h2.set('class', 'noter-header-amount')
        p_h2 = ET.SubElement(td_h2, 'p')
        p_h2.set('class', 'P noter-text-header')
        p_h2.text = header_col2
        
        td_h3 = ET.SubElement(tr_header, 'td')
        td_h3.set('class', 'noter-header-amount')
        p_h3 = ET.SubElement(td_h3, 'p')
        p_h3.set('class', 'P noter-text-header')
        p_h3.text = header_col3
        
        # Sub-headings that need extra space
        heading_kick = {"avskrivningar", "uppskrivningar", "nedskrivningar"}
        
        # Data rows
        for i, it in enumerate(visible_items):
            style = it.get('style', '')
            row_title = it.get('row_title', '')
            lbl = row_title.strip().lower()
            variable_name = it.get('variable_name', '')
            
            is_heading = self._is_heading_style_noter(style)
            is_s2 = self._is_s2_noter(style)
            is_sum = lbl.startswith('utgående ') or lbl.startswith('utgaende ') or lbl.startswith('summa ') or is_s2
            is_redv = 'redovisat värde' in lbl or 'redovisat varde' in lbl
            
            # Get amounts
            if is_heading:
                curr_fmt = ''
                prev_fmt = ''
            else:
                cur = self._num(it.get('current_amount', 0))
                prev = self._num(it.get('previous_amount', 0))
                curr_fmt = self._format_monetary_value(cur, for_display=True)
                prev_fmt = self._format_monetary_value(prev, for_display=True)
            
            # Determine semantic cell class based on row type
            is_section_row = (is_heading and style in ['H1', 'H2', 'H3'] and lbl in heading_kick) or is_redv
            label_class = 'noter-section-label' if is_section_row else 'noter-data-label'
            amount_class = 'noter-section-amount' if is_section_row else 'noter-data-amount'
            
            # Determine text class
            text_class = 'P noter-text-bold' if (is_heading or is_sum or is_redv) else 'P noter-text'
            amount_text_class = 'P noter-text-bold' if (is_sum or is_redv) else 'P noter-text'
            
            tr = ET.SubElement(table, 'tr')
            
            # Label column
            td_label = ET.SubElement(tr, 'td')
            td_label.set('class', label_class)
            p_label = ET.SubElement(td_label, 'p')
            p_label.set('class', text_class)
            p_label.text = row_title
            
            # Current amount column
            td_curr = ET.SubElement(tr, 'td')
            td_curr.set('class', amount_class)
            # Add semibold styling for sum and redv rows (when XBRL tags are added directly to td)
            if is_sum or is_redv:
                td_curr.set('style', 'font-weight: 500;')
            p_curr = ET.SubElement(td_curr, 'p')
            p_curr.set('class', amount_text_class)
            
            if not is_heading:
                # Add XBRL tagging
                mapping = noter_mappings_dict.get(variable_name)
                if mapping and curr_fmt:
                    element_name = mapping.get('item_name')
                    period_type = mapping.get('period_type', 'duration')
                    data_type = mapping.get('Datatyp', 'xbrli:monetaryItemType')
                    
                    if element_name:
                        namespace = 'se-gen-base'  # Default namespace for noter
                        element_qname = f'{namespace}:{element_name}'
                        
                        context_ref = period0_ref if period_type == 'duration' else balans0_ref
                        cur = self._num(it.get('current_amount', 0))
                        
                        # Use ix:nonNumeric for string/text types, ix:nonFraction for monetary/numeric
                        if 'stringItemType' in data_type or 'enumeration' in data_type:
                            ix_curr = ET.SubElement(p_curr, 'ix:nonNumeric')
                            ix_curr.set('name', element_qname)
                            ix_curr.set('contextRef', context_ref)
                            ix_curr.text = curr_fmt
                        else:
                            # Monetary or numeric value - tag directly in <td>, remove <p>
                            td_curr.remove(p_curr)
                            
                            # Handle negative values
                            if cur < 0:
                                td_curr.text = '-'
                            
                            ix_curr = ET.SubElement(td_curr, 'ix:nonFraction')
                            ix_curr.set('contextRef', context_ref)
                            ix_curr.set('name', element_qname)
                            # Add unique ID for this value (per Bolagsverket pattern)
                            if note_id_base:
                                year_suffix = '-ar-0' if context_ref in ['period0', 'balans0'] else '-ar-1'
                                ix_curr.set('id', f"{note_id_base}{year_suffix}-id{value_counter['count']}")
                                value_counter['count'] += 1
                            # Note 2 (Medelantalet anställda) uses antal-anstallda unit, others use SEK
                            unit_ref = 'antal-anstallda' if note_number == 2 else 'SEK'
                            ix_curr.set('unitRef', unit_ref)
                            ix_curr.set('decimals', 'INF')  # Exact value
                            ix_curr.set('scale', '0')  # No scaling
                            ix_curr.set('format', 'ixt:numspacecomma')  # Space thousands separator
                            ix_curr.text = self._format_monetary_value(abs(cur), for_display=True)
                    else:
                        p_curr.text = curr_fmt
                else:
                    p_curr.text = curr_fmt
            
            # Previous amount column
            td_prev = ET.SubElement(tr, 'td')
            td_prev.set('class', amount_class)
            # Add semibold styling for sum and redv rows (when XBRL tags are added directly to td)
            if is_sum or is_redv:
                td_prev.set('style', 'font-weight: 500;')
            p_prev = ET.SubElement(td_prev, 'p')
            p_prev.set('class', amount_text_class)
            
            if not is_heading:
                # Add XBRL tagging
                mapping = noter_mappings_dict.get(variable_name)
                if mapping and prev_fmt:
                    element_name = mapping.get('item_name')
                    period_type = mapping.get('period_type', 'duration')
                    data_type = mapping.get('Datatyp', 'xbrli:monetaryItemType')
                    
                    if element_name:
                        namespace = 'se-gen-base'  # Default namespace for noter
                        element_qname = f'{namespace}:{element_name}'
                        
                        context_ref = period1_ref if period_type == 'duration' else balans1_ref
                        prev = self._num(it.get('previous_amount', 0))
                        
                        # Use ix:nonNumeric for string/text types, ix:nonFraction for monetary/numeric
                        if 'stringItemType' in data_type or 'enumeration' in data_type:
                            ix_prev = ET.SubElement(p_prev, 'ix:nonNumeric')
                            ix_prev.set('name', element_qname)
                            ix_prev.set('contextRef', context_ref)
                            ix_prev.text = prev_fmt
                        else:
                            # Monetary or numeric value - tag directly in <td>, remove <p>
                            td_prev.remove(p_prev)
                            
                            # Handle negative values
                            if prev < 0:
                                td_prev.text = '-'
                            
                            ix_prev = ET.SubElement(td_prev, 'ix:nonFraction')
                            ix_prev.set('contextRef', context_ref)
                            ix_prev.set('name', element_qname)
                            # Add unique ID for this value (per Bolagsverket pattern)
                            if note_id_base:
                                year_suffix = '-ar-0' if context_ref in ['period0', 'balans0'] else '-ar-1'
                                ix_prev.set('id', f"{note_id_base}{year_suffix}-id{value_counter['count']}")
                                value_counter['count'] += 1
                            # Note 2 (Medelantalet anställda) uses antal-anstallda unit, others use SEK
                            unit_ref = 'antal-anstallda' if note_number == 2 else 'SEK'
                            ix_prev.set('unitRef', unit_ref)
                            ix_prev.set('decimals', 'INF')  # Exact value
                            ix_prev.set('scale', '0')  # No scaling
                            ix_prev.set('format', 'ixt:numspacecomma')  # Space thousands separator
                            ix_prev.text = self._format_monetary_value(abs(prev), for_display=True)
                    else:
                        p_prev.text = prev_fmt
                else:
                    p_prev.text = prev_fmt
    
    def _add_general_info_facts(self, company_data: Dict[str, Any], start_date: Optional[str], end_date: Optional[str]):
        """Add general company information facts (se-cd-base namespace)"""
        company_info = company_data.get('seFileData', {}).get('company_info', {})
        
        # Company name
        company_name = (company_data.get('company_name') 
                       or company_data.get('companyName')
                       or company_info.get('company_name'))
        if company_name:
            self.add_fact(
                element_name='ForetagetsNamn',
                namespace='se-cd-base',
                value=company_name,
                period_type='duration',
                start_date=start_date,
                end_date=end_date,
                data_type='stringItemType'
            )
        
        # Organization number
        org_number = (company_data.get('organization_number')
                     or company_data.get('organizationNumber')
                     or company_info.get('organization_number'))
        if org_number:
            # Remove dashes from org number
            org_number_clean = str(org_number).replace('-', '')
            self.add_fact(
                element_name='Organisationsnummer',
                namespace='se-cd-base',
                value=org_number_clean,
                period_type='duration',
                start_date=start_date,
                end_date=end_date,
                data_type='stringItemType'
            )
        
        # Country (Sweden)
        self.add_fact(
            element_name='LandForetagetsSateList',
            namespace='se-cd-base',
            value='LandSverigeMember',
            period_type='duration',
            start_date=start_date,
            end_date=end_date,
            data_type='enum:enumerationItemType'
        )
        
        # Registered office (Säte)
        sate = company_info.get('sate') or company_info.get('säte')
        if sate:
            self.add_fact(
                element_name='ForetagetsSate',
                namespace='se-cd-base',
                value=sate,
                period_type='duration',
                start_date=start_date,
                end_date=end_date,
                data_type='stringItemType'
            )
        
        # Language (Swedish)
        self.add_fact(
            element_name='SprakHandlingUpprattadList',
            namespace='se-cd-base',
            value='SprakSvenskaMember',
            period_type='duration',
            start_date=start_date,
            end_date=end_date,
            data_type='enum:enumerationItemType'
        )
        
        # Currency (SEK)
        self.add_fact(
            element_name='RedovisningsvalutaHandlingList',
            namespace='se-cd-base',
            value='RedovisningsvalutaSEKMember',
            period_type='duration',
            start_date=start_date,
            end_date=end_date,
            data_type='enum:enumerationItemType'
        )
        
        # Amount format (whole currency units)
        self.add_fact(
            element_name='BeloppsformatList',
            namespace='se-cd-base',
            value='BeloppsformatNormalformMember',
            period_type='duration',
            start_date=start_date,
            end_date=end_date,
            data_type='enum:enumerationItemType'
        )
    
    def _add_signature_facts(self, company_data: Dict[str, Any], end_date: Optional[str]):
        """Add signature and auditor information facts"""
        signering_data = company_data.get('signeringData') or company_data.get('signering_data', {})
        
        # Process företrädare (representatives)
        foretradare = signering_data.get('UnderskriftForetradare', [])
        for idx, person in enumerate(foretradare):
            # Create tuple for each signer
            tilltalsnamn = person.get('UnderskriftHandlingTilltalsnamn', '')
            efternamn = person.get('UnderskriftHandlingEfternamn', '')
            roll = person.get('UnderskriftHandlingRoll', '')
            datum = person.get('UnderskriftHandlingDagForUndertecknande', end_date)
            
            if tilltalsnamn or efternamn:
                # Note: XBRL tuples are complex - for now, we'll add individual facts
                # In a full implementation, these would be in tuple structures
                if tilltalsnamn:
                    self.add_fact(
                        element_name='UnderskriftHandlingTilltalsnamn',
                        namespace='se-gen-base',
                        value=tilltalsnamn,
                        period_type='duration',
                        start_date=None,
                        end_date=end_date,
                        data_type='stringItemType'
                    )
                if efternamn:
                    self.add_fact(
                        element_name='UnderskriftHandlingEfternamn',
                        namespace='se-gen-base',
                        value=efternamn,
                        period_type='duration',
                        start_date=None,
                        end_date=end_date,
                        data_type='stringItemType'
                    )
                if roll:
                    self.add_fact(
                        element_name='UnderskriftHandlingRoll',
                        namespace='se-gen-base',
                        value=roll,
                        period_type='duration',
                        start_date=None,
                        end_date=end_date,
                        data_type='stringItemType'
                    )
                if datum:
                    self.add_fact(
                        element_name='UndertecknandeDatum',
                        namespace='se-gen-base',
                        value=self._format_date(str(datum)),
                        period_type='duration',
                        start_date=None,
                        end_date=end_date,
                        data_type='dateItemType'
                    )
        
        # Process revisor (auditor)
        revisorer = signering_data.get('UnderskriftAvRevisor', [])
        for idx, person in enumerate(revisorer):
            tilltalsnamn = person.get('UnderskriftHandlingTilltalsnamn', '')
            efternamn = person.get('UnderskriftHandlingEfternamn', '')
            titel = person.get('UnderskriftHandlingTitel', '')
            huvudansvarig = person.get('UnderskriftRevisorspateckningRevisorHuvudansvarig', False)
            
            if tilltalsnamn or efternamn:
                if tilltalsnamn:
                    self.add_fact(
                        element_name='UnderskriftHandlingTilltalsnamn',
                        namespace='se-gen-base',
                        value=tilltalsnamn,
                        period_type='duration',
                        start_date=None,
                        end_date=end_date,
                        data_type='stringItemType'
                    )
                if efternamn:
                    self.add_fact(
                        element_name='UnderskriftHandlingEfternamn',
                        namespace='se-gen-base',
                        value=efternamn,
                        period_type='duration',
                        start_date=None,
                        end_date=end_date,
                        data_type='stringItemType'
                    )
                if titel:
                    self.add_fact(
                        element_name='UnderskriftHandlingTitel',
                        namespace='se-gen-base',
                        value=titel,
                        period_type='duration',
                        start_date=None,
                        end_date=end_date,
                        data_type='stringItemType'
                    )


def generate_xbrl_instance_document(company_data: Dict[str, Any]) -> bytes:
    """
    Generate XBRL instance document from company data
    
    Args:
        company_data: Dictionary containing parsed financial data (RR, BR, company info)
    
    Returns:
        XBRL XML document as bytes
    """
    generator = XBRLGenerator()
    xbrl_xml = generator.generate_xbrl_document(company_data)
    return xbrl_xml.encode('utf-8')

