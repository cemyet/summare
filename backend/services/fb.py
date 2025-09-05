"""
Förvaltningsberättelse (FB) Module
Standalone module for calculating "Förändring i eget kapital" table
"""

import re
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict


class ForvaltningsberattelseFB:
    """Förvaltningsberättelse module for calculating Förändring i eget kapital"""
    
    def __init__(self):
        self.br_data = None
        self.verifications = []
        self.calculated_variables = {}
        
    def _normalize_float(self, value: str) -> float:
        """Normalize string to float, handling Swedish number format"""
        if not value:
            return 0.0
        # Handle Swedish number format with spaces and commas
        value = str(value).strip().replace(" ", "").replace("\u00A0", "").replace(",", ".")
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0
    
    def _parse_sie_verifications(self, sie_text: str) -> List[Dict[str, Any]]:
        """Parse SIE file verifications and transactions"""
        lines = sie_text.splitlines()
        verifications = []
        
        # Regex patterns for parsing
        ver_header_re = re.compile(r'^#VER\s+(\S+)\s+(\d+)\s+(\d{8})(?:\s+(?:"([^"]*)"|(.+)))?\s*$')
        trans_re = re.compile(
            r'^#(?:BTRANS|RTRANS|TRANS)\s+'
            r'(\d{3,4})'  # Account number
            r'(?:\s+\{.*?\})?'  # Optional object
            r'\s+(-?(?:\d{1,3}(?:[ \u00A0]?\d{3})*|\d+)(?:[.,]\d+)?)'  # Amount
            r'(?:\s+\d{8})?'  # Optional date
            r'(?:\s+"(.*?)")?'  # Optional text
            r'\s*$'
        )
        
        current_ver = None
        in_block = False
        
        for line in lines:
            line = line.strip()
            
            # Check for verification header
            ver_match = ver_header_re.match(line)
            if ver_match:
                current_ver = {
                    'series': ver_match.group(1),
                    'number': int(ver_match.group(2)),
                    'date': ver_match.group(3),
                    'text': (ver_match.group(4) or ver_match.group(5) or "").strip('"'),
                    'transactions': []
                }
                continue
            
            # Handle block start/end
            if line == "{":
                in_block = True
                continue
            elif line == "}":
                in_block = False
                if current_ver:
                    verifications.append(current_ver)
                    current_ver = None
                continue
            
            # Parse transactions within blocks
            if in_block and current_ver:
                trans_match = trans_re.match(line)
                if trans_match:
                    account = int(trans_match.group(1))
                    amount = self._normalize_float(trans_match.group(2))
                    text = trans_match.group(3) or ""
                    
                    current_ver['transactions'].append({
                        'account': account,
                        'amount': amount,
                        'text': text
                    })
        
        return verifications
    
    def _calculate_utdelning_from_verifications(self, verifications: List[Dict[str, Any]]) -> float:
        """
        Calculate utdelning based on verification patterns:
        1. Look for verifications with 2898 account (preferred method)
        2. Fallback: Look for verifications with 2091 DEBET and 1XXX KREDIT
        """
        utdelning_amount = 0.0
        
        for ver in verifications:
            transactions = ver['transactions']
            
            # Method 1: Look for 2898 account usage
            has_2898 = any(t['account'] == 2898 for t in transactions)
            if has_2898:
                # Sum all amounts for account 2898 in this verification
                for trans in transactions:
                    if trans['account'] == 2898:
                        utdelning_amount += abs(trans['amount'])  # Take absolute value
                continue
            
            # Method 2: Fallback - Look for 2091 DEBET and 1XXX KREDIT pattern
            has_2091_debet = False
            has_1xxx_kredit = False
            ver_utdelning = 0.0
            
            for trans in transactions:
                if trans['account'] == 2091 and trans['amount'] > 0:  # DEBET (positive amount)
                    has_2091_debet = True
                    ver_utdelning = trans['amount']
                elif 1000 <= trans['account'] <= 1999 and trans['amount'] < 0:  # KREDIT (negative amount)
                    has_1xxx_kredit = True
            
            # If both conditions are met, this is likely a dividend payment
            if has_2091_debet and has_1xxx_kredit:
                utdelning_amount += ver_utdelning
        
        return utdelning_amount
    
    def _calculate_nyemission_from_verifications(self, verifications: List[Dict[str, Any]]) -> float:
        """
        Calculate nyemission: Sum all KREDIT amounts for account 2081 
        where verifications have KREDIT 2081 AND DEBIT 1XXX
        """
        nyemission_amount = 0.0
        
        for ver in verifications:
            transactions = ver['transactions']
            
            has_2081_kredit = False
            has_1xxx_debit = False
            ver_nyemission = 0.0
            
            for trans in transactions:
                if trans['account'] == 2081 and trans['amount'] < 0:  # KREDIT (negative amount)
                    has_2081_kredit = True
                    ver_nyemission += abs(trans['amount'])  # Take absolute value
                elif 1000 <= trans['account'] <= 1999 and trans['amount'] > 0:  # DEBIT (positive amount)
                    has_1xxx_debit = True
            
            if has_2081_kredit and has_1xxx_debit:
                nyemission_amount += ver_nyemission
        
        return nyemission_amount
    
    def _calculate_aktieagartillskott_from_verifications(self, verifications: List[Dict[str, Any]]) -> Tuple[float, float]:
        """
        Calculate aktieägartillskott:
        - Erhållna: Sum all KREDIT amounts for account 2093
        - Återbetalda: Sum all DEBIT amounts for account 2093
        """
        erhallna = 0.0
        aterbetalda = 0.0
        
        for ver in verifications:
            for trans in ver['transactions']:
                if trans['account'] == 2093:
                    if trans['amount'] < 0:  # KREDIT (negative amount)
                        erhallna += abs(trans['amount'])
                    elif trans['amount'] > 0:  # DEBIT (positive amount)
                        aterbetalda += trans['amount']
        
        return erhallna, aterbetalda
    
    def _calculate_uppskrivning_from_verifications(self, verifications: List[Dict[str, Any]]) -> Tuple[float, float]:
        """
        Calculate uppskrivning transactions:
        - Uppskrivning: KREDIT amounts for 2085 with DEBIT 1XXX
        - Återföring: DEBIT amounts for 2085 with KREDIT 1XXX or KREDIT 2091
        """
        uppskrivning = 0.0
        aterforing = 0.0
        
        for ver in verifications:
            transactions = ver['transactions']
            
            # Check for uppskrivning pattern: KREDIT 2085 AND DEBIT 1XXX
            has_2085_kredit = False
            has_1xxx_debit = False
            ver_uppskrivning = 0.0
            
            for trans in transactions:
                if trans['account'] == 2085 and trans['amount'] < 0:  # KREDIT
                    has_2085_kredit = True
                    ver_uppskrivning += abs(trans['amount'])
                elif 1000 <= trans['account'] <= 1999 and trans['amount'] > 0:  # DEBIT
                    has_1xxx_debit = True
            
            if has_2085_kredit and has_1xxx_debit:
                uppskrivning += ver_uppskrivning
                continue
            
            # Check for återföring pattern: DEBIT 2085 AND (KREDIT 1XXX OR KREDIT 2091)
            has_2085_debit = False
            has_kredit_target = False
            ver_aterforing = 0.0
            
            for trans in transactions:
                if trans['account'] == 2085 and trans['amount'] > 0:  # DEBIT
                    has_2085_debit = True
                    ver_aterforing += trans['amount']
                elif ((1000 <= trans['account'] <= 1999 and trans['amount'] < 0) or  # KREDIT 1XXX
                      (trans['account'] == 2091 and trans['amount'] < 0)):  # KREDIT 2091
                    has_kredit_target = True
            
            if has_2085_debit and has_kredit_target:
                aterforing += ver_aterforing
        
        return uppskrivning, aterforing
    
    def _get_br_value(self, br_data: List[Dict[str, Any]], variable_name: str, use_previous_year: bool = False) -> float:
        """Get BR value by variable name, handling current_amount (UB) vs previous_amount (IB)"""
        for item in br_data:
            if item.get('variable_name') == variable_name:
                value = item.get('previous_amount' if use_previous_year else 'current_amount', 0)
                return value if value is not None else 0.0
        return 0.0

    def calculate_forandring_eget_kapital(self, sie_text: str, br_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate all variables for Förändring i eget kapital table
        br_data should be the list of BR results from database_parser.parse_br_data()
        """
        # Parse verifications from SIE text
        verifications = self._parse_sie_verifications(sie_text)
        
        # Calculate voucher-based variables
        utdelning = self._calculate_utdelning_from_verifications(verifications)
        nyemission = self._calculate_nyemission_from_verifications(verifications)
        erhallna_tillskott, aterbetalda_tillskott = self._calculate_aktieagartillskott_from_verifications(verifications)
        uppskrivning_anl, aterforing_uppskr = self._calculate_uppskrivning_from_verifications(verifications)
        
        # Extract BR values using correct variable names from CSV
        # IB = previous_amount (Ingående balans), UB = current_amount (Utgående balans)
        aktiekapital_ib = self._get_br_value(br_data, 'Aktiekapital', use_previous_year=True)
        aktiekapital_ub = self._get_br_value(br_data, 'Aktiekapital', use_previous_year=False)
        reservfond_ib = self._get_br_value(br_data, 'Reservfond', use_previous_year=True)
        reservfond_ub = self._get_br_value(br_data, 'Reservfond', use_previous_year=False)
        uppskrfond_ib = self._get_br_value(br_data, 'Uppskrivningsfond', use_previous_year=True)
        uppskrfond_ub = self._get_br_value(br_data, 'Uppskrivningsfond', use_previous_year=False)
        # Calculate balansresultat_ib = SumFrittEgetKapital UB previous year - AretsResultat UB previous year
        # Note: previous_amount in BR data represents UB from previous year
        sum_fritt_eget_kapital_prev_ub = self._get_br_value(br_data, 'SumFrittEgetKapital', use_previous_year=True)
        arets_resultat_prev_ub = self._get_br_value(br_data, 'AretsResultat', use_previous_year=True)
        balansresultat_ib = sum_fritt_eget_kapital_prev_ub - arets_resultat_prev_ub
        balansresultat_ub = self._get_br_value(br_data, 'SumFrittEgetKapital', use_previous_year=False)
        arets_resultat_ib = self._get_br_value(br_data, 'AretsResultat', use_previous_year=True)
        arets_resultat_ub = self._get_br_value(br_data, 'AretsResultat', use_previous_year=False)
        
        # Calculate derived values
        reservfond_change = reservfond_ub - reservfond_ib
        aktiekapital_calculated_ub = aktiekapital_ib + nyemission
        uppskrfond_calculated_ub = (uppskrfond_ib + uppskrivning_anl - aterforing_uppskr)
        
        # Calculate balanseras_nyrakning
        balansresultat_balanseras = (balansresultat_ib - utdelning + erhallna_tillskott - 
                                   aterbetalda_tillskott + reservfond_change)
        arets_resultat_balanseras = -balansresultat_balanseras
        
        # Calculate årets resultat
        arets_resultat_calculated = (arets_resultat_ib + arets_resultat_balanseras)
        
        # Store all calculated variables
        variables = {
            # Aktiekapital
            'fb_aktiekaptial_ib': aktiekapital_ib,
            'fb_aktiekapital_nyemission': nyemission,
            'fb_aktiekaptial_ub': aktiekapital_calculated_ub,
            'fb_aktiekaptial_ub_red_varde': aktiekapital_ub,
            
            # Reservfond
            'fb_reservfond_ib': reservfond_ib,
            'fb_reservfond_change': reservfond_change,
            'fb_reservfond_ub': reservfond_ib + reservfond_change,
            'fb_reservfond_ub_red_varde': reservfond_ub,
            
            # Uppskrivningsfond
            'fb_uppskrfond_ib': uppskrfond_ib,
            'fb_uppskrfond_fondemission': 0.0,  # Editable field, default 0
            'fb_uppskrfond_uppskr_anltillgangar': uppskrivning_anl,
            'fb_uppskrfond_aterforing': -aterforing_uppskr,  # Negative sign as per CSV
            'fb_uppskrfond_fusionsdifferens': 0.0,  # Editable field, default 0
            'fb_uppskrfond_ub': uppskrfond_calculated_ub,
            'fb_uppskrfond_ub_red_varde': uppskrfond_ub,
            
            # Balanserat resultat
            'fb_balansresultat_ib': balansresultat_ib,
            'fb_balansresultat_utdelning': -utdelning,  # Negative sign as per CSV
            'fb_balansresultat_erhallna_aktieagartillskott': erhallna_tillskott,
            'fb_balansresultat_aterbetalda_aktieagartillskott': -aterbetalda_tillskott,
            'fb_balansresultat_forandring_reservfond': 0.0,  # Editable field, default 0
            'fb_balansresultat_fondemission': 0.0,  # Editable field, default 0
            'fb_balansresultat_balanseras_nyrakning': balansresultat_balanseras,
            'fb_balansresultat_ub': balansresultat_ub,
            'fb_balansresultat_ub_red_varde': balansresultat_ub,
            
            # Årets resultat
            'fb_aretsresultat_ib': arets_resultat_ib,
            'fb_aretsresultat_utdelning': 0.0,  # Editable field, default 0
            'fb_aretsresultat_aterbetalda_aktieagartillskott': 0.0,  # Editable field, default 0
            'fb_aretsresultat_balanseras_nyrakning': arets_resultat_balanseras,
            'fb_aretsresultat_forandring_reservfond': 0.0,  # Editable field, default 0
            'fb_aretsresultat_fondemission': 0.0,  # Editable field, default 0
            'fb_aretsresultat_arets_resultat': arets_resultat_ub,
            'fb_aretsresultat_ub_red_varde': arets_resultat_ub,
        }
        
        self.calculated_variables = variables
        return variables
    
    def generate_forandring_eget_kapital_table(self, variables: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        Generate the Förändring i eget kapital table structure
        """
        table_rows = [
            {
                'id': 1,
                'label': 'Belopp vid årets ingång',
                'aktiekapital': variables.get('fb_aktiekaptial_ib', 0.0),
                'reservfond': variables.get('fb_reservfond_ib', 0.0),
                'uppskrivningsfond': variables.get('fb_uppskrfond_ib', 0.0),
                'balanserat_resultat': variables.get('fb_balansresultat_ib', 0.0),
                'arets_resultat': variables.get('fb_aretsresultat_ib', 0.0),
                'total': (variables.get('fb_aktiekaptial_ib', 0.0) + 
                         variables.get('fb_reservfond_ib', 0.0) + 
                         variables.get('fb_uppskrfond_ib', 0.0) + 
                         variables.get('fb_balansresultat_ib', 0.0) + 
                         variables.get('fb_aretsresultat_ib', 0.0))
            },
            {
                'id': 2,
                'label': 'Utdelning',
                'aktiekapital': 0.0,
                'reservfond': 0.0,
                'uppskrivningsfond': 0.0,
                'balanserat_resultat': variables.get('fb_balansresultat_utdelning', 0.0),
                'arets_resultat': variables.get('fb_aretsresultat_utdelning', 0.0),
                'total': (variables.get('fb_balansresultat_utdelning', 0.0) + 
                         variables.get('fb_aretsresultat_utdelning', 0.0))
            },
            {
                'id': 3,
                'label': 'Erhållna aktieägartillskott',
                'aktiekapital': 0.0,
                'reservfond': 0.0,
                'uppskrivningsfond': 0.0,
                'balanserat_resultat': variables.get('fb_balansresultat_erhallna_aktieagartillskott', 0.0),
                'arets_resultat': 0.0,
                'total': variables.get('fb_balansresultat_erhallna_aktieagartillskott', 0.0)
            },
            {
                'id': 4,
                'label': 'Återbetalning av aktieägartillskott',
                'aktiekapital': 0.0,
                'reservfond': 0.0,
                'uppskrivningsfond': 0.0,
                'balanserat_resultat': variables.get('fb_balansresultat_aterbetalda_aktieagartillskott', 0.0),
                'arets_resultat': variables.get('fb_aretsresultat_aterbetalda_aktieagartillskott', 0.0),
                'total': (variables.get('fb_balansresultat_aterbetalda_aktieagartillskott', 0.0) + 
                         variables.get('fb_aretsresultat_aterbetalda_aktieagartillskott', 0.0))
            },
            {
                'id': 5,
                'label': 'Balanseras i ny räkning',
                'aktiekapital': 0.0,
                'reservfond': 0.0,
                'uppskrivningsfond': 0.0,
                'balanserat_resultat': variables.get('fb_balansresultat_balanseras_nyrakning', 0.0),
                'arets_resultat': variables.get('fb_aretsresultat_balanseras_nyrakning', 0.0),
                'total': (variables.get('fb_balansresultat_balanseras_nyrakning', 0.0) + 
                         variables.get('fb_aretsresultat_balanseras_nyrakning', 0.0))
            },
            {
                'id': 6,
                'label': 'Förändringar av reservfond',
                'aktiekapital': 0.0,
                'reservfond': variables.get('fb_reservfond_change', 0.0),
                'uppskrivningsfond': 0.0,
                'balanserat_resultat': variables.get('fb_balansresultat_forandring_reservfond', 0.0),
                'arets_resultat': variables.get('fb_aretsresultat_forandring_reservfond', 0.0),
                'total': (variables.get('fb_reservfond_change', 0.0) + 
                         variables.get('fb_balansresultat_forandring_reservfond', 0.0) + 
                         variables.get('fb_aretsresultat_forandring_reservfond', 0.0))
            },
            {
                'id': 7,
                'label': 'Fondemission',
                'aktiekapital': 0.0,
                'reservfond': 0.0,
                'uppskrivningsfond': variables.get('fb_uppskrfond_fondemission', 0.0),
                'balanserat_resultat': variables.get('fb_balansresultat_fondemission', 0.0),
                'arets_resultat': variables.get('fb_aretsresultat_fondemission', 0.0),
                'total': (variables.get('fb_uppskrfond_fondemission', 0.0) + 
                         variables.get('fb_balansresultat_fondemission', 0.0) + 
                         variables.get('fb_aretsresultat_fondemission', 0.0))
            },
            {
                'id': 8,
                'label': 'Nyemission',
                'aktiekapital': variables.get('fb_aktiekapital_nyemission', 0.0),
                'reservfond': 0.0,
                'uppskrivningsfond': 0.0,
                'balanserat_resultat': 0.0,
                'arets_resultat': 0.0,
                'total': variables.get('fb_aktiekapital_nyemission', 0.0)
            },
            {
                'id': 9,
                'label': 'Uppskrivning av anläggningstillgång',
                'aktiekapital': 0.0,
                'reservfond': 0.0,
                'uppskrivningsfond': variables.get('fb_uppskrfond_uppskr_anltillgangar', 0.0),
                'balanserat_resultat': 0.0,
                'arets_resultat': 0.0,
                'total': variables.get('fb_uppskrfond_uppskr_anltillgangar', 0.0)
            },
            {
                'id': 10,
                'label': 'Återföring av uppskrivningsfond',
                'aktiekapital': 0.0,
                'reservfond': 0.0,
                'uppskrivningsfond': variables.get('fb_uppskrfond_aterforing', 0.0),
                'balanserat_resultat': 0.0,
                'arets_resultat': 0.0,
                'total': variables.get('fb_uppskrfond_aterforing', 0.0)
            },
            {
                'id': 11,
                'label': 'Fusionsdifferens',
                'aktiekapital': 0.0,
                'reservfond': 0.0,
                'uppskrivningsfond': variables.get('fb_uppskrfond_fusionsdifferens', 0.0),
                'balanserat_resultat': 0.0,
                'arets_resultat': 0.0,
                'total': variables.get('fb_uppskrfond_fusionsdifferens', 0.0)
            },
            {
                'id': 12,
                'label': 'Årets resultat',
                'aktiekapital': 0.0,
                'reservfond': 0.0,
                'uppskrivningsfond': 0.0,
                'balanserat_resultat': 0.0,
                'arets_resultat': variables.get('fb_aretsresultat_arets_resultat', 0.0),
                'total': variables.get('fb_aretsresultat_arets_resultat', 0.0)
            },
            {
                'id': 13,
                'label': 'Belopp vid årets utgång',
                'aktiekapital': variables.get('fb_aktiekaptial_ub', 0.0),
                'reservfond': variables.get('fb_reservfond_ub', 0.0),
                'uppskrivningsfond': variables.get('fb_uppskrfond_ub', 0.0),
                'balanserat_resultat': variables.get('fb_balansresultat_ub', 0.0),
                'arets_resultat': variables.get('fb_aretsresultat_ub_red_varde', 0.0),
                'total': (variables.get('fb_aktiekaptial_ub', 0.0) + 
                         variables.get('fb_reservfond_ub', 0.0) + 
                         variables.get('fb_uppskrfond_ub', 0.0) + 
                         variables.get('fb_balansresultat_ub', 0.0) + 
                         variables.get('fb_aretsresultat_ub_red_varde', 0.0))
            },
            {
                'id': 14,
                'label': 'Redovisat värde',
                'aktiekapital': variables.get('fb_aktiekaptial_ub_red_varde', 0.0),
                'reservfond': variables.get('fb_reservfond_ub_red_varde', 0.0),
                'uppskrivningsfond': variables.get('fb_uppskrfond_ub_red_varde', 0.0),
                'balanserat_resultat': variables.get('fb_balansresultat_ub_red_varde', 0.0),
                'arets_resultat': variables.get('fb_aretsresultat_ub_red_varde', 0.0),
                'total': (variables.get('fb_aktiekaptial_ub_red_varde', 0.0) + 
                         variables.get('fb_reservfond_ub_red_varde', 0.0) + 
                         variables.get('fb_uppskrfond_ub_red_varde', 0.0) + 
                         variables.get('fb_balansresultat_ub_red_varde', 0.0) + 
                         variables.get('fb_aretsresultat_ub_red_varde', 0.0))
            }
        ]
        
        return table_rows
    
    def format_table_for_display(self, table_rows: List[Dict[str, Any]]) -> str:
        """Format the table for console display"""
        def format_amount_display(amount: float) -> str:
            """Format amount to match frontend Noter NORMAL style"""
            if amount == 0:
                return ""
            # Use Swedish locale formatting (space as thousands separator)
            formatted = f"{abs(amount):,.0f}".replace(",", " ")
            sign = "-" if amount < 0 else ""
            return f"{sign}{formatted} kr"
        
        output = []
        output.append("FÖRÄNDRING I EGET KAPITAL")
        output.append("=" * 140)
        output.append(f"{'':30} {'Aktiekapital':>20} {'Reservfond':>20} {'Uppskr.fond':>20} {'Bal.resultat':>20} {'Årets res.':>20} {'Totalt':>20}")
        output.append("-" * 140)
        
        for row in table_rows:
            output.append(
                f"{row['label']:30} "
                f"{format_amount_display(row['aktiekapital']):>20} "
                f"{format_amount_display(row['reservfond']):>20} "
                f"{format_amount_display(row['uppskrivningsfond']):>20} "
                f"{format_amount_display(row['balanserat_resultat']):>20} "
                f"{format_amount_display(row['arets_resultat']):>20} "
                f"{format_amount_display(row['total']):>20}"
            )
        
        return "\n".join(output)


# Test functionality
def test_fb_module():
    """Test the FB module with sample data"""
    
    # Sample SIE text with utdelning verification
    sample_sie = """
#VER A 27 20240628 "utdelning"
{
#TRANS 1930 {} -900000.00
#TRANS 1660 {} -19100000.00
#TRANS 2091 {} 20000000.00
}

#VER B 15 20240315 "nyemission"
{
#TRANS 1910 {} 500000.00
#TRANS 2081 {} -500000.00
}

#VER C 8 20240120 "aktieägartillskott"
{
#TRANS 1910 {} 1000000.00
#TRANS 2093 {} -1000000.00
}

#VER D 22 20240801 "uppskrivning"
{
#TRANS 1210 {} 750000.00
#TRANS 2085 {} -750000.00
}
"""
    
    # Sample BR data
    sample_br_data = {
        'aktiekapital_ib': 1000000.0,
        'aktiekapital_ub': 1500000.0,
        'reservfond_ib': 500000.0,
        'reservfond_ub': 500000.0,
        'uppskrivningsfond_ib': 0.0,
        'uppskrivningsfond_ub': 750000.0,
        'sum_fritt_eget_kapital_ib': 2000000.0,
        'sum_fritt_eget_kapital_ub': 1080000.0,
        'arets_resultat_ib': 0.0,
        'arets_resultat_ub': 800000.0
    }
    
    # Initialize FB module
    fb = ForvaltningsberattelseFB()
    
    # Calculate variables
    print("Calculating Förändring i eget kapital...")
    variables = fb.calculate_forandring_eget_kapital(sample_sie, sample_br_data)
    
    print("\nCalculated Variables:")
    for key, value in variables.items():
        print(f"{key}: {value:,.0f}")
    
    # Generate table
    table_rows = fb.generate_forandring_eget_kapital_table(variables)
    
    # Display table
    print("\n" + fb.format_table_for_display(table_rows))
    
    return variables, table_rows


if __name__ == "__main__":
    test_fb_module()
