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
            # Format with thousand separators (space) and 2 decimals for HTML display
            return f"{value:,.2f}".replace(',', ' ').replace('.', ',')
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
        """Return CSS styles that mirror the PDF typography (Roboto, headings, sums)."""
        return """
html {
  height: 100%;
}

@media screen {
  .ar-page0,
  .ar-page1,
  .ar-page2,
  .ar-page3,
  .ar-page4,
  .ar-page5,
  .ar-page6,
  .ar-page7,
  .ar-page8 {
    margin: 10px;
    padding: 0cm 0cm 0cm 1cm;
    border: 1px solid rgb(240, 240, 240);
    box-shadow: 0.25em 0.25em 0.3em #999;
    line-height: 1.2;
    min-height: 29.6926cm;
    max-width: 20.9804cm;
    background-color: #ffffff;
  }
}

@media print {
  html, body {
    height: 297mm;
    width: 210mm;
  }

  .ar-page0,
  .ar-page1,
  .ar-page2,
  .ar-page3,
  .ar-page4,
  .ar-page5,
  .ar-page6,
  .ar-page7,
  .ar-page8 {
    margin: 0;
    padding: 0cm 0cm 0cm 1cm;
    border: none;
    box-shadow: none;
    page-break-after: always;
  }

  .ar-page8 {
    page-break-after: auto;
  }
}

.pagebreak_before {
  page-break-before: always;
}

/* Base typography */

body {
  margin: 0;
  padding: 0;
  font-family: "Roboto", Arial, sans-serif;
  font-size: 10pt;
  line-height: 1.2;
  color: #000000;
}

p {
  margin-top: 0pt;
  margin-bottom: 0pt;
}

table {
  border-collapse: collapse;
  margin-top: 0pt;
  margin-bottom: 0pt;
}

.tab {
  border: 0;
  border-spacing: 0;
  padding: 0;
  margin-left: -3px;
}

/* Cover page */

.a16 {
  text-align: center;
  font-size: 10pt;
  font-weight: normal;
}

.a18 {
  text-align: center;
  font-size: 24pt;
  font-weight: 500;
}

.a17 {
  text-align: center;
  font-size: 16pt;
  font-weight: 500;
}

.a19 {
  text-align: center;
  font-size: 12pt;
  font-weight: 500;
}

/* Headings */

.rubrik2 {
  margin-top: 0pt;
  margin-bottom: 0pt;
  text-align: left;
  font-size: 16pt; /* H0: e.g. "Förvaltningsberättelse" */
  font-weight: 500;
}

.rubrik2b {
  margin-top: 0pt;
  margin-bottom: 0pt;
  text-align: left;
  font-size: 12pt; /* H1 used in FB headings */
  font-weight: 500;
}

.rubrik3 {
  margin-top: 12pt;
  margin-bottom: 0pt;
  text-align: left;
  font-size: 12pt; /* H1 */
  font-weight: 500;
}

.rubrik4 {
  margin-top: 8pt;
  margin-bottom: 0pt;
  text-align: left;
  font-size: 10pt; /* H2 / note headings */
  font-weight: 500;
}

/* Normal body text */

.a20,
.normal,
.a21,
.a22,
.b7,
.b8,
.b13,
.normalsidhuvud {
  text-align: left;
  font-size: 10pt;
  font-weight: normal;
}

/* Amount columns */

.b8 {
  text-align: left;
}

.b7,
.b13 {
  text-align: left;
}

.belopp {
  text-align: right;
  font-size: 10pt;
}

.summabelopp {
  text-align: right;
  font-size: 10pt;
  font-weight: 700;
}

.summatext,
.totalsummatext {
  text-align: left;
  font-size: 10pt;
  font-weight: 700;
}

.totalsummabelopp {
  text-align: right;
  font-size: 11pt;
  font-weight: 700;
}

/* Small annotation text like "Belopp i kr" */

.smalltext {
  font-size: 8pt;
}

/* Generic helpers */

.normalsidhuvud {
  text-align: left;
}

body .ar-page0 p,
body .ar-page1 p,
body .ar-page2 p,
body .ar-page3 p,
body .ar-page4 p,
body .ar-page5 p,
body .ar-page6 p,
body .ar-page7 p,
body .ar-page8 p {
  line-height: 1.2;
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
        """Render Förvaltningsberättelse section"""
        page1 = ET.SubElement(body, 'div')
        page1.set('class', 'pagebreak_before ar-page1')
        
        # Header with company name and page number
        header_table = ET.SubElement(page1, 'table')
        header_table.set('style', 'border-collapse: collapse; width: 17cm')
        tr_header = ET.SubElement(header_table, 'tr')
        
        td_name = ET.SubElement(tr_header, 'td')
        td_name.set('style', 'vertical-align: bottom; width: 13.5cm')
        p_name1 = ET.SubElement(td_name, 'p')
        p_name1.set('class', 'b8')
        p_name1.text = company_name
        p_org1 = ET.SubElement(td_name, 'p')
        p_org1.set('class', 'b8')
        p_org1.text = f'Org.nr {org_number}'
        
        td_page = ET.SubElement(tr_header, 'td')
        td_page.set('style', 'vertical-align: top; width: 3cm')
        p_page = ET.SubElement(td_page, 'p')
        p_page.set('class', 'b7')
        p_page.text = '2 (9)'  # TODO: Calculate actual page numbers
        
        # Add spacing
        p_spacing = ET.SubElement(page1, 'p')
        p_spacing.set('class', 'normal')
        p_spacing.text = ' '
        
        # Introduction text
        p_intro = ET.SubElement(page1, 'p')
        p_intro.set('class', 'a21')
        p_intro.text = f'Styrelsen för {company_name} avger följande årsredovisning för räkenskapsåret {fiscal_year}.'
        
        p_spacing2 = ET.SubElement(page1, 'p')
        p_spacing2.set('class', 'normal')
        p_spacing2.text = ' '
        
        # Currency note
        p_currency = ET.SubElement(page1, 'p')
        p_currency.set('class', 'normal')
        p_currency.text = 'Årsredovisningen är upprättad i svenska kronor, SEK. Om inte annat särskilt anges, redovisas alla belopp i tusentals kronor (Tkr). Uppgifter inom parentes avser föregående år.'
        
        # Add spacing
        for _ in range(2):
            p = ET.SubElement(page1, 'p')
            p.set('class', 'normal')
            p.text = ' '
        
        # "Förvaltningsberättelse" heading
        p_fb_title = ET.SubElement(page1, 'p')
        p_fb_title.set('class', 'rubrik2')
        p_fb_title.text = 'Förvaltningsberättelse'
        
        # Add spacing
        for _ in range(2):
            p = ET.SubElement(page1, 'p')
            p.set('class', 'normal')
            p.text = ' '
        
        # Load FB data
        fb_data_raw = (company_data.get('fbData') or
                      company_data.get('fb_variables') or
                      company_data.get('fbVariables') or
                      company_data.get('forvaltningsberattelse', {}))
        
        # Load FB mappings for XBRL tags
        try:
            from supabase import create_client
            import os
            from dotenv import load_dotenv
            load_dotenv()
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_ANON_KEY")
            if supabase_url and supabase_key:
                supabase = create_client(supabase_url, supabase_key)
                fb_mappings_response = supabase.table('variable_mapping_fb').select('variable_name,element_name,tillhor').execute()
                fb_mappings_dict = {m['variable_name']: m for m in fb_mappings_response.data if m.get('variable_name')}
            else:
                fb_mappings_dict = {}
        except:
            fb_mappings_dict = {}
        
        if fb_data_raw:
            # Section: Verksamheten
            if fb_data_raw.get('fb_beskrivning_verksamhet'):
                p_heading1 = ET.SubElement(page1, 'p')
                p_heading1.set('class', 'rubrik3')
                p_heading1.text = 'Verksamheten'
                
                p_content1 = ET.SubElement(page1, 'p')
                p_content1.set('class', 'normal')
                verksamhet_text = fb_data_raw.get('fb_beskrivning_verksamhet', '')
                
                # Add XBRL tagging if available
                if 'fb_beskrivning_verksamhet' in fb_mappings_dict:
                    mapping = fb_mappings_dict['fb_beskrivning_verksamhet']
                    element_name = mapping.get('element_name')
                    namespace = mapping.get('tillhor', 'se-gen-base')
                    namespace_prefix = self._get_namespace_prefix(namespace)
                    element_qname = f'{namespace_prefix}:{element_name}'
                    
                    ix_text = ET.SubElement(p_content1, 'ix:nonNumeric')
                    ix_text.set('name', element_qname)
                    ix_text.set('contextRef', period0_ref)
                    ix_text.text = verksamhet_text
                else:
                    p_content1.text = verksamhet_text
                
                for _ in range(2):
                    p = ET.SubElement(page1, 'p')
                    p.set('class', 'normal')
                    p.text = ' '
            
            # Section: Väsentliga händelser
            if fb_data_raw.get('fb_vasentliga_handelser'):
                p_heading2 = ET.SubElement(page1, 'p')
                p_heading2.set('class', 'rubrik3')
                p_heading2.text = 'Väsentliga händelser under räkenskapsåret'
                
                p_content2 = ET.SubElement(page1, 'p')
                p_content2.set('class', 'normal')
                handelser_text = fb_data_raw.get('fb_vasentliga_handelser', '')
                
                # Add XBRL tagging if available
                if 'fb_vasentliga_handelser' in fb_mappings_dict:
                    mapping = fb_mappings_dict['fb_vasentliga_handelser']
                    element_name = mapping.get('element_name')
                    namespace = mapping.get('tillhor', 'se-gen-base')
                    namespace_prefix = self._get_namespace_prefix(namespace)
                    element_qname = f'{namespace_prefix}:{element_name}'
                    
                    ix_text = ET.SubElement(p_content2, 'ix:nonNumeric')
                    ix_text.set('name', element_qname)
                    ix_text.set('contextRef', period0_ref)
                    ix_text.text = handelser_text
                else:
                    p_content2.text = handelser_text
                
                for _ in range(2):
                    p = ET.SubElement(page1, 'p')
                    p.set('class', 'normal')
                    p.text = ' '
            
            # Section: Flerårsöversikt (Multi-year overview table)
            p_heading3 = ET.SubElement(page1, 'p')
            p_heading3.set('class', 'rubrik3')
            p_heading3.text = 'Flerårsöversikt'
            
            multi_year_table = ET.SubElement(page1, 'table')
            multi_year_table.set('style', 'border-collapse: collapse; width: 17cm')
            
            # Table header
            tr_header = ET.SubElement(multi_year_table, 'tr')
            td_label = ET.SubElement(tr_header, 'td')
            td_label.set('style', 'vertical-align: bottom; width: 8cm')
            p_label = ET.SubElement(td_label, 'p')
            p_label.set('class', 'rubrik4')
            p_label.text = 'Tkr'
            
            td_year = ET.SubElement(tr_header, 'td')
            td_year.set('style', 'vertical-align: bottom; width: 3cm')
            p_year = ET.SubElement(td_year, 'p')
            p_year.set('class', 'summabelopp')
            p_year.text = str(fiscal_year) if fiscal_year else ''
            
            td_prev_year = ET.SubElement(tr_header, 'td')
            td_prev_year.set('style', 'vertical-align: bottom; width: 3cm')
            p_prev_year = ET.SubElement(td_prev_year, 'p')
            p_prev_year.set('class', 'summabelopp')
            p_prev_year.text = str(prev_year) if prev_year else ''
            
            # Add key metrics rows (example rows - adapt based on actual FB data structure)
            metrics = [
                ('Nettoomsättning', fb_data_raw.get('fb_nettoomsattning_curr'), fb_data_raw.get('fb_nettoomsattning_prev')),
                ('Resultat efter finansiella poster', fb_data_raw.get('fb_resultat_efter_fin_curr'), fb_data_raw.get('fb_resultat_efter_fin_prev')),
                ('Balansomslutning', fb_data_raw.get('fb_balansomslutning_curr'), fb_data_raw.get('fb_balansomslutning_prev')),
                ('Soliditet, %', fb_data_raw.get('fb_soliditet_curr'), fb_data_raw.get('fb_soliditet_prev')),
            ]
            
            for label, curr_val, prev_val in metrics:
                if curr_val is not None or prev_val is not None:
                    tr = ET.SubElement(multi_year_table, 'tr')
                    
                    td_label = ET.SubElement(tr, 'td')
                    td_label.set('style', 'vertical-align: bottom; width: 8cm')
                    p_label = ET.SubElement(td_label, 'p')
                    p_label.set('class', 'normal')
                    p_label.text = label
                    
                    td_curr = ET.SubElement(tr, 'td')
                    td_curr.set('style', 'vertical-align: bottom; width: 3cm')
                    p_curr = ET.SubElement(td_curr, 'p')
                    p_curr.set('class', 'belopp')
                    if curr_val is not None:
                        p_curr.text = self._format_monetary_value(self._num(curr_val), for_display=True).replace('.', ',')
                    else:
                        p_curr.text = ''
                    
                    td_prev = ET.SubElement(tr, 'td')
                    td_prev.set('style', 'vertical-align: bottom; width: 3cm')
                    p_prev = ET.SubElement(td_prev, 'p')
                    p_prev.set('class', 'belopp')
                    if prev_val is not None:
                        p_prev.text = self._format_monetary_value(self._num(prev_val), for_display=True).replace('.', ',')
                    else:
                        p_prev.text = ''
            
            for _ in range(2):
                p = ET.SubElement(page1, 'p')
                p.set('class', 'normal')
                p.text = ' '
    
    def _render_resultatrakning(self, body: ET.Element, company_data: Dict[str, Any],
                                company_name: str, org_number: str, fiscal_year: Optional[int],
                                prev_year: int, period0_ref: str, period1_ref: str, unit_ref: str):
        """Render Resultaträkning section"""
        page2 = ET.SubElement(body, 'div')
        page2.set('class', 'pagebreak_before ar-page2')
        
        # Header
        header_table = ET.SubElement(page2, 'table')
        header_table.set('style', 'border-collapse: collapse; width: 17cm')
        tr_header = ET.SubElement(header_table, 'tr')
        
        td_title = ET.SubElement(tr_header, 'td')
        td_title.set('style', 'vertical-align: top; width: 9cm')
        p_title = ET.SubElement(td_title, 'p')
        p_title.set('class', 'rubrik2')
        p_title.text = 'Resultaträkning'
        p_tkr = ET.SubElement(td_title, 'p')
        p_tkr.set('class', 'normal')
        p_tkr.text = 'Tkr'
        
        td_not = ET.SubElement(tr_header, 'td')
        td_not.set('style', 'vertical-align: top; width: 1.5cm')
        p_not = ET.SubElement(td_not, 'p')
        p_not.set('class', 'rubrik3')
        p_not.text = 'Not'
        
        td_year1 = ET.SubElement(tr_header, 'td')
        td_year1.set('style', 'vertical-align: top; width: 3cm')
        p_year1_start = ET.SubElement(td_year1, 'p')
        p_year1_start.set('class', 'belopp')
        span_year1 = ET.SubElement(p_year1_start, 'span')
        span_year1.set('style', 'font-weight: bold')
        span_year1.text = f'{fiscal_year}-01-01' if fiscal_year else ''
        p_year1_end = ET.SubElement(td_year1, 'p')
        p_year1_end.set('class', 'summabelopp')
        p_year1_end.text = f'-{fiscal_year}-12-31' if fiscal_year else ''
        
        td_year2 = ET.SubElement(tr_header, 'td')
        td_year2.set('style', 'vertical-align: top; width: 3cm')
        p_year2_start = ET.SubElement(td_year2, 'p')
        p_year2_start.set('class', 'summabelopp')
        p_year2_start.text = f'{prev_year}-01-01' if prev_year else ''
        p_year2_end = ET.SubElement(td_year2, 'p')
        p_year2_end.set('class', 'summabelopp')
        p_year2_end.text = f'-{prev_year}-12-31' if prev_year else ''
        
        # Add spacing
        p_spacing = ET.SubElement(page2, 'p')
        p_spacing.set('class', 'normal')
        p_spacing.text = ' '
        
        # RR table
        rr_data_raw = (company_data.get('rrData') or 
                      company_data.get('rrRows') or 
                      company_data.get('seFileData', {}).get('rr_data', []))
        
        if rr_data_raw:
            rr_table = ET.SubElement(page2, 'table')
            rr_table.set('style', 'border-collapse: collapse; width: 17cm')
            
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
            
            # Filter and render RR rows
            seen_rorelseresultat = False
            for row in rr_data_raw:
                # Skip show_tag=False rows (UI-only flag)
                if row.get('show_tag') == False:
                    continue
                
                label = row.get('label', '')
                
                # Skip first occurrence of "Rörelseresultat" (duplicate)
                if label == 'Rörelseresultat':
                    if not seen_rorelseresultat:
                        seen_rorelseresultat = True
                        continue
                
                # Apply show/hide logic
                if not self._should_show_row(row, rr_data_raw, 'rr'):
                    continue
                
                # Determine if heading or sum
                style = row.get('style', '')
                is_heading = style in ['H0', 'H1', 'H2', 'H3', 'H4']
                is_sum = style in ['S1', 'S2', 'S3', 'S4'] or label.startswith('Summa ')
                
                # Get note number
                note = str(row.get('note_number', '')) if row.get('note_number') else ''
                if 'Personalkostnader' in label or 'personalkostnader' in label.lower():
                    note = '2'
                
                # Create table row
                tr = ET.SubElement(rr_table, 'tr')
                
                # Label column
                td_label = ET.SubElement(tr, 'td')
                td_label.set('style', 'vertical-align: bottom; width: 9cm')
                p_label = ET.SubElement(td_label, 'p')
                if is_heading or is_sum:
                    p_label.set('class', 'summatext' if is_sum else 'rubrik4')
                else:
                    p_label.set('class', 'normal')
                p_label.text = label
                
                # Note column
                td_note = ET.SubElement(tr, 'td')
                td_note.set('style', 'vertical-align: bottom; width: 2cm')
                p_note = ET.SubElement(td_note, 'p')
                p_note.set('class', 'normal')
                p_note.text = note
                
                # Current year amount
                td_curr = ET.SubElement(tr, 'td')
                td_curr.set('style', 'vertical-align: bottom; width: 2.5cm')
                p_curr = ET.SubElement(td_curr, 'p')
                if is_sum:
                    p_curr.set('class', 'summabelopp')
                else:
                    p_curr.set('class', 'belopp')
                
                if is_heading:
                    p_curr.text = ''
                else:
                    curr_val = self._num(row.get('current_amount', 0))
                    if curr_val != 0 or row.get('always_show') or note:
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
                            # Fallback to plain text
                            p_curr.text = self._format_monetary_value(curr_val, for_display=True).replace('.', ',').replace(' ', ' ')
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
                td_prev.set('style', 'vertical-align: bottom; width: 2.5cm')
                p_prev = ET.SubElement(td_prev, 'p')
                if is_sum:
                    p_prev.set('class', 'summabelopp')
                else:
                    p_prev.set('class', 'belopp')
                
                if is_heading:
                    p_prev.text = ''
                else:
                    prev_val = self._num(row.get('previous_amount', 0))
                    if prev_val != 0 or row.get('always_show') or note:
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
                            # Fallback to plain text
                            p_prev.text = self._format_monetary_value(prev_val, for_display=True).replace('.', ',').replace(' ', ' ')
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
        
        # Header
        header_table = ET.SubElement(page3, 'table')
        header_table.set('style', 'border-collapse: collapse; width: 17cm')
        tr_header = ET.SubElement(header_table, 'tr')
        
        td_title = ET.SubElement(tr_header, 'td')
        td_title.set('style', 'vertical-align: top; width: 9cm')
        p_title = ET.SubElement(td_title, 'p')
        p_title.set('class', 'rubrik2')
        p_title.text = 'Balansräkning'
        p_tkr = ET.SubElement(td_title, 'p')
        p_tkr.set('class', 'normal')
        p_tkr.text = 'Tkr'
        
        td_not = ET.SubElement(tr_header, 'td')
        td_not.set('style', 'vertical-align: top; width: 1.5cm')
        p_not = ET.SubElement(td_not, 'p')
        p_not.set('class', 'rubrik3')
        p_not.text = 'Not'
        
        td_year1 = ET.SubElement(tr_header, 'td')
        td_year1.set('style', 'vertical-align: top; width: 3cm')
        p_year1 = ET.SubElement(td_year1, 'p')
        p_year1.set('class', 'summabelopp')
        p_year1.text = f'{fiscal_year}-12-31' if fiscal_year else ''
        
        td_year2 = ET.SubElement(tr_header, 'td')
        td_year2.set('style', 'vertical-align: top; width: 3cm')
        p_year2 = ET.SubElement(td_year2, 'p')
        p_year2.set('class', 'summabelopp')
        p_year2.text = f'{prev_year}-12-31' if prev_year else ''
        
        # Add spacing
        p_spacing = ET.SubElement(page3, 'p')
        p_spacing.set('class', 'normal')
        p_spacing.text = ' '
        
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
            br_table.set('style', 'border-collapse: collapse; width: 17cm')
            
            # Filter assets only
            br_assets = [r for r in br_data_raw if r.get('type') == 'asset']
            
            for row in br_assets:
                # Skip show_tag=False rows
                if row.get('show_tag') == False:
                    continue
                
                label = row.get('label', '').strip()
                
                # Skip "Tillgångar" top-level heading
                if label == 'Tillgångar':
                    continue
                
                # Skip equity/liability headings
                if label in ['Eget kapital och skulder', 'Eget kapital', 'Bundet eget kapital', 'Fritt eget kapital', 'Tecknat men ej inbetalt kapital']:
                    continue
                
                # Apply show/hide logic
                if not self._should_show_row(row, br_assets, 'br'):
                    continue
                
                # Determine if heading or sum
                style = row.get('style', '')
                is_heading = style in ['H0', 'H1', 'H2', 'H3', 'H4']
                is_sum = style in ['S1', 'S2', 'S3', 'S4'] or label.startswith('Summa ')
                
                # Get note number
                note = str(row.get('note_number', '')) if row.get('note_number') else ''
                
                # Create table row
                tr = ET.SubElement(br_table, 'tr')
                
                # Label column
                td_label = ET.SubElement(tr, 'td')
                td_label.set('style', 'vertical-align: bottom; width: 9cm')
                p_label = ET.SubElement(td_label, 'p')
                if is_heading:
                    if style == 'H2':
                        p_label.set('class', 'rubrik3')
                    else:
                        p_label.set('class', 'rubrik4')
                elif is_sum:
                    p_label.set('class', 'summatext')
                else:
                    p_label.set('class', 'normal')
                p_label.text = label
                
                # Note column
                td_note = ET.SubElement(tr, 'td')
                td_note.set('style', 'vertical-align: bottom; width: 2cm')
                p_note = ET.SubElement(td_note, 'p')
                p_note.set('class', 'normal')
                p_note.text = note
                
                # Current year amount
                td_curr = ET.SubElement(tr, 'td')
                td_curr.set('style', 'vertical-align: bottom; width: 2.5cm')
                p_curr = ET.SubElement(td_curr, 'p')
                if is_sum:
                    p_curr.set('class', 'summabelopp')
                else:
                    p_curr.set('class', 'belopp')
                
                if is_heading:
                    p_curr.text = ''
                else:
                    curr_val = self._num(row.get('current_amount', 0))
                    if curr_val != 0 or row.get('always_show') or note:
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
                td_prev.set('style', 'vertical-align: bottom; width: 2.5cm')
                p_prev = ET.SubElement(td_prev, 'p')
                if is_sum:
                    p_prev.set('class', 'summabelopp')
                else:
                    p_prev.set('class', 'belopp')
                
                if is_heading:
                    p_prev.text = ''
                else:
                    prev_val = self._num(row.get('previous_amount', 0))
                    if prev_val != 0 or row.get('always_show') or note:
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
                            p_prev.text = self._format_monetary_value(prev_val, for_display=True).replace('.', ',')
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
        
        # Header (similar to page 3)
        header_table = ET.SubElement(page4, 'table')
        header_table.set('style', 'border-collapse: collapse; width: 17cm')
        tr_header = ET.SubElement(header_table, 'tr')
        
        td_name = ET.SubElement(tr_header, 'td')
        td_name.set('style', 'vertical-align: bottom; width: 9cm')
        p_name1 = ET.SubElement(td_name, 'p')
        p_name1.set('class', 'normalsidhuvud')
        p_name1.text = company_name
        p_org1 = ET.SubElement(td_name, 'p')
        p_org1.set('class', 'normalsidhuvud')
        p_org1.text = f'Org.nr {org_number}'
        
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
        p_page.text = '4 (9)'  # TODO: Calculate actual page numbers
        
        # Add spacing
        p_spacing = ET.SubElement(page4, 'p')
        p_spacing.set('class', 'normal')
        p_spacing.text = ' '
        
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
            br_table.set('style', 'border-collapse: collapse; width: 17cm')
            
            # Filter equity and liabilities only
            br_equity_liabilities = [r for r in br_data_raw if r.get('type') in ['equity', 'liability']]
            
            for row in br_equity_liabilities:
                # Skip show_tag=False rows
                if row.get('show_tag') == False:
                    continue
                
                label = row.get('label', '').strip()
                
                # Apply show/hide logic
                if not self._should_show_row(row, br_equity_liabilities, 'br'):
                    continue
                
                # Determine if heading or sum
                style = row.get('style', '')
                is_heading = style in ['H0', 'H1', 'H2', 'H3', 'H4']
                is_sum = style in ['S1', 'S2', 'S3', 'S4'] or label.startswith('Summa ')
                
                # Get note number
                note = str(row.get('note_number', '')) if row.get('note_number') else ''
                
                # Create table row (same structure as assets)
                tr = ET.SubElement(br_table, 'tr')
                
                # Label column
                td_label = ET.SubElement(tr, 'td')
                td_label.set('style', 'vertical-align: bottom; width: 9cm')
                p_label = ET.SubElement(td_label, 'p')
                if is_heading:
                    if style == 'H2':
                        p_label.set('class', 'rubrik3')
                    else:
                        p_label.set('class', 'rubrik4')
                elif is_sum:
                    if label == 'Summa eget kapital och skulder':
                        p_label.set('class', 'totalsummatext')
                    else:
                        p_label.set('class', 'summatext')
                else:
                    p_label.set('class', 'normal')
                p_label.text = label
                
                # Note column
                td_note = ET.SubElement(tr, 'td')
                td_note.set('style', 'vertical-align: bottom; width: 2cm')
                p_note = ET.SubElement(td_note, 'p')
                p_note.set('class', 'normal')
                p_note.text = note
                
                # Current year amount
                td_curr = ET.SubElement(tr, 'td')
                td_curr.set('style', 'vertical-align: bottom; width: 2.5cm')
                p_curr = ET.SubElement(td_curr, 'p')
                if is_sum:
                    if label == 'Summa eget kapital och skulder':
                        p_curr.set('class', 'totalsummabelopp')
                    else:
                        p_curr.set('class', 'summabelopp')
                else:
                    p_curr.set('class', 'belopp')
                
                if is_heading:
                    p_curr.text = ''
                else:
                    curr_val = self._num(row.get('current_amount', 0))
                    if curr_val != 0 or row.get('always_show') or note:
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
                td_prev.set('style', 'vertical-align: bottom; width: 2.5cm')
                p_prev = ET.SubElement(td_prev, 'p')
                if is_sum:
                    if label == 'Summa eget kapital och skulder':
                        p_prev.set('class', 'totalsummabelopp')
                    else:
                        p_prev.set('class', 'summabelopp')
                else:
                    p_prev.set('class', 'belopp')
                
                if is_heading:
                    p_prev.text = ''
                else:
                    prev_val = self._num(row.get('previous_amount', 0))
                    if prev_val != 0 or row.get('always_show') or note:
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
                            p_prev.text = self._format_monetary_value(prev_val, for_display=True).replace('.', ',')
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

