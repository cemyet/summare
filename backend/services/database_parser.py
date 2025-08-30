"""
Database-driven parser for SE files
Replaces hardcoded BR_STRUCTURE and RR_STRUCTURE with database queries
"""

import os
import re
import unicodedata
import math
from typing import Dict, List, Any, Optional
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

# Feature flags
USE_168X_RECLASS = os.getenv("USE_168X_RECLASS", "1") == "1"  # default ON

class DatabaseParser:
    """Database-driven parser for financial data"""
    
    def __init__(self):
        self.rr_mappings = None
        self.br_mappings = None
        self.ink2_mappings = None
        self.noter_mappings = None
        self.global_variables = None
        self.accounts_lookup = None
        self._load_mappings()
    
    def _load_mappings(self):
        """Load variable mappings from database"""
        try:
            # Load RR mappings
            rr_response = supabase.table('variable_mapping_rr').select('*').execute()
            self.rr_mappings = rr_response.data
            
            # Load BR mappings
            br_response = supabase.table('variable_mapping_br').select('*').execute()
            self.br_mappings = br_response.data
            
            # Load INK2 mappings
            ink2_response = supabase.table('variable_mapping_ink2').select('*').execute()
            self.ink2_mappings = ink2_response.data
            
            # Load Noter mappings
            noter_response = supabase.table('variable_mapping_noter').select('*').execute()
            self.noter_mappings = noter_response.data
            

            
            # Load global variables (normalize values to floats; treat % values as decimals)
            global_vars_response = supabase.table('global_variables').select('*').execute()
            self.global_variables = {}
            for var in global_vars_response.data:
                name = var.get('variable_name')
                raw = var.get('value')
                had_percent = False
                if isinstance(raw, str) and '%' in raw:
                    had_percent = True
                if isinstance(raw, (int, float)):
                    value = float(raw)
                else:
                    text = str(raw or '').strip().replace('%', '').replace(' ', '').replace(',', '.')
                    try:
                        value = float(text)
                    except ValueError:
                        value = 0.0
                if had_percent or name.lower().startswith('skattesats'):
                    # Convert percent like 20.6 to 0.206
                    value = value / 100.0
                self.global_variables[name] = value
            
            # Load accounts lookup (map by both int and string id for robustness)
            accounts_response = supabase.table('accounts_table').select('*').execute()
            self.accounts_lookup = {}
            for acc in accounts_response.data:
                acc_id = acc.get('account_id')
                text = acc.get('account_text') or f"Konto {acc_id}"
                # int key
                try:
                    self.accounts_lookup[int(acc_id)] = text
                except Exception:
                    pass
                # string key
                self.accounts_lookup[str(acc_id)] = text
            

            
        except Exception as e:
            print(f"Error loading mappings: {e}")
            self.rr_mappings = []
            self.br_mappings = []
            self.ink2_mappings = []
            self.noter_mappings = []
            self.global_variables = {}
            self.accounts_lookup = {}
    
    def parse_account_balances(self, se_content: str) -> tuple[Dict[str, float], Dict[str, float], Dict[str, float], Dict[str, float]]:
        """Parse account balances from SE file content using the correct format"""
        current_accounts = {}
        previous_accounts = {}
        current_ib_accounts = {}  # Incoming balances for current year
        previous_ib_accounts = {}  # Incoming balances for previous year
        
        # Parse SE file content to extract account balances
        lines = se_content.split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Handle BR accounts: #UB (Uppgjord Balans) - both years
            if line.startswith('#UB '):
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        fiscal_year = int(parts[1])
                        account_id = parts[2]
                        balance = float(parts[3])
                        
                        if fiscal_year == 0:  # Current year
                            current_accounts[account_id] = balance
                        elif fiscal_year == -1:  # Previous year
                            previous_accounts[account_id] = balance
                    except (ValueError, TypeError):
                        continue
            
            # Handle IB accounts: #IB (Ingående Balans) - both years
            if line.startswith('#IB '):
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        fiscal_year = int(parts[1])
                        account_id = parts[2]
                        balance = float(parts[3])
                        
                        if fiscal_year == 0:  # Current year
                            current_ib_accounts[account_id] = balance
                        elif fiscal_year == -1:  # Previous year
                            previous_ib_accounts[account_id] = balance
                    except (ValueError, TypeError):
                        continue
                        
            # Handle RR accounts: #RES (Resultat) - both years
            elif line.startswith('#RES '):
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        fiscal_year = int(parts[1])
                        account_id = parts[2]
                        balance = float(parts[3])
                        
                        if fiscal_year == 0:  # Current year
                            current_accounts[account_id] = balance
                        elif fiscal_year == -1:  # Previous year
                            previous_accounts[account_id] = balance
                    except (ValueError, TypeError):
                        continue
                        
            # Handle legacy #VER format (fallback)
            elif line.startswith('#VER'):
                parts = line.split()
                if len(parts) >= 3:
                    account_id = parts[1]
                    try:
                        balance = float(parts[2])
                        current_accounts[account_id] = balance
                    except ValueError:
                        continue
        

        
        return current_accounts, previous_accounts, current_ib_accounts, previous_ib_accounts
    
    def parse_ib_ub_balances(self, se_content: str) -> tuple[Dict[str, float], Dict[str, float], Dict[str, float], Dict[str, float]]:
        """Parse both IB and UB balances from SE file for noter calculations"""
        current_ub_accounts = {}
        previous_ub_accounts = {}
        current_ib_accounts = {}
        previous_ib_accounts = {}
        
        lines = se_content.split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Handle UB accounts: #UB
            if line.startswith('#UB '):
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        fiscal_year = int(parts[1])
                        account_id = parts[2]
                        balance = float(parts[3])
                        
                        if fiscal_year == 0:  # Current year
                            current_ub_accounts[account_id] = balance
                        elif fiscal_year == -1:  # Previous year
                            previous_ub_accounts[account_id] = balance
                    except (ValueError, TypeError):
                        continue
            
            # Handle IB accounts: #IB
            if line.startswith('#IB '):
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        fiscal_year = int(parts[1])
                        account_id = parts[2]
                        balance = float(parts[3])
                        
                        if fiscal_year == 0:  # Current year
                            current_ib_accounts[account_id] = balance
                        elif fiscal_year == -1:  # Previous year
                            previous_ib_accounts[account_id] = balance
                    except (ValueError, TypeError):
                        continue
        
        return current_ub_accounts, previous_ub_accounts, current_ib_accounts, previous_ib_accounts
    
    def calculate_variable_value(self, mapping: Dict[str, Any], accounts: Dict[str, float]) -> float:
        """Calculate value for a specific variable based on its mapping"""
        total = 0.0
        
        # Get account ranges to include
        start = mapping.get('accounts_included_start')
        end = mapping.get('accounts_included_end')
        
        # Include accounts in range
        if start and end:
            for account_id in range(start, end + 1):
                account_str = str(account_id)
                if account_str in accounts:
                    total += accounts[account_str]
        
        # Include additional specific accounts
        additional_accounts = mapping.get('accounts_included')
        if additional_accounts:
            for account_spec in additional_accounts.split(';'):
                account_spec = account_spec.strip()
                if '-' in account_spec:
                    # Range specification (e.g., "4910-4931")
                    range_start, range_end = map(int, account_spec.split('-'))
                    for account_id in range(range_start, range_end + 1):
                        account_str = str(account_id)
                        if account_str in accounts:
                            total += accounts[account_str]
                else:
                    # Single account
                    if account_spec in accounts:
                        total += accounts[account_spec]
        
        # Exclude accounts in range
        exclude_start = mapping.get('accounts_excluded_start')
        exclude_end = mapping.get('accounts_excluded_end')
        
        if exclude_start and exclude_end:
            for account_id in range(exclude_start, exclude_end + 1):
                account_str = str(account_id)
                if account_str in accounts:
                    total -= accounts[account_str]
        
        # Exclude additional specific accounts
        excluded_accounts = mapping.get('accounts_excluded')
        if excluded_accounts:
            for account_spec in excluded_accounts.split(';'):
                account_spec = account_spec.strip()
                if '-' in account_spec:
                    # Range specification
                    range_start, range_end = map(int, account_spec.split('-'))
                    for account_id in range(range_start, range_end + 1):
                        account_str = str(account_id)
                        if account_str in accounts:
                            total -= accounts[account_str]
                else:
                    # Single account
                    if account_spec in accounts:
                        total -= accounts[account_str]
        
        # Apply sign based on SE file data structure
        # All account balances from 2000-8989 need to be reversed regardless of balance_type
        
        # Check if any accounts in the 2000-8989 range are being used
        should_reverse = False
        
        # Check account range
        start = mapping.get('accounts_included_start')
        end = mapping.get('accounts_included_end')
        if start and end and 2000 <= start <= 8989:
            should_reverse = True
        
        # Check additional specific accounts
        additional_accounts = mapping.get('accounts_included')
        if additional_accounts:
            for account_spec in additional_accounts.split(';'):
                account_spec = account_spec.strip()
                if '-' in account_spec:
                    # Range specification
                    range_start, range_end = map(int, account_spec.split('-'))
                    if 2000 <= range_start <= 8989:
                        should_reverse = True
                        break
                else:
                    # Single account
                    try:
                        account_id = int(account_spec)
                        if 2000 <= account_id <= 8989:
                            should_reverse = True
                            break
                    except ValueError:
                        continue
        
        # Optional explicit sign override from mapping column (e.g., '+/-' or 'sign')
        sign_override = mapping.get('+/-') or mapping.get('sign') or mapping.get('plus_minus')
        if sign_override:
            s = str(sign_override).strip()
            if s == '+':
                total = abs(total)
            elif s == '-':
                total = -abs(total)

        if should_reverse:
            return -total
        else:
            return total
    
    def calculate_formula_value(self, mapping: Dict[str, Any], accounts: Dict[str, float], existing_results: List[Dict[str, Any]], use_previous_year: bool = False, rr_data: List[Dict[str, Any]] = None) -> float:
        """Calculate value using a formula that references variable names"""
        formula = mapping.get('calculation_formula', '')
        if not formula:
            return 0.0
        

        
        # Parse formula like "NETTOOMSATTNING + OVRIGA_INTEKNINGAR"
        # Use variable names instead of row references
        import re
        
        # Replace variable references with their calculated values
        # Formula format: variable names like SumRorelseintakter, SumRorelsekostnader, etc.
        # Use word boundaries to match complete variable names
        pattern = r'\b([A-Z][a-zA-Z0-9_]*)\b'
        
        def replace_variable(match):
            var_name = match.group(1)
            # Use the new helper method to get calculated values
            value = self._get_calculated_value(var_name, existing_results, use_previous_year, rr_data)

            return str(value)
        
        # Replace all variable references
        formula_with_values = re.sub(pattern, replace_variable, formula)
        
        try:
            # Evaluate the formula
            result = eval(formula_with_values)
            return float(result)
        except Exception as e:
            print(f"Formula evaluation error: {e}")
            return 0.0
    
    def parse_rr_data(self, current_accounts: Dict[str, float], previous_accounts: Dict[str, float] = None) -> List[Dict[str, Any]]:
        """Parse RR (Resultaträkning) data using database mappings"""
        if not self.rr_mappings:
            return []
        
        results = []
        

        
        # First pass: Create all rows with direct calculations
        for mapping in self.rr_mappings:
            if not mapping.get('show_amount'):
                # Header row - no calculation needed
                results.append({
                    'id': mapping['row_id'],
                    'label': mapping['row_title'],
                    'current_amount': None,
                    'previous_amount': None,
                    'level': self._get_level_from_style(mapping['style']),
                    'section': 'RR',
                    'bold': mapping['style'] in ['H0', 'H1', 'H2', 'H4'],
                    'style': mapping['style'],
                    'variable_name': mapping['variable_name'],
                    'is_calculated': mapping['is_calculated'],
                    'calculation_formula': mapping['calculation_formula'],
                    'show_amount': mapping['show_amount'],
                    'block_group': mapping.get('block_group'),
                    'always_show': self._normalize_always_show(mapping.get('always_show', False))
                })
            else:
                # Data row - calculate amounts for both years
                if mapping.get('is_calculated'):
                    # For calculated items, set to 0 initially, will be updated in second pass
                    current_amount = 0.0
                    previous_amount = 0.0
                else:
                    # Direct account calculation
                    current_amount = self.calculate_variable_value(mapping, current_accounts)
                    previous_amount = self.calculate_variable_value(mapping, previous_accounts or {})
                

                
                results.append({
                    'id': mapping['row_id'],
                    'label': mapping['row_title'],
                    'current_amount': current_amount,
                    'previous_amount': previous_amount,
                    'level': self._get_level_from_style(mapping['style']),
                    'section': 'RR',
                    'bold': mapping['style'] in ['H0', 'H1', 'H2', 'H4'],
                    'style': mapping['style'],
                    'variable_name': mapping['variable_name'],
                    'is_calculated': mapping['is_calculated'],
                    'calculation_formula': mapping['calculation_formula'],
                    'show_amount': mapping['show_amount'],
                    'block_group': mapping.get('block_group'),
                    'always_show': self._normalize_always_show(mapping.get('always_show', False))
                })
        
        # Second pass: Calculate formulas using all available data
        
        # Sort calculated mappings by row_id to ensure dependencies are calculated first
        calculated_mappings = [(i, mapping) for i, mapping in enumerate(self.rr_mappings) 
                              if mapping.get('is_calculated')]
        calculated_mappings.sort(key=lambda x: int(x[1]['row_id']))
        
        for i, mapping in calculated_mappings:

                
                current_amount = self.calculate_formula_value(mapping, current_accounts, results, use_previous_year=False)
                previous_amount = self.calculate_formula_value(mapping, previous_accounts or {}, results, use_previous_year=True)

                
                # Find and update the correct result by row_id
                for result in results:
                    if result['id'] == mapping['row_id']:
                        result['current_amount'] = current_amount
                        result['previous_amount'] = previous_amount
                        break
        
        # Store calculated values in database for future use
        self.store_calculated_values(results, 'RR')
        
        # Sort results by ID to ensure correct order
        results.sort(key=lambda x: int(x['id']))
        
        return results
    
    def _calculate_noter_amounts(self, mapping: Dict[str, Any], current_ub: Dict[str, float], previous_ub: Dict[str, float], current_ib: Dict[str, float], previous_ib: Dict[str, float]) -> tuple[float, float]:
        """Calculate current and previous amounts for a noter mapping based on ib_ub column"""
        accounts_included = mapping.get('accounts_included', '')
        ib_ub = mapping.get('ib_ub', 'UB')  # Default to UB
        
        if not accounts_included:
            return 0.0, 0.0
        
        # Choose the correct account dictionaries based on ib_ub
        if ib_ub == 'IB':
            current_accounts = current_ib
            previous_accounts = previous_ib
        else:  # Default to UB
            current_accounts = current_ub
            previous_accounts = previous_ub
        
        # Sum included accounts for both years
        current_amount = self.sum_included_accounts(accounts_included, current_accounts)
        previous_amount = self.sum_included_accounts(accounts_included, previous_accounts)
        
        return current_amount, previous_amount
    
    def _evaluate_noter_formula(self, formula: str, calculated_variables: Dict[str, Dict[str, float]]) -> tuple[float, float]:
        """Evaluate a noter formula using calculated variables"""
        import ast
        import operator
        
        # Operators mapping for safe evaluation
        operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.USub: operator.neg,
            ast.UAdd: operator.pos,
        }
        
        def safe_eval(node, variables):
            if isinstance(node, ast.Constant):  # Python 3.8+
                return node.value
            elif isinstance(node, ast.Num):  # Python 3.7 and below
                return node.n
            elif isinstance(node, ast.Name):
                if node.id in variables:
                    return variables[node.id]
                else:
                    raise ValueError(f"Unknown variable: {node.id}")
            elif isinstance(node, ast.BinOp):
                left = safe_eval(node.left, variables)
                right = safe_eval(node.right, variables)
                return operators[type(node.op)](left, right)
            elif isinstance(node, ast.UnaryOp):
                operand = safe_eval(node.operand, variables)
                return operators[type(node.op)](operand)
            else:
                raise ValueError(f"Unsupported operation: {type(node)}")
        
        try:
            # Parse the formula into AST
            tree = ast.parse(formula, mode='eval')
            
            # Prepare variables for current and previous year
            current_vars = {var_name: values['current'] for var_name, values in calculated_variables.items()}
            previous_vars = {var_name: values['previous'] for var_name, values in calculated_variables.items()}
            
            # Evaluate for both years
            current_result = safe_eval(tree.body, current_vars)
            previous_result = safe_eval(tree.body, previous_vars)
            

            
            return float(current_result), float(previous_result)
            
        except Exception as e:
            print(f"Error evaluating noter formula '{formula}': {e}")
            return 0.0, 0.0
    
    def store_calculated_values(self, results: List[Dict[str, Any]], report_type: str):
        """Store calculated values in database for future retrieval"""
        try:
            # Create a dictionary of variable_name -> current_amount for calculated items
            calculated_values = {}
            for item in results:
                if item.get('is_calculated') and item.get('variable_name'):
                    # Include all calculated items, even if current_amount is 0 or -0
                    current_amount = item.get('current_amount')
                    if current_amount is not None:  # This includes 0, -0, and other values
                        calculated_values[item['variable_name']] = current_amount
            
            if calculated_values:
                # Store in a temporary table or update existing records
                # This will be used when formulas reference these variables
                for var_name, value in calculated_values.items():
                    # You might want to store this in a separate table or update existing records
                    # For now, we'll just use it in memory
                    pass
                    
        except Exception as e:
            print(f"Error storing calculated values: {e}")
    
    def _get_calculated_value(self, variable_name: str, results: List[Dict[str, Any]], use_previous_year: bool = False, rr_data: List[Dict[str, Any]] = None) -> float:
        """Get calculated value for a variable from results or RR data"""
        # First check in the current results (BR data)
        for item in results:
            if item.get('variable_name') == variable_name:
                value = item.get('previous_amount' if use_previous_year else 'current_amount', 0)
                return value if value is not None else 0
        
        # If not found in current results, check in RR data
        if rr_data:
            for item in rr_data:
                if item.get('variable_name') == variable_name:
                    value = item.get('previous_amount' if use_previous_year else 'current_amount', 0)
                    return value if value is not None else 0
        
        return 0
    
    def parse_br_data(self, current_accounts: Dict[str, float], previous_accounts: Dict[str, float] = None, rr_data: List[Dict[str, Any]] = None, sie_text: Optional[str] = None) -> List[Dict[str, Any]]:
        """Parse BR (Balansräkning) data using database mappings"""
        if not self.br_mappings:
            return []
        
        results = []
        
        # First pass: Create all rows with direct calculations
        for mapping in self.br_mappings:
            if not mapping.get('show_amount'):
                # Header row - no calculation needed
                results.append({
                    'id': mapping['row_id'],
                    'label': mapping['row_title'],
                    'current_amount': None,
                    'previous_amount': None,
                    'level': self._get_level_from_style(mapping['style']),
                    'section': 'BR',
                    'type': self._get_balance_type(mapping),
                    'bold': mapping['style'] in ['H0', 'H1', 'H2', 'H4'],
                    'style': mapping['style'],
                    'variable_name': mapping['variable_name'],
                    'is_calculated': mapping['is_calculated'],
                    'calculation_formula': mapping['calculation_formula'],
                    'show_amount': mapping['show_amount'],
                    'block_group': mapping.get('block_group'),
                    'always_show': self._normalize_always_show(mapping.get('always_show', False))
                })
            else:
                # Data row - calculate amounts for both years
                if mapping.get('is_calculated'):
                    # For calculated items, set to 0 initially, will be updated in second pass
                    current_amount = 0.0
                    previous_amount = 0.0
                else:
                    # Direct account calculation
                    current_amount = self.calculate_variable_value(mapping, current_accounts)
                    previous_amount = self.calculate_variable_value(mapping, previous_accounts or {})
                
                results.append({
                    'id': mapping['row_id'],
                    'label': mapping['row_title'],
                    'current_amount': current_amount,
                    'previous_amount': previous_amount,
                    'level': self._get_level_from_style(mapping['style']),
                    'section': 'BR',
                    'type': self._get_balance_type(mapping),
                    'bold': mapping['style'] in ['H0', 'H1', 'H2', 'H4'],
                    'style': mapping['style'],
                    'variable_name': mapping['variable_name'],
                    'is_calculated': mapping['is_calculated'],
                    'calculation_formula': mapping['calculation_formula'],
                    'show_amount': mapping['show_amount'],
                    'block_group': mapping.get('block_group'),
                    'always_show': self._normalize_always_show(mapping.get('always_show', False))
                })
        
        # Second pass: Calculate formulas using all available data
        # Sort calculated mappings by row_id to ensure dependencies are calculated first
        calculated_mappings = [(i, mapping) for i, mapping in enumerate(self.br_mappings) 
                              if mapping.get('is_calculated')]
        calculated_mappings.sort(key=lambda x: int(x[1]['row_id']))
        
        for i, mapping in calculated_mappings:
                current_amount = self.calculate_formula_value(mapping, current_accounts, results, use_previous_year=False, rr_data=rr_data)
                previous_amount = self.calculate_formula_value(mapping, previous_accounts or {}, results, use_previous_year=True, rr_data=rr_data)
                
                # Find and update the correct result by row_id
                for result in results:
                    if result['id'] == mapping['row_id']:
                        result['current_amount'] = current_amount
                        result['previous_amount'] = previous_amount
                        break
        
        # Apply 168x reclass before storing calculated values
        if USE_168X_RECLASS and sie_text:
            try:
                self._reclassify_168x_short_term_group_receivables(
                    sie_text=sie_text,
                    br_rows=results,
                    current_accounts=current_accounts
                )
            except Exception as e:
                print(f"168x reclass skipped due to error: {e}")
        
        # Store calculated values in database for future use
        self.store_calculated_values(results, 'BR')
        
        # Sort results by ID to ensure correct order
        results.sort(key=lambda x: int(x['id']))
        

        
        return results
    
    def reclass_using_koncern_note(self, br_rows: list[dict], koncern_note: dict, *, verbose: bool = True) -> list[dict]:
        """
        Make BR consistent with KONCERN note (K2):
        - Force 'Andelar i koncernföretag' to match NOTE 'red_varde_koncern'
          (row_id 329 / variable_name 'AndelarKoncernForetag').
        - Offset the same delta by decreasing koncern receivables:
          first 'FordringarKoncernForetagLang' (row_id 330), then
          'FordringarKoncernForetagKort' (row_id 351).
        - Only current year is adjusted; previous_amount is left as-is.
        """

        def _find(var: str = None, rid: int | None = None):
            for r in br_rows:
                if var and r.get('variable_name') == var:
                    return r
                if rid is not None and str(r.get('id')) == str(rid):
                    return r
            return None

        if not koncern_note or 'red_varde_koncern' not in koncern_note:
            if verbose:
                print("KONCERN reclass skipped: no note or no 'red_varde_koncern'.")
            return br_rows

        target_book = float(koncern_note.get('red_varde_koncern') or 0.0)
        if abs(target_book) < 0.5:
            if verbose:
                print("KONCERN reclass: red_varde_koncern is ~0 → nothing to do.")
            return br_rows

        # Rows we touch (verified against your BR CSV export)
        row_andelar = _find(var='AndelarKoncernForetag') or _find(rid=329)
        row_fordr_L = _find(var='FordringarKoncernForetagLang') or _find(rid=330)
        row_fordr_K = _find(var='FordringarKoncernForetagKort') or _find(rid=351)

        if not row_andelar:
            if verbose:
                print("KONCERN reclass aborted: 'AndelarKoncernForetag' not found in BR rows.")
            return br_rows

        current_andelar = float(row_andelar.get('current_amount') or 0.0)
        delta = target_book - current_andelar
        if abs(delta) < 0.5:
            if verbose:
                print(f"KONCERN reclass: Δ≈0 (andelar {current_andelar:.0f} ≈ note {target_book:.0f}).")
            return br_rows

        # 1) Force Andelar to NOTE
        row_andelar['current_amount'] = current_andelar + delta
        if verbose:
            print(f"KONCERN reclass: AndelarKoncernForetag {current_andelar:.0f} → {row_andelar['current_amount']:.0f} (Δ={delta:.0f}).")

        # 2) Offset the same Δ from koncern receivables so assets total stays unchanged
        remaining = delta

        def _pull_from(row: dict | None, amount: float) -> float:
            if row is None or abs(amount) < 0.5:
                return amount
            cur = float(row.get('current_amount') or 0.0)
            row['current_amount'] = cur - amount
            return 0.0

        if abs(remaining) >= 0.5:
            remaining = _pull_from(row_fordr_L, remaining)
        if abs(remaining) >= 0.5:
            remaining = _pull_from(row_fordr_K, remaining)

        if verbose and abs(remaining) >= 0.5:
            print("KONCERN reclass warning: Could not offset full Δ via koncern receivables "
                  f"(leftover {remaining:.0f}). Check BR mappings for #330/#351.")
        return br_rows

    def parse_br_data_with_koncern(self,
                                   se_content: str,
                                   current_accounts: Dict[str, float],
                                   previous_accounts: Dict[str, float] = None,
                                   rr_data: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Regular BR parsing + KONCERN-note reconciliation for Andelar/fordringar."""
        # 1) Normal BR (with 168x reclass)
        br_rows = self.parse_br_data(current_accounts, previous_accounts, rr_data=rr_data, sie_text=se_content)

        # 2) Parse KONCERN note and reconcile
        try:
            from .koncern_k2_parser import parse_koncern_k2_from_sie_text
            koncern_note = parse_koncern_k2_from_sie_text(se_content, debug=False)
        except Exception as e:
            print(f"KONCERN note parse failed: {e}")
            return br_rows

        if os.getenv("BR_USE_KONCERN_NOTE", "true").lower() == "true":
            br_rows = self.reclass_using_koncern_note(br_rows, koncern_note, verbose=True)

        return br_rows
    
    # ----------------- 168x → 351/352/353 BR RECLASS (uses SIE text) -----------------
    def _reclassify_168x_short_term_group_receivables(self, sie_text: str, br_rows: List[Dict[str, Any]], current_accounts: Dict[str, float]) -> None:
        import re, unicodedata

        def _norm(s: str) -> str:
            if not s: return ""
            s = unicodedata.normalize("NFKD", s)
            s = "".join(ch for ch in s if not unicodedata.combining(ch))
            s = s.lower().replace("\u00a0", " ").replace("\t", " ")
            return re.sub(r"\s+", " ", s).strip()

        def _tokens(name: str) -> set[str]:
            n = _norm(name)
            words = re.findall(r"[a-zåäö]{2,}", n)
            stop = {
                # relationship/financial
                "andel","andelar","aktie","aktier","ack","nedskrivn","nedskrivningar",
                "villkorade","ovillkorade","aktieagartillskott","aktieägartillskott",
                "koncernforetag","koncernföretag","intresseforetag","intresseföretag",
                "dotterforetag","dotterföretag","gemensamt","styrda","ovriga","övriga",
                "agarintresse","ägarintresse","foretag","företag","hos","det","finns","ett",
                "kortfristiga","langfristiga","långfristiga","fordringar","fordran",
                # very generic legal forms
                "ab","kb","hb","oy","as","gmbh","bv","ltd","group","holding"
            }
            return {w for w in words if w not in stop}

        def _company_phrases(name: str) -> set[str]:
            """
            Extract clean company phrase(s) from kontonamn:
            - prefer part after comma; otherwise use full string minus relationship words & legal suffixes.
            - keep 2+ letter words; join into 'brand phrases' like 'rh property', 'flying parking'.
            """
            n = _norm(name)
            part = n.split(",", 1)[1].strip() if "," in n else n
            # remove common relationship lead-ins
            part = re.sub(r"\b(andel(ar)?|aktier|aktieagartillskott|aktieägartillskott|ack(umulerade)?|nedskrivningar?|kortfristiga|fordringar?)\b", " ", part)
            # drop legal suffixes at end
            part = re.sub(r"\b(ab|kb|hb|oy|as|gmbh|bv|ltd)\b\.?", " ", part)
            words = re.findall(r"[a-zåäö]{2,}", part)
            if not words: 
                return set()
            # assemble a single main phrase, and also include 2-gram shards for robustness
            phrase = " ".join(words)
            shards = set()
            for i in range(len(words)-1):
                shards.add(f"{words[i]} {words[i+1]}")
            return {phrase} | shards

        # --- strict pattern classification for voucher/account texts ---
        def _classify_by_patterns(text_norm: str) -> str | None:
            # Övriga m. ägarintresse: need ALL three components
            has_ovr = bool(re.search(r"\b(övr|ovr)(iga)?\b", text_norm))
            has_f = bool(re.search(r"\b(företag|foretag|ftg)\b", text_norm))
            has_ai = bool(re.search(r"\b(ägarintresse|agarintresse|ägarint|agarint|ägarintr|agarintr)\b", text_norm))
            if has_ovr and has_f and has_ai:
                return "ovriga"

            # Intresse: keyword or combos
            if re.search(r"\b(intresseföretag|intresseforetag|intresseftg)\b", text_norm):
                return "intresse"
            if re.search(r"\bintr\w+\b", text_norm) and has_f:
                return "intresse"
            if re.search(r"\bgem\w+\b", text_norm) and re.search(r"\bstyrda\b", text_norm):
                return "intresse"

            # Koncern: koncern/dotter/moder
            if re.search(r"\b(koncern|dotter|moder)\b", text_norm):
                return "koncern"

            return None

        # ---------- quick exit: any 168x UB? ----------
        total_168_ub = sum(float(current_accounts.get(str(a), 0.0)) for a in range(1680, 1690))
        if abs(total_168_ub) < 0.5:
            return

        konto_re = re.compile(r'^#KONTO\s+(\d+)\s+"([^"]*)"', re.IGNORECASE)

        # learn tokens & phrases from 13xx
        koncern_keys, intresse_keys, ovriga_keys = set(), set(), set()
        koncern_phr,  intresse_phr,  ovriga_phr  = set(), set(), set()

        def _bucket_for_13xx(acct: int) -> str | None:
            if 1310 <= acct <= 1329: return "koncern"
            if (1330 <= acct <= 1335) or (1338 <= acct <= 1345) or acct == 1348: return "intresse"
            if (1336 <= acct <= 1337) or (1346 <= acct <= 1347): return "ovriga"
            return None

        # also map 168x kontonamn for per-account classification
        name_168x: dict[int, str] = {}

        for raw in sie_text.splitlines():
            m = konto_re.match(raw.strip())
            if not m: 
                continue
            acct = int(m.group(1))
            nm = m.group(2) or ""
            if 1680 <= acct <= 1689:
                name_168x[acct] = nm
            b = _bucket_for_13xx(acct)
            if not b:
                continue
            toks = _tokens(nm)
            phr  = _company_phrases(nm)
            if b == "koncern":
                koncern_keys |= toks;  koncern_phr |= phr
            elif b == "intresse":
                intresse_keys |= toks; intresse_phr |= phr
            else:
                ovriga_keys |= toks;   ovriga_phr |= phr

        if not (koncern_keys or intresse_keys or ovriga_keys or koncern_phr or intresse_phr or ovriga_phr):
            return

        # ---- per-account deterministic classification ----
        alloc = {"koncern": 0.0, "intresse": 0.0, "ovriga": 0.0}

        for a in range(1680, 1690):
            ub = float(current_accounts.get(str(a), 0.0))
            if abs(ub) < 0.5:
                continue
            nm = name_168x.get(a, "") or ""
            nmn = _norm(nm)

            # 1) strict pattern match on the 168x name itself
            cat = _classify_by_patterns(nmn)
            if cat:
                alloc[cat] += ub
                continue

            # 2) phrase (company name) matching – unambiguous only
            hits = set()
            if any(p and p in nmn for p in koncern_phr):   hits.add("koncern")
            if any(p and p in nmn for p in intresse_phr):  hits.add("intresse")
            if any(p and p in nmn for p in ovriga_phr):    hits.add("ovriga")
            if len(hits) == 1:
                alloc[next(iter(hits))] += ub
                continue
            if len(hits) > 1:
                # ambiguous → leave in 354
                continue

            # 3) token overlap fallback
            toks = _tokens(nm)
            s_k = len(toks & koncern_keys)
            s_i = len(toks & intresse_keys)
            s_o = len(toks & ovriga_keys)
            ranked = sorted([("koncern", s_k), ("intresse", s_i), ("ovriga", s_o)], key=lambda x: x[1], reverse=True)
            if ranked[0][1] > 0 and ranked[0][1] > ranked[1][1]:
                alloc[ranked[0][0]] += ub
            # else ambiguous/no signal → stays in 354

        # ---- mutate BR rows (current year only) ----
        def _find_by_id(rows: List[Dict[str, Any]], rid: int):
            for r in rows:
                if str(r.get("id")) == str(rid):
                    return r
            return None

        row_351 = _find_by_id(br_rows, 351) or next((r for r in br_rows if "koncernföretag" in _norm(r.get("label") or "")), None)
        row_352 = _find_by_id(br_rows, 352) or next((r for r in br_rows if "intresseföretag" in _norm(r.get("label") or "")), None)
        row_353 = _find_by_id(br_rows, 353) or next((r for r in br_rows if "övriga företag" in _norm(r.get("label") or "")), None)
        row_354 = _find_by_id(br_rows, 354) or next((r for r in br_rows if "övriga kortfristiga fordringar" in _norm(r.get("label") or "")), None)

        added = 0.0
        if row_351 and alloc["koncern"]:
            row_351["current_amount"] = float(row_351.get("current_amount") or 0.0) + alloc["koncern"]; added += alloc["koncern"]
        if row_352 and alloc["intresse"]:
            row_352["current_amount"] = float(row_352.get("current_amount") or 0.0) + alloc["intresse"]; added += alloc["intresse"]
        if row_353 and alloc["ovriga"]:
            row_353["current_amount"] = float(row_353.get("current_amount") or 0.0) + alloc["ovriga"];   added += alloc["ovriga"]

        if row_354 and added:
            cur = float(row_354.get("current_amount") or 0.0)
            row_354["current_amount"] = max(0.0, cur - added)
    
    def _get_level_from_style(self, style: str) -> int:
        """Get hierarchy level from style"""
        style_map = {
            'H0': 0,
            'H1': 1,
            'H2': 2,
            'H3': 3,
            'H4': 4,  # Replace S1, S2, S3 with H4
            'NORMAL': 4,
            'S1': 4,  # Map S1 to H4 level
            'S2': 4,  # Map S2 to H4 level
            'S3': 4   # Map S3 to H4 level
        }
        return style_map.get(style, 4)
    
    def _get_balance_type(self, mapping: Dict[str, Any]) -> str:
        """Get balance type (asset/liability/equity) from mapping"""
        balance_type = mapping.get('balance_type', 'DEBIT')
        
        # Simple mapping - you might need to refine this based on your BR structure
        if balance_type == 'DEBIT':
            return 'asset'
        elif balance_type == 'CREDIT':
            # Determine if it's liability or equity based on account ranges
            start = mapping.get('accounts_included_start', 0)
            if start and start >= 2000:  # Equity accounts typically start at 2000+
                return 'equity'
            else:
                return 'liability'
        else:
            return 'asset'  # Default
    
    def ensure_financial_data_columns(self, rr_data: List[Dict[str, Any]], br_data: List[Dict[str, Any]]) -> None:
        """Ensure that the financial_data table has columns for all variables"""
        # Temporarily disabled - exec_sql function doesn't exist in database
        # TODO: Implement proper dynamic column creation when database supports it
        pass

    def store_financial_data(self, company_id: str, fiscal_year: int, 
                           rr_data: List[Dict[str, Any]], br_data: List[Dict[str, Any]]) -> Dict[str, str]:
        """Store parsed financial data in the database"""
        try:
            # Temporarily disabled dynamic column creation
            # self.ensure_financial_data_columns(rr_data, br_data)
            
            # Store RR data
            rr_values = {}
            for item in rr_data:
                if item['current_amount'] is not None and item['variable_name']:
                    rr_values[item['variable_name']] = item['current_amount']
            
            if rr_values:
                try:
                    supabase.table('financial_data').upsert({
                        'company_id': company_id,
                        'fiscal_year': fiscal_year,
                        'report_type': 'RR',
                        **rr_values
                    }).execute()
                except Exception as e:
                    print(f"Warning: Could not store some RR data: {e}")
                    # Try storing only basic data without potentially problematic columns
                    basic_rr_data = {k: v for k, v in rr_values.items() 
                                   if not any(problematic in k for problematic in ['AktiveratArbeteEgenRakning'])}
                    if basic_rr_data:
                        try:
                            supabase.table('financial_data').upsert({
                                'company_id': company_id,
                                'fiscal_year': fiscal_year,
                                'report_type': 'RR',
                                **basic_rr_data
                            }).execute()
                        except Exception as e2:
                            print(f"Warning: Could not store RR data at all: {e2}")
            
            # Store BR data
            br_values = {}
            for item in br_data:
                if item['current_amount'] is not None and item['variable_name']:
                    br_values[item['variable_name']] = item['current_amount']
            
            if br_values:
                supabase.table('financial_data').upsert({
                    'company_id': company_id,
                    'fiscal_year': fiscal_year,
                    'report_type': 'BR',
                    **br_values
                }).execute()
            
            return {
                'rr_id': f"{company_id}_{fiscal_year}_RR",
                'br_id': f"{company_id}_{fiscal_year}_BR"
            }
            
        except Exception as e:
            print(f"Error storing financial data: {e}")
            return {}
    
    def get_financial_data(self, company_id: str, fiscal_year: int) -> Dict[str, Any]:
        """Retrieve financial data from database"""
        try:
            rr_data = supabase.table('financial_data').select('*').eq('company_id', company_id).eq('fiscal_year', fiscal_year).eq('report_type', 'RR').execute()
            br_data = supabase.table('financial_data').select('*').eq('company_id', company_id).eq('fiscal_year', fiscal_year).eq('report_type', 'BR').execute()
            
            return {
                'rr_data': rr_data.data[0] if rr_data.data else {},
                'br_data': br_data.data[0] if br_data.data else {}
            }
            
        except Exception as e:
            print(f"Error retrieving financial data: {e}")
            return {'rr_data': {}, 'br_data': {}}

    def extract_company_info(self, se_content: str) -> Dict[str, Any]:
        """Extract company information from SE file headers"""
        company_info = {}
        lines = se_content.split('\n')
        
        for line in lines:
            line = line.strip()
            
            if line.startswith('#FNAMN'):
                # Company name: #FNAMN "Company Name"
                parts = line.split('"', 2)
                if len(parts) >= 2:
                    company_info['company_name'] = parts[1]
                    
            elif line.startswith('#ORGNR'):
                # Organization number: #ORGNR 556610-3643
                parts = line.split()
                if len(parts) >= 2:
                    company_info['organization_number'] = parts[1]
                    
            elif line.startswith('#RAR'):
                # Fiscal year: #RAR 0 20240101 20241231
                parts = line.split()
                if len(parts) >= 4 and parts[1] == '0':  # Current year
                    company_info['fiscal_year'] = int(parts[2][:4])  # Extract year from date
                    company_info['start_date'] = parts[2]
                    company_info['end_date'] = parts[3]
        

        return company_info
    
    def update_calculation_formula(self, row_id: int, formula: str) -> bool:
        """Update calculation formula for a specific row in the database"""
        try:
            # Update the formula in variable_mapping_br table
            response = supabase.table('variable_mapping_br').update({
                'calculation_formula': formula,
                'is_calculated': True
            }).eq('id', row_id).execute()
            

            return True
            
        except Exception as e:
            print(f"Error updating formula for row {row_id}: {e}")
            return False
    
    def parse_ink2_data(self, current_accounts: Dict[str, float], fiscal_year: int = None, rr_data: List[Dict[str, Any]] = None, br_data: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Parse INK2 tax calculation data using database mappings.
        Returns simplified structure: row_title and amount only.
        """
        # Force reload mappings to get fresh data from database
        self._load_mappings()
        if not self.ink2_mappings:
            return []
        
        results = []
        
        # Sort mappings by row_id to maintain correct order
        sorted_mappings = sorted(self.ink2_mappings, key=lambda x: x.get('row_id', 0))
        
        ink_values: Dict[str, float] = {}
        for mapping in sorted_mappings:
            try:
                # Always calculate (or default to 0) so rows can be shown with blank amount if needed
                amount = self.calculate_ink2_variable_value(mapping, current_accounts, fiscal_year, rr_data, ink_values, br_data)
                
                # Special handling: hide INK4_header (duplicate "Skatteberäkning")
                variable_name = mapping.get('variable_name', '')
                if variable_name == 'INK4_header':
                    continue  # Skip this row entirely
                
                # Return all rows - let frontend handle visibility logic
                result = {
                        'row_id': mapping.get('row_id'),
                        'row_title': mapping.get('row_title', ''),
                        'amount': amount,
                        'variable_name': mapping.get('variable_name', ''),
                        'show_tag': mapping.get('show_tag', False),
                        'accounts_included': mapping.get('accounts_included', ''),
                        'account_details': self._get_account_details(mapping.get('accounts_included', ''), current_accounts) if mapping.get('show_tag', False) else None,
                        'show_amount': self._normalize_show_amount(mapping.get('show_amount', True)),
                        'is_calculated': self._normalize_is_calculated(mapping.get('is_calculated', True)),
                        'always_show': self._normalize_always_show(mapping.get('always_show', False)),
                        'style': mapping.get('style'),
                        'explainer': mapping.get('explainer', ''),
                        'block': mapping.get('block', ''),
                        'header': mapping.get('header', False)
                    }
                results.append(result)
                # store for later formula dependencies
                var_name = mapping.get('variable_name')
                if var_name:
                    ink_values[var_name] = amount
                    
            except Exception as e:
                print(f"Error processing INK2 mapping {mapping.get('variable_name', 'unknown')}: {e}")
                continue
        
        return results
    
    def parse_ink2_data_with_overrides(self, current_accounts: Dict[str, float], fiscal_year: int = None, 
                                       rr_data: List[Dict[str, Any]] = None, br_data: List[Dict[str, Any]] = None,
                                       manual_amounts: Dict[str, float] = None) -> List[Dict[str, Any]]:
        """
        Parse INK2 tax calculation data with manual amount overrides for dynamic recalculation.
        """
        # Force reload mappings to get fresh data from database
        self._load_mappings()
        if not self.ink2_mappings:
            return []
        
        manual_amounts = manual_amounts or {}
        results = []
        
        # Sort mappings by row_id to maintain correct order
        sorted_mappings = sorted(self.ink2_mappings, key=lambda x: x.get('row_id', 0))
        
        ink_values: Dict[str, float] = {}
        
        # Inject justering_sarskild_loneskatt into ink_values if provided
        if 'justering_sarskild_loneskatt' in manual_amounts:
            ink_values['justering_sarskild_loneskatt'] = manual_amounts['justering_sarskild_loneskatt']

        
        # Inject INK4.14a (outnyttjat underskott) into ink_values if provided
        if 'INK4.14a' in manual_amounts:
            ink_values['INK4.14a'] = manual_amounts['INK4.14a']

        
        # Inject underskott adjustment for INK4.16 if provided
        if 'ink4_16_underskott_adjustment' in manual_amounts:
            ink_values['ink4_16_underskott_adjustment'] = manual_amounts['ink4_16_underskott_adjustment']
            print(f"Injected ink4_16_underskott_adjustment: {manual_amounts['ink4_16_underskott_adjustment']}")
        
        
        for mapping in sorted_mappings:
            try:
                variable_name = mapping.get('variable_name', '')
                
                # Force recalculation of dependent summary values even if not manually edited
                force_recalculate = variable_name in ['INK_skattemassigt_resultat', 'INK_beraknad_skatt']
                
                # Check if this value has been manually overridden (but only for non-calculated fields)
                if variable_name in manual_amounts and not force_recalculate:
                    amount = manual_amounts[variable_name]
                    ink_values[variable_name] = amount  # Store for dependencies
                    print(f"Using manual override for {variable_name}: {amount}")
                else:
                    # Calculate normally (or force recalculate for dependent values)
                    amount = self.calculate_ink2_variable_value(mapping, current_accounts, fiscal_year, rr_data, ink_values, br_data)
                    # Round all INK2 values to 0 decimals (skattemässigt resultat already has special rounding)
                    if variable_name != 'INK_skattemassigt_resultat':
                        amount = round(amount, 0)
                    # IMPORTANT: Store calculated values for later formulas
                    ink_values[variable_name] = amount
                    if variable_name in ['INK_skattemassigt_resultat', 'INK_beraknad_skatt']:
                        print(f"Calculated {variable_name}: {amount} (available ink_values: {list(ink_values.keys())})")
                
                # Keep only essential debug for important tax calculations
                
                # Special handling: hide INK4_header (duplicate "Skatteberäkning")
                if variable_name == 'INK4_header':
                    continue  # Skip this row entirely
                
                # Return all rows - let frontend handle visibility logic
                # Get account details for SHOW button if needed
                account_details = []
                if mapping.get('show_tag') and mapping.get('accounts_included'):
                    account_details = self._get_account_details(mapping['accounts_included'], current_accounts)
                
                results.append({
                        'row_id': mapping.get('row_id', 0),
                        'row_title': mapping['row_title'],
                        'amount': amount,
                        'variable_name': variable_name,
                        'show_tag': mapping.get('show_tag', False),
                        'accounts_included': mapping.get('accounts_included', ''),
                        'show_amount': self._normalize_show_amount(mapping.get('show_amount')),
                        'style': mapping.get('style', 'NORMAL'),
                        'is_calculated': self._normalize_is_calculated(mapping.get('is_calculated')),
                        'always_show': self._normalize_always_show(mapping.get('always_show', False)),
                        'explainer': mapping.get('explainer', ''),
                        'block': mapping.get('block', ''),
                        'header': mapping.get('header', False),
                        'account_details': account_details
                    })
                
            except Exception as e:
                print(f"Error processing INK2 mapping {mapping.get('variable_name', 'unknown')}: {e}")
                continue
        
        return results


    def _normalize_show_amount(self, value: Any) -> bool:
        """Normalize show_amount to boolean. Handles string 'TRUE'/'FALSE' from database."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.upper() == 'TRUE'
        return bool(value)
    
    def _normalize_is_calculated(self, value: Any) -> bool:
        """Normalize is_calculated to boolean. Handles string 'TRUE'/'FALSE' from database."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.upper() == 'TRUE'
        return bool(value)
    
    def _normalize_always_show(self, value: Any) -> bool:
        """Normalize always_show to boolean values only."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().upper()
            if normalized == 'TRUE':
                return True
            else:
                return False  # Any other string (including 'FALSE', empty, etc.) = False
        return False  # Default to False for any other type
    
    def calculate_ink2_variable_value(self, mapping: Dict[str, Any], accounts: Dict[str, float], fiscal_year: int = None, rr_data: List[Dict[str, Any]] = None, ink_values: Optional[Dict[str, float]] = None, br_data: Optional[List[Dict[str, Any]]] = None) -> float:
        """
        Calculate the value for an INK2 variable using accounts and formulas.
        """
        variable_name = mapping.get('variable_name', '')

        # Helper to fetch RR variables
        def rr(var: str) -> float:
            if not rr_data:
                return 0.0
            for item in rr_data:
                if item.get('variable_name') == var:
                    value = item.get('current_amount')
                    return float(value) if value is not None else 0.0
            return 0.0

        # Explicit logic for key variables
        if variable_name == 'INK4.1':
            sum_arets = rr('SumAretsResultat')
            return sum_arets if sum_arets > 0 else 0.0
        if variable_name == 'INK4.2':
            sum_arets = rr('SumAretsResultat')
            return -sum_arets if sum_arets < 0 else 0.0
        if variable_name == 'INK4.3a':
            return rr('SkattAretsResultat')
        if variable_name == 'INK4.6a':
            # Periodiseringsfonder previous_year * statslaneranta
            rate = float(self.global_variables.get('statslaneranta', 0.0))
            prev = 0.0
            if br_data:
                for item in br_data:
                    if item.get('variable_name') == 'Periodiseringsfonder':
                        val = item.get('previous_amount')
                        prev = float(val) if val is not None else 0.0
                        break
            return prev * rate
        
        # New pension tax variables
        if variable_name == 'pension_premier':
            # Amount in account 7410
            return abs(float(accounts.get('7410', 0.0)))
        if variable_name == 'sarskild_loneskatt_pension':
            # Amount in account 7531
            return abs(float(accounts.get('7531', 0.0)))
        if variable_name == 'sarskild_loneskatt_pension_calculated':
            # pension_premier * sarskild_loneskatt (global variable)
            pension_premier = abs(float(accounts.get('7410', 0.0)))
            rate = float(self.global_variables.get('sarskild_loneskatt', 0.0))
            result = pension_premier * rate
            # Round to 0 decimals for tax module
            return round(result, 0)
        if variable_name == 'INK_sarskild_loneskatt':
            # Hardcoded formula: -justering_sarskild_loneskatt
            justering = float(ink_values.get('justering_sarskild_loneskatt', 0.0)) if ink_values else 0.0
            result = -justering
            # Round to 0 decimals for tax module
            result = round(result, 0)
            print(f"INK_sarskild_loneskatt: justering={justering}, result={result}")
            return result
        

        
        if variable_name == 'INK_skattemassigt_resultat':
            def v(name: str) -> float:
                if not ink_values:
                    return 0.0
                return float(ink_values.get(name, 0.0))
            
            # Hardcoded formula: INK4.1-INK4.2+INK4.3b+INK4.3c-INK4.4a-INK4.4b-INK4.5a-INK4.5b-INK4.5c+INK4.6a+INK4.6b+INK4.6c+INK4.6d+INK4.6e-INK4.7a+INK4.7b-INK4.7c+INK4.7d+INK4.7e-INK4.7f-INK4.8a+INK4.8b+INK4.8c-INK4.8d+INK4.9(+)-INK4.9(-)+INK4.10(+)-INK4.10(-)-INK4.11+INK4.12+INK4.13(+)-INK4.13(-)-INK4.14a+INK4.14b+INK4.14c-justering_sarskild_loneskatt
            justering = float(ink_values.get('justering_sarskild_loneskatt', 0.0)) if ink_values else 0.0
            total = (
                v('INK4.1') - v('INK4.2') + v('INK4.3b') + v('INK4.3c')
                - v('INK4.4a') - v('INK4.4b') - v('INK4.5a') - v('INK4.5b') - v('INK4.5c')
                + v('INK4.6a') + v('INK4.6b') + v('INK4.6c') + v('INK4.6d') + v('INK4.6e')
                - v('INK4.7a') + v('INK4.7b') - v('INK4.7c') + v('INK4.7d') + v('INK4.7e') - v('INK4.7f')
                - v('INK4.8a') + v('INK4.8b') + v('INK4.8c') - v('INK4.8d')
                + v('INK4.9(+)') - v('INK4.9(-)')
                + v('INK4.10(+)') - v('INK4.10(-)')
                - v('INK4.11') + v('INK4.12') + v('INK4.13(+)') - v('INK4.13(-)')
                - v('INK4.14a') + v('INK4.14b') + v('INK4.14c')
                - justering  # Subtract pension tax adjustment
            )
            # Apply FLOOR(total, 100) - round down to nearest 100 per Skatteverket rules
            floored_total = int(total // 100) * 100
            print(f"INK_skattemassigt_resultat: raw_total={total}, floored={floored_total}")
            return float(floored_total)
        if variable_name == 'INK4.15':
            def v(name: str) -> float:
                if not ink_values:
                    return 0.0
                return float(ink_values.get(name, 0.0))
            
            # Hardcoded formula: MAX(0, INK4.1-INK4.2+INK4.3a+INK4.3b+INK4.3c-INK4.4a-INK4.4b-INK4.5a-INK4.5b-INK4.5c+INK4.6a+INK4.6b+INK4.6c+INK4.6d+INK4.6e-INK4.7a+INK4.7b-INK4.7c+INK4.7d+INK4.7e-INK4.7f-INK4.8a+INK4.8b+INK4.8c-INK4.8d+INK4.9(+)-INK4.9(-)+INK4.10(+)-INK4.10(-)-INK4.11+INK4.12+INK4.13(+)-INK4.13(-)-INK4.14a+INK4.14b+INK4.14c-justering_sarskild_loneskatt)
            justering = float(ink_values.get('justering_sarskild_loneskatt', 0.0)) if ink_values else 0.0
            total = (
                v('INK4.1') - v('INK4.2') + v('INK4.3a') + v('INK4.3b') + v('INK4.3c')
                - v('INK4.4a') - v('INK4.4b') - v('INK4.5a') - v('INK4.5b') - v('INK4.5c')
                + v('INK4.6a') + v('INK4.6b') + v('INK4.6c') + v('INK4.6d') + v('INK4.6e')
                - v('INK4.7a') + v('INK4.7b') - v('INK4.7c') + v('INK4.7d') + v('INK4.7e') - v('INK4.7f')
                - v('INK4.8a') + v('INK4.8b') + v('INK4.8c') - v('INK4.8d')
                + v('INK4.9(+)') - v('INK4.9(-)')
                + v('INK4.10(+)') - v('INK4.10(-)')
                - v('INK4.11') + v('INK4.12') + v('INK4.13(+)') - v('INK4.13(-)')
                - v('INK4.14a') + v('INK4.14b') + v('INK4.14c')
                - justering  # Subtract pension tax adjustment
            )
            # MAX(0, total) - show only if positive
            return float(max(0, round(total)))
        if variable_name == 'INK4.16':
            def v(name: str) -> float:
                if not ink_values:
                    return 0.0
                return float(ink_values.get(name, 0.0))
            
            # Hardcoded formula: IF(INK4.1-INK4.2+INK4.3a+INK4.3b+INK4.3c-INK4.4a-INK4.4b-INK4.5a-INK4.5b-INK4.5c+INK4.6a+INK4.6b+INK4.6c+INK4.6d+INK4.6e-INK4.7a+INK4.7b-INK4.7c+INK4.7d+INK4.7e-INK4.7f-INK4.8a+INK4.8b+INK4.8c-INK4.8d+INK4.9(+)-INK4.9(-)+INK4.10(+)-INK4.10(-)-INK4.11+INK4.12+INK4.13(+)-INK4.13(-)-INK4.14a+INK4.14b+INK4.14c-justering_sarskild_loneskatt < 0, sum, 0)
            justering = float(ink_values.get('justering_sarskild_loneskatt', 0.0)) if ink_values else 0.0
            total = (
                v('INK4.1') - v('INK4.2') + v('INK4.3a') + v('INK4.3b') + v('INK4.3c')
                - v('INK4.4a') - v('INK4.4b') - v('INK4.5a') - v('INK4.5b') - v('INK4.5c')
                + v('INK4.6a') + v('INK4.6b') + v('INK4.6c') + v('INK4.6d') + v('INK4.6e')
                - v('INK4.7a') + v('INK4.7b') - v('INK4.7c') + v('INK4.7d') + v('INK4.7e') - v('INK4.7f')
                - v('INK4.8a') + v('INK4.8b') + v('INK4.8c') - v('INK4.8d')
                + v('INK4.9(+)') - v('INK4.9(-)')
                + v('INK4.10(+)') - v('INK4.10(-)')
                - v('INK4.11') + v('INK4.12') + v('INK4.13(+)') - v('INK4.13(-)')
                - v('INK4.14a') + v('INK4.14b') + v('INK4.14c')
                - justering  # Subtract pension tax adjustment
            )
            # IF(total < 0, abs(total), 0) - show absolute value if negative, otherwise 0
            return float(abs(total) if total < 0 else 0)
        if variable_name == 'INK_bokford_skatt':
            return rr('SkattAretsResultat')
        if variable_name == 'INK_beraknad_skatt':
            base = 0.0
            if ink_values:
                base = float(ink_values.get('INK_skattemassigt_resultat', 0.0))
            if base <= 0:
                return 0.0
            # base is already rounded down to nearest 100 in INK_skattemassigt_resultat
            rate = float(self.global_variables.get('skattesats', 0.0))
            tax_amount = base * rate
            # Round to whole kronor: ≥50 öre up, <50 öre down
            rounded_tax = round(tax_amount)
            print(f"INK_beraknad_skatt: base={base}, rate={rate}, tax_amount={tax_amount}, rounded={rounded_tax}")
            return float(rounded_tax)

        # If there's a calculation formula, use it
        if mapping.get('calculation_formula'):
            return self.calculate_ink2_formula_value(mapping, accounts, fiscal_year, rr_data, ink_values)
        
        # Otherwise, sum the included accounts (use absolute values for positive-only variables)
        account_sum = self.sum_included_accounts(mapping.get('accounts_included', ''), accounts)
        # Variables that should always be positive (account-based calculations)
        positive_only_variables = [
            'INK4.3c', 'INK4.4a', 'INK4.5b', 'INK4.5c', 
            'INK4.6a', 'INK4.6c', 'INK4.21'
        ]
        if variable_name in positive_only_variables:
            return abs(account_sum)
        return account_sum
    
    def calculate_ink2_formula_value(self, mapping: Dict[str, Any], accounts: Dict[str, float], fiscal_year: int = None, rr_data: List[Dict[str, Any]] = None, ink_values: Optional[Dict[str, float]] = None) -> float:
        """
        Calculate value using formula that may reference global variables.
        """
        variable_name = mapping.get('variable_name', '')
        formula = mapping.get('calculation_formula', '')
        if not formula:
            return 0.0
        
        try:
            # Replace global variable references using safe curly brace syntax
            formula_with_values = formula
            for var_name, var_value in self.global_variables.items():
                # Safe replacement: only replace {variable_name} patterns
                placeholder = f"{{{var_name}}}"
                if placeholder in formula_with_values:
                    formula_with_values = formula_with_values.replace(placeholder, str(var_value))
            
            # Replace RR variable references if RR data is available
            if rr_data:
                rr_variables = {}
                for item in rr_data:
                    if item.get('variable_name'):
                        rr_variables[item['variable_name']] = item.get('current_amount', 0) or 0
                
                # Replace RR variable references - Use regex with word boundaries to prevent partial matches
                import re
                for var_name, var_value in rr_variables.items():
                    # Use word boundaries (\b) to match whole words only
                    pattern = r'\b' + re.escape(var_name) + r'\b'
                    if re.search(pattern, formula_with_values):
                        formula_with_values = re.sub(pattern, str(var_value), formula_with_values)
                        # Variable replacement completed
            
            # Keep formula debugging minimal
            
            # Replace INK variable references with their calculated values
            if ink_values:
                import re
                for var_name, var_value in ink_values.items():
                    # Use word boundaries to match whole words only
                    pattern = r'\b' + re.escape(var_name) + r'\b'
                    if re.search(pattern, formula_with_values):
                        # Get the sign from the mapping for this variable
                        var_mapping = next((m for m in self.ink2_mappings if m.get('variable_name') == var_name), None)
                        if var_mapping:
                            sign_column = var_mapping.get('*/+/-', '+')
                            if sign_column == '-':
                                # Apply negative sign for subtraction
                                formula_with_values = re.sub(pattern, f"(-{var_value})", formula_with_values)
                            else:
                                # Use positive value (+ or *)
                                formula_with_values = re.sub(pattern, str(var_value), formula_with_values)
                        else:
                            # Fallback: use value as-is
                            formula_with_values = re.sub(pattern, str(var_value), formula_with_values)
                        
            # Replace account references (format: account_XXXX)
            import re
            account_pattern = r'account_(\d+)'
            matches = re.findall(account_pattern, formula_with_values)
            for account_id in matches:
                account_value = accounts.get(account_id, 0)
                # Use word boundaries for account replacement too
                account_pattern = r'\baccount_' + re.escape(account_id) + r'\b'
                formula_with_values = re.sub(account_pattern, str(account_value), formula_with_values)
            
            # Clean up formula for Python evaluation
            # Handle common Excel-like syntax issues
            formula_with_values = self._clean_formula_for_python(formula_with_values)
            
            # Evaluate the formula safely
            # Note: In production, consider using a safer eval alternative
            return float(eval(formula_with_values))
            
        except Exception as e:
            print(f"Error evaluating formula '{formula}': {e}")
            return 0.0
    
    def _clean_formula_for_python(self, formula: str) -> str:
        """
        Interpret and convert formula logic to executable Python code.
        This handles the actual business logic from the calculation_formula column.
        """
        formula = formula.strip()
        if not formula:
            return '0'
        
        # Handle specific formula patterns based on your database content
        
        # Pattern 1: Simple variable references (e.g., "SumResultatForeSkatt")
        if formula.isalnum() or ('_' in formula and formula.replace('_', '').isalnum()):
            # This is likely a variable reference - it should already be replaced by RR variables
            return '0'  # If we get here, the variable wasn't found
        
        # Pattern 2: "IF statement" logic (e.g., "if >0 = formula")
        if formula.lower().startswith('if '):
            # Extract the condition and formula parts
            # Example: "if >0 = INK4.1-INK4.2+..." becomes conditional logic
            parts = formula.split(' = ', 1)
            if len(parts) == 2:
                condition_part = parts[0].replace('if ', '').strip()
                formula_part = parts[1].strip()
                
                # Convert condition (e.g., ">0", "<0")
                if condition_part == '>0':
                    return f'max(0, {self._convert_ink_formula(formula_part)})'
                elif condition_part == '<0':
                    return f'min(0, {self._convert_ink_formula(formula_part)})'
            return '0'
        
        # Pattern 3: Direct INK formula references (e.g., "INK4.1-INK4.2+INK4.3c...")
        if 'INK4.' in formula:
            return self._convert_ink_formula(formula)
        
        # Pattern 4: FLOOR function (e.g., "FLOOR(value;precision) * rate")
        if 'FLOOR(' in formula:
            import re
            # Replace FLOOR(value;precision) with int(value/precision)*precision
            formula = re.sub(r'FLOOR\(([^;]+);([^)]+)\)', r'(int(\1/\2)*\2)', formula)
        
        # Pattern 5: Simple arithmetic with known variables
        # Clean up operators and return as-is for eval()
        formula = formula.replace(' * ', '*').replace(' + ', '+').replace(' - ', '-').replace(' / ', '/')
        
        return formula
    
    def _convert_ink_formula(self, formula: str) -> str:
        """
        Convert INK4.x variable references to actual calculated values.
        This is a placeholder - in practice, you'd need to either:
        1. Pre-calculate all INK4 values in order, or
        2. Create a dependency resolver
        """
        # For now, return 0 for complex INK formulas since they reference other INK variables
        # that may not be calculated yet. This needs a more sophisticated approach.
        return '0'
    
    def sum_included_accounts(self, accounts_included: str, accounts: Dict[str, float]) -> float:
        """
        Sum the values of included accounts.
        accounts_included format: "6072;6992;7632" or "6000-6999"
        """
        if not accounts_included:
            return 0.0
        
        total = 0.0
        
        # Split by both semicolon and comma for multiple accounts/ranges (handle both separators)
        account_specs = accounts_included.replace(',', ';').split(';')
        
        for spec in account_specs:
            spec = spec.strip()
            if not spec:
                continue
                
            if '-' in spec:
                # Range format: "6000-6999"
                try:
                    start, end = spec.split('-')
                    start_num = int(start.strip())
                    end_num = int(end.strip())
                    
                    for account_id, balance in accounts.items():
                        try:
                            account_num = int(account_id)
                            if start_num <= account_num <= end_num:
                                total += balance
                        except ValueError:
                            continue
                            
                except ValueError:
                    print(f"Invalid range format: {spec}")
                    continue
            else:
                # Single account
                try:
                    account_id = spec.strip()
                    balance = accounts.get(account_id, 0.0)
                    total += balance
                except Exception:
                    print(f"Invalid account format: {spec}")
                    continue
        
        return total
    
    def _get_account_details(self, accounts_included: str, accounts: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        Get detailed account information for popup display.
        Returns list with account_id, account_text, and balance.
        """
        if not accounts_included:
            return []
        
        details = []
        
        # Split by semicolon for multiple accounts/ranges
        account_specs = accounts_included.split(';')
        
        for spec in account_specs:
            spec = spec.strip()
            if not spec:
                continue
                
            if '-' in spec:
                # Range format: "6000-6999"
                try:
                    start, end = spec.split('-')
                    start_num = int(start.strip())
                    end_num = int(end.strip())
                    
                    for account_id, balance in accounts.items():
                        try:
                            account_num = int(account_id)
                            if start_num <= account_num <= end_num and balance != 0:
                                details.append({
                                    'account_id': account_id,
                                    'account_text': self._get_account_text(account_num),
                                    'balance': balance
                                })
                        except ValueError:
                            continue
                            
                except ValueError:
                    continue
            else:
                # Single account
                try:
                    account_id = spec.strip()
                    balance = accounts.get(account_id, 0.0)
                    if balance != 0:  # Only include accounts with non-zero balance
                        details.append({
                            'account_id': account_id,
                            'account_text': self._get_account_text(account_id),
                            'balance': balance
                        })
                except Exception:
                    continue
        
        # Sort by account_id
        details.sort(key=lambda x: int(x['account_id']))
        return details

    def _get_account_text(self, account_id: Any) -> str:
        """Return kontotext for given account id using cache and DB fallback."""
        # Try int key
        try:
            acc_int = int(account_id)
            if acc_int in self.accounts_lookup:
                return self.accounts_lookup[acc_int]
        except Exception:
            acc_int = None
        # Try string key
        key_str = str(account_id)
        if key_str in self.accounts_lookup:
            return self.accounts_lookup[key_str]
        # Fallback: query Supabase directly and update cache
        try:
            resp = supabase.table('accounts_table').select('account_text,account_id').eq('account_id', key_str).limit(1).execute()
            if resp.data:
                text = resp.data[0].get('account_text') or f'Konto {key_str}'
                if acc_int is not None:
                    self.accounts_lookup[acc_int] = text
                self.accounts_lookup[key_str] = text
                return text
        except Exception:
            pass
        return f'Konto {key_str}'
    
    def parse_noter_data(self, se_content: str, user_toggles: Dict[str, bool] = None) -> List[Dict[str, Any]]:
        """
        Parse Noter (Notes) data using database mappings.
        Returns structure with current_amount and previous_amount for both fiscal year and previous year.
        """
        # Force reload mappings to get fresh data from database
        self._load_mappings()
        if not self.noter_mappings:
            print("No Noter mappings available")
            return []
        
        # Parse all balance types from SE file
        current_ub, previous_ub, current_ib, previous_ib = self.parse_ib_ub_balances(se_content)
        
        # Get precise KONCERN calculations from transaction analysis
        from .koncern_k2_parser import parse_koncern_k2_from_sie_text
        koncern_k2_data = parse_koncern_k2_from_sie_text(se_content, debug=False)
        
        # Get precise INTRESSEFTG calculations from transaction analysis
        print("DEBUG: Starting INTRESSEFTG K2 parser...")
        from .intresseftg_k2_parser import parse_intresseftg_k2_from_sie_text
        print("DEBUG: INTRESSEFTG K2 parser imported successfully")
        intresseftg_k2_data = parse_intresseftg_k2_from_sie_text(se_content, debug=True)
        print(f"DEBUG: INTRESSEFTG K2 data calculated successfully: {len(intresseftg_k2_data)} variables")
        print(f"DEBUG: INTRESSEFTG K2 data: {intresseftg_k2_data}")
        
        # Get precise BYGG calculations from transaction analysis
        from .bygg_k2_parser import parse_bygg_k2_from_sie_text
        bygg_k2_data = parse_bygg_k2_from_sie_text(se_content, debug=False)
        
        # Get precise MASKINER calculations from transaction analysis
        from .maskiner_k2_parser import parse_maskiner_k2_from_sie_text
        maskiner_k2_data = parse_maskiner_k2_from_sie_text(se_content, debug=False)
        
        # Get precise INVENTARIER calculations from transaction analysis
        from .inventarier_k2_parser import parse_inventarier_k2_from_sie_text
        inventarier_k2_data = parse_inventarier_k2_from_sie_text(se_content, debug=False)
        
        # Get precise ÖVRIGA calculations from transaction analysis
        from .ovriga_k2_parser import parse_ovriga_k2_from_sie_text
        ovriga_k2_data = parse_ovriga_k2_from_sie_text(se_content, debug=False)
        
        # Get precise LVP calculations from transaction analysis
        from .lvp_k2_parser import parse_lvp_k2_from_sie_text
        lvp_k2_data = parse_lvp_k2_from_sie_text(se_content, debug=False)
        
        # Get precise FORDRKONC calculations from transaction analysis
        from .fordringar_koncern_k2_parser import parse_fordringar_koncern_k2_from_sie_text
        fordrkonc_k2_data = parse_fordringar_koncern_k2_from_sie_text(se_content, debug=False)
        
        # Get precise FORDRINTRE calculations from transaction analysis
        from .fordringar_intresseftg_k2_parser import parse_fordringar_intresseftg_k2_from_sie_text
        fordrintre_k2_data = parse_fordringar_intresseftg_k2_from_sie_text(se_content, debug=False)
        
        # Get precise FORDROVRFTG calculations from transaction analysis
        from .fordringar_ovrftg_k2_parser import parse_fordringar_ovrftg_k2_from_sie_text
        fordrovrftg_k2_data = parse_fordringar_ovrftg_k2_from_sie_text(se_content, debug=False)
        
        # Define all K2 variable names to exclude from database processing
        koncern_variables = set(koncern_k2_data.keys())
        intresseftg_variables = set(intresseftg_k2_data.keys())
        bygg_variables = set(bygg_k2_data.keys())
        maskiner_variables = set(maskiner_k2_data.keys())
        inventarier_variables = set(inventarier_k2_data.keys())
        ovriga_variables = set(ovriga_k2_data.keys())
        lvp_variables = set(lvp_k2_data.keys())
        fordrkonc_variables = set(fordrkonc_k2_data.keys())
        fordrintre_variables = set(fordrintre_k2_data.keys())
        fordrovrftg_variables = set(fordrovrftg_k2_data.keys())
        k2_variables = koncern_variables | intresseftg_variables | bygg_variables | maskiner_variables | inventarier_variables | ovriga_variables | lvp_variables | fordrkonc_variables | fordrintre_variables | fordrovrftg_variables
        
        results = []
        user_toggles = user_toggles or {}
        calculated_variables = {}  # Store calculated values for formula references
        
        # Pre-populate calculated_variables with K2 parser results
        for var_name, value in koncern_k2_data.items():
            calculated_variables[var_name] = {
                'current': value,
                'previous': 0.0
            }
            
        for var_name, value in intresseftg_k2_data.items():
            calculated_variables[var_name] = {
                'current': value,
                'previous': 0.0
            }
            print(f"DEBUG: Pre-loaded INTRESSEFTG K2 variable {var_name}: {value}")
            
        for var_name, value in bygg_k2_data.items():
            calculated_variables[var_name] = {
                'current': value,
                'previous': 0.0
            }
            
        for var_name, value in maskiner_k2_data.items():
            calculated_variables[var_name] = {
                'current': value,
                'previous': 0.0
            }
            
        for var_name, value in inventarier_k2_data.items():
            calculated_variables[var_name] = {
                'current': value,
                'previous': 0.0
            }
            
        for var_name, value in ovriga_k2_data.items():
            calculated_variables[var_name] = {
                'current': value,
                'previous': 0.0
            }
            
        for var_name, value in lvp_k2_data.items():
            calculated_variables[var_name] = {
                'current': value,
                'previous': 0.0
            }
            
        for var_name, value in fordrkonc_k2_data.items():
            calculated_variables[var_name] = {
                'current': value,
                'previous': 0.0
            }
            
        for var_name, value in fordrintre_k2_data.items():
            calculated_variables[var_name] = {
                'current': value,
                'previous': 0.0
            }
            
        for var_name, value in fordrovrftg_k2_data.items():
            calculated_variables[var_name] = {
                'current': value,
                'previous': 0.0
            }
        
        # Sort mappings by row_id to maintain correct order
        sorted_mappings = sorted(self.noter_mappings, key=lambda x: x.get('row_id', 0))
        
        # First pass: Calculate all account-based variables
        for mapping in sorted_mappings:
            variable_name = (mapping.get('variable_name') or '').strip()
            accounts_included = mapping.get('accounts_included', '')
            
            # Skip rows without variable names - they're toggle-only display rows
            # These will be included in final results with amount = 0
            if not variable_name:
                continue
                
            # Completely skip all K2 variables (BYGG and MASKINER) - no database processing at all
            # (K2 parser values are already pre-loaded in calculated_variables)
            if variable_name in k2_variables:
                continue
                
            # Skip rows without accounts (but keep the variable_name for later reference)
            if not accounts_included:
                # Still add to calculated_variables with 0 amounts for toggle-only rows
                calculated_variables[variable_name] = {
                    'current': 0.0,
                    'previous': 0.0
                }
                continue
                
            # Use database calculation only for non-BYGG variables
            current_amount, previous_amount = self._calculate_noter_amounts(
                mapping, current_ub, previous_ub, current_ib, previous_ib
            )
            
            calculated_variables[variable_name] = {
                'current': current_amount, 
                'previous': previous_amount
            }
        
        # Second pass: Calculate all formula-based variables using stored values
        for mapping in sorted_mappings:
            variable_name = (mapping.get('variable_name') or '').strip()
            is_calculated = self._normalize_is_calculated(mapping.get('calculated', False))
            formula = mapping.get('formula', '')
            
            # Skip rows without variable names or K2 variables
            if not variable_name or variable_name in k2_variables:
                continue
            
            if is_calculated and formula and variable_name not in calculated_variables:
                current_amount, previous_amount = self._evaluate_noter_formula(
                    formula, calculated_variables
                )
                
                calculated_variables[variable_name] = {
                    'current': current_amount,
                    'previous': previous_amount
                }
        
        # Build final results (return all rows, let frontend handle filtering like RR/BR do)
        for mapping in sorted_mappings:
            try:
                # Get visibility properties but don't filter here - frontend handles it
                always_show = self._normalize_always_show(mapping.get('always_show', False))
                toggle_show = self._normalize_always_show(mapping.get('toggle_show', False))
                block = mapping.get('block', '')
                

                
                # Calculate amounts for both years
                current_amount = 0.0
                previous_amount = 0.0
                
                variable_name = mapping.get('variable_name') or ''
                
                if self._normalize_is_calculated(mapping.get('calculated', False)):
                    # Use pre-calculated values from first pass if available
                    if variable_name and variable_name in calculated_variables:
                        current_amount = calculated_variables[variable_name]['current']
                        previous_amount = calculated_variables[variable_name]['previous']
                else:
                    # Use pre-calculated account values
                    if variable_name in calculated_variables:
                        values = calculated_variables[variable_name]
                        current_amount = values['current']
                        previous_amount = values['previous']
                
                # Apply +/- sign override from database mapping (for K2 parser values and others)
                sign_override = mapping.get('plus_minus') or mapping.get('+/-') or mapping.get('sign')
                if sign_override:
                    s = str(sign_override).strip()
                    if s == '+':
                        current_amount = abs(current_amount)
                        previous_amount = abs(previous_amount)
                    elif s == '-':
                        current_amount = -abs(current_amount)
                        previous_amount = -abs(previous_amount)
                
                # Return all rows - frontend will handle filtering based on always_show and toggle_show
                # This matches how RR/BR work
                result = {
                    'row_id': mapping.get('row_id'),
                    'row_title': mapping.get('row_title', ''),
                    'current_amount': current_amount,
                    'previous_amount': previous_amount,
                    'variable_name': mapping.get('variable_name', ''),
                    'show_tag': mapping.get('show_tag', False),
                    'accounts_included': mapping.get('accounts_included', ''),
                    'account_details': self._get_account_details(mapping.get('accounts_included', ''), current_ub) if mapping.get('show_tag', False) else None,
                    'block': mapping.get('block', ''),
                    'style': mapping.get('style', 'NORMAL'),
                    'always_show': always_show,
                    'toggle_show': toggle_show
                }
                results.append(result)
                    
            except Exception as e:
                print(f"Error processing Noter mapping {mapping.get('variable_name', 'unknown')}: {e}")
                continue
        
        return results
