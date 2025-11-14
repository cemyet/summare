# XBRL File and Mapping Structure Explanation

## Overview

This document explains the structure of XBRL files and mapping files used in the Summare project for processing Swedish financial data (SIE files) and generating annual reports.

## XBRL File Structure

The XBRL (eXtensible Business Reporting Language) file you provided appears to be a binary/encoded file (possibly a PDF or font file based on the content). XBRL files typically contain:

1. **Taxonomy definitions** - The structure and rules for financial reporting elements
2. **Instance documents** - Actual financial data tagged with XBRL elements
3. **Linkbases** - Relationships between elements, labels, and references

In this project, XBRL taxonomy elements are referenced through mapping files (CSV) that define how SIE account data maps to Swedish XBRL taxonomy standards (se-gen-base, se-cd-base, etc.).

## Mapping File Structure

The mapping files are CSV files with semicolon (`;`) delimiters that define how SIE account data maps to XBRL taxonomy elements. There are several mapping files:

### 1. **rr.csv** (Resultaträkning / Income Statement)
- Maps income statement items
- Key columns:
  - `ID`: Unique identifier for the row
  - `Row number`: Display order
  - `Radrubrik`: Row heading/label in Swedish
  - `Elementnamn`: XBRL element name (e.g., `Nettoomsattning`, `Rorelseresultat`)
  - `Tillhör`: Taxonomy namespace (e.g., `se-gen-base`)
  - `Standardrubrik`: Standard heading
  - `Datatyp`: Data type (e.g., `xbrli:monetaryItemType`, `xbrli:stringItemType`)
  - `Saldo`: Balance type (`credit` or `debit`)
  - `Periodtyp`: Period type (`duration` for income statement, `instant` for balance sheet)
  - `Typ`: Item type (`item`, `abstract`, `tuple`)
  - `Dokumentation`: Documentation/description
  - Multiple reference columns pointing to Swedish accounting standards (ÅRL, BFN, BAS, etc.)

### 2. **br_mapping_file.csv** (Balansräkning / Balance Sheet)
- Maps balance sheet items
- Similar structure to rr.csv
- Uses `instant` period type (snapshot at a point in time)
- Maps assets (Tillgångar) and liabilities/equity (Skulder och eget kapital)

### 3. **fb.csv** (Förvaltningsberättelse / Management Report)
- Maps management report sections
- Includes:
  - Verksamheten (Business operations)
  - Flerårsöversikt (Multi-year overview)
  - Key performance indicators (Nettoomsättning, Rörelseresultat, Soliditet, etc.)

### 4. **signature.csv** (Undertecknande / Signatures)
- Maps signature and auditor information
- Includes:
  - Undertecknande av företrädare (Signatures of representatives)
  - Revisorspåteckning (Auditor's statement)

### 5. **general info.csv** (Allmän information / General Information)
- Maps general company information
- Includes:
  - Företagets namn (Company name)
  - Organisationsnummer (Organization number)
  - Land (Country)
  - Säte (Registered office)
  - Språk (Language)
  - Redovisningsvaluta (Reporting currency)

## How Mapping Works

### Database-Driven Approach

The project uses a **database-driven parser** (`DatabaseParser` class) that:

1. **Loads mappings from Supabase tables**:
   - `variable_mapping_rr` - Income statement mappings
   - `variable_mapping_br` - Balance sheet mappings
   - `variable_mapping_ink2` - Tax form (INK2) mappings
   - `variable_mapping_noter` - Notes mappings
   - `global_variables` - Global variables (tax rates, etc.)
   - `accounts_table` - Account descriptions

2. **Parses SIE files**:
   - Extracts account balances (`#IB`, `#UB`, `#RES`)
   - Extracts company information (`#FNAMN`, `#ORGNR`, etc.)
   - Maps accounts to XBRL elements using the mappings

3. **Calculates values**:
   - Uses `calculation_formula` from mappings
   - Aggregates account balances
   - Applies business rules (e.g., reclassifications)

### Example Mapping Flow

```
SIE File Account (#KONTO 1930) 
  ↓
Mapping File (br_mapping_file.csv)
  - Account range: 19xx → "Kassa och bank"
  - Elementnamn: "KassaOchBank"
  - Tillhör: "se-gen-base"
  ↓
XBRL Element: se-gen-base:KassaOchBank
  ↓
Annual Report PDF / XBRL Instance Document
```

## Key XBRL Taxonomy Namespaces Used

- **se-gen-base**: Swedish general base taxonomy (most common)
- **se-cd-base**: Swedish company data base taxonomy
- **se-gaap-ext**: Swedish GAAP extensions
- **se-mem-base**: Swedish member/base taxonomy

## Data Types

- `xbrli:monetaryItemType`: Monetary amounts (SEK)
- `xbrli:stringItemType`: Text strings
- `xbrli:dateItemType`: Dates
- `xbrli:decimalItemType`: Decimal numbers
- `xbrli:pureItemType`: Pure numbers (ratios, percentages)
- `enum:enumerationItemType`: Enumerated values (dropdowns)

## Period Types

- **duration**: For income statement items (covers a period)
- **instant**: For balance sheet items (snapshot at a point in time)

## Balance Types (Saldo)

- **credit**: For income/revenue items (normally positive)
- **debit**: For expense/asset items (normally positive)

## References to Swedish Standards

The mapping files include extensive references to Swedish accounting standards:

- **ÅRL** (Årsredovisningslagen): Annual Accounts Act
- **BFN** (Bokföringsnämnden): Swedish Accounting Standards Board
- **BFNAR**: BFN Accounting Regulations
- **BAS**: BAS-konto (Swedish chart of accounts)
- **ABL**: Aktiebolagslagen (Companies Act)

## Processing Flow

```
SIE File (.se)
  ↓
DatabaseParser.parse_account_balances()
  ↓
DatabaseParser.parse_rr_data() / parse_br_data()
  ↓
Mapped to XBRL elements via Supabase tables
  ↓
Stored in financial_data table
  ↓
Used for:
  - Annual Report PDF generation
  - INK2 tax form generation
  - SRU file generation
  - XBRL instance document (future)
```

## Detailed Mapping Process

### Step-by-Step Example: Mapping "Kassa och bank" (Cash and Bank)

Let's trace how account 1930 (Cash) gets mapped to the XBRL element `se-gen-base:KassaOchBank`:

1. **SIE File Parsing**:
   ```
   #UB 0 1930 150000.00
   ```
   This means: Closing balance (UB) for fiscal year 0 (current year), account 1930, amount 150,000 SEK

2. **Account Balance Extraction** (`parse_account_balances`):
   ```python
   current_accounts = {
       "1930": 150000.00,
       "1940": 50000.00,
       # ... other accounts
   }
   ```

3. **Mapping Lookup** (from `variable_mapping_br` table):
   ```python
   mapping = {
       'row_id': 193,
       'row_title': 'Kassa och bank',
       'variable_name': 'KassaOchBank',
       'element_name': 'KassaOchBank',
       'accounts_included_start': 1930,
       'accounts_included_end': 1940,
       'accounts_excluded': None,
       'is_calculated': False,
       'calculation_formula': None,
       'show_amount': True,
       'style': 'P',
       'balance_type': 'debit',
       'period_type': 'instant'
   }
   ```

4. **Value Calculation** (`calculate_variable_value`):
   ```python
   # Include accounts 1930-1940
   total = accounts["1930"] + accounts["1940"]
   # = 150000 + 50000 = 200000
   
   # No exclusions, no sign reversal (accounts < 2000)
   return 200000.00
   ```

5. **Result Structure**:
   ```python
   {
       'id': 193,
       'label': 'Kassa och bank',
       'current_amount': 200000.00,
       'previous_amount': 180000.00,  # from previous year
       'variable_name': 'KassaOchBank',
       'element_name': 'KassaOchBank',  # XBRL element
       'section': 'BR',
       'type': 'asset',
       'period_type': 'instant'  # Balance sheet snapshot
   }
   ```

### Example: Calculated Values (Formulas)

For calculated rows like "Summa tillgångar" (Total Assets):

1. **Mapping**:
   ```python
   mapping = {
       'row_id': 250,
       'row_title': 'Summa tillgångar',
       'variable_name': 'Tillgangar',
       'is_calculated': True,
       'calculation_formula': 'TecknatMenEjInbetaltKapital + ImmateriellaAnlaggningstillgangar + MateriellaAnlaggningstillgangar + FinansiellaAnlaggningstillgangar + Varulager + KortfristigaFordringar + KortfristigaPlaceringar + KassaOchBank',
       'show_amount': True
   }
   ```

2. **Formula Evaluation** (`calculate_formula_value`):
   ```python
   # Replace variable names with their values
   formula = "0 + 50000 + 200000 + 100000 + 300000 + 150000 + 50000 + 200000"
   result = eval(formula)  # = 1,050,000
   ```

### Account Range Specifications

The mapping supports flexible account specifications:

- **Range**: `accounts_included_start: 1930, accounts_included_end: 1940`
  - Includes accounts 1930, 1931, ..., 1940
  
- **Additional accounts**: `accounts_included: "1950;1960-1965"`
  - Includes account 1950 and range 1960-1965
  
- **Exclusions**: `accounts_excluded: "1935;1940-1942"`
  - Excludes account 1935 and range 1940-1942

### Sign Handling

Swedish accounting uses different sign conventions:

- **Accounts 1000-1999** (Assets): Positive = asset
- **Accounts 2000-8989** (Liabilities/Equity): In SIE files, these are stored with reversed signs, so the parser automatically reverses them:
  ```python
  if 2000 <= account_id <= 8989:
      return -total  # Reverse sign
  ```

### Two-Pass Calculation

The parser uses a two-pass approach:

1. **First Pass**: Calculate direct account mappings
   ```python
   for mapping in br_mappings:
       if not mapping['is_calculated']:
           amount = calculate_variable_value(mapping, accounts)
           results.append({...})
   ```

2. **Second Pass**: Calculate formulas that reference other variables
   ```python
   for mapping in calculated_mappings:
       amount = calculate_formula_value(mapping, accounts, results)
       # Update the result row
   ```

This ensures dependencies are resolved correctly (e.g., subtotals are calculated before totals).

### Reclassification Logic

The system includes special reclassification rules:

- **168x accounts**: Short-term group receivables moved between current and non-current
- **17xx accounts**: Prepaid and accrued group receivables
- **296x accounts**: Short-term group liabilities

These reclassifications update both amounts and `account_details` to show which accounts contributed to each line item.

## Database Schema

The Supabase tables store the mapping data:

### `variable_mapping_rr` / `variable_mapping_br`
- `row_id`: Unique identifier
- `row_title`: Swedish label
- `variable_name`: Internal variable name
- `element_name`: XBRL element name
- `accounts_included_start`: Start of account range
- `accounts_included_end`: End of account range
- `accounts_included`: Additional accounts (semicolon-separated)
- `accounts_excluded`: Excluded accounts
- `is_calculated`: Boolean flag
- `calculation_formula`: Formula string (e.g., "A + B - C")
- `show_amount`: Whether to display amount
- `style`: Display style (H0, H1, H2, P, etc.)
- `balance_type`: debit/credit
- `period_type`: duration/instant
- `always_show`: Show even if zero
- `show_tag`: Show account breakdown

### `global_variables`
- `variable_name`: Variable name
- `value`: Numeric value (percentages stored as decimals, e.g., 0.22 for 22%)

### `accounts_table`
- `account_id`: Account number
- `account_text`: Account description

## Notes

- The mapping files (CSV) are imported into Supabase tables for faster querying
- The system prioritizes edited/posted data over raw parsed data
- Calculations can reference other mapped variables by `variable_name`
- Some rows are "abstract" (headers) and don't contain amounts (`show_amount: false`)
- The system supports both current year and previous year data
- Account details (`account_details`) show which accounts contributed to each line item
- Reclassifications can move accounts between line items based on business rules

