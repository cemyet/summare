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
                               end_date: Optional[str] = None, instant_date: Optional[str] = None) -> str:
        """Get or create a context ID for the given period"""
        if period_type == 'duration':
            key = f"duration_{start_date}_{end_date}"
        else:
            key = f"instant_{instant_date}"
        
        if key not in self.contexts:
            self.context_counter += 1
            context_id = f"c{self.context_counter}"
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
                 context_ref: Optional[str] = None):
        """Add a fact to the XBRL document"""
        # Get or create context
        if not context_ref:
            context_ref = self._get_or_create_context(period_type, start_date, end_date, instant_date)
        
        # Get or create unit (only for monetary items)
        if not unit_ref and data_type == 'monetaryItemType':
            unit_ref = self._get_or_create_unit('SEK')
        elif data_type != 'monetaryItemType':
            unit_ref = None  # No unit for non-monetary items
        
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
            'data_type': data_type
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
        
        # Add meta tags
        meta_program = ET.SubElement(head, 'meta')
        meta_program.set('name', 'programvara')
        meta_program.set('content', 'Summare')
        
        meta_version = ET.SubElement(head, 'meta')
        meta_version.set('name', 'programversion')
        meta_version.set('content', '1.0')
        
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
        
        # Add CSS styles (basic styling)
        style = ET.SubElement(head, 'style')
        style.set('type', 'text/css')
        style.text = """
            body { margin: 0; font-family: Arial, sans-serif; }
            table { margin: auto; border-collapse: collapse; }
            .blank_row { height: 14px; background-color: #FFFFFF; }
        """
        
        # Create body element
        body = ET.SubElement(root, 'body')
        
        # Create hidden div for iXBRL content
        hidden_div = ET.SubElement(body, 'div')
        hidden_div.set('style', 'display:none')
        
        # Create ix:header element
        ix_header = ET.SubElement(hidden_div, 'ix:header')
        
        # Create ix:hidden element for XBRL facts
        ix_hidden = ET.SubElement(ix_header, 'ix:hidden')
        
        # Create xbrli:xbrl element inside ix:hidden for contexts and units
        xbrl_root = ET.SubElement(ix_hidden, 'xbrli:xbrl')
        
        # Add schemaRef(s) – main K2-all AB RISBS 2024 taxonomy
        schema_ref = ET.SubElement(xbrl_root, 'link:schemaRef')
        schema_ref.set('xlink:type', 'simple')
        schema_ref.set(
            'xlink:href',
            'http://www.taxonomier.se/se/fr/gaap/k2-all/ab/risbs/2024-09-12/se-k2-ab-risbs-2024-09-12.xsd'
        )
        
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
                    data_type='monetaryItemType'
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
                    data_type='monetaryItemType'
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
                    data_type='monetaryItemType'
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
                        data_type='monetaryItemType'
                    )
                else:
                    prev_end = self._format_date(f"{fiscal_year - 1}1231") if fiscal_year else None
                    self.add_fact(
                        element_name=element_name,
                        namespace=namespace,
                        value=prev_value,
                        period_type='instant',
                        instant_date=prev_end,
                        data_type='monetaryItemType'
                    )
        
        # Process Signature info
        self._add_signature_facts(company_data, end_date)
        
        # Add all contexts to xbrl_root
        org_number_clean = (company_info.get('organization_number', '') or 
                           company_data.get('organization_number', '') or
                           company_data.get('organizationNumber', '')).replace('-', '')
        for context_key, context_info in self.contexts.items():
            context_element = ET.SubElement(xbrl_root, 'xbrli:context')
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
        
        # Add all units to xbrl_root
        for unit_key, unit_info in self.units.items():
            unit_element = ET.SubElement(xbrl_root, 'xbrli:unit')
            unit_element.set('id', unit_info['id'])
            measure = ET.SubElement(unit_element, 'xbrli:measure')
            measure.text = f'iso4217:{unit_info["currency"]}'
        
        # Add transformation rules for iXBRL
        ixt_ns = ET.SubElement(ix_hidden, 'ixt:transform')
        ixt_ns.set('name', 'numdotdecimal')
        ixt_ns.set('scale', '0')
        ixt_ns.set('infinity', 'false')
        ixt_ns.set('zerotxt', 'false')
        ixt_ns.set('negativesign', '-')
        ixt_ns.set('negativenumberformat', 'negparen')
        ixt_ns.set('trailingzeros', 'false')
        
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
                fact_element.set('format', 'ixt:numdotdecimal')
                fact_element.text = fact['value']
            else:
                # Use ix:nonNumeric for strings, dates, enums
                fact_element = ET.SubElement(ix_hidden, 'ix:nonNumeric')
                fact_element.set('name', element_qname)
                fact_element.set('contextRef', fact['context_ref'])
                fact_element.text = fact['value']
        
        # Also add facts to xbrl_root for validation (standard XBRL format)
        for fact in self.facts:
            namespace_prefix = self._get_namespace_prefix(fact['namespace'])
            fact_element = ET.SubElement(xbrl_root, f'{namespace_prefix}:{fact["element_name"]}')
            fact_element.set('contextRef', fact['context_ref'])
            if fact['unit_ref']:
                fact_element.set('unitRef', fact['unit_ref'])
            fact_element.text = fact['value']
        
        # ------------------------------------------------------------------
        # Minimal visible HTML so the page is not blank
        # ------------------------------------------------------------------
        visible_container = ET.SubElement(body, 'div')
        visible_container.set(
            'style',
            'max-width: 900px; margin: 40px auto; font-family: Arial, sans-serif;'
        )
        
        company_name = (company_info.get('company_name')
                        or company_data.get('company_name')
                        or company_data.get('companyName')
                        or 'Årsredovisning')
        
        h1 = ET.SubElement(visible_container, 'h1')
        h1.text = f'Årsredovisning – {company_name}'
        
        if start_date and end_date:
            p_period = ET.SubElement(visible_container, 'p')
            p_period.text = f'Räkenskapsår {start_date} – {end_date}'
        
        # Very simple RR table (for debugging / visual sanity check)
        rr_data = (company_data.get('rrData')
                   or company_data.get('rrRows')
                   or company_data.get('rr_data')
                   or (company_data.get('seFileData') or {}).get('rr_data', []))
        
        if rr_data and isinstance(rr_data, list) and len(rr_data) > 0:
            h2_rr = ET.SubElement(visible_container, 'h2')
            h2_rr.text = 'Resultaträkning (översikt)'
            
            rr_table = ET.SubElement(visible_container, 'table')
            rr_table.set('border', '1')
            rr_table.set('cellpadding', '4')
            rr_table.set('style', 'border-collapse:collapse;width:100%;')
            
            header_row = ET.SubElement(rr_table, 'tr')
            for col in ('Post', 'Belopp innevarande år'):
                th = ET.SubElement(header_row, 'th')
                th.text = col
            
            for item in rr_data:
                if not item.get('show_amount'):
                    continue
                
                label = (item.get('row_title')
                         or item.get('label')
                         or item.get('radrubrik')
                         or item.get('variable_name'))
                
                value = item.get('current_amount')
                if value is None:
                    continue
                
                row = ET.SubElement(rr_table, 'tr')
                td_label = ET.SubElement(row, 'td')
                td_label.text = str(label)
                
                td_value = ET.SubElement(row, 'td')
                # Use plain text here; XBRL facts are already in ix:hidden
                td_value.text = self._format_monetary_value(value, for_display=True)
        
        # Simple BR table
        br_data = (company_data.get('brData')
                   or company_data.get('brRows')
                   or company_data.get('br_data')
                   or (company_data.get('seFileData') or {}).get('br_data', []))
        
        if br_data and isinstance(br_data, list) and len(br_data) > 0:
            h2_br = ET.SubElement(visible_container, 'h2')
            h2_br.text = 'Balansräkning (översikt)'
            
            br_table = ET.SubElement(visible_container, 'table')
            br_table.set('border', '1')
            br_table.set('cellpadding', '4')
            br_table.set('style', 'border-collapse:collapse;width:100%;')
            
            header_row = ET.SubElement(br_table, 'tr')
            for col in ('Post', 'Belopp innevarande år'):
                th = ET.SubElement(header_row, 'th')
                th.text = col
            
            for item in br_data:
                if not item.get('show_amount'):
                    continue
                
                label = (item.get('row_title')
                         or item.get('label')
                         or item.get('radrubrik')
                         or item.get('variable_name'))
                
                value = item.get('current_amount')
                if value is None:
                    continue
                
                row = ET.SubElement(br_table, 'tr')
                td_label = ET.SubElement(row, 'td')
                td_label.text = str(label)
                
                td_value = ET.SubElement(row, 'td')
                td_value.text = self._format_monetary_value(value)
        
        # Convert to pretty XML string
        rough_string = ET.tostring(root, encoding='unicode')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ", encoding=None)
    
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

