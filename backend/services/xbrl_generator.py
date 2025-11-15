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
    
    # XBRL namespaces (updated to match Swedish taxonomy)
    NAMESPACES = {
        'xbrli': 'http://www.xbrl.org/2003/instance',
        'xbrldi': 'http://xbrl.org/2006/xbrldi',
        'xlink': 'http://www.w3.org/1999/xlink',
        'link': 'http://www.xbrl.org/2003/linkbase',
        'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
        'ix': 'http://www.xbrl.org/2013/inlineXBRL',
        'ixt': 'http://www.xbrl.org/inlineXBRL/transformation/2010-04-20',
        'iso4217': 'http://www.xbrl.org/2003/iso4217',
        'se-gen-base': 'http://www.taxonomier.se/se/fr/gen-base/2021-10-31',
        'se-cd-base': 'http://www.taxonomier.se/se/fr/cd-base/2021-10-31',
        'se-gaap-ext': 'http://www.taxonomier.se/se/fr/gaap/gaap-ext/2021-10-31',
        'se-mem-base': 'http://www.taxonomier.se/se/fr/mem-base/2021-10-31',
        'se-bol-base': 'http://www.bolagsverket.se/se/fr/comp-base/2020-12-01',
        'se-ar-base': 'http://www.far.se/se/fr/ar/base/2020-12-01',
        'se-misc-base': 'http://www.taxonomier.se/se/fr/misc-base/2017-09-30',
        'se-k2-type': 'http://www.taxonomier.se/se/fr/k2/datatype',
    }
    
    def __init__(self):
        self.contexts = {}
        self.units = {}
        self.facts = []
        self.context_counter = 0
        self.unit_counter = 0
    
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
                               is_current: bool = True) -> str:
        """Get or create a context ID for the given period with semantic naming"""
        if period_type == 'duration':
            key = f"duration_{start_date}_{end_date}"
            # Use semantic IDs: period0 for current year, period1 for previous
            context_id = "period0" if is_current else "period1"
        else:
            key = f"instant_{instant_date}"
            # Use semantic IDs: instant0 for current year end, instant1 for previous
            context_id = "instant0" if is_current else "instant1"
        
        if key not in self.contexts:
            self.contexts[key] = {
                'id': context_id,
                'period_type': period_type,
                'start_date': start_date,
                'end_date': end_date,
                'instant_date': instant_date
            }
        return self.contexts[key]['id']
    
    def _get_or_create_unit(self, currency: str = 'SEK') -> str:
        """Get or create a unit ID for the given currency"""
        key = f"unit_{currency}"
        if key not in self.units:
            self.unit_counter += 1
            unit_id = f"u{self.unit_counter}"
            self.units[key] = {
                'id': unit_id,
                'currency': currency
            }
        return self.units[key]['id']
    
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
        
        # Load mappings to get element_name and namespace
        try:
            from supabase import create_client
            import os
            from dotenv import load_dotenv
            load_dotenv()
            
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_ANON_KEY")
            if supabase_url and supabase_key:
                supabase = create_client(supabase_url, supabase_key)
                
                # Load RR mappings
                rr_mappings_response = supabase.table('variable_mapping_rr').select('variable_name,element_name,tillhor').execute()
                rr_mappings_dict = {m['variable_name']: m for m in rr_mappings_response.data if m.get('variable_name')}
                
                # Load BR mappings
                br_mappings_response = supabase.table('variable_mapping_br').select('variable_name,element_name,tillhor').execute()
                br_mappings_dict = {m['variable_name']: m for m in br_mappings_response.data if m.get('variable_name')}
                
                # Load FB mappings (if table exists)
                try:
                    fb_mappings_response = supabase.table('variable_mapping_fb').select('variable_name,element_name,tillhor').execute()
                    fb_mappings_dict = {m['variable_name']: m for m in fb_mappings_response.data if m.get('variable_name')}
                except:
                    fb_mappings_dict = {}
                
                # Load Noter mappings
                try:
                    noter_mappings_response = supabase.table('variable_mapping_noter').select('variable_name,element_name,tillhor').execute()
                    noter_mappings_dict = {m['variable_name']: m for m in noter_mappings_response.data if m.get('variable_name')}
                except:
                    noter_mappings_dict = {}
            else:
                rr_mappings_dict = {}
                br_mappings_dict = {}
                fb_mappings_dict = {}
                noter_mappings_dict = {}
        except Exception as e:
            print(f"Warning: Could not load mappings for XBRL: {e}")
            rr_mappings_dict = {}
            br_mappings_dict = {}
            fb_mappings_dict = {}
            noter_mappings_dict = {}
        
        # Process RR data (Income Statement - duration)
        rr_data = company_data.get('rrData') or company_data.get('rrRows') or company_data.get('seFileData', {}).get('rr_data', [])
        for item in rr_data:
            if not item.get('show_amount'):
                continue  # Skip header rows
            
            variable_name = item.get('variable_name')
            if not variable_name:
                continue
            
            # Get element_name and namespace from mapping
            mapping = rr_mappings_dict.get(variable_name, {})
            element_name = mapping.get('element_name') or variable_name
            namespace = mapping.get('tillhor') or 'se-gen-base'
            
            value = item.get('current_amount')
            
            if value is None or value == 0:
                if not item.get('always_show'):
                    continue  # Skip zero values unless always_show is True
            
            # Add current year fact
            self.add_fact(
                element_name=element_name,
                namespace=namespace,
                value=value or 0,
                period_type='duration',
                start_date=start_date,
                end_date=end_date,
                data_type='monetaryItemType'
            )
            
            # Add previous year fact if available
            prev_value = item.get('previous_amount')
            if prev_value is not None:
                # Create previous year context
                prev_start = self._format_date(f"{fiscal_year - 1}0101") if fiscal_year else None
                prev_end = self._format_date(f"{fiscal_year - 1}1231") if fiscal_year else None
                
                self.add_fact(
                    element_name=element_name,
                    namespace=namespace,
                    value=prev_value,
                    period_type='duration',
                    start_date=prev_start,
                    end_date=prev_end,
                    data_type='monetaryItemType',
                    is_current=False
                )
        
        # Process BR data (Balance Sheet - instant)
        br_data = company_data.get('brData') or company_data.get('brRows') or company_data.get('seFileData', {}).get('br_data', [])
        for item in br_data:
            if not item.get('show_amount'):
                continue  # Skip header rows
            
            variable_name = item.get('variable_name')
            if not variable_name:
                continue
            
            # Get element_name and namespace from mapping
            mapping = br_mappings_dict.get(variable_name, {})
            element_name = mapping.get('element_name') or variable_name
            namespace = mapping.get('tillhor') or 'se-gen-base'
            
            value = item.get('current_amount')
            
            if value is None or value == 0:
                if not item.get('always_show'):
                    continue  # Skip zero values unless always_show is True
            
            # Add current year fact (instant)
            self.add_fact(
                element_name=element_name,
                namespace=namespace,
                value=value or 0,
                period_type='instant',
                instant_date=end_date,
                data_type='monetaryItemType'
            )
            
            # Add previous year fact if available
            prev_value = item.get('previous_amount')
            if prev_value is not None:
                prev_end = self._format_date(f"{fiscal_year - 1}1231") if fiscal_year else None
                
                self.add_fact(
                    element_name=element_name,
                    namespace=namespace,
                    value=prev_value,
                    period_type='instant',
                    instant_date=prev_end,
                    data_type='monetaryItemType',
                    is_current=False
                )
        
        # Process General Info (se-cd-base namespace)
        self._add_general_info_facts(company_data, start_date, end_date)
        
        # Process FB data (Förvaltningsberättelse)
        fb_data = company_data.get('fbData') or company_data.get('fbVariables') or company_data.get('forvaltningsberattelse', {})
        if isinstance(fb_data, dict):
            # If it's a dict of variables, convert to list format
            fb_items = []
            for var_name, var_value in fb_data.items():
                if isinstance(var_value, dict) and 'current_amount' in var_value:
                    fb_items.append({
                        'variable_name': var_name,
                        'current_amount': var_value.get('current_amount'),
                        'previous_amount': var_value.get('previous_amount')
                    })
                elif isinstance(var_value, (int, float)):
                    fb_items.append({
                        'variable_name': var_name,
                        'current_amount': var_value
                    })
        else:
            fb_items = fb_data if isinstance(fb_data, list) else []
        
        for item in fb_items:
            variable_name = item.get('variable_name')
            if not variable_name:
                continue
            
            # Get element_name and namespace from mapping
            mapping = fb_mappings_dict.get(variable_name, {})
            element_name = mapping.get('element_name') or variable_name
            namespace = mapping.get('tillhor') or 'se-gen-base'
            
            value = item.get('current_amount')
            if value is None or value == 0:
                continue
            
            # FB items are typically duration (period) type
            self.add_fact(
                element_name=element_name,
                namespace=namespace,
                value=value,
                period_type='duration',
                start_date=start_date,
                end_date=end_date,
                data_type='monetaryItemType'
            )
            
            # Add previous year if available
            prev_value = item.get('previous_amount')
            if prev_value is not None:
                prev_start = self._format_date(f"{fiscal_year - 1}0101") if fiscal_year else None
                prev_end = self._format_date(f"{fiscal_year - 1}1231") if fiscal_year else None
                
                self.add_fact(
                    element_name=element_name,
                    namespace=namespace,
                    value=prev_value,
                    period_type='duration',
                    start_date=prev_start,
                    end_date=prev_end,
                    data_type='monetaryItemType',
                    is_current=False
                )
        
        # Process Noter data
        noter_data = company_data.get('noterData') or company_data.get('noter_data', [])
        for item in noter_data:
            if not item.get('show_amount'):
                continue  # Skip header/text-only rows
            
            variable_name = item.get('variable_name')
            if not variable_name:
                continue
            
            # Get element_name and namespace from mapping
            mapping = noter_mappings_dict.get(variable_name, {})
            element_name = mapping.get('element_name') or item.get('element_name') or variable_name
            namespace = mapping.get('tillhor') or 'se-gen-base'
            
            value = item.get('current_amount')
            if value is None or value == 0:
                if not item.get('always_show'):
                    continue
            
            # Noter items can be either duration or instant depending on the item
            # Most are instant (balance sheet related), but some might be duration
            period_type = item.get('period_type', 'instant')
            
            if period_type == 'duration':
                self.add_fact(
                    element_name=element_name,
                    namespace=namespace,
                    value=value or 0,
                    period_type='duration',
                    start_date=start_date,
                    end_date=end_date,
                    data_type='monetaryItemType'
                )
            else:
                self.add_fact(
                    element_name=element_name,
                    namespace=namespace,
                    value=value or 0,
                    period_type='instant',
                    instant_date=end_date,
                    data_type='monetaryItemType'
                )
            
            # Add previous year if available
            prev_value = item.get('previous_amount')
            if prev_value is not None:
                if period_type == 'duration':
                    prev_start = self._format_date(f"{fiscal_year - 1}0101") if fiscal_year else None
                    prev_end = self._format_date(f"{fiscal_year - 1}1231") if fiscal_year else None
                    self.add_fact(
                        element_name=element_name,
                        namespace=namespace,
                        value=prev_value,
                        period_type='duration',
                        start_date=prev_start,
                        end_date=prev_end,
                        data_type='monetaryItemType',
                        is_current=False
                    )
                else:
                    prev_end = self._format_date(f"{fiscal_year - 1}1231") if fiscal_year else None
                    self.add_fact(
                        element_name=element_name,
                        namespace=namespace,
                        value=prev_value,
                        period_type='instant',
                        instant_date=prev_end,
                        data_type='monetaryItemType',
                        is_current=False
                    )
        
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
        
        # Add all units to ix:resources
        for unit_key, unit_info in self.units.items():
            unit_element = ET.SubElement(ix_resources, 'xbrli:unit')
            unit_element.set('id', unit_info['id'])
            measure = ET.SubElement(unit_element, 'xbrli:measure')
            measure.text = f'iso4217:{unit_info["currency"]}'
        
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
        
        # Add all facts as ix:nonNumeric or ix:nonFraction elements in ix:hidden
        for fact in self.facts:
            namespace_prefix = self._get_namespace_prefix(fact['namespace'])
            element_qname = f'{namespace_prefix}:{fact["element_name"]}'
            
            if fact['data_type'] == 'monetaryItemType':
                # Use ix:nonFraction for monetary values
                fact_element = ET.SubElement(ix_hidden, 'ix:nonFraction')
                fact_element.set('name', element_qname)
                fact_element.set('contextRef', fact['context_ref'])
                if fact['unit_ref']:
                    fact_element.set('unitRef', fact['unit_ref'])
                # Add decimals attribute (required for monetary facts)
                if fact.get('decimals'):
                    fact_element.set('decimals', fact['decimals'])
                fact_element.set('format', 'ixt:numdotdecimal')
                fact_element.text = fact['value']
            else:
                # Use ix:nonNumeric for strings, dates, enums
                fact_element = ET.SubElement(ix_hidden, 'ix:nonNumeric')
                fact_element.set('name', element_qname)
                fact_element.set('contextRef', fact['context_ref'])
                fact_element.text = fact['value']
        
        # ------------------------------------------------------------------
        # Generate visible HTML content matching PDF structure
        # ------------------------------------------------------------------
        self._generate_visible_content(body, company_data, start_date, end_date, fiscal_year)
        
        # Convert to pretty XML string with UTF-8 encoding
        rough_string = ET.tostring(root, encoding='unicode')
        reparsed = minidom.parseString(rough_string)
        # Generate XML with proper UTF-8 declaration
        xml_bytes = reparsed.toprettyxml(indent="  ", encoding='UTF-8')
        # Convert bytes to string for return
        return xml_bytes.decode('UTF-8')
    
    def _get_css_styles(self) -> str:
        """
        Return CSS styles matching PDF generator exactly.
        Margins: 19.2mm top (54pt), 24mm left/right/bottom (68pt)
        Typography: H0 (16pt), H1 (12pt), H2 (15pt), P (10pt), SMALL (8pt)
        """
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

/* Page container with PDF margins: 19.2mm top, 24mm left/right/bottom */
@media screen {
  .ar-page0, .ar-page1, .ar-page2, .ar-page3, .ar-page4, 
  .ar-page5, .ar-page6, .ar-page7, .ar-page8 {
    width: 210mm;
    min-height: 297mm;
    margin: 10mm auto;
    padding: 54pt 68pt 68pt 68pt; /* 19.2mm top, 24mm left/right/bottom */
    background-color: #ffffff;
    box-shadow: 0 0 10px rgba(0,0,0,0.1);
  }
}

@media print {
  body {
    background-color: #ffffff;
  }
  
  .ar-page0, .ar-page1, .ar-page2, .ar-page3, .ar-page4,
  .ar-page5, .ar-page6, .ar-page7, .ar-page8 {
    width: 210mm;
    height: 297mm;
    margin: 0;
    padding: 54pt 68pt 68pt 68pt; /* 19.2mm top, 24mm left/right/bottom */
    box-shadow: none;
    page-break-after: always;
  }
  
  .ar-page8 {
    page-break-after: auto;
  }
}

/* Typography styles (matching pdf_annual_report.py _styles()) */

/* H0 - Main section titles (16pt semibold, "Förvaltningsberättelse") */
.H0 {
  font-family: "Roboto", Arial, sans-serif;
  font-weight: 500;
  font-size: 16pt;
  margin-top: 0pt;
  margin-bottom: 0pt;
  line-height: 1.2;
}

/* H1 - Subsection headings (12pt semibold, "Verksamheten", "Flerårsöversikt") */
.H1 {
  font-family: "Roboto", Arial, sans-serif;
  font-weight: 500;
  font-size: 12pt;
  margin-top: 18pt;
  margin-bottom: 0pt;
  line-height: 1.2;
}

/* H2 - Major headings (15pt semibold in text, 11pt in tables) */
.H2 {
  font-family: "Roboto", Arial, sans-serif;
  font-weight: 500;
  font-size: 15pt;
  margin-top: 18pt;
  margin-bottom: 0pt;
  line-height: 1.2;
}

/* H2 in tables (11pt semibold, like "Anläggningstillgångar") */
.H2-table {
  font-family: "Roboto", Arial, sans-serif;
  font-weight: 500;
  font-size: 11pt;
  line-height: 1.2;
}

/* H3 treated as H1 in Balance Sheet (10pt semibold) */
.H3-table {
  font-family: "Roboto", Arial, sans-serif;
  font-weight: 500;
  font-size: 10pt;
  line-height: 1.2;
}

/* P - Body text (10pt regular, 12pt leading) */
.P {
  font-family: "Roboto", Arial, sans-serif;
  font-weight: normal;
  font-size: 10pt;
  line-height: 12pt;
  margin-top: 0pt;
  margin-bottom: 2pt;
}

/* SMALL - 8pt for "Belopp i kr" annotations */
.SMALL {
  font-family: "Roboto", Arial, sans-serif;
  font-weight: normal;
  font-size: 8pt;
  margin-top: 0pt;
  margin-bottom: 0pt;
  line-height: 1.2;
}

/* Cover page specific styles */
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

/* Amount columns */
.amount-right {
  text-align: right;
  font-size: 10pt;
  font-weight: normal;
}

.amount-right-bold {
  text-align: right;
  font-size: 10pt;
  font-weight: 700;
}

.amount-center {
  text-align: center;
  font-size: 10pt;
}

/* Sum rows (S1, S2, S3, S4) - semibold like headings */
.sum-label {
  font-family: "Roboto", Arial, sans-serif;
  font-weight: 500;
  font-size: 10pt;
  line-height: 1.2;
}

.sum-amount {
  text-align: right;
  font-family: "Roboto", Arial, sans-serif;
  font-weight: 500;
  font-size: 10pt;
  line-height: 1.2;
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

/* Legacy class names for backward compatibility */
.rubrik2 { font-weight: 500; font-size: 16pt; } /* H0 */
.rubrik2b { font-weight: 500; font-size: 12pt; margin-top: 18pt; } /* H1 */
.rubrik3 { font-weight: 500; font-size: 12pt; margin-top: 12pt; } /* H1 */
.rubrik4 { font-weight: 500; font-size: 10pt; margin-top: 8pt; } /* H2-table/H3-table */
.normal, .P { font-size: 10pt; line-height: 12pt; }
.belopp, .amount-right { text-align: right; font-size: 10pt; }
.summabelopp, .amount-right-bold { text-align: right; font-size: 10pt; font-weight: 500; }
.summatext, .sum-label { font-weight: 500; font-size: 10pt; }
.smalltext, .SMALL { font-size: 8pt; }
.a16, .cover-center { text-align: center; font-size: 10pt; }
.a17, .cover-subtitle { text-align: center; font-size: 16pt; font-weight: 500; }
.a18, .cover-title { text-align: center; font-size: 24pt; font-weight: 500; }

/* Header table styling with underline */
.header-underline {
  border-bottom: 0.5pt solid rgba(0, 0, 0, 0.7);
  padding-bottom: 6pt;
  margin-bottom: 6pt;
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
    
    def _get_context_refs(self, fiscal_year: int, period_type: str = 'duration') -> tuple:
        """Get contextRef IDs for current and previous year with semantic naming"""
        if period_type == 'duration':
            return ('period0', 'period1')
        else:
            return ('instant0', 'instant1')
    
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
        
        # Get context refs
        period0_ref, period1_ref = self._get_context_refs(fiscal_year or 0, 'duration')
        balans0_ref, balans1_ref = self._get_context_refs(fiscal_year or 0, 'instant')
        unit_ref = self._get_or_create_unit('SEK')
        
        # Page 0: Cover page
        self._render_cover_page(body, company_name, org_number, fiscal_year, start_date, end_date, period0_ref)
        
        # Page 1: Förvaltningsberättelse
        self._render_forvaltningsberattelse(body, company_data, company_name, org_number, fiscal_year, prev_year, period0_ref, period1_ref, balans0_ref, balans1_ref, unit_ref)
        
        # Page 2: Resultaträkning
        self._render_resultatrakning(body, company_data, company_name, org_number, fiscal_year, prev_year, period0_ref, period1_ref, unit_ref)
        
        # Page 3: Balansräkning (Tillgångar)
        self._render_balansrakning_tillgangar(body, company_data, company_name, org_number, fiscal_year, prev_year, balans0_ref, balans1_ref, unit_ref)
        
        # Page 4: Balansräkning (Eget kapital och skulder)
        self._render_balansrakning_skulder(body, company_data, company_name, org_number, fiscal_year, prev_year, balans0_ref, balans1_ref, unit_ref)
        
        # Page 5+: Noter
        self._render_noter(body, company_data, company_name, org_number, fiscal_year, prev_year, period0_ref, period1_ref, balans0_ref, balans1_ref, unit_ref)
    
    def _render_cover_page(self, body: ET.Element, company_name: str, org_number: str, 
                          fiscal_year: Optional[int], start_date: Optional[str], end_date: Optional[str],
                          period0_ref: str):
        """Render cover page"""
        page0 = ET.SubElement(body, 'div')
        page0.set('class', 'ar-page0')
        
        # Add spacing
        for _ in range(8):
            p = ET.SubElement(page0, 'p')
            p.set('class', 'normal')
            p.text = ' '
        
        # Center spacing
        p_center = ET.SubElement(page0, 'p')
        p_center.set('class', 'a16')
        p_center.text = '\n' * 8
        
        # "Årsredovisning" title
        p_title = ET.SubElement(page0, 'p')
        p_title.set('class', 'a18')
        span_title = ET.SubElement(p_title, 'span')
        span_title.set('style', 'line-height: 27.59765625pt')
        span_title.text = 'Årsredovisning'
        
        p_center2 = ET.SubElement(page0, 'p')
        p_center2.set('class', 'a16')
        p_center2.text = ' '
        
        # "för" label
        p_for = ET.SubElement(page0, 'p')
        p_for.set('class', 'a19')
        p_for.text = 'för'
        
        p_normal = ET.SubElement(page0, 'p')
        p_normal.set('class', 'normal')
        p_normal.text = ' '
        
        # Company name
        p_name = ET.SubElement(page0, 'p')
        p_name.set('class', 'a18')
        span_name = ET.SubElement(p_name, 'span')
        span_name.set('style', 'line-height: 27.59765625pt')
        ix_name = ET.SubElement(span_name, 'ix:nonNumeric')
        ix_name.set('name', 'se-cd-base:ForetagetsNamn')
        ix_name.set('contextRef', period0_ref)
        ix_name.text = company_name
        
        p_center3 = ET.SubElement(page0, 'p')
        p_center3.set('class', 'a16')
        p_center3.text = ' '
        
        # Organization number
        p_org = ET.SubElement(page0, 'p')
        p_org.set('class', 'a16')
        span_org = ET.SubElement(p_org, 'span')
        span_org.set('style', 'font-size: 14pt')
        ix_org = ET.SubElement(span_org, 'ix:nonNumeric')
        ix_org.set('name', 'se-cd-base:Organisationsnummer')
        ix_org.set('contextRef', period0_ref)
        ix_org.text = str(org_number).replace('-', '')
        
        # Add more spacing
        for _ in range(4):
            p = ET.SubElement(page0, 'p')
            p.set('class', 'a16')
            p.text = ' '
        
        # "Räkenskapsåret" label
        p_period_label = ET.SubElement(page0, 'p')
        p_period_label.set('class', 'a16')
        span_period_label = ET.SubElement(p_period_label, 'span')
        span_period_label.set('style', 'font-size: 14pt')
        span_period_label.text = 'Räkenskapsåret'
        
        p_center4 = ET.SubElement(page0, 'p')
        p_center4.set('class', 'a16')
        p_center4.text = ' '
        
        # Fiscal year
        p_year = ET.SubElement(page0, 'p')
        p_year.set('class', 'a17')
        span_year = ET.SubElement(p_year, 'span')
        span_year.set('style', 'font-weight: normal; line-height: 18.3984375pt')
        span_year.text = str(fiscal_year) if fiscal_year else ''
        
        # Add remaining spacing
        for _ in range(10):
            p = ET.SubElement(page0, 'p')
            p.set('class', 'normal')
            p.text = ' '
    
    def _render_forvaltningsberattelse(self, body: ET.Element, company_data: Dict[str, Any],
                                      company_name: str, org_number: str, fiscal_year: Optional[int],
                                      prev_year: int, period0_ref: str, period1_ref: str,
                                      balans0_ref: str, balans1_ref: str, unit_ref: str):
        """Render Förvaltningsberättelse section with proper FB mapping"""
        page1 = ET.SubElement(body, 'div')
        page1.set('class', 'pagebreak_before ar-page1')
        
        # Main heading "Förvaltningsberättelse" with spacing
        p_fb_title = ET.SubElement(page1, 'p')
        p_fb_title.set('class', 'H0')
        p_fb_title.set('style', 'margin-bottom: 18pt;')
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
        
        p_h_verksamhet = ET.SubElement(page1, 'p')
        p_h_verksamhet.set('class', 'H1')
        p_h_verksamhet.text = 'Verksamheten'
        
        p_verksamhet = ET.SubElement(page1, 'p')
        p_verksamhet.set('class', 'P')
        p_verksamhet.text = verksamhet_text
        
        # Väsentliga händelser
        vasentliga_text = company_data.get('vasentligaHandelser')
        if not vasentliga_text:
            vasentliga_text = "Inga väsentliga händelser under året."
        
        p_h_vasentliga = ET.SubElement(page1, 'p')
        p_h_vasentliga.set('class', 'H1')
        p_h_vasentliga.set('style', 'margin-top: 18pt;')
        p_h_vasentliga.text = 'Väsentliga händelser under räkenskapsåret'
        
        p_vasentliga = ET.SubElement(page1, 'p')
        p_vasentliga.set('class', 'P')
        p_vasentliga.text = vasentliga_text
        
        # Flerårsöversikt - render with proper logic
        self._render_flerarsoversikt_xbrl(page1, company_data, fiscal_year, prev_year, fb_variables, fb_mappings, period0_ref, balans0_ref, balans1_ref, unit_ref)
        
        # Förändringar i eget kapital - render with show/hide logic
        self._render_forandringar_eget_kapital_xbrl(page1, fb_table, fiscal_year, prev_year, fb_variables, fb_mappings, balans0_ref, balans1_ref, period0_ref, unit_ref)
        
        # Resultatdisposition - render with proper formatting
        self._render_resultatdisposition_xbrl(page1, fb_table, company_data, fb_mappings, balans0_ref, unit_ref)
    
    def _render_flerarsoversikt_xbrl(self, page: ET.Element, company_data: dict, fiscal_year: int, prev_year: int,
                                     fb_variables: dict, fb_mappings: list, period0_ref: str, balans0_ref: str, 
                                     balans1_ref: str, unit_ref: str) -> None:
        """Render Flerårsöversikt table with 3 years"""
        p_heading = ET.SubElement(page, 'p')
        p_heading.set('class', 'H1')
        p_heading.set('style', 'margin-top: 18pt;')
        p_heading.text = 'Flerårsöversikt'
        
        p_tkr = ET.SubElement(page, 'p')
        p_tkr.set('class', 'SMALL')
        p_tkr.text = 'Belopp i tkr'
        
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
        
        # Nettoomsättning (row 31 in CSV)
        oms_vals = [get_var('oms1'), get_var('oms2'), get_var('oms3')]
        if all(v == 0 for v in oms_vals):
            scraped_oms = get_scraped_values(['Omsättning', 'Total omsättning', 'omsättning'])
            oms_vals = scraped_oms
        rows_data.append(('Nettoomsättning', oms_vals, False))
        
        # Resultat efter finansiella poster (row 34)
        ref_vals = [get_var('ref1'), get_var('ref2'), get_var('ref3')]
        if all(v == 0 for v in ref_vals):
            scraped_ref = get_scraped_values(['Resultat efter finansnetto', 'Resultat efter finansiella poster'])
            ref_vals = scraped_ref
        rows_data.append(('Resultat efter finansiella poster', ref_vals, False))
        
        # Balansomslutning (row 39)
        bal_vals = [get_var('bal1'), get_var('bal2'), get_var('bal3')]
        if all(v == 0 for v in bal_vals):
            scraped_bal = get_scraped_values(['Summa tillgångar', 'Balansomslutning'])
            bal_vals = scraped_bal
        rows_data.append(('Balansomslutning', bal_vals, False))
        
        # Soliditet (row 41) - percentage
        sol_vals = [get_var('sol1'), get_var('sol2'), get_var('sol3')]
        if all(v == 0 for v in sol_vals):
            scraped_sol = get_scraped_values(['Soliditet'])
            sol_vals = scraped_sol
        rows_data.append(('Soliditet', sol_vals, True))  # True = percentage
        
        # Create table
        table = ET.SubElement(page, 'table')
        table.set('style', 'border-collapse: collapse; width: 16.5cm; table-layout: fixed; margin-top: 6pt;')
        
        # Header row
        tr_header = ET.SubElement(table, 'tr')
        td_label_h = ET.SubElement(tr_header, 'td')
        td_label_h.set('style', 'vertical-align: bottom; width: 10.5cm; padding-bottom: 4pt; border-bottom: 0.5pt solid rgba(0, 0, 0, 0.7);')
        # Empty
        
        for year in years:
            td_year = ET.SubElement(tr_header, 'td')
            td_year.set('style', 'vertical-align: bottom; width: 2cm; padding-bottom: 4pt; text-align: right; border-bottom: 0.5pt solid rgba(0, 0, 0, 0.7);')
            p_year = ET.SubElement(td_year, 'p')
            p_year.set('class', 'P')
            p_year.set('style', 'margin-top: 0; margin-bottom: 0; font-weight: 500;')
            p_year.text = year
        
        # Data rows
        for label, values, is_percentage in rows_data:
            tr = ET.SubElement(table, 'tr')
            
            # Label
            td_label = ET.SubElement(tr, 'td')
            td_label.set('style', 'vertical-align: top; width: 10.5cm; padding-top: 2pt;')
            p_label = ET.SubElement(td_label, 'p')
            p_label.set('class', 'P')
            p_label.set('style', 'margin-top: 0; margin-bottom: 0;')
            p_label.text = label
            
            # Values
            for val in values:
                td_val = ET.SubElement(tr, 'td')
                td_val.set('style', 'vertical-align: top; width: 2cm; text-align: right; padding-top: 2pt;')
                p_val = ET.SubElement(td_val, 'p')
                p_val.set('class', 'P')
                p_val.set('style', 'margin-top: 0; margin-bottom: 0;')
                
                if is_percentage:
                    # Soliditet - show as percentage
                    p_val.text = f"{int(round(val))}%"
                else:
                    # Amounts in thousands
                    p_val.text = self._format_monetary_value(val, for_display=True)
    
    def _render_forandringar_eget_kapital_xbrl(self, page: ET.Element, fb_table: list, fiscal_year: int, 
                                               prev_year: int, fb_variables: dict, fb_mappings: list,
                                               balans0_ref: str, balans1_ref: str, period0_ref: str, unit_ref: str) -> None:
        """Render Förändringar i eget kapital table with column/row filtering"""
        if not fb_table or len(fb_table) == 0:
            return
        
        p_heading = ET.SubElement(page, 'p')
        p_heading.set('class', 'H1')
        p_heading.set('style', 'margin-top: 18pt;')
        p_heading.text = 'Förändringar i eget kapital'
        
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
        available_width = 459  # Full page width in pt
        label_width = 160
        num_cols = len(visible_cols)
        data_width = available_width - label_width
        col_width = data_width / num_cols if num_cols > 0 else 60
        
        table_width = label_width + (col_width * num_cols)
        table.set('style', f'border-collapse: collapse; width: {table_width}pt; table-layout: fixed; margin-top: 6pt;')
        
        # Header row
        tr_header = ET.SubElement(table, 'tr')
        td_label_h = ET.SubElement(tr_header, 'td')
        td_label_h.set('style', f'vertical-align: bottom; width: {label_width}pt; padding-bottom: 4pt; border-bottom: 0.5pt solid rgba(0, 0, 0, 0.7);')
        # Empty
        
        for col_label in visible_labels:
            td_col = ET.SubElement(tr_header, 'td')
            td_col.set('style', f'vertical-align: bottom; width: {col_width}pt; padding-bottom: 4pt; text-align: right; border-bottom: 0.5pt solid rgba(0, 0, 0, 0.7);')
            # Handle multi-line headers
            lines = col_label.split('\n')
            for line in lines:
                p_line = ET.SubElement(td_col, 'p')
                p_line.set('class', 'P')
                p_line.set('style', 'margin-top: 0; margin-bottom: 0; font-weight: 500;')
                p_line.text = line
        
        # Data rows
        for idx, (label, values) in enumerate(table_data):
            tr = ET.SubElement(table, 'tr')
            is_utgaende = idx in utgaende_rows_idx
            
            # Label
            td_label = ET.SubElement(tr, 'td')
            td_label.set('style', f'vertical-align: top; width: {label_width}pt; padding-top: 2pt;')
            p_label = ET.SubElement(td_label, 'p')
            p_label.set('class', 'P')
            if is_utgaende:
                p_label.set('style', 'margin-top: 0; margin-bottom: 0; font-weight: 500;')
            else:
                p_label.set('style', 'margin-top: 0; margin-bottom: 0;')
            p_label.text = label
            
            # Values
            for val in values:
                td_val = ET.SubElement(tr, 'td')
                td_val.set('style', f'vertical-align: top; width: {col_width}pt; text-align: right; padding-top: 2pt;')
                p_val = ET.SubElement(td_val, 'p')
                p_val.set('class', 'P')
                if is_utgaende:
                    p_val.set('style', 'margin-top: 0; margin-bottom: 0; font-weight: 500;')
                else:
                    p_val.set('style', 'margin-top: 0; margin-bottom: 0;')
                p_val.text = self._format_monetary_value(val, for_display=True)
    
    def _render_resultatdisposition_xbrl(self, page: ET.Element, fb_table: list, company_data: dict,
                                        fb_mappings: list, balans0_ref: str, unit_ref: str) -> None:
        """Render Resultatdisposition section"""
        arets_utdelning = self._num(company_data.get('arets_utdelning', 0))
        
        if not fb_table:
            return
        
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
        p_heading.set('class', 'H1')
        p_heading.set('style', 'margin-top: 18pt;')
        p_heading.text = 'Resultatdisposition'
        
        p_intro = ET.SubElement(page, 'p')
        p_intro.set('class', 'P')
        p_intro.text = 'Styrelsen och VD föreslår att till förfogande stående medel'
        
        # Create table
        table = ET.SubElement(page, 'table')
        table.set('style', 'border-collapse: collapse; width: 300pt; table-layout: fixed; margin-top: 6pt;')
        
        # Available funds
        if balanserat != 0:
            tr = ET.SubElement(table, 'tr')
            td_label = ET.SubElement(tr, 'td')
            td_label.set('style', 'vertical-align: top; width: 150pt;')
            p_label = ET.SubElement(td_label, 'p')
            p_label.set('class', 'P')
            p_label.set('style', 'margin-top: 0; margin-bottom: 0;')
            p_label.text = 'Balanserat resultat'
            
            td_val = ET.SubElement(tr, 'td')
            td_val.set('style', 'vertical-align: top; width: 150pt; text-align: right;')
            p_val = ET.SubElement(td_val, 'p')
            p_val.set('class', 'P')
            p_val.set('style', 'margin-top: 0; margin-bottom: 0;')
            p_val.text = self._format_monetary_value(balanserat, for_display=True)
        
        if arets_res != 0:
            tr = ET.SubElement(table, 'tr')
            td_label = ET.SubElement(tr, 'td')
            td_label.set('style', 'vertical-align: top; width: 150pt;')
            p_label = ET.SubElement(td_label, 'p')
            p_label.set('class', 'P')
            p_label.set('style', 'margin-top: 0; margin-bottom: 0;')
            p_label.text = 'Årets resultat'
            
            td_val = ET.SubElement(tr, 'td')
            td_val.set('style', 'vertical-align: top; width: 150pt; text-align: right;')
            p_val = ET.SubElement(td_val, 'p')
            p_val.set('class', 'P')
            p_val.set('style', 'margin-top: 0; margin-bottom: 0;')
            p_val.text = self._format_monetary_value(arets_res, for_display=True)
        
        # First Summa row
        tr = ET.SubElement(table, 'tr')
        td_label = ET.SubElement(tr, 'td')
        td_label.set('style', 'vertical-align: top; width: 150pt;')
        p_label = ET.SubElement(td_label, 'p')
        p_label.set('class', 'P')
        p_label.set('style', 'margin-top: 0; margin-bottom: 0; font-weight: 500;')
        p_label.text = 'Summa'
        
        td_val = ET.SubElement(tr, 'td')
        td_val.set('style', 'vertical-align: top; width: 150pt; text-align: right;')
        p_val = ET.SubElement(td_val, 'p')
        p_val.set('class', 'P')
        p_val.set('style', 'margin-top: 0; margin-bottom: 0; font-weight: 500;')
        p_val.text = self._format_monetary_value(summa, for_display=True)
        
        # Empty row for spacing
        tr_empty = ET.SubElement(table, 'tr')
        td_empty1 = ET.SubElement(tr_empty, 'td')
        td_empty1.set('style', 'height: 10pt;')
        td_empty2 = ET.SubElement(tr_empty, 'td')
        td_empty2.set('style', 'height: 10pt;')
        
        # Disposition header
        tr = ET.SubElement(table, 'tr')
        td_label = ET.SubElement(tr, 'td')
        td_label.set('style', 'vertical-align: top; width: 150pt;')
        p_label = ET.SubElement(td_label, 'p')
        p_label.set('class', 'P')
        p_label.set('style', 'margin-top: 0; margin-bottom: 0;')
        p_label.text = 'Disponeras enligt följande'
        td_empty = ET.SubElement(tr, 'td')
        
        # Utdelas till aktieägare
        tr = ET.SubElement(table, 'tr')
        td_label = ET.SubElement(tr, 'td')
        td_label.set('style', 'vertical-align: top; width: 150pt;')
        p_label = ET.SubElement(td_label, 'p')
        p_label.set('class', 'P')
        p_label.set('style', 'margin-top: 0; margin-bottom: 0;')
        p_label.text = 'Utdelas till aktieägare'
        
        td_val = ET.SubElement(tr, 'td')
        td_val.set('style', 'vertical-align: top; width: 150pt; text-align: right;')
        p_val = ET.SubElement(td_val, 'p')
        p_val.set('class', 'P')
        p_val.set('style', 'margin-top: 0; margin-bottom: 0;')
        p_val.text = self._format_monetary_value(arets_utdelning, for_display=True)
        
        # Balanseras i ny räkning
        balanseras = summa - arets_utdelning
        tr = ET.SubElement(table, 'tr')
        td_label = ET.SubElement(tr, 'td')
        td_label.set('style', 'vertical-align: top; width: 150pt;')
        p_label = ET.SubElement(td_label, 'p')
        p_label.set('class', 'P')
        p_label.set('style', 'margin-top: 0; margin-bottom: 0;')
        p_label.text = 'Balanseras i ny räkning'
        
        td_val = ET.SubElement(tr, 'td')
        td_val.set('style', 'vertical-align: top; width: 150pt; text-align: right;')
        p_val = ET.SubElement(td_val, 'p')
        p_val.set('class', 'P')
        p_val.set('style', 'margin-top: 0; margin-bottom: 0;')
        p_val.text = self._format_monetary_value(balanseras, for_display=True)
        
        # Final Summa row
        tr = ET.SubElement(table, 'tr')
        td_label = ET.SubElement(tr, 'td')
        td_label.set('style', 'vertical-align: top; width: 150pt;')
        p_label = ET.SubElement(td_label, 'p')
        p_label.set('class', 'P')
        p_label.set('style', 'margin-top: 0; margin-bottom: 0; font-weight: 500;')
        p_label.text = 'Summa'
        
        td_val = ET.SubElement(tr, 'td')
        td_val.set('style', 'vertical-align: top; width: 150pt; text-align: right;')
        p_val = ET.SubElement(td_val, 'p')
        p_val.set('class', 'P')
        p_val.set('style', 'margin-top: 0; margin-bottom: 0; font-weight: 500;')
        p_val.text = self._format_monetary_value(summa, for_display=True)
        
        # Add dividend policy text if utdelning > 0
        if arets_utdelning > 0:
            p_policy = ET.SubElement(page, 'p')
            p_policy.set('class', 'P')
            p_policy.set('style', 'margin-top: 18pt;')
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
        p_title.set('style', 'margin-bottom: 18pt;')
        p_title.text = 'Resultaträkning'
        
        # Column headers table (with underline) - must match data table structure EXACTLY
        header_table = ET.SubElement(page2, 'table')
        header_table.set('style', 'border-collapse: collapse; width: 16.5cm; table-layout: fixed; border-bottom: 0.5pt solid rgba(0, 0, 0, 0.7); margin-bottom: 6pt;')
        tr_header = ET.SubElement(header_table, 'tr')
        
        # Label column - same width as data rows
        td_label = ET.SubElement(tr_header, 'td')
        td_label.set('style', 'vertical-align: bottom; width: 9cm; padding-bottom: 4pt;')
        # Empty
        
        # Note column - same width as data rows
        td_not = ET.SubElement(tr_header, 'td')
        td_not.set('style', 'vertical-align: bottom; width: 2cm; padding-bottom: 4pt; text-align: center;')
        p_not = ET.SubElement(td_not, 'p')
        p_not.set('class', 'P')  # 10pt like normal text
        p_not.set('style', 'margin-top: 0; margin-bottom: 0; font-weight: 500;')
        p_not.text = 'Not'
        
        # Current year column - same width as data rows
        td_year1 = ET.SubElement(tr_header, 'td')
        td_year1.set('style', 'vertical-align: bottom; width: 2.5cm; padding-bottom: 4pt; text-align: right;')
        p_year1_start = ET.SubElement(td_year1, 'p')
        p_year1_start.set('class', 'P')  # 10pt like normal text
        p_year1_start.set('style', 'margin-top: 0; margin-bottom: 0; font-weight: 500;')
        p_year1_start.text = f'{fiscal_year}-01-01' if fiscal_year else ''
        p_year1_end = ET.SubElement(td_year1, 'p')
        p_year1_end.set('class', 'P')  # 10pt like normal text
        p_year1_end.set('style', 'margin-top: 0; margin-bottom: 0; font-weight: 500;')
        p_year1_end.text = f'-{fiscal_year}-12-31' if fiscal_year else ''
        
        # Spacing column - same as data rows
        td_spacing_h = ET.SubElement(tr_header, 'td')
        td_spacing_h.set('style', 'vertical-align: bottom; width: 0.5cm; padding-bottom: 4pt;')
        # Empty
        
        # Previous year column - same width as data rows
        td_year2 = ET.SubElement(tr_header, 'td')
        td_year2.set('style', 'vertical-align: bottom; width: 2.5cm; padding-bottom: 4pt; text-align: right;')
        p_year2_start = ET.SubElement(td_year2, 'p')
        p_year2_start.set('class', 'P')  # 10pt like normal text
        p_year2_start.set('style', 'margin-top: 0; margin-bottom: 0; font-weight: 500;')
        p_year2_start.text = f'{prev_year}-01-01' if prev_year else ''
        p_year2_end = ET.SubElement(td_year2, 'p')
        p_year2_end.set('class', 'P')  # 10pt like normal text
        p_year2_end.set('style', 'margin-top: 0; margin-bottom: 0; font-weight: 500;')
        p_year2_end.text = f'-{prev_year}-12-31' if prev_year else ''
        
        # RR table
        rr_data_raw = (company_data.get('rrData') or 
                      company_data.get('rrRows') or 
                      company_data.get('seFileData', {}).get('rr_data', []))
        
        if rr_data_raw:
            rr_table = ET.SubElement(page2, 'table')
            rr_table.set('style', 'border-collapse: collapse; width: 16.5cm; table-layout: fixed;')
            
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
                    rr_mappings_response = supabase.table('variable_mapping_rr').select('variable_name,element_name,tillhor').execute()
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
                
                # Add row spacing based on type (matching PDF spacing)
                row_style = ''
                if label == 'Årets resultat':
                    row_style = 'padding-top: 18pt;'  # Extra space before final result
                elif is_sum:
                    row_style = 'padding-bottom: 10pt;'  # 10pt space after sum rows
                elif is_heading:
                    row_style = 'padding-top: 2pt;'  # Small space before headings
                
                # Label column
                td_label = ET.SubElement(tr, 'td')
                td_label.set('style', f'vertical-align: top; width: 9cm; {row_style}')
                p_label = ET.SubElement(td_label, 'p')
                if is_heading:
                    p_label.set('class', 'H3-table')  # 10pt semibold for RR headings
                    p_label.set('style', 'margin-top: 0; margin-bottom: 0;')
                elif is_sum:
                    p_label.set('class', 'sum-label')  # Bold sum text
                    p_label.set('style', 'margin-top: 0; margin-bottom: 0;')
                else:
                    p_label.set('class', 'P')  # Normal body text
                    p_label.set('style', 'margin-top: 0; margin-bottom: 0;')
                p_label.text = label
                
                # Note column
                td_note = ET.SubElement(tr, 'td')
                td_note.set('style', f'vertical-align: top; width: 2cm; text-align: center; {row_style}')
                p_note = ET.SubElement(td_note, 'p')
                p_note.set('class', 'P')
                p_note.set('style', 'margin-top: 0; margin-bottom: 0;')
                p_note.text = note
                
                # Current year amount
                td_curr = ET.SubElement(tr, 'td')
                td_curr.set('style', f'vertical-align: top; width: 2.5cm; text-align: right; {row_style}')
                p_curr = ET.SubElement(td_curr, 'p')
                if is_sum:
                    p_curr.set('class', 'sum-amount')  # Bold right-aligned
                    p_curr.set('style', 'margin-top: 0; margin-bottom: 0;')
                else:
                    p_curr.set('class', 'amount-right')  # Normal right-aligned
                    p_curr.set('style', 'margin-top: 0; margin-bottom: 0;')
                
                if is_heading:
                    p_curr.text = ''
                else:
                    curr_val = self._num(row.get('current_amount', 0))
                    prev_val = self._num(row.get('previous_amount', 0))
                    # Show amount if: non-zero, OR other year has value, OR always_show, OR has note
                    if curr_val != 0 or prev_val != 0 or row.get('always_show') or note:
                        variable_name = row.get('variable_name')
                        if variable_name and variable_name in rr_mappings_dict:
                            mapping = rr_mappings_dict[variable_name]
                            element_name = mapping.get('element_name')
                            namespace = mapping.get('tillhor', 'se-gen-base')
                            namespace_prefix = self._get_namespace_prefix(namespace)
                            element_qname = f'{namespace_prefix}:{element_name}'
                            
                            # Use ix:nonFraction for monetary values
                            ix_curr = ET.SubElement(p_curr, 'ix:nonFraction')
                            ix_curr.set('name', element_qname)
                            ix_curr.set('contextRef', period0_ref)
                            ix_curr.set('unitRef', unit_ref)
                            ix_curr.set('format', 'ixt:numdotdecimal')
                            ix_curr.set('decimals', '0')
                            ix_curr.set('scale', '3')
                            ix_curr.text = str(int(round(curr_val)))
                        else:
                            # Fallback to plain text (no decimals)
                            p_curr.text = self._format_monetary_value(curr_val, for_display=True)
                    else:
                        p_curr.text = ''
                
                # Spacing column
                td_spacing = ET.SubElement(tr, 'td')
                td_spacing.set('style', f'vertical-align: top; width: 0.5cm; {row_style}')
                p_spacing = ET.SubElement(td_spacing, 'p')
                p_spacing.set('class', 'P')
                p_spacing.set('style', 'margin-top: 0; margin-bottom: 0;')
                p_spacing.text = ''
                
                # Previous year amount
                td_prev = ET.SubElement(tr, 'td')
                td_prev.set('style', f'vertical-align: top; width: 2.5cm; text-align: right; {row_style}')
                p_prev = ET.SubElement(td_prev, 'p')
                if is_sum:
                    p_prev.set('class', 'sum-amount')  # Bold right-aligned
                    p_prev.set('style', 'margin-top: 0; margin-bottom: 0;')
                else:
                    p_prev.set('class', 'amount-right')  # Normal right-aligned
                    p_prev.set('style', 'margin-top: 0; margin-bottom: 0;')
                
                if is_heading:
                    p_prev.text = ''
                else:
                    # prev_val already calculated above for current year logic
                    # Show amount if: non-zero, OR other year has value, OR always_show, OR has note
                    if prev_val != 0 or curr_val != 0 or row.get('always_show') or note:
                        variable_name = row.get('variable_name')
                        if variable_name and variable_name in rr_mappings_dict:
                            mapping = rr_mappings_dict[variable_name]
                            element_name = mapping.get('element_name')
                            namespace = mapping.get('tillhor', 'se-gen-base')
                            namespace_prefix = self._get_namespace_prefix(namespace)
                            element_qname = f'{namespace_prefix}:{element_name}'
                            
                            # Use ix:nonFraction for previous year
                            ix_prev = ET.SubElement(p_prev, 'ix:nonFraction')
                            ix_prev.set('name', element_qname)
                            ix_prev.set('contextRef', period1_ref)
                            ix_prev.set('unitRef', unit_ref)
                            ix_prev.set('format', 'ixt:numdotdecimal')
                            ix_prev.set('decimals', '0')
                            ix_prev.set('scale', '3')
                            ix_prev.text = str(int(round(prev_val)))
                        else:
                            # Fallback to plain text (no decimals)
                            p_prev.text = self._format_monetary_value(prev_val, for_display=True)
                    else:
                        p_prev.text = ''
                
                # Final spacing column
                td_spacing2 = ET.SubElement(tr, 'td')
                td_spacing2.set('style', 'vertical-align: bottom; width: 0.5cm')
                p_spacing2 = ET.SubElement(td_spacing2, 'p')
                p_spacing2.set('class', 'normal')
                p_spacing2.text = ' '
    
    def _render_balansrakning_tillgangar(self, body: ET.Element, company_data: Dict[str, Any],
                                         company_name: str, org_number: str, fiscal_year: Optional[int],
                                         prev_year: int, balans0_ref: str, balans1_ref: str, unit_ref: str):
        """Render Balansräkning (Tillgångar) section"""
        page3 = ET.SubElement(body, 'div')
        page3.set('class', 'pagebreak_before ar-page3')
        
        # Header with title
        p_title = ET.SubElement(page3, 'p')
        p_title.set('class', 'H0')
        p_title.set('style', 'margin-bottom: 18pt;')
        p_title.text = 'Balansräkning'
        
        # Column headers table (with underline) - must match data table structure EXACTLY
        header_table = ET.SubElement(page3, 'table')
        header_table.set('style', 'border-collapse: collapse; width: 16.5cm; table-layout: fixed; border-bottom: 0.5pt solid rgba(0, 0, 0, 0.7); margin-bottom: 6pt;')
        tr_header = ET.SubElement(header_table, 'tr')
        
        # Label column - same width as data rows
        td_label = ET.SubElement(tr_header, 'td')
        td_label.set('style', 'vertical-align: bottom; width: 9cm; padding-bottom: 4pt;')
        # Empty
        
        # Note column - same width as data rows
        td_not = ET.SubElement(tr_header, 'td')
        td_not.set('style', 'vertical-align: bottom; width: 2cm; padding-bottom: 4pt; text-align: center;')
        p_not = ET.SubElement(td_not, 'p')
        p_not.set('class', 'P')  # 10pt like normal text
        p_not.set('style', 'margin-top: 0; margin-bottom: 0; font-weight: 500;')
        p_not.text = 'Not'
        
        # Current year column - same width as data rows
        td_year1 = ET.SubElement(tr_header, 'td')
        td_year1.set('style', 'vertical-align: bottom; width: 2.5cm; padding-bottom: 4pt; text-align: right;')
        p_year1 = ET.SubElement(td_year1, 'p')
        p_year1.set('class', 'P')  # 10pt like normal text
        p_year1.set('style', 'margin-top: 0; margin-bottom: 0; font-weight: 500;')
        p_year1.text = f'{fiscal_year}-12-31' if fiscal_year else ''
        
        # Spacing column - same as data rows
        td_spacing_h = ET.SubElement(tr_header, 'td')
        td_spacing_h.set('style', 'vertical-align: bottom; width: 0.5cm; padding-bottom: 4pt;')
        # Empty
        
        # Previous year column - same width as data rows
        td_year2 = ET.SubElement(tr_header, 'td')
        td_year2.set('style', 'vertical-align: bottom; width: 2.5cm; padding-bottom: 4pt; text-align: right;')
        p_year2 = ET.SubElement(td_year2, 'p')
        p_year2.set('class', 'P')  # 10pt like normal text
        p_year2.set('style', 'margin-top: 0; margin-bottom: 0; font-weight: 500;')
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
                br_mappings_response = supabase.table('variable_mapping_br').select('variable_name,element_name,tillhor').execute()
                br_mappings_dict = {m['variable_name']: m for m in br_mappings_response.data if m.get('variable_name')}
            else:
                br_mappings_dict = {}
        except:
            br_mappings_dict = {}
        
        if br_data_raw:
            br_table = ET.SubElement(page3, 'table')
            br_table.set('style', 'border-collapse: collapse; width: 16.5cm; table-layout: fixed;')
            
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
                row_padding_top = ''
                row_padding_bottom = ''
                if is_heading:
                    if style in ['H2', 'H0']:
                        row_padding_top = 'padding-top: 8pt;'  # 8pt before H2 headings
                        row_padding_bottom = 'padding-bottom: 12pt;'  # 12pt after H2 headings
                    else:
                        row_padding_top = 'padding-top: 2pt;'  # Small space before H1/H3
                elif is_sum:
                    row_padding_bottom = 'padding-bottom: 10pt;'  # 10pt space after sums
                
                row_style = f'{row_padding_top} {row_padding_bottom}'
                
                # Label column
                td_label = ET.SubElement(tr, 'td')
                td_label.set('style', f'vertical-align: top; width: 9cm; {row_style}')
                p_label = ET.SubElement(td_label, 'p')
                if is_heading:
                    # H2/H0 → 11pt (larger BR headings like "Anläggningstillgångar")
                    # H1/H3 → 10pt (smaller BR headings like "Bundet eget kapital")
                    if style in ['H2', 'H0']:
                        p_label.set('class', 'H2-table')  # 11pt semibold
                    else:
                        p_label.set('class', 'H3-table')  # 10pt semibold
                    p_label.set('style', 'margin-top: 0; margin-bottom: 0;')
                elif is_sum:
                    p_label.set('class', 'sum-label')  # Bold sum text
                    p_label.set('style', 'margin-top: 0; margin-bottom: 0;')
                else:
                    p_label.set('class', 'P')  # Normal body text
                    p_label.set('style', 'margin-top: 0; margin-bottom: 0;')
                p_label.text = label
                
                # Note column
                td_note = ET.SubElement(tr, 'td')
                td_note.set('style', f'vertical-align: top; width: 2cm; text-align: center; {row_style}')
                p_note = ET.SubElement(td_note, 'p')
                p_note.set('class', 'P')
                p_note.set('style', 'margin-top: 0; margin-bottom: 0;')
                p_note.text = note
                
                # Current year amount
                td_curr = ET.SubElement(tr, 'td')
                td_curr.set('style', f'vertical-align: top; width: 2.5cm; text-align: right; {row_style}')
                p_curr = ET.SubElement(td_curr, 'p')
                if is_sum:
                    p_curr.set('class', 'sum-amount')  # Bold right-aligned
                    p_curr.set('style', 'margin-top: 0; margin-bottom: 0;')
                else:
                    p_curr.set('class', 'amount-right')  # Normal right-aligned
                    p_curr.set('style', 'margin-top: 0; margin-bottom: 0;')
                
                if is_heading:
                    p_curr.text = ''
                else:
                    curr_val = self._num(row.get('current_amount', 0))
                    prev_val = self._num(row.get('previous_amount', 0))
                    # Show amount if: non-zero, OR other year has value, OR always_show, OR has note
                    if curr_val != 0 or prev_val != 0 or row.get('always_show') or note:
                        variable_name = row.get('variable_name')
                        if variable_name and variable_name in br_mappings_dict:
                            mapping = br_mappings_dict[variable_name]
                            element_name = mapping.get('element_name')
                            namespace = mapping.get('tillhor', 'se-gen-base')
                            namespace_prefix = self._get_namespace_prefix(namespace)
                            element_qname = f'{namespace_prefix}:{element_name}'
                            
                            ix_curr = ET.SubElement(p_curr, 'ix:nonFraction')
                            ix_curr.set('name', element_qname)
                            ix_curr.set('contextRef', balans0_ref)
                            ix_curr.set('unitRef', unit_ref)
                            ix_curr.set('format', 'ixt:numdotdecimal')
                            ix_curr.set('decimals', '0')
                            ix_curr.set('scale', '3')
                            ix_curr.text = str(int(round(curr_val)))
                        else:
                            # Fallback to plain text (no decimals)
                            p_curr.text = self._format_monetary_value(curr_val, for_display=True)
                    else:
                        p_curr.text = ''
                
                # Spacing column
                td_spacing = ET.SubElement(tr, 'td')
                td_spacing.set('style', f'vertical-align: top; width: 0.5cm; {row_style}')
                p_spacing = ET.SubElement(td_spacing, 'p')
                p_spacing.set('class', 'P')
                p_spacing.set('style', 'margin-top: 0; margin-bottom: 0;')
                p_spacing.text = ''
                
                # Previous year amount
                td_prev = ET.SubElement(tr, 'td')
                td_prev.set('style', f'vertical-align: top; width: 2.5cm; text-align: right; {row_style}')
                p_prev = ET.SubElement(td_prev, 'p')
                if is_sum:
                    p_prev.set('class', 'sum-amount')  # Bold right-aligned
                    p_prev.set('style', 'margin-top: 0; margin-bottom: 0;')
                else:
                    p_prev.set('class', 'amount-right')  # Normal right-aligned
                    p_prev.set('style', 'margin-top: 0; margin-bottom: 0;')
                
                if is_heading:
                    p_prev.text = ''
                else:
                    # prev_val already calculated above for current year logic
                    # Show amount if: non-zero, OR other year has value, OR always_show, OR has note
                    if prev_val != 0 or curr_val != 0 or row.get('always_show') or note:
                        variable_name = row.get('variable_name')
                        if variable_name and variable_name in br_mappings_dict:
                            mapping = br_mappings_dict[variable_name]
                            element_name = mapping.get('element_name')
                            namespace = mapping.get('tillhor', 'se-gen-base')
                            namespace_prefix = self._get_namespace_prefix(namespace)
                            element_qname = f'{namespace_prefix}:{element_name}'
                            
                            ix_prev = ET.SubElement(p_prev, 'ix:nonFraction')
                            ix_prev.set('name', element_qname)
                            ix_prev.set('contextRef', balans1_ref)
                            ix_prev.set('unitRef', unit_ref)
                            ix_prev.set('format', 'ixt:numdotdecimal')
                            ix_prev.set('decimals', '0')
                            ix_prev.set('scale', '3')
                            ix_prev.text = str(int(round(prev_val)))
                        else:
                            # Fallback to plain text (no decimals)
                            p_prev.text = self._format_monetary_value(prev_val, for_display=True)
                    else:
                        p_prev.text = ''
                
                # Final spacing column
                td_spacing2 = ET.SubElement(tr, 'td')
                td_spacing2.set('style', 'vertical-align: bottom; width: 0.5cm')
                p_spacing2 = ET.SubElement(td_spacing2, 'p')
                p_spacing2.set('class', 'normal')
                p_spacing2.text = ' '
    
    def _render_balansrakning_skulder(self, body: ET.Element, company_data: Dict[str, Any],
                                     company_name: str, org_number: str, fiscal_year: Optional[int],
                                     prev_year: int, balans0_ref: str, balans1_ref: str, unit_ref: str):
        """Render Balansräkning (Eget kapital och skulder) section"""
        page4 = ET.SubElement(body, 'div')
        page4.set('class', 'pagebreak_before ar-page4')
        
        # Header with title (same as assets page)
        p_title = ET.SubElement(page4, 'p')
        p_title.set('class', 'H0')
        p_title.set('style', 'margin-bottom: 18pt;')
        p_title.text = 'Balansräkning'
        
        # Column headers table (with underline) - must match data table structure EXACTLY
        header_table = ET.SubElement(page4, 'table')
        header_table.set('style', 'border-collapse: collapse; width: 16.5cm; table-layout: fixed; border-bottom: 0.5pt solid rgba(0, 0, 0, 0.7); margin-bottom: 6pt;')
        tr_header = ET.SubElement(header_table, 'tr')
        
        # Label column - same width as data rows
        td_label = ET.SubElement(tr_header, 'td')
        td_label.set('style', 'vertical-align: bottom; width: 9cm; padding-bottom: 4pt;')
        # Empty
        
        # Note column - same width as data rows
        td_not = ET.SubElement(tr_header, 'td')
        td_not.set('style', 'vertical-align: bottom; width: 2cm; padding-bottom: 4pt; text-align: center;')
        p_not = ET.SubElement(td_not, 'p')
        p_not.set('class', 'P')  # 10pt like normal text
        p_not.set('style', 'margin-top: 0; margin-bottom: 0; font-weight: 500;')
        p_not.text = 'Not'
        
        # Current year column - same width as data rows
        td_year1 = ET.SubElement(tr_header, 'td')
        td_year1.set('style', 'vertical-align: bottom; width: 2.5cm; padding-bottom: 4pt; text-align: right;')
        p_year1 = ET.SubElement(td_year1, 'p')
        p_year1.set('class', 'P')  # 10pt like normal text
        p_year1.set('style', 'margin-top: 0; margin-bottom: 0; font-weight: 500;')
        p_year1.text = f'{fiscal_year}-12-31' if fiscal_year else ''
        
        # Spacing column - same as data rows
        td_spacing_h = ET.SubElement(tr_header, 'td')
        td_spacing_h.set('style', 'vertical-align: bottom; width: 0.5cm; padding-bottom: 4pt;')
        # Empty
        
        # Previous year column - same width as data rows
        td_year2 = ET.SubElement(tr_header, 'td')
        td_year2.set('style', 'vertical-align: bottom; width: 2.5cm; padding-bottom: 4pt; text-align: right;')
        p_year2 = ET.SubElement(td_year2, 'p')
        p_year2.set('class', 'P')  # 10pt like normal text
        p_year2.set('style', 'margin-top: 0; margin-bottom: 0; font-weight: 500;')
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
                br_mappings_response = supabase.table('variable_mapping_br').select('variable_name,element_name,tillhor').execute()
                br_mappings_dict = {m['variable_name']: m for m in br_mappings_response.data if m.get('variable_name')}
            else:
                br_mappings_dict = {}
        except:
            br_mappings_dict = {}
        
        if br_data_raw:
            br_table = ET.SubElement(page4, 'table')
            br_table.set('style', 'border-collapse: collapse; width: 16.5cm; table-layout: fixed;')
            
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
                row_padding_top = ''
                row_padding_bottom = ''
                if is_heading:
                    if style in ['H2', 'H0']:
                        row_padding_top = 'padding-top: 8pt;'  # 8pt before H2 headings
                        row_padding_bottom = 'padding-bottom: 12pt;'  # 12pt after H2 headings
                    else:
                        row_padding_top = 'padding-top: 2pt;'  # Small space before H1/H3
                elif is_sum:
                    row_padding_bottom = 'padding-bottom: 10pt;'  # 10pt space after sums
                
                row_style = f'{row_padding_top} {row_padding_bottom}'
                
                # Label column
                td_label = ET.SubElement(tr, 'td')
                td_label.set('style', f'vertical-align: top; width: 9cm; {row_style}')
                p_label = ET.SubElement(td_label, 'p')
                if is_heading:
                    # H2/H0 → 11pt (larger BR headings like "Eget kapital")
                    # H1/H3 → 10pt (smaller BR headings like "Bundet eget kapital")
                    if style in ['H2', 'H0']:
                        p_label.set('class', 'H2-table')  # 11pt semibold
                    else:
                        p_label.set('class', 'H3-table')  # 10pt semibold
                    p_label.set('style', 'margin-top: 0; margin-bottom: 0;')
                elif is_sum:
                    p_label.set('class', 'sum-label')  # Semibold sum text
                    p_label.set('style', 'margin-top: 0; margin-bottom: 0;')
                else:
                    p_label.set('class', 'P')  # Normal body text
                    p_label.set('style', 'margin-top: 0; margin-bottom: 0;')
                p_label.text = label
                
                # Note column
                td_note = ET.SubElement(tr, 'td')
                td_note.set('style', f'vertical-align: top; width: 2cm; text-align: center; {row_style}')
                p_note = ET.SubElement(td_note, 'p')
                p_note.set('class', 'P')
                p_note.set('style', 'margin-top: 0; margin-bottom: 0;')
                p_note.text = note
                
                # Current year amount
                td_curr = ET.SubElement(tr, 'td')
                td_curr.set('style', f'vertical-align: top; width: 2.5cm; text-align: right; {row_style}')
                p_curr = ET.SubElement(td_curr, 'p')
                if is_sum:
                    p_curr.set('class', 'sum-amount')  # Semibold right-aligned
                    p_curr.set('style', 'margin-top: 0; margin-bottom: 0;')
                else:
                    p_curr.set('class', 'amount-right')  # Normal right-aligned
                    p_curr.set('style', 'margin-top: 0; margin-bottom: 0;')
                
                if is_heading:
                    p_curr.text = ''
                else:
                    curr_val = self._num(row.get('current_amount', 0))
                    prev_val = self._num(row.get('previous_amount', 0))
                    # Show amount if: non-zero, OR other year has value, OR always_show, OR has note
                    if curr_val != 0 or prev_val != 0 or row.get('always_show') or note:
                        variable_name = row.get('variable_name')
                        if variable_name and variable_name in br_mappings_dict:
                            mapping = br_mappings_dict[variable_name]
                            element_name = mapping.get('element_name')
                            namespace = mapping.get('tillhor', 'se-gen-base')
                            namespace_prefix = self._get_namespace_prefix(namespace)
                            element_qname = f'{namespace_prefix}:{element_name}'
                            
                            ix_curr = ET.SubElement(p_curr, 'ix:nonFraction')
                            ix_curr.set('name', element_qname)
                            ix_curr.set('contextRef', balans0_ref)
                            ix_curr.set('unitRef', unit_ref)
                            ix_curr.set('format', 'ixt:numdotdecimal')
                            ix_curr.set('decimals', '0')
                            ix_curr.set('scale', '3')
                            ix_curr.text = str(int(round(curr_val)))
                        else:
                            # Fallback to plain text (no decimals)
                            p_curr.text = self._format_monetary_value(curr_val, for_display=True)
                    else:
                        p_curr.text = ''
                
                # Spacing column
                td_spacing = ET.SubElement(tr, 'td')
                td_spacing.set('style', f'vertical-align: top; width: 0.5cm; {row_style}')
                p_spacing = ET.SubElement(td_spacing, 'p')
                p_spacing.set('class', 'P')
                p_spacing.set('style', 'margin-top: 0; margin-bottom: 0;')
                p_spacing.text = ''
                
                # Previous year amount
                td_prev = ET.SubElement(tr, 'td')
                td_prev.set('style', f'vertical-align: top; width: 2.5cm; text-align: right; {row_style}')
                p_prev = ET.SubElement(td_prev, 'p')
                if is_sum:
                    p_prev.set('class', 'sum-amount')  # Semibold right-aligned
                    p_prev.set('style', 'margin-top: 0; margin-bottom: 0;')
                else:
                    p_prev.set('class', 'amount-right')  # Normal right-aligned
                    p_prev.set('style', 'margin-top: 0; margin-bottom: 0;')
                
                if is_heading:
                    p_prev.text = ''
                else:
                    # prev_val already calculated above for current year logic
                    # Show amount if: non-zero, OR other year has value, OR always_show, OR has note
                    if prev_val != 0 or curr_val != 0 or row.get('always_show') or note:
                        variable_name = row.get('variable_name')
                        if variable_name and variable_name in br_mappings_dict:
                            mapping = br_mappings_dict[variable_name]
                            element_name = mapping.get('element_name')
                            namespace = mapping.get('tillhor', 'se-gen-base')
                            namespace_prefix = self._get_namespace_prefix(namespace)
                            element_qname = f'{namespace_prefix}:{element_name}'
                            
                            ix_prev = ET.SubElement(p_prev, 'ix:nonFraction')
                            ix_prev.set('name', element_qname)
                            ix_prev.set('contextRef', balans1_ref)
                            ix_prev.set('unitRef', unit_ref)
                            ix_prev.set('format', 'ixt:numdotdecimal')
                            ix_prev.set('decimals', '0')
                            ix_prev.set('scale', '3')
                            ix_prev.text = str(int(round(prev_val)))
                        else:
                            # Fallback to plain text (no decimals)
                            p_prev.text = self._format_monetary_value(prev_val, for_display=True)
                    else:
                        p_prev.text = ''
                
                # Final spacing column
                td_spacing2 = ET.SubElement(tr, 'td')
                td_spacing2.set('style', 'vertical-align: bottom; width: 0.5cm')
                p_spacing2 = ET.SubElement(td_spacing2, 'p')
                p_spacing2.set('class', 'normal')
                p_spacing2.text = ' '
    
    def _render_noter(self, body: ET.Element, company_data: Dict[str, Any],
                     company_name: str, org_number: str, fiscal_year: Optional[int],
                     prev_year: int, period0_ref: str, period1_ref: str,
                     balans0_ref: str, balans1_ref: str, unit_ref: str):
        """Render Noter section"""
        page5 = ET.SubElement(body, 'div')
        page5.set('class', 'pagebreak_before ar-page5')
        
        # Header
        header_table = ET.SubElement(page5, 'table')
        header_table.set('style', 'border-collapse: collapse; width: 17cm')
        tr_header = ET.SubElement(header_table, 'tr')
        
        td_name = ET.SubElement(tr_header, 'td')
        td_name.set('style', 'vertical-align: bottom; width: 9cm')
        p_name = ET.SubElement(td_name, 'p')
        p_name.set('class', 'normalsidhuvud')
        p_name.text = company_name
        p_org = ET.SubElement(td_name, 'p')
        p_org.set('class', 'normalsidhuvud')
        p_org.text = f'Org.nr {org_number}'
        
        td_not = ET.SubElement(tr_header, 'td')
        td_not.set('style', 'vertical-align: bottom; width: 1.5cm')
        p_not = ET.SubElement(td_not, 'p')
        p_not.set('class', 'normal')
        p_not.text = ' '
        
        td_year1 = ET.SubElement(tr_header, 'td')
        td_year1.set('style', 'vertical-align: bottom; width: 3cm')
        p_year1 = ET.SubElement(td_year1, 'p')
        p_year1.set('class', 'normal')
        p_year1.text = ' '
        
        td_page = ET.SubElement(tr_header, 'td')
        td_page.set('style', 'vertical-align: top; width: 3cm')
        p_page = ET.SubElement(td_page, 'p')
        p_page.set('class', 'b13')
        p_page.text = '5 (9)'  # TODO: Calculate actual page numbers
        
        # Add spacing
        p_spacing = ET.SubElement(page5, 'p')
        p_spacing.set('class', 'normal')
        p_spacing.text = ' '
        
        # Noter title
        p_title = ET.SubElement(page5, 'p')
        p_title.set('class', 'rubrik2')
        p_title.text = 'Noter'
        
        p_spacing2 = ET.SubElement(page5, 'p')
        p_spacing2.set('class', 'normal')
        p_spacing2.text = ' '
        
        p_tkr = ET.SubElement(page5, 'p')
        p_tkr.set('class', 'normal')
        p_tkr.text = 'Alla belopp i tkr om inget annat anges'
        
        p_spacing3 = ET.SubElement(page5, 'p')
        p_spacing3.set('class', 'normal')
        p_spacing3.text = ' '
        
        # Load noter data
        noter_data_raw = (company_data.get('noterData') or
                         company_data.get('noter_data') or
                         company_data.get('seFileData', {}).get('noter_data', []))
        
        # Load noter mappings
        try:
            from supabase import create_client
            import os
            from dotenv import load_dotenv
            load_dotenv()
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_ANON_KEY")
            if supabase_url and supabase_key:
                supabase = create_client(supabase_url, supabase_key)
                noter_mappings_response = supabase.table('variable_mapping_noter').select('variable_name,element_name,tillhor').execute()
                noter_mappings_dict = {m['variable_name']: m for m in noter_mappings_response.data if m.get('variable_name')}
            else:
                noter_mappings_dict = {}
        except:
            noter_mappings_dict = {}
        
        if noter_data_raw:
            # Group notes by note number
            notes_by_number = {}
            for row in noter_data_raw:
                note_num = row.get('note_number')
                if note_num:
                    if note_num not in notes_by_number:
                        notes_by_number[note_num] = []
                    notes_by_number[note_num].append(row)
            
            # Render each note
            for note_num in sorted(notes_by_number.keys()):
                rows = notes_by_number[note_num]
                
                # Note title
                p_note_title = ET.SubElement(page5, 'p')
                p_note_title.set('class', 'rubrik3')
                note_label = rows[0].get('note_label', f'Not {note_num}')
                p_note_title.text = f'Not {note_num} {note_label}'
                
                # Note table
                note_table = ET.SubElement(page5, 'table')
                note_table.set('style', 'border-collapse: collapse; width: 17cm')
                
                for row in rows:
                    # Skip show_tag=False rows
                    if row.get('show_tag') == False:
                        continue
                    
                    label = row.get('label', '').strip()
                    
                    # Skip if no content
                    if not label:
                        continue
                    
                    # Determine if heading or sum
                    style = row.get('style', '')
                    is_heading = style in ['H0', 'H1', 'H2', 'H3', 'H4']
                    is_sum = style in ['S1', 'S2', 'S3', 'S4'] or label.startswith('Summa ')
                    
                    # Create table row
                    tr = ET.SubElement(note_table, 'tr')
                    
                    # Label column
                    td_label = ET.SubElement(tr, 'td')
                    td_label.set('style', 'vertical-align: bottom; width: 10cm')
                    p_label = ET.SubElement(td_label, 'p')
                    if is_heading:
                        p_label.set('class', 'rubrik4')
                    elif is_sum:
                        p_label.set('class', 'summatext')
                    else:
                        p_label.set('class', 'normal')
                    p_label.text = label
                    
                    # Current year amount
                    td_curr = ET.SubElement(tr, 'td')
                    td_curr.set('style', 'vertical-align: bottom; width: 3cm')
                    p_curr = ET.SubElement(td_curr, 'p')
                    if is_sum:
                        p_curr.set('class', 'summabelopp')
                    else:
                        p_curr.set('class', 'belopp')
                    
                    if is_heading:
                        p_curr.text = ''
                    else:
                        curr_val = self._num(row.get('current_amount', 0))
                        if curr_val != 0 or row.get('always_show'):
                            variable_name = row.get('variable_name')
                            if variable_name and variable_name in noter_mappings_dict:
                                mapping = noter_mappings_dict[variable_name]
                                element_name = mapping.get('element_name')
                                namespace = mapping.get('tillhor', 'se-gen-base')
                                namespace_prefix = self._get_namespace_prefix(namespace)
                                element_qname = f'{namespace_prefix}:{element_name}'
                                
                                # Determine context based on data type
                                context_ref = period0_ref
                                if row.get('period_type') == 'instant':
                                    context_ref = balans0_ref
                                
                                ix_curr = ET.SubElement(p_curr, 'ix:nonFraction')
                                ix_curr.set('name', element_qname)
                                ix_curr.set('contextRef', context_ref)
                                ix_curr.set('unitRef', unit_ref)
                                ix_curr.set('format', 'ixt:numdotdecimal')
                                ix_curr.set('decimals', '0')
                                ix_curr.set('scale', '3')
                                ix_curr.text = str(int(round(curr_val)))
                            else:
                                p_curr.text = self._format_monetary_value(curr_val, for_display=True).replace('.', ',')
                        else:
                            p_curr.text = ''
                    
                    # Spacing column
                    td_spacing = ET.SubElement(tr, 'td')
                    td_spacing.set('style', 'vertical-align: bottom; width: 0.5cm')
                    p_spacing = ET.SubElement(td_spacing, 'p')
                    p_spacing.set('class', 'normal')
                    p_spacing.text = ' '
                    
                    # Previous year amount
                    td_prev = ET.SubElement(tr, 'td')
                    td_prev.set('style', 'vertical-align: bottom; width: 3cm')
                    p_prev = ET.SubElement(td_prev, 'p')
                    if is_sum:
                        p_prev.set('class', 'summabelopp')
                    else:
                        p_prev.set('class', 'belopp')
                    
                    if is_heading:
                        p_prev.text = ''
                    else:
                        prev_val = self._num(row.get('previous_amount', 0))
                        if prev_val != 0 or row.get('always_show'):
                            variable_name = row.get('variable_name')
                            if variable_name and variable_name in noter_mappings_dict:
                                mapping = noter_mappings_dict[variable_name]
                                element_name = mapping.get('element_name')
                                namespace = mapping.get('tillhor', 'se-gen-base')
                                namespace_prefix = self._get_namespace_prefix(namespace)
                                element_qname = f'{namespace_prefix}:{element_name}'
                                
                                # Determine context based on data type
                                context_ref = period1_ref
                                if row.get('period_type') == 'instant':
                                    context_ref = balans1_ref
                                
                                ix_prev = ET.SubElement(p_prev, 'ix:nonFraction')
                                ix_prev.set('name', element_qname)
                                ix_prev.set('contextRef', context_ref)
                                ix_prev.set('unitRef', unit_ref)
                                ix_prev.set('format', 'ixt:numdotdecimal')
                                ix_prev.set('decimals', '0')
                                ix_prev.set('scale', '3')
                                ix_prev.text = str(int(round(prev_val)))
                            else:
                                p_prev.text = self._format_monetary_value(prev_val, for_display=True).replace('.', ',')
                        else:
                            p_prev.text = ''
                
                # Add spacing after each note
                p_spacing_note = ET.SubElement(page5, 'p')
                p_spacing_note.set('class', 'normal')
                p_spacing_note.text = ' '
    
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

