"""
Database-driven parser for SE files
Replaces hardcoded BR_STRUCTURE and RR_STRUCTURE with database queries
"""

import os
import re
import unicodedata
import math
from typing import Dict, List, Any, Optional, Union
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
USE_17XX_RECLASS = os.getenv("USE_17XX_RECLASS", "1") == "1"  # default ON
USE_296X_RECLASS = os.getenv("USE_296X_RECLASS", "1") == "1"  # default ON

class DatabaseParser:
    """Database-driven parser for financial data"""
    
    def __init__(self):
        self.rr_mappings = None
        self.br_mappings = None
        self.ink2_mappings = None
        self.noter_mappings = None
        self.global_variables = None
        self.accounts_lookup = None
        self.sie_account_descriptions = {}  # Cache for SIE file account descriptions
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
            
            # Apply rr_not migration if needed
            self._apply_rr_not_migration()
            
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
                if had_percent or name.lower().startswith('skattesats') or name.lower() == 'statslaneranta':
                    # Convert percent like 2.62 to 0.0262
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
    
    def _apply_rr_not_migration(self):
        """Apply the rr_not column migration if it hasn't been applied yet"""
        try:
            # Check if NOT2 block already has rr_not set
            not2_mapping = None
            for mapping in self.noter_mappings or []:
                if mapping.get('block') == 'NOT2':
                    not2_mapping = mapping
                    break
            
            if not2_mapping and not not2_mapping.get('rr_not'):
                # Update the NOT2 block with rr_not = 252 (Personalkostnader)
                response = supabase.table('variable_mapping_noter').update({
                    'rr_not': 252
                }).eq('block', 'NOT2').execute()
                
                print(f"DEBUG: ✅ Updated NOT2 block with rr_not=252")
                
                # Reload noter mappings to get the updated data
                noter_response = supabase.table('variable_mapping_noter').select('*').execute()
                self.noter_mappings = noter_response.data
                
            elif not2_mapping and not2_mapping.get('rr_not'):
                pass
            else:
                pass
                
        except Exception as e:
            pass

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
                        total -= accounts[account_spec]
        
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
        
        # Apply 168x, 17xx (FKUI) and 296x reclass before storing calculated values
        if sie_text:
            try:
                if USE_168X_RECLASS:
                    self._reclassify_168x_short_term_group_receivables(
                        sie_text=sie_text,
                        br_rows=results,
                        current_accounts=current_accounts
                    )
                if USE_17XX_RECLASS:
                    self._reclassify_17xx_prepaid_and_accrued_group_receivables(
                        sie_text=sie_text,
                        br_rows=results,
                        current_accounts=current_accounts
                    )
                if USE_296X_RECLASS:
                    self._reclassify_296x_short_term_group_liabilities(
                        sie_text=sie_text,
                        br_rows=results,
                        current_accounts=current_accounts
                    )
            except Exception as e:
                print(f"BR reclass skipped due to error: {e}")
        
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
                pass
            return br_rows

        target_book = float(koncern_note.get('red_varde_koncern') or 0.0)
        if abs(target_book) < 0.5:
            if verbose:
                pass
            return br_rows

        # Rows we touch (verified against your BR CSV export)
        row_andelar = _find(var='AndelarKoncernForetag') or _find(rid=329)
        row_fordr_L = _find(var='FordringarKoncernForetagLang') or _find(rid=330)
        row_fordr_K = _find(var='FordringarKoncernForetagKort') or _find(rid=351)

        if not row_andelar:
            if verbose:
                pass
            return br_rows

        current_andelar = float(row_andelar.get('current_amount') or 0.0)
        delta = target_book - current_andelar
        if abs(delta) < 0.5:
            if verbose:
                pass
            return br_rows

        # 1) Force Andelar to NOTE
        row_andelar['current_amount'] = current_andelar + delta
        if verbose:
            pass

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
            pass
        return br_rows

    def parse_br_data_with_koncern(self,
                                   se_content: str,
                                   current_accounts: Dict[str, float],
                                   previous_accounts: Dict[str, float] = None,
                                   rr_data: List[Dict[str, Any]] = None,
                                   two_files_flag: bool = False,
                                   previous_year_se_content: str = None) -> List[Dict[str, Any]]:
        """Regular BR parsing + KONCERN-note reconciliation for Andelar/fordringar."""
        # 1) Normal BR (with 168x reclass)
        br_rows = self.parse_br_data(current_accounts, previous_accounts, rr_data=rr_data, sie_text=se_content)

        # 2) Parse KONCERN note and reconcile
        try:
            from .koncern_k2_parser import parse_koncern_k2_from_sie_text
            koncern_note = parse_koncern_k2_from_sie_text(
                se_content, 
                debug=False, 
                two_files_flag=two_files_flag, 
                previous_year_sie_text=previous_year_se_content
            )
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

        def _find_by_label(rows: List[Dict[str, Any]], text: str):
            n = _norm(text)
            for r in rows:
                lbl = _norm(r.get("label") or r.get("row_title") or "")
                if lbl == n:
                    return r
            for r in rows:
                lbl = _norm(r.get("label") or r.get("row_title") or "")
                if n in lbl:
                    return r
            return None

        row_351 = _find_by_id(br_rows, 351) or _find_by_label(br_rows, "Kortfristiga fordringar hos koncernföretag")
        row_352 = _find_by_id(br_rows, 352) or _find_by_label(br_rows, "Kortfristiga fordringar hos intresseföretag och gemensamt styrda företag")
        row_353 = _find_by_id(br_rows, 353) or _find_by_label(br_rows, "Kortfristiga fordringar hos övriga företag som det finns ett ägarintresse i")
        row_354 = _find_by_id(br_rows, 354) or _find_by_label(br_rows, "Övriga kortfristiga fordringar")

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
    
    # ----------------- 17xx → 351/352/353 BR RECLASS (uses SIE text) -----------------
    def _reclassify_17xx_prepaid_and_accrued_group_receivables(self, sie_text: str, br_rows: List[Dict[str, Any]], current_accounts: Dict[str, float]) -> None:
        """
        Reclassify 1700–1799 (Förutbetalda kostnader och upplupna intäkter, etc.) into:
          351 Kortfristiga fordringar hos koncernföretag
          352 Kortfristiga fordringar hos intresseföretag och gemensamt styrda företag
          353 Kortfristiga fordringar hos övriga företag som det finns ett ägarintresse i

        Same philosophy as 168x:
          • Learn company names/tokens from 13xx kontonamn buckets.
          • Per-account deterministic allocation (whole UB per account).
          • Asset side → use UB as-is (no sign flip).
          • Subtract the reclassed sum from FKUI ("Förutbetalda kostnader och upplupna intäkter");
            if not found, fall back to "Övriga kortfristiga fordringar" (354).
        """
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
                # relationship/financial (we want company-ish tokens only)
                "andel","andelar","aktie","aktier","ack","nedskrivn","nedskrivningar",
                "villkorade","ovillkorade","aktieagartillskott","aktieägartillskott",
                "koncernforetag","koncernföretag","intresseforetag","intresseföretag",
                "dotterforetag","dotterföretag","gemensamt","styrda","ovriga","övriga",
                "agarintresse","ägarintresse","foretag","företag","hos","det","finns","ett",
                "kortfristiga","langfristiga","långfristiga","fordringar","fordran",
                "förutbetalda","forutbetalda","kostnader","upplupna","intäkter","intakter",
                # very generic legal forms
                "ab","kb","hb","oy","as","gmbh","bv","ltd","group","holding"
            }
            return {w for w in words if w not in stop}

        def _company_phrases(name: str) -> set[str]:
            n = _norm(name)
            part = n.split(",", 1)[1].strip() if "," in n else n
            part = re.sub(r"\b(andel(ar)?|aktier?|aktieagartillskott|aktieägartillskott|ack(umulerade)?|nedskrivningar?|kortfristiga|fordringar?|förutbetalda|forutbetalda|kostnader|upplupna|intäkter|intakter)\b", " ", part)
            part = re.sub(r"\b(ab|kb|hb|oy|as|gmbh|bv|ltd)\b\.?", " ", part)
            words = re.findall(r"[a-zåäö]{2,}", part)
            if not words:
                return set()
            phrase = " ".join(words)
            shards = set()
            for i in range(len(words)-1):
                shards.add(f"{words[i]} {words[i+1]}")
            return {phrase} | shards

        def _classify_by_patterns(text_norm: str) -> str | None:
            # KONCERN cues (include common shorthands used in kontonamn)
            if re.search(r"\b(koncern|dotter|moder)\b", text_norm):
                return "koncern"
            if re.search(r"\b(intern(a)?|intragroup|intra|koncernintern(a)?|koncernmellan\w*|group|holding)\b", text_norm):
                return "koncern"

            # INTRESSE cues
            if re.search(r"\b(intresseföretag|intresseforetag|intresseftg)\b", text_norm):
                return "intresse"
            if re.search(r"\bintr\w+\b", text_norm) and re.search(r"\b(företag|foretag|ftg)\b", text_norm):
                return "intresse"
            if re.search(r"\bgem\w+\b", text_norm) and re.search(r"\bstyrda\b", text_norm):
                return "intresse"

            # ÖVRIGA m. ägarintresse ⇒ must have all three components
            has_ovr = bool(re.search(r"\b(övr|ovr)(iga)?\b", text_norm))
            has_f   = bool(re.search(r"\b(företag|foretag|ftg)\b", text_norm))
            has_ai  = bool(re.search(r"\b(ägarintresse|agarintresse|ägarint|agarint|ägarintr|agarintr)\b", text_norm))
            if has_ovr and has_f and has_ai:
                return "ovriga"
            return None

        # quick exit: any 17xx UB?
        total_17xx = sum(float(current_accounts.get(str(a), 0.0)) for a in range(1700, 1800))
        if abs(total_17xx) < 0.5:
            return

        konto_re = re.compile(r'^#KONTO\s+(\d+)\s+"([^"]*)"', re.IGNORECASE)

        # learn company tokens/phrases from 13xx buckets
        koncern_keys, intresse_keys, ovriga_keys = set(), set(), set()
        koncern_phr,  intresse_phr,  ovriga_phr  = set(), set(), set()
        name_17xx: dict[int, str] = {}

        def _bucket_for_13xx(acct: int) -> str | None:
            if 1310 <= acct <= 1329: return "koncern"
            if (1330 <= acct <= 1335) or (1338 <= acct <= 1345) or acct == 1348: return "intresse"
            if (1336 <= acct <= 1337) or (1346 <= acct <= 1347): return "ovriga"
            return None

        for raw in sie_text.splitlines():
            m = konto_re.match(raw.strip())
            if not m:
                continue
            acct = int(m.group(1)); nm = m.group(2) or ""
            if 1700 <= acct <= 1799:
                name_17xx[acct] = nm
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
                ovriga_keys |= toks;   ovriga_phr  |= phr

        if not (koncern_keys or intresse_keys or ovriga_keys or koncern_phr or intresse_phr or ovriga_phr):
            return

        # per-account deterministic allocation (asset side: UB as-is)
        alloc = {"koncern": 0.0, "intresse": 0.0, "ovriga": 0.0}
        for a in range(1700, 1800):
            ub = float(current_accounts.get(str(a), 0.0))
            if abs(ub) < 0.5:
                continue
            nm  = name_17xx.get(a, "") or ""
            nmn = _norm(nm)

            # strict patterns first
            cat = _classify_by_patterns(nmn)
            if cat:
                alloc[cat] += ub
                continue

            # phrase (company name) matching — unambiguous only
            hits = set()
            if any(p and p in nmn for p in koncern_phr):   hits.add("koncern")
            if any(p and p in nmn for p in intresse_phr):  hits.add("intresse")
            if any(p and p in nmn for p in ovriga_phr):    hits.add("ovriga")
            if len(hits) == 1:
                alloc[next(iter(hits))] += ub
                continue
            if len(hits) > 1:
                # ambiguous → leave in source row
                continue

            # token overlap fallback — unambiguous only
            toks = _tokens(nm)
            s_k = len(toks & koncern_keys)
            s_i = len(toks & intresse_keys)
            s_o = len(toks & ovriga_keys)
            ranked = sorted([("koncern", s_k), ("intresse", s_i), ("ovriga", s_o)], key=lambda x: x[1], reverse=True)
            if ranked[0][1] > 0 and ranked[0][1] > ranked[1][1]:
                alloc[ranked[0][0]] += ub
            # else ambiguous/no-signal → keep in source row

        # --- helpers to find rows ---
        def _find_by_id(rows: List[Dict[str, Any]], rid: int):
            for r in rows:
                if str(r.get("id")) == str(rid):
                    return r
            return None

        def _find_by_label(rows: List[Dict[str, Any]], text: str):
            n = _norm(text)
            for r in rows:
                lbl = _norm(r.get("label") or r.get("row_title") or "")
                if lbl == n:
                    return r
            for r in rows:
                lbl = _norm(r.get("label") or r.get("row_title") or "")
                if n in lbl:
                    return r
            return None

        def _find_by_tokens(rows: List[Dict[str, Any]], must_have: set[str], any_of: list[set[str]] | None = None):
            for r in rows:
                lbl = _norm(r.get("label") or r.get("row_title") or "")
                words = set(lbl.split())
                if not must_have.issubset(words):
                    continue
                if any_of and not any(opt.issubset(words) for opt in any_of):
                    continue
                return r
            return None

        # destinations (351/352/353)
        row_351 = _find_by_id(br_rows, 351) or _find_by_label(br_rows, "Kortfristiga fordringar hos koncernföretag")
        row_352 = _find_by_id(br_rows, 352) or _find_by_label(br_rows, "Kortfristiga fordringar hos intresseföretag och gemensamt styrda företag")
        row_353 = _find_by_id(br_rows, 353) or _find_by_label(br_rows, "Kortfristiga fordringar hos övriga företag som det finns ett ägarintresse i")

        # source (FKUI). Try several caption shapes; fallback to 354 if not found.
        row_src = (
            _find_by_label(br_rows, "Förutbetalda kostnader och upplupna intäkter")
            or _find_by_label(br_rows, "Forutbetalda kostnader och upplupna intakter")
            or _find_by_tokens(br_rows, must_have={"förutbetalda","kostnader","upplupna","intäkter"})
            or _find_by_tokens(br_rows, must_have={"forutbetalda","kostnader","upplupna","intakter"})
            or _find_by_id(br_rows, 349)  # common id, if you have it
            or _find_by_label(br_rows, "Övriga kortfristiga fordringar")
            or _find_by_id(br_rows, 354)
        )

        # apply
        added = 0.0
        if row_351 and alloc["koncern"]:
            row_351["current_amount"] = float(row_351.get("current_amount") or 0.0) + alloc["koncern"]; added += alloc["koncern"]
        if row_352 and alloc["intresse"]:
            row_352["current_amount"] = float(row_352.get("current_amount") or 0.0) + alloc["intresse"]; added += alloc["intresse"]
        if row_353 and alloc["ovriga"]:
            row_353["current_amount"] = float(row_353.get("current_amount") or 0.0) + alloc["ovriga"];   added += alloc["ovriga"]

        # reduce source row by same total (not below zero)
        if row_src and added:
            cur = float(row_src.get("current_amount") or 0.0)
            row_src["current_amount"] = max(0.0, cur - added)

        # debug - targets verified

    # ----------------- 296x → 410/411/412 BR RECLASS (uses SIE text) -----------------
    def _reclassify_296x_short_term_group_liabilities(self, sie_text: str, br_rows: List[Dict[str, Any]], current_accounts: Dict[str, float]) -> None:
        """
        Reclassify accrued interest payables (2960–2969) from generic short-term
        liabilities to:
          410 Kortfristiga skulder till koncernföretag
          411 Kortfristiga skulder till intresseföretag och gemensamt styrda företag
          412 Kortfristiga skulder till övriga företag som det finns ett ägarintresse i

        Rules (same philosophy as 168x):
          • Learn company names/tokens from 13xx kontonamn:
               1310–1329 => koncern
               1330–1335, 1338–1345, 1348 => intresse
               1336–1337, 1346–1347 => övriga (ägarlänkade)
          • Strict text patterns on the 296x kontonamn:
               övr/ovr + (företag|foretag|ftg) + (ägarintresse-variant) => övriga
               "intresseföretag/intresseforetag/intresseftg" OR (intr* + företag/ftg) OR (gem* + styrda) => intresse
               koncern|dotter|moder => koncern
          • Contextual match on company phrases (e.g. "rh property", "flying parking", "guldkula", "dare").
          • Per-account deterministic: whole UB of each 296x goes to one bucket or stays put if ambiguous.
          • Convert 296x UB to BR sign (liability => add -UB).
          • Subtract the reclassed sum from source row (prefer "Upplupna kostnader och förutbetalda intäkter").
        """
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
                "andel","andelar","aktie","aktier","ack","nedskrivn","nedskrivningar",
                "villkorade","ovillkorade","aktieagartillskott","aktieägartillskott",
                "koncernforetag","koncernföretag","intresseforetag","intresseföretag",
                "dotterforetag","dotterföretag","gemensamt","styrda","ovriga","övriga",
                "agarintresse","ägarintresse","foretag","företag","hos","det","finns","ett",
                "kortfristiga","langfristiga","långfristiga","fordringar","fordran",
                # legal/generic suffixes
                "ab","kb","hb","oy","as","gmbh","bv","ltd","group","holding"
            }
            return {w for w in words if w not in stop}

        def _company_phrases(name: str) -> set[str]:
            n = _norm(name)
            part = n.split(",", 1)[1].strip() if "," in n else n
            part = re.sub(r"\b(andel(ar)?|aktier?|aktieagartillskott|aktieägartillskott|ack(umulerade)?|nedskrivningar?|kortfristiga|fordringar?)\b", " ", part)
            part = re.sub(r"\b(ab|kb|hb|oy|as|gmbh|bv|ltd)\b\.?", " ", part)
            words = re.findall(r"[a-zåäö]{2,}", part)
            if not words: 
                return set()
            phrase = " ".join(words)
            shards = set()
            for i in range(len(words)-1):
                shards.add(f"{words[i]} {words[i+1]}")
            return {phrase} | shards

        def _classify_by_patterns(text_norm: str) -> str | None:
            # KONCERN cues
            if re.search(r"\b(koncern|dotter|moder)\b", text_norm):
                return "koncern"
            # Treat common shorthand as intra-group (koncern)
            if re.search(r"\b(intern(a)?|intragroup|intra|koncernintern(a)?|koncernmellan\w*|group|holding)\b", text_norm):
                return "koncern"

            # INTRESSE cues
            if re.search(r"\b(intresseföretag|intresseforetag|intresseftg)\b", text_norm):
                return "intresse"
            if re.search(r"\bintr\w+\b", text_norm) and re.search(r"\b(företag|foretag|ftg)\b", text_norm):
                return "intresse"
            if re.search(r"\bgem\w+\b", text_norm) and re.search(r"\bstyrda\b", text_norm):
                return "intresse"

            # ÖVRIGA m. ägarintresse ⇒ must have all three components
            has_ovr = bool(re.search(r"\b(övr|ovr)(iga)?\b", text_norm))
            has_f   = bool(re.search(r"\b(företag|foretag|ftg)\b", text_norm))
            has_ai  = bool(re.search(r"\b(ägarintresse|agarintresse|ägarint|agarint|ägarintr|agarintr)\b", text_norm))
            if has_ovr and has_f and has_ai:
                return "ovriga"

            return None

        # any 296x UB at all?
        total_296_raw = sum(float(current_accounts.get(str(a), 0.0)) for a in range(2960, 2970))
        # Convert to BR sign (liabilities shown positive in BR)
        total_296_br = -total_296_raw
        if abs(total_296_br) < 0.5:
            return

        # learn company names from 13xx
        konto_re = re.compile(r'^#KONTO\s+(\d+)\s+"([^"]*)"', re.IGNORECASE)
        name_296x: dict[int, str] = {}

        def _bucket_for_13xx(acct: int) -> str | None:
            if 1310 <= acct <= 1329: return "koncern"
            if (1330 <= acct <= 1335) or (1338 <= acct <= 1345) or acct == 1348: return "intresse"
            if (1336 <= acct <= 1337) or (1346 <= acct <= 1347): return "ovriga"
            return None

        koncern_keys, intresse_keys, ovriga_keys = set(), set(), set()
        koncern_phr,  intresse_phr,  ovriga_phr  = set(), set(), set()

        for raw in sie_text.splitlines():
            m = konto_re.match(raw.strip())
            if not m:
                continue
            acct = int(m.group(1)); nm = m.group(2) or ""
            if 2960 <= acct <= 2969:
                name_296x[acct] = nm
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

        # per-account deterministic allocation
        alloc = {"koncern": 0.0, "intresse": 0.0, "ovriga": 0.0}
        for a in range(2960, 2970):
            ub_raw = float(current_accounts.get(str(a), 0.0))
            if abs(ub_raw) < 0.5:
                continue
            # convert single-account UB to BR sign (liability => positive)
            ub_br = -ub_raw
            nm = name_296x.get(a, "") or ""
            nmn = _norm(nm)

            cat = _classify_by_patterns(nmn)
            if cat:
                alloc[cat] += ub_br
                continue

            # phrase matching first (unambiguous)
            hits = set()
            if any(p and p in nmn for p in koncern_phr):   hits.add("koncern")
            if any(p and p in nmn for p in intresse_phr):  hits.add("intresse")
            if any(p and p in nmn for p in ovriga_phr):    hits.add("ovriga")
            if len(hits) == 1:
                alloc[next(iter(hits))] += ub_br
                continue
            if len(hits) > 1:
                # ambiguous → leave in source row
                continue

            # token overlap fallback (unambiguous only)
            toks = _tokens(nm)
            s_k = len(toks & koncern_keys)
            s_i = len(toks & intresse_keys)
            s_o = len(toks & ovriga_keys)
            rank = sorted([("koncern", s_k), ("intresse", s_i), ("ovriga", s_o)], key=lambda x: x[1], reverse=True)
            if rank[0][1] > 0 and rank[0][1] > rank[1][1]:
                alloc[rank[0][0]] += ub_br
            # else: ambiguous/no signal → no reclass for this account

        # --- mutate BR rows ---
        def _find_by_id(rows: List[Dict[str, Any]], rid: int):
            for r in rows:
                if str(r.get("id")) == str(rid):
                    return r
            return None

        def _find_by_label(rows: List[Dict[str, Any]], text: str):
            n = _norm(text)
            for r in rows:
                lbl = _norm(r.get("label") or r.get("row_title") or "")
                if lbl == n:
                    return r
            for r in rows:
                lbl = _norm(r.get("label") or r.get("row_title") or "")
                if n in lbl:
                    return r
            return None

        def _find_by_tokens(rows: List[Dict[str, Any]], must_have: set[str], any_of: list[set[str]] | None = None):
            for r in rows:
                lbl = _norm(r.get("label") or r.get("row_title") or "")
                words = set(lbl.split())
                if not must_have.issubset(words):
                    continue
                if any_of and not any(opt.issubset(words) for opt in any_of):
                    continue
                return r
            return None

        row_410 = (
            _find_by_id(br_rows, 410)
            or _find_by_label(br_rows, "Kortfristiga skulder till koncernföretag")
            or _find_by_tokens(br_rows, must_have={"skulder", "koncernforetag"})
        )

        row_411 = (
            _find_by_id(br_rows, 411)
            or _find_by_label(br_rows, "Kortfristiga skulder till intresseföretag och gemensamt styrda företag")
            or _find_by_tokens(
                br_rows,
                must_have={"skulder"},
                any_of=[{"intresseforetag"}, {"gemensamt","styrda"}]
            )
        )

        row_412 = (
            _find_by_id(br_rows, 412)
            or _find_by_label(br_rows, "Kortfristiga skulder till övriga företag som det finns ett ägarintresse i")
            or _find_by_tokens(
                br_rows,
                must_have={"skulder"},
                any_of=[{"ovriga","foretag","agarintresse"}, {"foretag","agarintresse"}]
            )
        )

        # source row (where 296x sits today)
        row_src = (
            _find_by_label(br_rows, "Upplupna kostnader och förutbetalda intäkter")
            or _find_by_label(br_rows, "Upplupna kostnader")
            or _find_by_tokens(br_rows, must_have={"upplupna"}, any_of=[{"kostnader"}, {"rantekostnader"}, {"utgiftsrantor"}, {"ranta"}])
            or _find_by_label(br_rows, "Övriga kortfristiga skulder")
            or _find_by_id(br_rows, 418)
            or _find_by_id(br_rows, 415)
        )

        # debug - targets verified

        added = 0.0
        if row_410 and alloc["koncern"]:
            row_410["current_amount"] = float(row_410.get("current_amount") or 0.0) + alloc["koncern"]; added += alloc["koncern"]
        if row_411 and alloc["intresse"]:
            row_411["current_amount"] = float(row_411.get("current_amount") or 0.0) + alloc["intresse"]; added += alloc["intresse"]
        if row_412 and alloc["ovriga"]:
            row_412["current_amount"] = float(row_412.get("current_amount") or 0.0) + alloc["ovriga"];   added += alloc["ovriga"]

        # reduce source row by same total (not below zero)
        if row_src and added:
            cur = float(row_src.get("current_amount") or 0.0)
            row_src["current_amount"] = max(0.0, cur - added)
    
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
        from datetime import datetime
        
        company_info = {}
        lines = se_content.split('\n')
        
        # Add report creation date and time (Framställningsdatum)
        now = datetime.now()
        company_info['DatFramst'] = now.strftime('%Y%m%d')  # YYYYMMDD format
        company_info['TidFramst'] = now.strftime('%H%M%S')  # HHMMSS format
        
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
                # Fiscal year: #RAR 0 20240101 20241231 or #RAR -1 20230101 20231231
                parts = line.split()
                if len(parts) >= 4:
                    if parts[1] == '0':  # Current year
                        company_info['fiscal_year'] = int(parts[2][:4])  # Extract year from date
                        company_info['start_date'] = parts[2]
                        company_info['end_date'] = parts[3]
                    elif parts[1] == '-1':  # Previous year
                        company_info['previous_start_date'] = parts[2]
                        company_info['previous_end_date'] = parts[3]
                        
            elif line.startswith('#PROGRAM'):
                # System info: #PROGRAM iOrdning 7.6.39
                # Extract everything after #PROGRAM
                system_info_text = line[len('#PROGRAM'):].strip()
                if system_info_text:
                    company_info['system_info'] = system_info_text
        
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
    
    def add_note_numbers_to_br_data(self, br_data: List[Dict[str, Any]], dynamic_note_numbers: Dict[str, int] = None) -> List[Dict[str, Any]]:
        """
        Add note numbers to BR data based on br_not mappings from noter table.
        Uses dynamic note numbering from frontend - only notes that are actually visible
        and numbered in the Noter section get their numbers inserted into BR.
        
        Args:
            br_data: List of BR data items
            dynamic_note_numbers: Dict mapping block names to their actual note numbers from frontend
                                 e.g., {'BYGG': 3, 'KONCERN': 5} (only for visible notes)
        
        Returns:
            BR data with note numbers added to appropriate rows
        """
        if not self.noter_mappings:
            return br_data
        
        # Use dynamic note numbers from frontend, or empty dict if not provided
        block_note_numbers = dynamic_note_numbers or {}
        
        # Create mapping from br_not row_id to note number
        br_note_mapping = {}
        for noter_mapping in self.noter_mappings:
            br_not = noter_mapping.get('br_not')
            block = noter_mapping.get('block')
            
            # Only process blocks that have br_not values and are in our fixed numbering
            if br_not and block and block in block_note_numbers:
                br_note_mapping[br_not] = block_note_numbers[block]
        
        # Add note numbers to BR data
        updated_br_data = []
        for br_item in br_data:
            br_item_copy = br_item.copy()
            br_row_id = br_item.get('id')
            
            # If this BR row should have a note number, add it
            if br_row_id in br_note_mapping:
                note_number = br_note_mapping[br_row_id]
                br_item_copy['note_number'] = note_number
            
            updated_br_data.append(br_item_copy)
        
        return updated_br_data
    
    def add_note_numbers_to_financial_data(self, br_data: List[Dict[str, Any]], rr_data: List[Dict[str, Any]], dynamic_note_numbers: Dict[str, int] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Add note numbers to both BR and RR data based on mappings from noter table.
        Uses dynamic note numbering from frontend - only notes that are actually visible
        and numbered in the Noter section get their numbers inserted.
        
        Args:
            br_data: List of BR data items
            rr_data: List of RR data items  
            dynamic_note_numbers: Dict mapping block names to their actual note numbers from frontend
                                 e.g., {'BYGG': 3, 'KONCERN': 5, 'NOT2': 2} (only for visible notes)
        
        Returns:
            Dict with updated BR and RR data: {'br_data': [...], 'rr_data': [...]}
        """
        if not self.noter_mappings:
            return {'br_data': br_data, 'rr_data': rr_data}
        
        # Use dynamic note numbers from frontend, or empty dict if not provided
        block_note_numbers = dynamic_note_numbers or {}
        
        # Create mapping from br_not row_id to note number (for BR)
        br_note_mapping = {}
        # Create mapping from rr_not row_id to note number (for RR) - mirror BR approach exactly
        rr_note_mapping = {}
        
        for noter_mapping in self.noter_mappings:
            br_not = noter_mapping.get('br_not')
            rr_not = noter_mapping.get('rr_not')
            block = noter_mapping.get('block')
            
            # Handle BR mappings (blocks with br_not values) - existing approach that works
            if br_not and block and block in block_note_numbers:
                br_note_mapping[br_not] = block_note_numbers[block]
            
            # Handle RR mappings (blocks with rr_not values) - mirror BR approach exactly
            if rr_not and block and block in block_note_numbers:
                rr_note_mapping[str(rr_not)] = block_note_numbers[block]  # Convert to string to match frontend id format
        
        # Add note numbers to BR data
        updated_br_data = []
        for br_item in br_data:
            br_item_copy = br_item.copy()
            br_row_id = br_item.get('id')
            
            # If this BR row should have a note number, add it
            if br_row_id in br_note_mapping:
                note_number = br_note_mapping[br_row_id]
                br_item_copy['note_number'] = note_number
            
            updated_br_data.append(br_item_copy)
        
        # Add note numbers to RR data
        updated_rr_data = []
        for rr_item in rr_data:
            rr_item_copy = rr_item.copy()
            rr_row_id = rr_item.get('id')
            
            # Check if RR item matches pattern
            if rr_item.get('label') and 'Personal' in rr_item.get('label', ''):
                pass
            
            # If this RR row should have a note number, add it
            if rr_row_id in rr_note_mapping:
                note_number = rr_note_mapping[rr_row_id]
                rr_item_copy['note_number'] = note_number
            
            updated_rr_data.append(rr_item_copy)
        
        return {
            'br_data': updated_br_data,
            'rr_data': updated_rr_data
        }
    
    def parse_ink2_data(self, current_accounts: Dict[str, float], fiscal_year: int = None, rr_data: List[Dict[str, Any]] = None, br_data: List[Dict[str, Any]] = None, sie_text: str = None, previous_accounts: Dict[str, float] = None) -> List[Dict[str, Any]]:
        """
        Parse INK2 tax calculation data using database mappings.
        Returns simplified structure: row_title and amount only.
        """
        # Parse SIE account descriptions if provided
        if sie_text:
            self._parse_sie_account_descriptions(sie_text)
        
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
                amount = self.calculate_ink2_variable_value(mapping, current_accounts, fiscal_year, rr_data, ink_values, br_data, previous_accounts)
                
                
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
                        'account_details': self._get_ink2_account_details(mapping, current_accounts, previous_accounts) if mapping.get('show_tag', False) else None,
                        'show_amount': self._normalize_show_amount(mapping.get('show_amount', True)),
                        'is_calculated': self._normalize_is_calculated(mapping.get('is_calculated', True)),
                        'always_show': self._normalize_always_show(mapping.get('always_show', False)),
                        'toggle_show': mapping.get('toggle_show', False),
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
                                       manual_amounts: Dict[str, float] = None, sie_text: str = None, previous_accounts: Dict[str, float] = None) -> List[Dict[str, Any]]:
        """
        Parse INK2 tax calculation data with manual amount overrides for dynamic recalculation.
        """
        # Parse SIE account descriptions if provided
        if sie_text:
            self._parse_sie_account_descriptions(sie_text)
        
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
        
        # Inject INK4.6b (outnyttjat underskott) into ink_values if provided
        if 'INK4.6b' in manual_amounts:
            ink_values['INK4.6b'] = manual_amounts['INK4.6b']

        # Inject INK4.6d (återföring periodiseringsfonder) into ink_values if provided
        if 'INK4.6d' in manual_amounts:
            ink_values['INK4.6d'] = manual_amounts['INK4.6d']

        
        # Inject underskott adjustment for INK4.16 if provided
        if 'ink4_16_underskott_adjustment' in manual_amounts:
            ink_values['ink4_16_underskott_adjustment'] = manual_amounts['ink4_16_underskott_adjustment']
        
        # Inject calculated values from editable ranges if provided (sticky values)
        calculated_editable_vars = ['INK4.6a', 'INK4.6b', 'INK4.6d']  # Add others as needed
        for var_name in calculated_editable_vars:
            if var_name in manual_amounts:
                ink_values[var_name] = manual_amounts[var_name]
               
        for mapping in sorted_mappings:
            try:
                variable_name = mapping.get('variable_name', '')
                
                # Force recalculation of dependent summary values even if not manually edited
                force_recalculate = variable_name in ['INK_skattemassigt_resultat', 'INK_beraknad_skatt']
                
                # Check if this value has been manually overridden (but only for non-calculated fields)
                if variable_name in manual_amounts and not force_recalculate:
                    amount = manual_amounts[variable_name]
                    ink_values[variable_name] = amount  # Store for dependencies
                else:
                    # Calculate normally (or force recalculate for dependent values)
                    amount = self.calculate_ink2_variable_value(mapping, current_accounts, fiscal_year, rr_data, ink_values, br_data, previous_accounts)
                    # Round all INK2 values to 0 decimals (skattemässigt resultat already has special rounding)
                    if variable_name != 'INK_skattemassigt_resultat':
                        amount = round(amount, 0)
                    # IMPORTANT: Store calculated values for later formulas
                    ink_values[variable_name] = amount
                
                
                # Keep only essential debug for important tax calculations
                
                # Special handling: hide INK4_header (duplicate "Skatteberäkning")
                if variable_name == 'INK4_header':
                    continue  # Skip this row entirely
                
                # Return all rows - let frontend handle visibility logic
                # Get account details for SHOW button if needed
                account_details = []
                if mapping.get('show_tag'):
                    account_details = self._get_ink2_account_details(mapping, current_accounts, previous_accounts)
                
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
                        'toggle_show': mapping.get('toggle_show', False),
                        'explainer': mapping.get('explainer', ''),
                        'block': mapping.get('block', ''),
                        'header': mapping.get('header', False),
                        'account_details': account_details
                    })
                
            except Exception as e:
                print(f"Error processing INK2 mapping {mapping.get('variable_name', 'unknown')}: {e}")
                continue
        
        # Add calculated values to ink_values to make them sticky
        for result in results:
            if result['variable_name'] in ['INK4.6a', 'INK4.6b', 'INK4.6d'] and result['amount'] != 0:
                ink_values[result['variable_name']] = result['amount']
                print(f"Added {result['variable_name']} to ink_values: {result['amount']}")
        
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
    
    def _normalize_always_show(self, value: Any) -> Union[bool, None]:
        """Normalize always_show to boolean or None values for proper toggle logic."""
        if value is None:
            return None  # Keep None as None for "show if amount != 0 OR toggle on" logic
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().upper()
            if normalized == 'TRUE':
                return True
            elif normalized == 'FALSE':
                return False
            else:
                return None  # Empty string or other values = None (show if amount != 0 OR toggle on)
        return None  # Default to None for any other type
    
    def calculate_ink2_variable_value(self, mapping: Dict[str, Any], accounts: Dict[str, float], fiscal_year: int = None, rr_data: List[Dict[str, Any]] = None, ink_values: Optional[Dict[str, float]] = None, br_data: Optional[List[Dict[str, Any]]] = None, previous_accounts: Dict[str, float] = None) -> float:
        """
        Calculate the value for an INK2 variable using accounts and formulas.
        # Back to latest commit with all fixes
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
            # INK4.3a: Skatt på årets resultat
            # Returns booked tax from RR (typically negative, so we negate it)
            # This will be OVERRIDDEN by injection with INK_beraknad_skatt
            return -float(rr('SkattAretsResultat'))
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
        
        if variable_name == 'INK4.6b':
            # Outnyttjat underskott - this is typically a manual field set from chat
            # For now, return 0 as it's usually set manually
            return 0.0
        
        if variable_name == 'INK4.6d':
            # Återföring av periodiseringsfonder - tax on reversed funds
            # 4% for 2019-2020 funds, 6% for 2018 and earlier
            total_tax = 0.0
            
            # If no previous_accounts available (e.g., during recalculation), 
            # check if we have a manual amount to preserve stickiness
            if not previous_accounts:
                # During recalculation, preserve existing calculated value if available
                if ink_values and 'INK4.6d' in ink_values:
                    return float(ink_values['INK4.6d'])
                return 0.0
            
            # Check each periodiseringsfond account for återföring
            for account_id in range(2110, 2150):
                account_str = str(account_id)
                current_balance = float(accounts.get(account_str, 0.0))
                previous_balance = float(previous_accounts.get(account_str, 0.0))
                
                # Calculate återföring: if balance becomes less negative, that's återföring
                # Example: -500,000 → -300,000 = 200,000 återförd
                if previous_balance < 0 and current_balance > previous_balance:
                    aterforing_amount = current_balance - previous_balance  # Positive amount
                    
                    # Extract avsättning year from account description (same logic as account details)
                    account_text = self._get_account_text(account_id)
                    avsattning_year = None
                    
                    # Try to extract year from account description
                    import re
                    year_match = re.search(r'(\d{4})', account_text)
                    if year_match:
                        avsattning_year = int(year_match.group(1))
                    else:
                        # Fallback mapping based on account number
                        year_mapping = {2121: 2023, 2122: 2022, 2123: 2021, 2124: 2020, 2125: 2019}
                        avsattning_year = year_mapping.get(account_id, 2018)
                    
                    # Determine tax rate based on avsättning year and återföring year (2024)
                    if avsattning_year >= 2021:  # 2021 and later (0% tax)
                        tax_rate = 0.0
                    elif 2019 <= avsattning_year <= 2020:  # 2019-2020 (4% tax)
                        tax_rate = 0.04
                    else:  # 2018 and earlier (6% tax)
                        tax_rate = 0.06
                    
                    # Only add tax if rate > 0
                    if tax_rate > 0:
                        account_tax = aterforing_amount * tax_rate
                        total_tax += account_tax
            
            return total_tax
        
        if variable_name == 'aterforing_periodiseringsfond_current_year':
            # Återföring av periodiseringsfonder - AMOUNT (not tax) reversed in current year
            # This sums ALL återföring amounts across multiple historical years/accounts
            total_aterforing = 0.0
            
            # If no previous_accounts available (e.g., during recalculation), 
            # check if we have a manual amount to preserve stickiness
            if not previous_accounts:
                # During recalculation, preserve existing calculated value if available
                if ink_values and 'aterforing_periodiseringsfond_current_year' in ink_values:
                    return float(ink_values['aterforing_periodiseringsfond_current_year'])
                return 0.0
            
            # Check each periodiseringsfond account for återföring
            for account_id in range(2110, 2150):
                account_str = str(account_id)
                current_balance = float(accounts.get(account_str, 0.0))
                previous_balance = float(previous_accounts.get(account_str, 0.0))
                
                # Calculate återföring: if balance becomes less negative, that's återföring
                # Example: -500,000 → -300,000 = 200,000 återförd
                if previous_balance < 0 and current_balance > previous_balance:
                    aterforing_amount = current_balance - previous_balance  # Positive amount
                    total_aterforing += aterforing_amount
            
            return total_aterforing
        
        if variable_name == 'avsattning_periodiseringsfond':
            # Avsättning till periodiseringsfond - new allocations to periodization funds
            # This detects when balance becomes MORE negative (opposite of återföring)
            total_avsattning = 0.0
            
            # If no previous_accounts available (e.g., during recalculation), 
            # check if we have a manual amount to preserve stickiness
            if not previous_accounts:
                # During recalculation, preserve existing calculated value if available
                if ink_values and 'avsattning_periodiseringsfond' in ink_values:
                    return float(ink_values['avsattning_periodiseringsfond'])
                return 0.0
            
            # Check each periodiseringsfond account for avsättning
            for account_id in range(2110, 2150):
                account_str = str(account_id)
                current_balance = float(accounts.get(account_str, 0.0))
                previous_balance = float(previous_accounts.get(account_str, 0.0))
                
                # Calculate avsättning: if balance becomes more negative, that's avsättning
                # Example: -300,000 → -500,000 = 200,000 avsatt
                if current_balance < previous_balance:  # More negative = allocation
                    avsattning_amount = previous_balance - current_balance  # Positive amount
                    total_avsattning += avsattning_amount
            
            return total_avsattning
        
        if variable_name == 'avsattning_periodiseringsfond_current_year':
            # Avsättning till periodiseringsfond för innevarande räkenskapsår
            # Detects allocation to CURRENT fiscal year's periodization fund only
            
            # If no previous_accounts or fiscal_year available, return 0
            if not previous_accounts or not fiscal_year:
                if ink_values and 'avsattning_periodiseringsfond_current_year' in ink_values:
                    return float(ink_values['avsattning_periodiseringsfond_current_year'])
                return 0.0
            
            # Map fiscal year to account number
            # Typically: 2121=2023, 2122=2022, 2123=2021, 2124=2020, 2125=2019
            # For current year, we need to determine the correct account
            # Assuming fiscal_year is 2024, we check accounts for a match
            
            # Check all periodization fund accounts for the current year
            for account_id in range(2110, 2150):
                account_str = str(account_id)
                account_text = self._get_account_text(account_id)
                
                # Check if this account corresponds to the current fiscal year
                import re
                year_match = re.search(r'(\d{4})', account_text)
                if year_match:
                    account_year = int(year_match.group(1))
                    if account_year == fiscal_year:
                        # Found the current year's account
                        current_balance = float(accounts.get(account_str, 0.0))
                        previous_balance = float(previous_accounts.get(account_str, 0.0))
                        
                        # Calculate avsättning: if balance becomes more negative, that's avsättning
                        # Example: 0 → -500,000 = 500,000 avsatt
                        # Or: -300,000 → -800,000 = 500,000 avsatt
                        if current_balance < previous_balance:  # More negative = allocation
                            avsattning_amount = previous_balance - current_balance  # Positive amount
                            return avsattning_amount
            
            return 0.0
        
        # New pension tax variables
        if variable_name == 'pension_premier':
            # Amount in account 7410
            return abs(float(accounts.get('7410', 0.0)))
        if variable_name == 'sarskild_loneskatt_pension':
            # Amount in accounts 7530, 7531, 7532, 7533 (särskild löneskatt can be booked in any of these)
            return (
                abs(float(accounts.get('7530', 0.0))) +
                abs(float(accounts.get('7531', 0.0))) +
                abs(float(accounts.get('7532', 0.0))) +
                abs(float(accounts.get('7533', 0.0)))
            )
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
            return float(rounded_tax)

        # If there's a calculation formula, use it
        if mapping.get('calculation_formula'):
            return self.calculate_ink2_formula_value(mapping, accounts, fiscal_year, rr_data, ink_values)
        
        # Otherwise, sum the included accounts (use absolute values for positive-only variables)
        account_sum = self.sum_included_accounts(mapping.get('accounts_included', ''), accounts)
        # Variables that should always be positive (account-based calculations)
        positive_only_variables = [
            'INK4.3c', 'INK4.4a', 'INK4.5b', 'INK4.5c', 
            'INK4.6a', 'INK4.6c', 'INK4.20', 'INK4.21'
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

    def _get_ink2_account_details(self, mapping: Dict[str, Any], accounts: Dict[str, float], previous_accounts: Dict[str, float] = None) -> List[Dict[str, Any]]:
        """
        Get account details for INK2 variables with special handling for INK4.6a.
        INK4.6a should show all accounts in range 2110-2149 with PREVIOUS YEAR balances.
        """
        variable_name = mapping.get('variable_name', '')
        
        if variable_name == 'INK4.6a':
            # Special case: Show all periodiseringsfond accounts (2110-2149) with PREVIOUS YEAR balances
            details = []
            accounts_to_check = previous_accounts if previous_accounts else accounts
            
            for account_id, balance in accounts_to_check.items():
                try:
                    account_num = int(account_id)
                    if 2110 <= account_num <= 2149 and balance != 0:
                        details.append({
                            'account_id': account_id,
                            'account_text': self._get_account_text(account_num),
                            'balance': balance
                        })
                except ValueError:
                    continue
            
            # Sort by account_id
            details.sort(key=lambda x: int(x['account_id']))
            return details
            
        elif variable_name == 'INK4.6d':
            # Special case: Show återföring details for each account with tax calculation
            details = []
            
            if not previous_accounts:
                return details
            
            for account_id in range(2110, 2150):
                account_str = str(account_id)
                current_balance = float(accounts.get(account_str, 0.0))
                previous_balance = float(previous_accounts.get(account_str, 0.0))
                
                # Only show accounts with återföring (balance became less negative)
                if previous_balance < 0 and current_balance > previous_balance:
                    aterforing_amount = current_balance - previous_balance
                    
                    # Extract avsättning year from account description (e.g., "Periodiseringsfond TAX 2022" → 2022)
                    account_text = self._get_account_text(account_id)
                    avsattning_year = None
                    
                    # Try to extract year from account description
                    import re
                    year_match = re.search(r'(\d{4})', account_text)
                    if year_match:
                        avsattning_year = int(year_match.group(1))
                    else:
                        # Fallback mapping based on account number
                        year_mapping = {2121: 2023, 2122: 2022, 2123: 2021, 2124: 2020, 2125: 2019}
                        avsattning_year = year_mapping.get(account_id, 2018)
                    
                    # Determine tax rate based on avsättning year and återföring year (2024)
                    if avsattning_year >= 2021:  # 2021 and later (0% tax)
                        tax_rate = 0.0
                        tax_rate_str = '0%'
                    elif 2019 <= avsattning_year <= 2020:  # 2019-2020 (4% tax)
                        tax_rate = 0.04
                        tax_rate_str = '4%'
                    else:  # 2018 and earlier (6% tax)
                        tax_rate = 0.06
                        tax_rate_str = '6%'
                    
                    tax_amount = aterforing_amount * tax_rate
                    
                    # Only add to details if there's actually tax (> 0%)
                    if tax_rate > 0:
                        details.append({
                            'account_id': account_str,
                            'account_text': account_text,
                            'balance': aterforing_amount,  # Show återförd amount
                            'tax_rate': tax_rate_str,
                            'tax_amount': tax_amount,
                            'avsattning_year': avsattning_year
                        })
            
            # Sort by account_id
            details.sort(key=lambda x: int(x['account_id']))
            return details
        else:
            # Standard account details for other variables
            return self._get_account_details(mapping.get('accounts_included', ''), accounts)

    def _parse_sie_account_descriptions(self, sie_text: str):
        """Parse account descriptions from SIE file #KONTO lines with character normalization"""
        import re
        import unicodedata
        
        def _norm(s: str) -> str:
            """Use existing normalization function from the codebase"""
            if not s: return ""
            s = unicodedata.normalize("NFKD", s)
            s = "".join(ch for ch in s if not unicodedata.combining(ch))
            s = s.lower().replace("\u00a0", " ").replace("\t", " ")
            return re.sub(r"\s+", " ", s).strip()
        
        def _fix_mojibake(s: str) -> str:
            """Fix common SIE encoding issues using proven patterns from koncern parser"""
            return (s or "").translate(str.maketrans({
                "Ñ": "ä", "ñ": "ä",
                "î": "ö", "Î": "Ö",
                "ô": "ö", "Ô": "Ö", 
                "Õ": "å", "õ": "å",
                "Ý": "å", "ý": "å",
            }))
        
        # Pre-normalize SIE text like other parsers
        sie_text = sie_text.replace("\u00A0", " ").replace("\t", " ")
        
        konto_re = re.compile(r'^#KONTO\s+(\d+)\s+"([^"]*)"\s*$')
        
        for line in sie_text.splitlines():
            line = line.strip()
            match = konto_re.match(line)
            if match:
                account_id = int(match.group(1))
                raw_description = match.group(2)
                # Apply mojibake fixes but keep original case for display
                description = _fix_mojibake(raw_description)
                self.sie_account_descriptions[account_id] = description
                self.sie_account_descriptions[str(account_id)] = description

    def _get_account_text(self, account_id: Any) -> str:
        """Return kontotext for given account id using SIE file first, then cache and DB fallback."""
        # Try SIE account descriptions first (most accurate)
        try:
            acc_int = int(account_id)
            if acc_int in self.sie_account_descriptions:
                return self.sie_account_descriptions[acc_int]
        except Exception:
            acc_int = None
        
        key_str = str(account_id)
        if key_str in self.sie_account_descriptions:
            return self.sie_account_descriptions[key_str]
        
        # Try cached database lookup
        try:
            if acc_int and acc_int in self.accounts_lookup:
                return self.accounts_lookup[acc_int]
        except Exception:
            pass
        
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
    
    def parse_noter_data(self, se_content: str, user_toggles: Dict[str, bool] = None, two_files_flag: bool = False, previous_year_se_content: str = None) -> List[Dict[str, Any]]:
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
        koncern_k2_data = parse_koncern_k2_from_sie_text(
            se_content, 
            debug=False, 
            two_files_flag=two_files_flag, 
            previous_year_sie_text=previous_year_se_content
        )
        
        # Get precise INTRESSEFTG calculations from transaction analysis
        from .intresseftg_k2_parser import parse_intresseftg_k2_from_sie_text
        intresseftg_k2_data = parse_intresseftg_k2_from_sie_text(
            se_content, 
            debug=False, 
            two_files_flag=two_files_flag, 
            previous_year_sie_text=previous_year_se_content
        )
        
        # Get precise BYGG calculations from transaction analysis
        from .bygg_k2_parser import parse_bygg_k2_from_sie_text
        bygg_k2_data = parse_bygg_k2_from_sie_text(
            se_content, 
            debug=False, 
            two_files_flag=two_files_flag, 
            previous_year_sie_text=previous_year_se_content
        )
        
        # Get precise MASKINER calculations from transaction analysis
        from .maskiner_k2_parser import parse_maskiner_k2_from_sie_text
        maskiner_k2_data = parse_maskiner_k2_from_sie_text(
            se_content, 
            debug=False, 
            two_files_flag=two_files_flag, 
            previous_year_sie_text=previous_year_se_content
        )
        
        # Get precise INVENTARIER calculations from transaction analysis
        from .inventarier_k2_parser import parse_inventarier_k2_from_sie_text
        inventarier_k2_data = parse_inventarier_k2_from_sie_text(
            se_content, 
            debug=False, 
            two_files_flag=two_files_flag, 
            previous_year_sie_text=previous_year_se_content
        )
        
        # Get precise ÖVRIGA calculations from transaction analysis
        from .ovriga_k2_parser import parse_ovriga_k2_from_sie_text
        ovriga_k2_data = parse_ovriga_k2_from_sie_text(
            se_content, 
            debug=False, 
            two_files_flag=two_files_flag, 
            previous_year_sie_text=previous_year_se_content
        )
        
        # Get precise LVP calculations from transaction analysis
        from .lvp_k2_parser import parse_lvp_k2_from_sie_text
        lvp_k2_data = parse_lvp_k2_from_sie_text(
            se_content, 
            debug=False, 
            two_files_flag=two_files_flag, 
            previous_year_sie_text=previous_year_se_content
        )
        
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
            # Check if this variable has a corresponding previous year value
            prev_var_name = var_name + '_prev'
            previous_value = koncern_k2_data.get(prev_var_name, 0.0)
            
            calculated_variables[var_name] = {
                'current': value,
                'previous': previous_value
            }
            
        for var_name, value in intresseftg_k2_data.items():
            # Check if this variable has a corresponding previous year value
            prev_var_name = var_name + '_prev'
            previous_value = intresseftg_k2_data.get(prev_var_name, 0.0)
            
            calculated_variables[var_name] = {
                'current': value,
                'previous': previous_value
            }
            
        for var_name, value in bygg_k2_data.items():
            # Check if this variable has a corresponding previous year value
            prev_var_name = var_name + '_prev'
            previous_value = bygg_k2_data.get(prev_var_name, 0.0)
            
            calculated_variables[var_name] = {
                'current': value,
                'previous': previous_value
            }
            
        for var_name, value in maskiner_k2_data.items():
            # Check if this variable has a corresponding previous year value
            prev_var_name = var_name + '_prev'
            previous_value = maskiner_k2_data.get(prev_var_name, 0.0)
            
            calculated_variables[var_name] = {
                'current': value,
                'previous': previous_value
            }
            
        for var_name, value in inventarier_k2_data.items():
            # Check if this variable has a corresponding previous year value
            prev_var_name = var_name + '_prev'
            previous_value = inventarier_k2_data.get(prev_var_name, 0.0)
            
            calculated_variables[var_name] = {
                'current': value,
                'previous': previous_value
            }
            
        for var_name, value in ovriga_k2_data.items():
            # Check if this variable has a corresponding previous year value
            prev_var_name = var_name + '_prev'
            previous_value = ovriga_k2_data.get(prev_var_name, 0.0)
            
            calculated_variables[var_name] = {
                'current': value,
                'previous': previous_value
            }
            
        for var_name, value in lvp_k2_data.items():
            # Check if this variable has a corresponding previous year value
            prev_var_name = var_name + '_prev'
            previous_value = lvp_k2_data.get(prev_var_name, 0.0)
            
            calculated_variables[var_name] = {
                'current': value,
                'previous': previous_value
            }
            
        for var_name, value in fordrkonc_k2_data.items():
            # Check if this variable has a corresponding previous year value
            prev_var_name = var_name + '_prev'
            previous_value = fordrkonc_k2_data.get(prev_var_name, 0.0)
            
            calculated_variables[var_name] = {
                'current': value,
                'previous': previous_value
            }
            
        for var_name, value in fordrintre_k2_data.items():
            # Check if this variable has a corresponding previous year value
            prev_var_name = var_name + '_prev'
            previous_value = fordrintre_k2_data.get(prev_var_name, 0.0)
            
            calculated_variables[var_name] = {
                'current': value,
                'previous': previous_value
            }
            
        for var_name, value in fordrovrftg_k2_data.items():
            # Check if this variable has a corresponding previous year value
            prev_var_name = var_name + '_prev'
            previous_value = fordrovrftg_k2_data.get(prev_var_name, 0.0)
            
            calculated_variables[var_name] = {
                'current': value,
                'previous': previous_value
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
        
        # Calculate depreciation periods for Note 1
        def calculate_depreciation_period(ub_value, avskr_value, default_years, var_name):
            """Calculate depreciation period with default fallback"""
            try:
    
                if avskr_value and avskr_value > 0 and ub_value and ub_value > 0:
                    calc_result = ub_value / avskr_value
                    
                    # Special rounding for maskiner and inventarier groups
                    if var_name in ['avskrtid_mask', 'avskrtid_inv']:
                        # Round to nearest of [3, 5, 10, 15, 20, 25]
                        allowed_values = [3, 5, 10, 15, 20, 25]
                        result = min(allowed_values, key=lambda x: abs(x - calc_result))
                        print(f"DEBUG: {var_name} calc = {calc_result:.1f}, rounded to nearest allowed = {result} years")
                    else:
                        # Regular rounding for other groups
                        result = round(calc_result, 0)
                        print(f"DEBUG: {var_name} calc = {calc_result:.1f}, rounded = {result:.0f} years")
                    
                    return int(result)

                return default_years
            except (TypeError, ZeroDivisionError) as e:
                print(f"DEBUG: {var_name} error: {e}, using default = {default_years} years")
                return default_years
        
        # Add depreciation period calculations
        depreciation_calculations = {
            'avskrtid_bygg': calculate_depreciation_period(
                calculated_variables.get('bygg_ub', {}).get('current', 0),
                calculated_variables.get('arets_avskr_bygg', {}).get('current', 0),
                20,
                'avskrtid_bygg'
            ),
            'avskrtid_mask': calculate_depreciation_period(
                calculated_variables.get('maskiner_ub', {}).get('current', 0),
                calculated_variables.get('arets_avskr_maskiner', {}).get('current', 0),
                5,
                'avskrtid_mask'
            ),
            'avskrtid_inv': calculate_depreciation_period(
                calculated_variables.get('inventarier_ub', {}).get('current', 0),
                calculated_variables.get('arets_avskr_inventarier', {}).get('current', 0),
                3,
                'avskrtid_inv'
            ),
            'avskrtid_ovriga': calculate_depreciation_period(
                calculated_variables.get('ovrmat_ub', {}).get('current', 0),
                calculated_variables.get('arets_avskr_ovrmat', {}).get('current', 0),
                3,
                'avskrtid_ovriga'
            )
        }
               
        # Add depreciation periods to calculated_variables
        for var_name, value in depreciation_calculations.items():
            calculated_variables[var_name] = {
                'current': value,
                'previous': value  # Same value for both years since it's a period calculation
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
                    'toggle_show': toggle_show,
                    'variable_text': mapping.get('variable_text', '')
                }
                results.append(result)
                    
            except Exception as e:

                continue
        
        # Add depreciation period results directly (they don't have database mappings)
        for var_name, value in depreciation_calculations.items():
            depreciation_result = {
                'row_id': 9000 + len(results),  # High row_id to avoid conflicts
                'row_title': f'Avskrivningstid {var_name}',
                'current_amount': value,
                'previous_amount': value,
                'variable_name': var_name,
                'show_tag': False,
                'accounts_included': '',
                'account_details': None,
                'block': 'NOT1',
                'style': 'NORMAL',
                'always_show': True,
                'toggle_show': False,
                'variable_text': ''
            }
            results.append(depreciation_result)
       
        return results