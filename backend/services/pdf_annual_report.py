# pdf_annual_report.py
# Server-side PDF generation for full annual report using ReportLab
from io import BytesIO
from typing import Any, Dict, List, Tuple
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

# Register Roboto fonts
FONT_DIR = os.path.join(os.path.dirname(__file__), '..', 'fonts')
pdfmetrics.registerFont(TTFont('Roboto', os.path.join(FONT_DIR, 'Roboto-Regular.ttf')))
pdfmetrics.registerFont(TTFont('Roboto-Medium', os.path.join(FONT_DIR, 'Roboto-Medium.ttf')))
pdfmetrics.registerFont(TTFont('Roboto-Bold', os.path.join(FONT_DIR, 'Roboto-Bold.ttf')))

# Balance sheet heading sizes / spacing (one source of truth)
BR_H1_SIZE = 10            # Bundet/Fritt/Kortfristiga skulder etc.
BR_H2_SIZE = 11            # e.g. "Anläggningstillgångar", "Omsättningstillgångar"
BR_H2_SPACE_BEFORE = 8     # extra air *before* an H2 row
BR_H2_SPACE_AFTER = 12     # extra air *after* an H2 row
BR_ROW_SPACING = 2         # spacing between normal rows

# Noter styling
THIN_GREY = colors.Color(0, 0, 0, alpha=0.20)  # 20% opacity for subtle lines

def _num(v):
    """Convert value to float, handling bools, None, empty strings"""
    try:
        if isinstance(v, bool): return 0.0
        if v is None or v == "": return 0.0
        if isinstance(v, (int, float)): return float(v)
        s = str(v).replace(" ", "").replace("\u00A0", "").replace(",", ".")
        return float(s) if s else 0.0
    except Exception:
        return 0.0

def _fmt_sek(n: float) -> str:
    """Format number as Swedish kronor: '12 345 kr'"""
    i = int(round(n))
    s = f"{i:,}".replace(",", " ")
    return f"{s} kr"

def _fmt_int(n: float) -> str:
    """Format number with space separator: '12 345'"""
    i = int(round(n))
    return f"{i:,}".replace(",", " ")

def _styles():
    """
    Typography styles for PDF generation (19.2mm top margin, 24mm other margins, compact spacing)
    H0: 16pt semibold, 0pt before, 0pt after (main titles like "Förvaltningsberättelse")
    H1: 12pt semibold, 18pt before, 0pt after (subsections like "Verksamheten", "Flerårsöversikt")
    H2: 15pt semibold, 18pt before, 0pt after (major section headings - overridden in BR to 11pt/10pt)
    P: 10pt regular, 12pt leading, 2pt after
    SMALL: 8pt for "Belopp i tkr"
    Note: BR uses custom BR_H1 (10pt semibold) and BR_H2 (11pt semibold, 8pt before, 12pt after) for its headings
    """
    ss = getSampleStyleSheet()
    
    # H0 - Main section titles (semibold)
    h0 = ParagraphStyle(
        'H0', 
        parent=ss['Heading1'], 
        fontName='Roboto-Medium', 
        fontSize=16, 
        spaceBefore=0, 
        spaceAfter=0
    )
    
    # H1 - Subsection headings (semibold)
    h1 = ParagraphStyle(
        'H1', 
        parent=ss['Heading2'], 
        fontName='Roboto-Medium', 
        fontSize=12, 
        spaceBefore=18, 
        spaceAfter=0  # No padding after heading
    )
    
    # H2 - Major section headings (semibold, 3pt larger than H1)
    h2 = ParagraphStyle(
        'H2', 
        parent=ss['Heading2'], 
        fontName='Roboto-Medium', 
        fontSize=15,  # 3pt larger than H1
        spaceBefore=18, 
        spaceAfter=0
    )
    
    # P - Body text
    p = ParagraphStyle(
        'P', 
        parent=ss['BodyText'], 
        fontName='Roboto', 
        fontSize=10, 
        leading=12,  # 12pt line height
        spaceBefore=0, 
        spaceAfter=2
    )
    
    # SMALL - 8pt for table subheadings like "Belopp i tkr"
    small = ParagraphStyle(
        'SMALL', 
        parent=p, 
        fontSize=8,
        spaceBefore=0, 
        spaceAfter=0,  # No extra space after
        textColor=colors.black
    )
    return h0, h1, h2, p, small

def _table_style():
    """Standard table style: 0.5pt 70% black borders, 0pt spacing, semibold headers"""
    return TableStyle([
        ('FONT', (0,0), (-1,0), 'Roboto-Medium', 10),  # Semibold header row
        ('FONT', (0,1), (-1,-1), 'Roboto', 10),  # Regular for data rows
        ('LINEBELOW', (0,0), (-1,0), 0.5, colors.Color(0, 0, 0, alpha=0.7)),  # Header underline
        ('ALIGN', (1,1), (-1,-1), 'RIGHT'),  # Right-align numbers (not first column)
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ROWSPACING', (0,0), (-1,-1), 0),  # 0pt row spacing
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),  # 0pt bottom padding (compact)
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),  # More padding between columns
    ])

def _company_meta(data: Dict[str, Any]) -> Tuple[str, str, int]:
    se = (data or {}).get('seFileData') or {}
    info = se.get('company_info') or {}
    name = data.get('company_name') or info.get('company_name') or "Bolag"
    orgnr = data.get('organizationNumber') or info.get('organization_number') or ""
    fy = data.get('fiscalYear') or info.get('fiscal_year') or 0
    return str(name), str(orgnr), int(fy) if fy else 0

def _format_date(date_str: str) -> str:
    """Format date from YYYYMMDD to YYYY-MM-DD"""
    if not date_str or len(date_str) != 8:
        return date_str
    try:
        return f"{date_str[0:4]}-{date_str[4:6]}-{date_str[6:8]}"
    except Exception:
        return date_str

def _get_year_headers(data: Dict[str, Any], fiscal_year: int, prev_year: int) -> Tuple[str, str]:
    """Get formatted year headers with end dates for BR columns"""
    se = (data or {}).get('seFileData') or {}
    info = se.get('company_info') or {}
    
    # Try to get end dates from company_info
    current_end_date = info.get('end_date', '')
    previous_end_date = info.get('previous_end_date', '')
    
    # Format dates if available, otherwise use year numbers
    if current_end_date:
        current_header = _format_date(current_end_date)
    else:
        current_header = str(fiscal_year)
    
    if previous_end_date:
        previous_header = _format_date(previous_end_date)
    else:
        previous_header = str(prev_year)
    
    return current_header, previous_header

def _extract_fb_texts(cd: Dict[str, Any]) -> Tuple[str, str]:
    """Extract Förvaltningsberättelse text fields"""
    scraped = (cd or {}).get('scraped_company_data') or {}
    verksamhet = scraped.get('verksamhetsbeskrivning') or scraped.get('Verksamhetsbeskrivning') or ""
    sate = scraped.get('säte') or scraped.get('sate') or scraped.get('Säte') or ""
    if sate:
        verksamhet = (verksamhet + " " if verksamhet else "") + f"Bolaget har sitt säte i {sate}."
    
    # Get väsentliga händelser from forvaltningsberattelse if available
    fb = cd.get('forvaltningsberattelse') or {}
    vasentliga = fb.get('vasentliga_handelser') or "Inga väsentliga händelser under året."
    
    return verksamhet.strip() or "–", vasentliga

def _render_flerarsoversikt(elems, company_data, fiscal_year, H1, SMALL):
    """Render Flerårsöversikt exactly as shown in frontend - 3 years from scraped data"""
    elems.append(Paragraph("Flerårsöversikt", H1))
    elems.append(Paragraph("Belopp i tkr", SMALL))
    
    # Get flerårsöversikt data from companyData (comes from frontend state)
    flerars = company_data.get('flerarsoversikt', {})
    
    # If we have structured flerårsöversikt data with years/rows, use it
    if flerars and flerars.get('years'):
        years = flerars.get('years', [])
        rows = flerars.get('rows', [])
        
        if not years or not rows:
            return
        
        table_data = [[""] + [str(y) for y in years]]
        for row in rows:
            label = row.get('label', '')
            values = row.get('values', [])
            
            # Format values: Soliditet gets %, others get plain numbers
            if 'Soliditet' in label or 'soliditet' in label.lower():
                formatted = [f"{int(round(v))}%" if v else "0%" for v in values]
            else:
                formatted = [_fmt_int(v) if v else "0" for v in values]
            
            table_data.append([label] + formatted)
    elif flerars and any(k.startswith(('oms', 'ref', 'bal', 'sol')) for k in flerars.keys()):
        # Handle edited values map format: {'oms1': 1000, 'oms2': 2000, ...}
        # Merge with scraped data for missing values
        scraped = company_data.get('scraped_company_data', {})
        nyckeltal = scraped.get('nyckeltal', {})
        
        # Helper to get scraped values
        def get_scraped_values(key_variants):
            for key in key_variants:
                arr = nyckeltal.get(key)
                if arr and isinstance(arr, list):
                    return [_num(x) for x in arr[:3]]
            return [0, 0, 0]
        
        # Get scraped values as fallback
        scraped_oms = get_scraped_values(['Omsättning', 'Total omsättning', 'omsättning'])
        scraped_ref = get_scraped_values(['Resultat efter finansnetto', 'Resultat efter finansiella poster'])
        scraped_bal = get_scraped_values(['Summa tillgångar', 'Balansomslutning'])
        scraped_sol = get_scraped_values(['Soliditet'])
        
        # Extract edited values, fallback to scraped if not present
        oms_vals = [_num(flerars.get(f'oms{i}')) if flerars.get(f'oms{i}') is not None else scraped_oms[i-1] for i in [1, 2, 3]]
        ref_vals = [_num(flerars.get(f'ref{i}')) if flerars.get(f'ref{i}') is not None else scraped_ref[i-1] for i in [1, 2, 3]]
        bal_vals = [_num(flerars.get(f'bal{i}')) if flerars.get(f'bal{i}') is not None else scraped_bal[i-1] for i in [1, 2, 3]]
        sol_vals = [_num(flerars.get(f'sol{i}')) if flerars.get(f'sol{i}') is not None else scraped_sol[i-1] for i in [1, 2, 3]]
        
        # Build years (fiscal year and 2 previous)
        years = [str(fiscal_year), str(fiscal_year-1), str(fiscal_year-2)]
        
        # Build table
        table_data = [[""] + years]
        table_data.append(["Omsättning"] + [_fmt_int(v) for v in oms_vals])
        table_data.append(["Resultat efter finansiella poster"] + [_fmt_int(v) for v in ref_vals])
        table_data.append(["Balansomslutning"] + [_fmt_int(v) for v in bal_vals])
        table_data.append(["Soliditet"] + [f"{int(round(v))}%" for v in sol_vals])
    else:
        # Fallback: build from scraped data
        scraped = company_data.get('scraped_company_data', {})
        nyckeltal = scraped.get('nyckeltal', {})
        
        if not nyckeltal:
            return
        
        # Check if scraped data includes fiscal year
        scraped_years = nyckeltal.get('years', [])
        scraped_includes_fiscal_year = len(scraped_years) > 0 and scraped_years[0] == fiscal_year
        
        def get_values(key_variants):
            for key in key_variants:
                arr = nyckeltal.get(key)
                if arr and isinstance(arr, list):
                    return [_num(x) for x in arr[:3]]  # Get first 3 values
            return [0, 0, 0]
        
        if scraped_includes_fiscal_year:
            # Use scraped years directly (scraped data already includes fiscal year)
            years = [str(y) for y in scraped_years[:3]] if scraped_years else [str(fiscal_year), str(fiscal_year-1), str(fiscal_year-2)]
            
            # Get data from scraped (3 years)
            oms = get_values(['Omsättning', 'Total omsättning', 'omsättning'])
            ref = get_values(['Resultat efter finansnetto', 'Resultat efter finansiella poster'])
            bal = get_values(['Summa tillgångar', 'Balansomslutning'])
            sol = get_values(['Soliditet'])
            
            # Build table with scraped data
            table_data = [[""] + years]
            table_data.append(["Omsättning"] + [_fmt_int(v) for v in oms])
            table_data.append(["Resultat efter finansiella poster"] + [_fmt_int(v) for v in ref])
            table_data.append(["Balansomslutning"] + [_fmt_int(v) for v in bal])
            table_data.append(["Soliditet"] + [f"{int(round(v))}%" for v in sol])
        else:
            # Scraped data doesn't include fiscal year - need to calculate current year
            years = [str(fiscal_year), str(fiscal_year-1), str(fiscal_year-2)]
            
            # Get scraped data (fy-1, fy-2, fy-3)
            oms_scraped = get_values(['Omsättning', 'Total omsättning', 'omsättning'])
            ref_scraped = get_values(['Resultat efter finansnetto', 'Resultat efter finansiella poster'])
            bal_scraped = get_values(['Summa tillgångar', 'Balansomslutning'])
            sol_scraped = get_values(['Soliditet'])
            
            # Calculate current year values from rr/br data - use posted data if available
            rr_data = (company_data.get('rrData') or 
                       company_data.get('rrRows') or 
                       company_data.get('seFileData', {}).get('rr_data', []))
            br_data = (company_data.get('brData') or 
                       company_data.get('brRows') or 
                       company_data.get('seFileData', {}).get('br_data', []))
            
            # Find nettoomsättning (current year) in tkr
            netto_oms_fy = 0
            for row in rr_data:
                if row.get('variable_name') == 'SumRorelseintakter':
                    netto_oms_fy = _num(row.get('current_amount', 0)) / 1000
                    break
            
            # Find result after financial items (current year) in tkr
            refp_fy = 0
            for row in rr_data:
                if row.get('variable_name') == 'SumResultatEfterFinansiellaPoster':
                    refp_fy = _num(row.get('current_amount', 0)) / 1000
                    break
            
            # Find sum tillgångar (current year) in tkr
            tillg_fy = 0
            for row in br_data:
                if row.get('variable_name') == 'SumTillgangar':
                    tillg_fy = _num(row.get('current_amount', 0)) / 1000
                    break
            
            # Calculate soliditet (current year)
            eget_kap = 0
            for row in br_data:
                if row.get('variable_name') == 'SumEgetKapital':
                    eget_kap = _num(row.get('current_amount', 0))
                    break
            
            tillg_fy_full = 0
            for row in br_data:
                if row.get('variable_name') == 'SumTillgangar':
                    tillg_fy_full = _num(row.get('current_amount', 0))
                    break
            
            soliditet_fy = (eget_kap / tillg_fy_full * 100) if tillg_fy_full != 0 else 0
            
            # Build table with current year + scraped data (take only first 2 from scraped)
            table_data = [[""] + years]
            table_data.append(["Omsättning"] + [_fmt_int(netto_oms_fy)] + [_fmt_int(v) for v in oms_scraped[:2]])
            table_data.append(["Resultat efter finansiella poster"] + [_fmt_int(refp_fy)] + [_fmt_int(v) for v in ref_scraped[:2]])
            table_data.append(["Balansomslutning"] + [_fmt_int(tillg_fy)] + [_fmt_int(v) for v in bal_scraped[:2]])
            table_data.append(["Soliditet"] + [f"{int(round(soliditet_fy))}%"] + [f"{int(round(v))}%" for v in sol_scraped[:2]])
    
    if len(table_data) > 1:
        # Use full page width (459pt available)
        available_width = 459
        label_width = 200  # Label column
        num_years = len(table_data[0]) - 1  # Number of year columns
        year_width = (available_width - label_width) / num_years if num_years > 0 else 85
        
        col_widths = [label_width] + [year_width] * num_years
        
        t = Table(table_data, hAlign='LEFT', colWidths=col_widths)
        # Custom style with right-aligned headers and semibold year headers
        style = TableStyle([
            ('FONT', (0,0), (-1,0), 'Roboto-Medium', 10),  # Semibold year header row
            ('FONT', (0,1), (-1,-1), 'Roboto', 10),  # Regular for data rows
            ('LINEBELOW', (0,0), (-1,0), 0.5, colors.Color(0, 0, 0, alpha=0.7)),
            ('ALIGN', (1,0), (-1,0), 'RIGHT'),  # Right-align year headers
            ('ALIGN', (1,1), (-1,-1), 'RIGHT'),  # Right-align numbers
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('ROWSPACING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ])
        t.setStyle(style)
        elems.append(t)
        elems.append(Spacer(1, 8))

def _render_forandringar_i_eget_kapital(elems, company_data, fiscal_year, prev_year, H1):
    """Render Förändringar i eget kapital table with multi-line headers"""
    fb_table = company_data.get('fbTable', [])
    
    if not fb_table or len(fb_table) == 0:
        return
    
    elems.append(Paragraph("Förändringar i eget kapital", H1))
    
    # Column headers with line breaks
    cols = ['aktiekapital', 'reservfond', 'uppskrivningsfond', 'balanserat_resultat', 'arets_resultat', 'total']
    col_labels = [
        'Aktie\nkapital', 
        'Reserv\nfond', 
        'Uppskrivnings\nfond', 
        'Balanserat\nresultat', 
        'Årets\nresultat', 
        'Totalt'
    ]
    
    # Determine which columns have non-zero values
    col_has_data = {}
    for col in cols:
        col_has_data[col] = any(_num(row.get(col, 0)) != 0 for row in fb_table)
    
    # Build visible columns list
    visible_cols = [col for col in cols if col_has_data[col]]
    visible_labels = [col_labels[cols.index(col)] for col in visible_cols]
    
    if not visible_cols:
        return  # All columns are zero
    
    # Build table data, filtering out all-zero rows and "Redovisat värde"
    table_data = [[""] + visible_labels]
    utgaende_rows = []  # Track rows with "utgång" or "Utgående" to make them bold
    
    for row in fb_table:
        label = row.get('label', '')
        
        # Skip "Redovisat värde" rows completely
        if 'Redovisat' in label:
            continue
        
        row_values = [_num(row.get(col, 0)) for col in visible_cols]
        
        # Skip rows where all visible columns are zero (except IB/UB rows)
        if not any(v != 0 for v in row_values):
            # Keep IB and UB rows even if zero
            if not ('Ingående' in label or 'Utgående' in label or 'utgång' in label.lower()):
                continue
        
        formatted_values = [_fmt_int(v) for v in row_values]
        table_data.append([label] + formatted_values)
        
        # Track if this row should be bold (contains "utgång" or "Utgående")
        if 'utgång' in label.lower() or 'Utgående' in label:
            utgaende_rows.append(len(table_data) - 1)  # Store row index (0-based)
    
    if len(table_data) > 1:  # Has data beyond header
        # Use full page width (459pt available)
        available_width = 459
        label_width = 160
        num_cols = len(visible_cols)
        data_width = available_width - label_width
        col_width = data_width / num_cols if num_cols > 0 else 60
        
        col_widths = [label_width] + [col_width] * num_cols
        
        t = Table(table_data, hAlign='LEFT', colWidths=col_widths)
        # Custom style with right-aligned headers
        style = TableStyle([
            ('FONT', (0,0), (-1,0), 'Roboto-Medium', 10),  # Semibold header row
            ('FONT', (0,1), (-1,-1), 'Roboto', 10),  # Regular for data rows
            ('LINEBELOW', (0,0), (-1,0), 0.5, colors.Color(0, 0, 0, alpha=0.7)),
            ('ALIGN', (1,0), (-1,0), 'RIGHT'),  # Right-align column headers
            ('ALIGN', (1,1), (-1,-1), 'RIGHT'),  # Right-align numbers
            ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),  # Bottom align to bring "Totalt" down
            ('ROWSPACING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ])
        # Make "Belopp vid årets utgång" rows semibold (no line above)
        for row_idx in utgaende_rows:
            style.add('FONT', (0, row_idx), (-1, row_idx), 'Roboto-Medium', 10)
        t.setStyle(style)
        elems.append(t)
        elems.append(Spacer(1, 8))

def _render_resultatdisposition(elems, company_data, H1, P):
    """Render Resultatdisposition section with correct row structure and utdelning text"""
    fb_table = company_data.get('fbTable', [])
    arets_utdelning = _num(company_data.get('arets_utdelning', 0))
    
    if not fb_table:
        return
    
    # Find UB row (Redovisat värde or last row)
    ub_row = None
    for row in fb_table:
        if 'Redovisat' in row.get('label', '') or 'Utgående' in row.get('label', ''):
            ub_row = row
            break
    
    if not ub_row:
        ub_row = fb_table[-1] if fb_table else {}
    
    # Get balanserat resultat and årets resultat from UB row
    balanserat = _num(ub_row.get('balanserat_resultat', 0))
    arets_res = _num(ub_row.get('arets_resultat', 0))
    summa = balanserat + arets_res
    
    if summa == 0 and arets_utdelning == 0:
        return  # Nothing to report
    
    elems.append(Paragraph("Resultatdisposition", H1))
    elems.append(Paragraph("Styrelsen och VD föreslår att till förfogande stående medel", P))
    
    table_data = []
    summa_rows = []  # Track which rows are "Summa" rows for bold styling
    
    # Available funds breakdown
    if balanserat != 0:
        table_data.append(["Balanserat resultat", _fmt_int(balanserat)])
    if arets_res != 0:
        table_data.append(["Årets resultat", _fmt_int(arets_res)])
    
    # First Summa row
    summa_rows.append(len(table_data))
    table_data.append(["Summa", _fmt_int(summa)])
    
    # Empty row for spacing
    table_data.append(["", ""])
    
    # Disposition section header
    table_data.append(["Disponeras enligt följande", ""])
    
    # Disposition breakdown - always show "Utdelas till aktieägare" even if 0
    table_data.append(["Utdelas till aktieägare", _fmt_int(arets_utdelning)])
    
    balanseras = summa - arets_utdelning
    table_data.append(["Balanseras i ny räkning", _fmt_int(balanseras)])
    
    # Final summa row
    summa_rows.append(len(table_data))
    table_data.append(["Summa", _fmt_int(summa)])
    
    # Simple 2-column layout with amounts close to labels
    t = Table(table_data, hAlign='LEFT', colWidths=[150, 150])
    # Custom style for Resultatdisposition (no header underline, 0pt spacing, semibold Summa rows)
    style = TableStyle([
        ('FONT', (0,0), (-1,-1), 'Roboto', 10),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),  # Right-align amounts
        ('ROWSPACING', (0,0), (-1,-1), 0),  # 0pt row spacing
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ])
    # Make Summa rows semibold
    for row_idx in summa_rows:
        style.add('FONT', (0, row_idx), (-1, row_idx), 'Roboto-Medium', 10)
    t.setStyle(style)
    elems.append(t)
    elems.append(Spacer(1, 8))
    
    # Add dividend policy text if utdelning > 0 (with extra line break before)
    if arets_utdelning > 0:
        elems.append(Spacer(1, 8))  # Extra line break
        dividend_text = ("Styrelsen anser att förslaget är förenligt med försiktighetsregeln "
                        "i 17 kap. 3 § aktiebolagslagen enligt följande redogörelse. Styrelsens "
                        "uppfattning är att vinstutdelningen är försvarlig med hänsyn till de krav "
                        "verksamhetens art, omfattning och risk ställer på storleken på det egna "
                        "kapitalet, bolagets konsolideringsbehov, likviditet och ställning i övrigt.")
        elems.append(Paragraph(dividend_text, P))
        elems.append(Spacer(1, 8))

def generate_full_annual_report_pdf(company_data: Dict[str, Any]) -> bytes:
    """
    Generate complete annual report PDF with all sections:
    1. Förvaltningsberättelse
    2. Resultaträkning
    3. Balansräkning (Tillgångar)
    4. Balansräkning (Eget kapital och skulder)
    5. Noter
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, 
        pagesize=A4, 
        leftMargin=68,  # 24mm (~68pt)
        rightMargin=68, 
        topMargin=54,  # 19.2mm (80% of 24mm)
        bottomMargin=68
    )
    
    H0, H1, H2, P, SMALL = _styles()
    elems: List[Any] = []
    
    # Extract company metadata
    name, orgnr, fiscal_year = _company_meta(company_data)
    prev_year = fiscal_year - 1 if fiscal_year else 0
    
    # Get year headers with end dates for BR
    current_year_header, previous_year_header = _get_year_headers(company_data, fiscal_year, prev_year)
    
    # Extract data sections - PREFER posted/edited data over parsing
    # RR: Check for edited data first, fallback to seFileData
    rr_data = (company_data.get('rrData') or 
               company_data.get('rrRows') or 
               company_data.get('seFileData', {}).get('rr_data', []))
    
    # BR: Check for edited data first, fallback to seFileData  
    br_data = (company_data.get('brData') or 
               company_data.get('brRows') or 
               company_data.get('seFileData', {}).get('br_data', []))
    
    # Noter: Use edited data from database + toggle states
    noter_data = company_data.get('noterData', [])
    noter_toggle_on = company_data.get('noterToggleOn', False)
    noter_block_toggles = company_data.get('noterBlockToggles', {})
    
    # Scraped data (for Medeltal anställda, moderbolag, etc.)
    scraped_company_data = company_data.get('scraped_company_data', {})
    
    # FB: Extract data
    fb_table = company_data.get('fbTable', [])
    fb_variables = company_data.get('fbVariables', {})
    
    # ===== 1. FÖRVALTNINGSBERÄTTELSE =====
    elems.append(Paragraph("Förvaltningsberättelse", H0))
    elems.append(Spacer(1, 8))
    
    # Extract text content - prefer edited values, fallback to building from scraped data (like frontend)
    verksamhet_text = company_data.get('verksamhetContent')
    vasentliga_text = company_data.get('vasentligaHandelser')
    
    # If not edited, build from scraped data exactly like frontend does
    if not verksamhet_text:
        # Build verksamhet text from scraped data (mirrors AnnualReportPreview.tsx lines 343-357)
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
        
        # Fallback if still empty
        if not verksamhet_text:
            verksamhet_text = "Bolaget bedriver verksamhet enligt bolagsordningen."
    
    if not vasentliga_text:
        vasentliga_text = "Inga väsentliga händelser under året."
    
    elems.append(Paragraph("Verksamheten", H1))
    elems.append(Paragraph(verksamhet_text, P))
    elems.append(Spacer(1, 4))
    
    elems.append(Paragraph("Väsentliga händelser under räkenskapsåret", H1))
    elems.append(Paragraph(vasentliga_text, P))
    elems.append(Spacer(1, 8))
    
    # Flerårsöversikt
    _render_flerarsoversikt(elems, company_data, fiscal_year, H1, SMALL)
    
    # Förändringar i eget kapital
    _render_forandringar_i_eget_kapital(elems, company_data, fiscal_year, prev_year, H1)
    
    # Resultatdisposition
    _render_resultatdisposition(elems, company_data, H1, P)
    
    # ===== 2. RESULTATRÄKNING =====
    elems.append(PageBreak())
    elems.append(Paragraph("Resultaträkning", H0))
    elems.append(Spacer(1, 16))  # 2 line breaks
    
    # Define section headings and sum rows for special formatting
    # Headings are category labels with no amounts (semibold)
    rr_headings = [
        'Rörelseintäkter', 'lagerförändringar m.m.', 'Rörelseintäkter, lagerförändringar m.m.',
        'Rörelsekostnader', 'Finansiella poster', 'Bokslutsdispositioner', 'Skatter'
    ]
    # Sum rows are calculated totals with amounts (semibold)
    rr_sum_rows = [
        'Summa rörelseintäkter', 'lagerförändringar m.m.', 'Summa rörelsekostnader',
        'Rörelseresultat',  # This is a sum row with formula (comes after Summa rörelsekostnader)
        'Summa finansiella poster', 'Resultat efter finansiella poster',
        'Summa bokslutsdispositioner', 'Resultat före skatt', 'Årets resultat'
    ]
    
    # Helper function to check if a block_group has content
    def block_has_content(block_group: str) -> bool:
        """Check if any non-heading row in this block has non-zero amounts"""
        if not block_group:
            return True  # Items without block_group always show
        
        # Skatter block always shows
        if 'Skatter' in block_group:
            return True
        
        for row in rr_data:
            if row.get('block_group') != block_group:
                continue
            label = row.get('label', '')
            
            # Skip headings (exact match only)
            row_is_heading = any(h == label for h in rr_headings)
            # Skip sums (exact match or starts with "Summa")
            row_is_sum = any(s == label or (s in label and label.startswith('Summa')) for s in rr_sum_rows)
            
            if row_is_heading or row_is_sum:
                continue
            
            # Check if this row has non-zero amount or always_show
            if row.get('always_show'):
                return True
            curr = _num(row.get('current_amount', 0))
            prev = _num(row.get('previous_amount', 0))
            if curr != 0 or prev != 0:
                return True
        
        return False
    
    # Header: Post (no text), Not, years (right-aligned)
    rr_table_data = [["", "Not", str(fiscal_year), str(prev_year)]]
    semibold_rows = []  # Track rows that need semibold styling
    sum_rows = []  # Track sum rows for extra spacing after
    arets_resultat_row = None  # Track "Årets resultat" row for spacing before
    seen_rorelseresultat = False  # Track to skip the first (duplicate) Rörelseresultat
    
    for row in rr_data:
        # Filter logic: respect show_tag
        if row.get('show_tag') == False:
            continue
        
        label = row.get('label', '')
        block_group = row.get('block_group', '')
        
        # Skip the FIRST occurrence of "Rörelseresultat" (the duplicate at the top)
        # Keep the second one (the sum row after Summa rörelsekostnader)
        if label == 'Rörelseresultat':
            if not seen_rorelseresultat:
                seen_rorelseresultat = True
                continue  # Skip the first one
            # If we get here, it's the second one - keep it
        
        # Check if this is a heading or sum row
        # Use exact match or specific logic to avoid confusion
        # e.g., "lagerförändringar m.m." is a heading, but "Summa rörelseintäkter, lagerförändringar m.m." is a sum
        is_sum = False
        is_heading = False
        
        # Check sum rows first (more specific)
        for sum_label in rr_sum_rows:
            if sum_label == label or (sum_label in label and label.startswith('Summa')):
                is_sum = True
                break
        
        # If not a sum, check headings (exact match only)
        if not is_sum:
            for heading in rr_headings:
                if heading == label:
                    is_heading = True
                    break
        
        # Block hiding logic: if this row belongs to a block, check if block has content
        if block_group and not block_has_content(block_group):
            continue
        
        # Add note number "2" to Personalkostnader
        note = str(row.get('note_number', '')) if row.get('note_number') else ''
        if 'Personalkostnader' in label or 'personalkostnader' in label.lower():
            note = '2'
        
        # For heading rows: show empty amounts
        if is_heading:
            curr_fmt = ''
            prev_fmt = ''
        else:
            # Filter zero rows (unless always_show or sum)
            if not row.get('always_show') and not is_sum:
                curr = _num(row.get('current_amount', 0))
                prev = _num(row.get('previous_amount', 0))
                if curr == 0 and prev == 0:
                    continue
            
            curr_fmt = _fmt_int(_num(row.get('current_amount', 0)))
            prev_fmt = _fmt_int(_num(row.get('previous_amount', 0)))
        
        # Swap order: Post (label), Not (note), amounts
        from reportlab.platypus import Paragraph as RLParagraph
        # Apply semibold style directly to label if it's a heading or sum
        if is_heading or is_sum:
            label_style = ParagraphStyle('SemiboldLabel', parent=P, fontName='Roboto-Medium')
            label_para = RLParagraph(label, label_style)
            # Also apply semibold to amounts for sum rows (not for headings which have empty amounts)
            if is_sum and curr_fmt:  # Sum rows have amounts
                amount_style = ParagraphStyle('SemiboldAmount', parent=P, fontName='Roboto-Medium', alignment=2)  # 2=RIGHT
                curr_para = RLParagraph(curr_fmt, amount_style)
                prev_para = RLParagraph(prev_fmt, amount_style)
                rr_table_data.append([label_para, note, curr_para, prev_para])
            else:  # Headings with empty amounts
                rr_table_data.append([label_para, note, curr_fmt, prev_fmt])
        else:
            label_para = RLParagraph(label, P)
            rr_table_data.append([label_para, note, curr_fmt, prev_fmt])
        
        # Track semibold rows (headings and sums) - still track for potential additional styling
        if is_heading or is_sum:
            semibold_rows.append(len(rr_table_data) - 1)  # Row index
        
        # Track sum rows for spacing after
        if is_sum:
            sum_rows.append(len(rr_table_data) - 1)
        
        # Track "Årets resultat" for spacing before
        if label == 'Årets resultat':
            arets_resultat_row = len(rr_table_data) - 1
    
    if len(rr_table_data) > 1:  # Has data beyond header
        # Col widths: Post (269pt fixed with wrap), Not (30pt), Year1 (80pt), Year2 (80pt)
        t = Table(rr_table_data, hAlign='LEFT', colWidths=[269, 30, 80, 80])
        # Custom style with right-aligned year headers
        style = TableStyle([
            ('FONT', (0,0), (-1,0), 'Roboto-Medium', 10),  # Semibold header row
            ('LINEBELOW', (0,0), (-1,0), 0.5, colors.Color(0, 0, 0, alpha=0.7)),  # Header underline
            ('ALIGN', (1,0), (1,-1), 'CENTER'),  # Center "Not" column (header and all rows)
            ('ALIGN', (2,0), (3,0), 'RIGHT'),  # Right-align year headers
            ('ALIGN', (2,1), (3,-1), 'RIGHT'),  # Right-align amounts
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('ROWSPACING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ])
        # Add 10pt space after sum rows
        for row_idx in sum_rows:
            style.add('BOTTOMPADDING', (0, row_idx), (-1, row_idx), 10)
        # Add 10pt space before "Årets resultat"
        if arets_resultat_row is not None:
            style.add('TOPPADDING', (0, arets_resultat_row), (-1, arets_resultat_row), 10)
        t.setStyle(style)
        elems.append(t)
    else:
        elems.append(Paragraph("Ingen data tillgänglig", P))
    
    # ===== 3. BALANSRÄKNING (TILLGÅNGAR) =====
    elems.append(PageBreak())
    elems.append(Paragraph("Balansräkning", H0))
    elems.append(Spacer(1, 16))  # 2 line breaks
    
    # Define H2 headings for BR Tillgångar (larger, semibold, no amounts)
    br_assets_h2_headings = [
        'Tillgångar', 'Anläggningstillgångar', 'Omsättningstillgångar'
    ]
    # Define H1 headings for BR Tillgångar (semibold, no amounts)
    br_assets_h1_headings = [
        'Immateriella anläggningstillgångar',
        'Materiella anläggningstillgångar', 'Finansiella anläggningstillgångar',
        'Varulager m.m.', 'Kortfristiga fordringar',
        'Kortfristiga placeringar', 'Kassa och bank'
    ]
    # All headings combined
    br_assets_headings = br_assets_h2_headings + br_assets_h1_headings
    
    # Define sum rows for BR Tillgångar (semibold for both text and amounts)
    br_assets_sum_rows = [
        'Summa immateriella anläggningstillgångar', 'Summa materiella anläggningstillgångar',
        'Summa finansiella anläggningstillgångar', 'Summa anläggningstillgångar',
        'Summa varulager m.m.', 'Summa kortfristiga fordringar',
        'Summa kortfristiga placeringar', 'Summa kassa och bank',
        'Summa omsättningstillgångar', 'Summa tillgångar'  # Added Summa tillgångar
    ]
    
    # Rows to hide (equity headings that belong in the second table)
    br_assets_rows_to_hide = [
        'Eget kapital och skulder', 'Eget kapital', 'Bundet eget kapital', 'Fritt eget kapital'
    ]
    
    # Helper function to check if a block_group has content (same as RR)
    def block_has_content_br_assets(block_group: str) -> bool:
        """Check if any non-heading row in this block has non-zero amounts"""
        if not block_group:
            return True  # Items without block_group always show
        
        for row in br_data:
            if row.get('type') != 'asset':
                continue
            if row.get('block_group') != block_group:
                continue
            label = row.get('label', '')
            
            # Skip hidden rows
            if label in br_assets_rows_to_hide:
                continue
            
            # Skip headings and sums
            row_is_heading = any(h == label for h in br_assets_headings)
            row_is_sum = any(s == label or (s in label and label.startswith('Summa')) for s in br_assets_sum_rows)
            
            if row_is_heading or row_is_sum:
                continue
            
            # Check if this row has non-zero amount or always_show
            if row.get('always_show'):
                return True
            curr = _num(row.get('current_amount', 0))
            prev = _num(row.get('previous_amount', 0))
            if curr != 0 or prev != 0:
                return True
        
        return False
    
    br_assets = [r for r in br_data if r.get('type') == 'asset']
    # Header: Post (no text), Not, year end dates (right-aligned)
    br_assets_table = [["", "Not", current_year_header, previous_year_header]]
    table_cmds = []  # Per-row style commands
    
    for row in br_assets:
        if row.get('show_tag') == False:
            continue
        
        label = row.get('label', '').strip()
        block_group = row.get('block_group', '')
        
        # Hide "Tillgångar" (page 1 top-level heading)
        if label == 'Tillgångar':
            continue
        
        # Hide rows that belong in the second table
        if label in br_assets_rows_to_hide:
            continue
        
        # Check if this is a heading or sum row
        is_sum = False
        is_h2_heading = False
        is_h1_heading = False
        
        # Check sum rows first
        for sum_label in br_assets_sum_rows:
            if sum_label == label or (sum_label in label and label.startswith('Summa')):
                is_sum = True
                break
        
        # If not a sum, check headings
        if not is_sum:
            for heading in br_assets_h2_headings:
                if heading == label:
                    is_h2_heading = True
                    break
            if not is_h2_heading:
                for heading in br_assets_h1_headings:
                    if heading == label:
                        is_h1_heading = True
                        break
        
        is_heading = is_h2_heading or is_h1_heading
        
        # Block hiding logic - but not for always_show headings
        if block_group and not block_has_content_br_assets(block_group):
            # If this is a heading with always_show=true, show it anyway
            if not (is_heading and row.get('always_show')):
                continue
        
        note = str(row.get('note_number', '')) if row.get('note_number') else ''
        
        # For heading rows: show empty amounts
        if is_heading:
            curr_fmt = ''
            prev_fmt = ''
        else:
            # Filter zero rows (unless always_show or sum)
            if not row.get('always_show') and not is_sum:
                curr = _num(row.get('current_amount', 0))
                prev = _num(row.get('previous_amount', 0))
                if curr == 0 and prev == 0:
                    continue
            
            curr_fmt = _fmt_int(_num(row.get('current_amount', 0)))
            prev_fmt = _fmt_int(_num(row.get('previous_amount', 0)))
        
        # Add row as plain strings
        br_assets_table.append([label, note, curr_fmt, prev_fmt])
        r = len(br_assets_table) - 1  # Current row index
        
        # Default row padding
        table_cmds += [
            ('TOPPADDING', (0,r), (-1,r), 0),
            ('BOTTOMPADDING', (0,r), (-1,r), BR_ROW_SPACING),  # Add spacing between rows
            ('LEFTPADDING', (0,r), (-1,r), 0),
            ('RIGHTPADDING', (0,r), (-1,r), 8),
            ('VALIGN', (0,r), (-1,r), 'TOP'),
        ]
        
        # Apply heading/sum styles
        if is_h2_heading:
            table_cmds += [
                ('FONT', (0,r), (0,r), 'Roboto-Medium', BR_H2_SIZE),
                ('TOPPADDING', (0,r), (-1,r), BR_H2_SPACE_BEFORE),  # 8pt space before H2
                ('BOTTOMPADDING', (0,r), (-1,r), BR_H2_SPACE_AFTER),  # 12pt space after H2
            ]
        elif is_h1_heading:
            table_cmds += [
                ('FONT', (0,r), (0,r), 'Roboto-Medium', BR_H1_SIZE),  # Semibold
                # NO extra bottom padding on H1 so its block starts immediately
            ]
        elif is_sum:
            # Semibold for sum rows (both label and amounts)
            table_cmds += [
                ('FONT', (0,r), (0,r), 'Roboto-Medium', 10),
                ('FONT', (2,r), (3,r), 'Roboto-Medium', 10),
                ('BOTTOMPADDING', (0,r), (-1,r), 10),  # 10pt space after sums
            ]
    
    if len(br_assets_table) > 1:
        # Col widths: Post (269pt fixed with wrap), Not (30pt), Year1 (80pt), Year2 (80pt)
        t = Table(br_assets_table, hAlign='LEFT', colWidths=[269, 30, 80, 80])
        # Base style + per-row commands
        base_style = [
            ('FONT', (0,0), (-1,0), 'Roboto-Medium', 10),  # Header row semibold
            ('FONT', (0,1), (-1,-1), 'Roboto', 10),  # Data rows regular Roboto
            ('LINEBELOW', (0,0), (-1,0), 0.5, colors.Color(0, 0, 0, alpha=0.7)),
            ('ALIGN', (1,0), (1,-1), 'CENTER'),  # Center "Not" column
            ('ALIGN', (2,0), (3,0), 'RIGHT'),  # Right-align year headers
            ('ALIGN', (2,1), (3,-1), 'RIGHT'),  # Right-align amounts
            ('ROWSPACING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ]
        t.setStyle(TableStyle(base_style + table_cmds))
        elems.append(t)
    else:
        elems.append(Paragraph("Ingen data tillgänglig", P))
    
    # ===== 4. BALANSRÄKNING (EGET KAPITAL OCH SKULDER) =====
    elems.append(PageBreak())
    elems.append(Paragraph("Balansräkning", H0))
    elems.append(Spacer(1, 16))  # 2 line breaks
    
    # Define sum rows for BR Eget kapital och skulder (semibold for both text and amounts)
    br_equity_liab_sum_rows = [
        'Summa bundet eget kapital', 'Summa fritt eget kapital', 'Summa eget kapital',
        'Summa obeskattade reserver', 'Summa avsättningar',
        'Summa långfristiga skulder', 'Summa kortfristiga skulder',
        'Summa eget kapital och skulder'
    ]
    
    # Helper function to check if a block_group has content (use style field)
    def block_has_content_br_equity_liab(block_group: str) -> bool:
        """Check if any non-heading row in this block has non-zero amounts"""
        if not block_group:
            return True  # Items without block_group always show
        
        for row in br_data:
            if row.get('type') not in ['equity', 'liability']:
                continue
            if row.get('block_group') != block_group:
                continue
            
            style = row.get('style', '')
            label = row.get('label', '')
            
            # Skip headings (H0, H1, H2, H3) and sums
            row_is_heading = style in ['H0', 'H1', 'H2', 'H3']
            row_is_sum = any(s == label or (s in label and label.startswith('Summa')) for s in br_equity_liab_sum_rows)
            
            if row_is_heading or row_is_sum:
                continue
            
            # Check if this row has non-zero amount or always_show
            if row.get('always_show'):
                return True
            curr = _num(row.get('current_amount', 0))
            prev = _num(row.get('previous_amount', 0))
            if curr != 0 or prev != 0:
                return True
        
        return False
    
    # Include equity/liability rows AND any heading rows (style H0-H3) regardless of type
    def _is_br_heading(item: dict) -> bool:
        return item.get('style') in ['H0', 'H1', 'H2', 'H3']
    
    br_equity_liab = [
        r for r in br_data
        if (r.get('type') in ['equity', 'liability']) or _is_br_heading(r)
    ]
    
    # Headings that must NOT appear on the equity & liabilities page
    HIDE_HEADINGS_BR_EQ = {
        'Balansräkning',
        'Tillgångar',
        'Tecknat men ej inbetalt kapital',
        'Anläggningstillgångar',
        'Omsättningstillgångar',
        'Eget kapital och skulder',  # top-level page-1 heading, not here
    }
    
    # Force-correct some headings to H1 (10pt) regardless of incoming style
    FORCE_H1_EQ = {
        'Kortfristiga skulder', 
        'Långfristiga skulder',
        'Avsättningar',
        'Bundet eget kapital', 
        'Fritt eget kapital'
    }
    
    # Header: Post (no text), Not, year end dates (right-aligned)
    br_eq_table = [["", "Not", current_year_header, previous_year_header]]
    table_cmds_eq = []  # Per-row style commands
    skulder_header_added = False  # Track if we've added the "Skulder" header
    
    # Helper: Check if row should show (headings show if block has content)
    def should_show_row_br_equity(item: dict) -> bool:
        """Determine if a row should be shown based on frontend logic"""
        style = item.get('style', '')
        block_group = item.get('block_group', '')
        
        # Check if this is a heading based on style field (H0, H1, H2, H3)
        is_heading = style in ['H0', 'H1', 'H2', 'H3']
        
        # For headings: hide entire block (including heading) if it has no content
        # UNLESS the heading itself has always_show=true
        if is_heading:
            if block_group and not block_has_content_br_equity_liab(block_group):
                # Show anyway if always_show=true
                if not item.get('always_show'):
                    return False
            # Otherwise show the heading
            return True
        
        # For non-headings, check amounts or always_show
        has_non_zero = (item.get('current_amount') not in [None, 0]) or \
                      (item.get('previous_amount') not in [None, 0])
        is_always_show = item.get('always_show') == True
        has_note = item.get('note_number') is not None
        
        return has_non_zero or is_always_show or has_note
    
    for row in br_equity_liab:
        if row.get('show_tag') == False:
            continue
        
        label = row.get('label', '').strip()
        
        # Hide assets-page and global headings on this page
        if label in HIDE_HEADINGS_BR_EQ:
            continue
        
        # Use frontend logic to determine if row should show
        if not should_show_row_br_equity(row):
            continue
        note = str(row.get('note_number', '')) if row.get('note_number') else ''
        style = row.get('style', '')
        
        # Normalize specific headings to H1 (10pt)
        if label in FORCE_H1_EQ:
            style = 'H1'
        
        # Check if this is a heading or sum row based on style
        is_heading = style in ['H0', 'H1', 'H2', 'H3']
        is_sum = any(sum_label == label or (sum_label in label and label.startswith('Summa')) 
                    for sum_label in br_equity_liab_sum_rows)
        
        # Format amounts
        if is_heading:
            curr_fmt = ''
            prev_fmt = ''
        else:
            curr_fmt = _fmt_int(_num(row.get('current_amount', 0)))
            prev_fmt = _fmt_int(_num(row.get('previous_amount', 0)))
        
        # Add row as plain strings
        br_eq_table.append([label, note, curr_fmt, prev_fmt])
        r = len(br_eq_table) - 1  # Current row index
        
        # Default row padding
        table_cmds_eq += [
            ('TOPPADDING', (0,r), (-1,r), 0),
            ('BOTTOMPADDING', (0,r), (-1,r), BR_ROW_SPACING),  # Add spacing between rows
            ('LEFTPADDING', (0,r), (-1,r), 0),
            ('RIGHTPADDING', (0,r), (-1,r), 8),
            ('VALIGN', (0,r), (-1,r), 'TOP'),
        ]
        
        # Apply heading/sum styles
        if is_heading:
            # H2 or H0 → 11pt (larger headings)
            # H1 or H3 → 10pt (smaller headings)
            if style in ['H2', 'H0']:
                table_cmds_eq += [
                    ('FONT', (0,r), (0,r), 'Roboto-Medium', BR_H2_SIZE),
                    ('TOPPADDING', (0,r), (-1,r), BR_H2_SPACE_BEFORE),  # 8pt space before H2
                    ('BOTTOMPADDING', (0,r), (-1,r), BR_H2_SPACE_AFTER),  # 12pt space after H2
                ]
            else:  # H1, H3
                table_cmds_eq += [
                    ('FONT', (0,r), (0,r), 'Roboto-Medium', BR_H1_SIZE),  # Semibold
                    # NO extra bottom padding on H1 so its block starts immediately
                ]
        elif is_sum:
            # Semibold for sum rows (both label and amounts)
            table_cmds_eq += [
                ('FONT', (0,r), (0,r), 'Roboto-Medium', 10),
                ('FONT', (2,r), (3,r), 'Roboto-Medium', 10),
                ('BOTTOMPADDING', (0,r), (-1,r), 10),  # 10pt space after sums
            ]
        
        # Insert "Skulder" header after "Summa eget kapital"
        if label == 'Summa eget kapital' and not skulder_header_added:
            skulder_header_added = True
            # Add "Skulder" as H2 heading (no amounts)
            br_eq_table.append(['Skulder', '', '', ''])
            r_skulder = len(br_eq_table) - 1
            
            # Apply H2 styling to "Skulder" header
            table_cmds_eq += [
                ('TOPPADDING', (0, r_skulder), (-1, r_skulder), 0),
                ('BOTTOMPADDING', (0, r_skulder), (-1, r_skulder), 0),
                ('LEFTPADDING', (0, r_skulder), (-1, r_skulder), 0),
                ('RIGHTPADDING', (0, r_skulder), (-1, r_skulder), 8),
                ('VALIGN', (0, r_skulder), (-1, r_skulder), 'TOP'),
                ('FONT', (0, r_skulder), (0, r_skulder), 'Roboto-Medium', BR_H2_SIZE),
                ('TOPPADDING', (0, r_skulder), (-1, r_skulder), BR_H2_SPACE_BEFORE),
                ('BOTTOMPADDING', (0, r_skulder), (-1, r_skulder), BR_H2_SPACE_AFTER),
            ]
    
    if len(br_eq_table) > 1:
        # Col widths: Post (269pt fixed with wrap), Not (30pt), Year1 (80pt), Year2 (80pt)
        t = Table(br_eq_table, hAlign='LEFT', colWidths=[269, 30, 80, 80])
        # Base style + per-row commands
        base_style = [
            ('FONT', (0,0), (-1,0), 'Roboto-Medium', 10),  # Header row semibold
            ('FONT', (0,1), (-1,-1), 'Roboto', 10),  # Data rows regular Roboto
            ('LINEBELOW', (0,0), (-1,0), 0.5, colors.Color(0, 0, 0, alpha=0.7)),
            ('ALIGN', (1,0), (1,-1), 'CENTER'),  # Center "Not" column
            ('ALIGN', (2,0), (3,0), 'RIGHT'),  # Right-align year headers
            ('ALIGN', (2,1), (3,-1), 'RIGHT'),  # Right-align amounts
            ('ROWSPACING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ]
        t.setStyle(TableStyle(base_style + table_cmds_eq))
        elems.append(t)
    else:
        elems.append(Paragraph("Ingen data tillgänglig", P))
    
    # ===== 5. NOTER =====
    elems.append(PageBreak())
    elems.append(Paragraph("Noter", H0))
    elems.append(Spacer(1, 8))
    
    # Group notes by block
    blocks = {}
    for note in noter_data:
        block = note.get('block') or 'Övriga'  # Handle None values
        if block not in blocks:
            blocks[block] = []
        blocks[block].append(note)
    
    # Collect and filter blocks, then assign note numbers
    rendered_blocks = _collect_visible_note_blocks(blocks, company_data, noter_toggle_on, noter_block_toggles, scraped_company_data)
    
    # Render each block with assigned note number
    for block_name, block_title, note_number, visible_items in rendered_blocks:
        _render_note_block(elems, block_name, block_title, note_number, visible_items, company_data, H1, P)
    
    # Build PDF
    doc.build(elems)
    return buf.getvalue()

# ---- Noter visibility logic (mirror of Noter.tsx) ----
# Notes that must always show
ALWAYS_SHOW_NOTES = {
    "Redovisningsprinciper",  # Not 1
    "Medeltal anställda",     # Not 2
    "NOT1",  # Block name
    "NOT2",  # Block name
}

# Fixed note numbers
NOTE_NUM_FIXED = {
    "Redovisningsprinciper": 1,
    "Medeltal anställda": 2,
    "NOT1": 1,
    "NOT2": 2,
}

def _fmt_note_title(nr: int, title: str) -> str:
    """Format note title by removing '–' and cleaning up spaces"""
    t = (title or "").replace(" – ", " ").replace(" - ", " ").replace("–", " ").replace("-", " ")
    # Clean up multiple spaces
    import re
    t = re.sub(r'\s+', ' ', t).strip()
    return f"Not {nr} {t}".strip()

def _is_heading_style(s):
    """Check if style is a heading (H0, H1, H2, H3)"""
    return (s or "NORMAL") in {"H0", "H1", "H2", "H3"}

def _is_head(s):
    """Alias for _is_heading_style"""
    return _is_heading_style(s)

def _is_sum_line(s):
    """Check if style is a sum line (S2, S3, TS2, TS3)"""
    return (s or "") in {"S2", "S3", "TS2", "TS3"}

def _is_sum(s):
    """Alias for _is_sum_line"""
    return _is_sum_line(s)

def _is_subtotal_trigger(s):
    """Check if style is a subtotal trigger (S2, TS2)"""
    return (s or "") in {"S2", "TS2"}

def _is_s2(s):
    """Alias for _is_subtotal_trigger"""
    return _is_subtotal_trigger(s)

def _sum_group_above(rows, idx, key):
    """Sum content rows above current row until hitting a heading or subtotal"""
    total = 0.0
    j = idx - 1
    while j >= 0:
        r = rows[j]
        st = r.get("style", "")
        if _is_head(st) or _is_s2(st):  # stop at head or another subtotal
            break
        total += _num(r.get(key, 0))
        j -= 1
    return total

def _s2_amount_by_label(visible, key, startswith_text):
    """Find S2 row by label and return its subtotal"""
    sl = startswith_text.lower()
    for i, rr in enumerate(visible):
        if not _is_s2(rr.get('style', '')):
            continue
        t = (rr.get('row_title') or '').lower()
        if t.startswith(sl):
            return _sum_group_above(visible, i, key)
    return 0.0

def compute_redovisat_varde(block_title, visible, key):
    """Calculate Redovisat värde from visible S2 UB rows (exactly like Preview)"""
    bt = (block_title or '').lower()
    a = _s2_amount_by_label(visible, key, 'utgående anskaffningsvärden')
    v = _s2_amount_by_label(visible, key, 'utgående avskrivningar')
    n = _s2_amount_by_label(visible, key, 'utgående nedskrivningar')
    total = a + v + n
    if 'bygg' in bt:  # only for Byggnader och mark
        u = _s2_amount_by_label(visible, key, 'utgående uppskrivningar')
        total += u
    
    return total

def build_visible_with_headings_pdf(items, toggle_on=False):
    """
    items: list of dicts with keys:
      row_id, row_title, current_amount, previous_amount, toggle_show, always_show, style, variable_name, ...
    toggle_on: when True, rows with toggle_show=True become visible even if amounts are zero
    Mirrors Noter.tsx buildVisibleWithHeadings.
    """
    # --- Pass 1: base visibility (row itself is visible?) ---
    base_visible = []
    for it in items:
        if it.get("always_show"):
            base_visible.append(it)
            continue
        cur = _num(it.get("current_amount", 0))
        prev = _num(it.get("previous_amount", 0))
        if cur != 0 or prev != 0 or (it.get("toggle_show") is True and toggle_on):
            base_visible.append(it)

    base_ids = {it.get("row_id") for it in base_visible}

    # Rows allowed to TRIGGER headings/subtotals (content rows only)
    triggers = []
    for it in items:
        if _is_sum_line(it.get("style")): 
            continue
        if it.get("always_show"):
            continue
        cur = _num(it.get("current_amount", 0))
        prev = _num(it.get("previous_amount", 0))
        if cur != 0 or prev != 0 or (it.get("toggle_show") is True and toggle_on):
            triggers.append(it)
    trigger_ids = {it.get("row_id") for it in triggers}

    # --- Pass 2: add H2/H3 headings + S2/TS2 subtotals based on nearby trigger rows ---
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
        if _is_heading_style(sty):
            show = False
            j = i + 1
            while j < n:
                nxt = items[j]
                if _is_heading_style(nxt.get("style")):
                    break
                if nxt.get("row_id") in trigger_ids:
                    show = True
                    break
                j += 1
            if show:
                out.append(it)
                continue

        # Subtotals (S2/TS2): show if ANY preceding trigger row until previous heading/S2 is present
        if _is_subtotal_trigger(sty):
            show = False
            j = i - 1
            while j >= 0:
                prv = items[j]
                if _is_heading_style(prv.get("style")) or _is_subtotal_trigger(prv.get("style")):
                    break
                if prv.get("row_id") in trigger_ids:
                    show = True
                    break
                j -= 1
            if show:
                out.append(it)
                continue

    return out

def _has_nonzero_content(rows):
    """Check if block has any non-zero content rows (excluding headings and subtotals)"""
    for r in rows:
        s = r.get("style", "")
        if _is_heading_style(s) or _is_subtotal_trigger(s):
            continue
        if (_num(r.get("current_amount", 0)) != 0) or (_num(r.get("previous_amount", 0)) != 0):
            return True
    return False

def _collect_visible_note_blocks(blocks, company_data, toggle_on=False, block_toggles=None, scraped_data=None):
    """
    Collect visible note blocks, apply visibility filters, and assign note numbers.
    Returns list of (block_name, block_title, note_number, visible_items)
    toggle_on: Global "visa alla rader" toggle (usually False for PDF)
    block_toggles: Dict of per-block toggles (e.g., {'sakerhet-visibility': True, 'eventual-visibility': True})
    scraped_data: Scraped company data (for Medeltal anställda, etc.)
    """
    block_toggles = block_toggles or {}
    scraped_data = scraped_data or {}
    
    # Block title mapping
    block_title_map = {
        'NOT1': 'Redovisningsprinciper',
        'NOT2': 'Medeltal anställda',
        'KONCERN': 'Andelar i koncernföretag',
        'INTRESSEFTG': 'Andelar i intresseföretag',
        'BYGG': 'Byggnader och mark',
        'INV': 'Inventarier, verktyg och installationer',  # Fixed order: INV before MASKIN
        'MASKIN': 'Maskiner och andra tekniska anläggningar',  # Fixed title
        'MAT': 'Övriga materiella anläggningstillgångar',  # Fixed title
        'LVP': 'Långfristiga fordringar',
        'FORDR_KONCERN': 'Fordringar hos koncernföretag',
        'FORDR_INTRESSE': 'Fordringar hos intresseföretag',
        'FORDR_OVRIG': 'Övriga fordringar',
        'EVENTUAL': 'Eventualförpliktelser',
        'SAKERHET': 'Ställda säkerheter',
        'OVRIGA': 'Övriga upplysningar',
    }
    
    collected = []
    
    # Define explicit order to match preview (NOT1, NOT2, then by asset type)
    note_order = [
        'NOT1', 'NOT2',  # Always first
        'BYGG',   # Not 3 - Byggnader och mark
        'MASKIN', # Not 4 - Maskiner och andra tekniska anläggningar (BEFORE INV in preview!)
        'INV',    # Not 5 - Inventarier, verktyg och installationer (AFTER MASKIN in preview!)
        'MAT',    # Not 6 - Övriga materiella
        'KONCERN', 'INTRESSEFTG', 'LVP',  # Financial assets
        'FORDRKONC', 'FORDRINTRE', 'FORDROVRFTG', 'OVRIGAFTG',  # Receivables
        'EVENTUAL', 'SAKERHET',  # Contingencies
        'OVRIGA', 'OTHER'  # Other notes
    ]
    
    # Collect blocks in the defined order, then add any blocks not in the order list
    remaining_block_names = []
    for block_name in blocks.keys():
        if block_name not in note_order:
            remaining_block_names.append(block_name)
    
    # Process in explicit order, then add any remaining blocks
    ordered_blocks = [b for b in note_order if b in blocks] + sorted(remaining_block_names)
    
    for block_name in ordered_blocks:
        if block_name not in blocks:
            continue
            
        items = blocks[block_name]
        block_title = block_title_map.get(block_name, block_name)
        
        # Special handling for NOT2 "Medeltal anställda" - ensure single row display
        if block_title.strip().lower() == "medeltal anställda" or block_name == "NOT2":
            # Prefer values from noter data (scraped + edited)
            emp_current = 0
            emp_previous = 0
            
            if items and len(items) > 0:
                # Try to find the explicit row for employee count
                # PRIORITY: Items with variable_name set (these have user edits)
                src = None
                
                # First pass: Look for items with variable_name (most reliable)
                for r in items:
                    vn = r.get("variable_name", "")
                    if vn in {"ant_anstallda", "medelantal_anstallda_under_aret"}:
                        src = r
                        break
                
                # Second pass: Look for title match if no variable_name match
                if not src:
                    for r in items:
                        rt = (r.get("row_title") or "").lower()
                        if "medelantalet anställda under året" in rt or rt == "medelantalet anställda":
                            # Only accept if this looks like the data row (has variable_name or non-zero values)
                            if r.get("variable_name") or r.get("current_amount") or r.get("previous_amount"):
                                src = r
                                break
                
                # Fallback to first item with variable_name
                if not src:
                    for r in items:
                        if r.get("variable_name"):
                            src = r
                            break
                
                # Last resort: first item
                if not src and items:
                    src = items[0]
                
                if src:
                    emp_current = _num(src.get('current_amount', 0))
                    emp_previous = _num(src.get('previous_amount', 0))
            
            # Fallback to scraper data for missing values
            # Check each value independently (user might edit current but not previous)
            if emp_previous == 0:
                # Try scraped data for previous year
                emp_previous = _num(scraped_data.get('medeltal_anstallda') or 
                                   scraped_data.get('medeltal_anstallda_prev') or
                                   scraped_data.get('employees') or
                                   company_data.get("employees", 0))
            
            if emp_current == 0:
                # Try scraped data for current year, fallback to previous
                emp_current = _num(scraped_data.get('medeltal_anstallda_cur') or emp_previous)
            
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
        
        # Check block type early for all subsequent logic
        block_name_lower = block_name.lower()
        block_title_lower = block_title.lower()
        
        is_ovriga = (block_name == 'OVRIGA')
        is_eventual = (block_name_lower in {"eventualförpliktelser", "eventual"} or
                      block_title_lower in {"eventualförpliktelser", "eventual"})
        is_sakerhet = (block_name_lower in {"säkerheter", "säkerhet", "sakerhet"} or
                      block_title_lower in {"säkerheter", "säkerhet", "sakerhet"})
        
        # Special handling for OVRIGA - always show if there's moderbolag data (mirrors frontend logic)
        moderbolag = scraped_data.get('moderbolag')
        
        if is_ovriga:
            if not moderbolag:
                # Check if block has any non-zero content
                has_content = any(
                    _num(it.get('current_amount', 0)) != 0 or 
                    _num(it.get('previous_amount', 0)) != 0 
                    for it in items
                )
                if not has_content:
                    continue
        
        # Check if this block should be hidden (Eventualförpliktelser, Säkerheter)
        # These blocks require explicit toggle to be visible
        
        if is_eventual or is_sakerhet:
            # Check block-specific toggle (e.g., 'eventual-visibility', 'sakerhet-visibility')
            toggle_key = 'eventual-visibility' if is_eventual else 'sakerhet-visibility'
            block_visible = block_toggles.get(toggle_key, False)
            
            if not block_visible:
                continue
        
        # Force always_show for NOT1 and NOT2
        force_always = (block_name in ALWAYS_SHOW_NOTES or block_title in ALWAYS_SHOW_NOTES)
        if force_always:
            for it in items:
                it["always_show"] = True
        
        # For EVENTUAL and SAKERHET blocks, DON'T use toggle for visibility in PDF
        # The toggle is only used to show the block, not to show zero-value rows within it
        # Zero-value toggle_show rows are only for editing, not for final PDF
        effective_toggle = toggle_on  # Keep as False for PDF (no zero rows)
        
        # For EVENTUAL and SAKERHET blocks, check if toggle is enabled BEFORE filtering
        # (we need to show the block if toggle is on, even if rows get filtered out)
        block_toggle_enabled = False
        if is_eventual or is_sakerhet:
            toggle_key = 'eventual-visibility' if is_eventual else 'sakerhet-visibility'
            block_toggle_enabled = block_toggles.get(toggle_key, False)
        
        # Apply visibility logic
        visible = build_visible_with_headings_pdf(items, toggle_on=effective_toggle)
        
        # Skip rows before first heading (but not for NOT1/NOT2 which don't have headings)
        if block_name not in ['NOT1', 'NOT2']:
            pruned = []
            seen_heading = False
            for r in visible:
                if _is_heading_style(r.get("style")):
                    seen_heading = True
                    pruned.append(r)
                elif seen_heading:
                    pruned.append(r)
            visible = pruned
        
        # Skip block if no visible items (UNLESS it's EVENTUAL/SAKERHET with toggle enabled or OVRIGA with moderbolag)
        ovriga_with_moderbolag = (is_ovriga and moderbolag)
        if not visible:
            # Allow empty blocks for: EVENTUAL/SAKERHET with toggle, OVRIGA with moderbolag, or forced blocks
            if not (block_toggle_enabled or ovriga_with_moderbolag or force_always):
                continue
        
        # Skip block if not force-always, not toggle-enabled, has no non-zero content, and not OVRIGA with moderbolag
        if (not force_always) and (not block_toggle_enabled) and (not ovriga_with_moderbolag) and (not _has_nonzero_content(visible)):
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

def _render_note_block(elems, block_name, block_title, note_number, visible, company_data, H1, P):
    """Render a single note block with its table - uses pre-filtered visible items"""
    
    # Get fiscal year info from company_data
    fiscal_year = company_data.get('fiscal_year', 2024)
    prev_year = fiscal_year - 1
    
    # Start building note flowables (will wrap in KeepTogether)
    note_flow = []
    
    # Format and render title
    title = _fmt_note_title(note_number, block_title)
    note_flow.append(Paragraph(title, H1))
    note_flow.append(Spacer(1, 10))  # 10pt after heading
    
    # For OVRIGA (text note with moderbolag info), render text first
    if block_name == 'OVRIGA':
        scraped_data = company_data.get('scraped_company_data', {})
        moderbolag = scraped_data.get('moderbolag')
        moderbolag_orgnr = scraped_data.get('moderbolag_orgnr')
        sate = scraped_data.get('säte')
        
        if moderbolag:
            text = f"Företaget är ett dotterbolag till {moderbolag} med organisationsnummer {moderbolag_orgnr} med säte i {sate}, som upprättar koncernredovisning."
            note_flow.append(Paragraph(text, P))
            note_flow.append(Spacer(1, 10))
        
        # If there are visible items with amounts, render them as table
        if visible and any(_num(it.get('current_amount', 0)) != 0 or _num(it.get('previous_amount', 0)) != 0 for it in visible):
            # Continue to table rendering below
            pass
        else:
            # Just text, no table needed
            note_flow.append(Spacer(1, 16))
            elems.append(KeepTogether(note_flow))
            return
    
    # For NOT1 (text note + depreciation table), render as paragraphs plus table
    if block_name == 'NOT1':
        # Render the text paragraph(s)
        for note in visible:
            text = note.get('variable_text', note.get('row_title', ''))
            if text:
                note_flow.append(Paragraph(text, P))
        
        # Add spacing before the depreciation table
        note_flow.append(Spacer(1, 10))
        
        # Build the depreciation table from company noterData
        noter_data = company_data.get('noterData', [])
        avskrtid_bygg = next((item['current_amount'] for item in noter_data if item.get('variable_name') == 'avskrtid_bygg'), 0)
        avskrtid_mask = next((item['current_amount'] for item in noter_data if item.get('variable_name') == 'avskrtid_mask'), 0)
        avskrtid_inv = next((item['current_amount'] for item in noter_data if item.get('variable_name') == 'avskrtid_inv'), 0)
        avskrtid_ovriga = next((item['current_amount'] for item in noter_data if item.get('variable_name') == 'avskrtid_ovriga'), 0)
        
        # Create the depreciation table
        depr_table_data = [
            ['Anläggningstillgångar', 'År'],
            ['Byggnader & mark', _fmt_int(avskrtid_bygg) if avskrtid_bygg else '0'],
            ['Maskiner och andra tekniska anläggningar', _fmt_int(avskrtid_mask) if avskrtid_mask else '0'],
            ['Inventarier, verktyg och installationer', _fmt_int(avskrtid_inv) if avskrtid_inv else '0'],
            ['Övriga materiella anläggningstillgångar', _fmt_int(avskrtid_ovriga) if avskrtid_ovriga else '0'],
        ]
        
        # Create table with appropriate column widths
        depr_table = Table(depr_table_data, hAlign='LEFT', colWidths=[320, 80])
        depr_style = TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 1.5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1.5),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ('ALIGN', (1,0), (1,-1), 'RIGHT'),  # Right-align "År" column
            ('FONT', (0,0), (-1,0), 'Roboto-Medium', 10),  # Header row semibold
            ('FONT', (0,1), (-1,-1), 'Roboto', 10),       # Data rows regular
            ('LINEBELOW', (0,0), (-1,0), 0.5, colors.Color(0, 0, 0, alpha=0.20)),  # Line under header
        ])
        depr_table.setStyle(depr_style)
        note_flow.append(depr_table)
        
        note_flow.append(Spacer(1, 16))  # gap before next note
        elems.append(KeepTogether(note_flow))
        return
    
    # Get period end dates from company_data (or years for NOT2)
    if block_name == 'NOT2':
        # NOT2 uses years instead of dates
        header_row = ["", str(fiscal_year), str(prev_year)]
    else:
        cur_end = company_data.get("currentPeriodEndDate") or f"{fiscal_year}-12-31"
        prev_end = company_data.get("previousPeriodEndDate") or f"{prev_year}-12-31"
        header_row = ["", cur_end, prev_end]
    
    # For other notes, render as table with style-aware formatting
    table_data = [header_row]
    
    # Clean style with only header line (no body lines) - mirrors RR
    note_style = [
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 1.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1.5),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('ALIGN', (1,0), (2,0), 'RIGHT'),
        ('ALIGN', (1,1), (2,-1), 'RIGHT'),
        ('FONT', (0,0), (-1,0), 'Roboto-Medium', 9),  # Header row
        ('FONT', (0,1), (-1,-1), 'Roboto', 10),       # Data rows (default)
        # keep one thin line only under the header (dates)
        ('LINEBELOW', (0,0), (-1,0), 0.5, colors.Color(0, 0, 0, alpha=0.20)),
    ]
    
    # Sub-headings that need 10pt space before them
    heading_kick = {"avskrivningar", "uppskrivningar", "nedskrivningar"}
    
    # Build table rows with proper styling
    for i, it in enumerate(visible):
        style = it.get('style', '')
        row_title = it.get('row_title', '')
        lbl = (row_title or '').strip().lower()
        
        # Check if this is a heading (no amounts)
        if _is_heading_style(style):
            curr_fmt = ''
            prev_fmt = ''
        else:
            # Detect Redovisat värde and calculate it specially
            is_redv = 'redovisat värde' in lbl or 'redovisat varde' in lbl or 'redovisat' in lbl
            if is_redv:
                cur = compute_redovisat_varde(block_title, visible, 'current_amount')
                prev = compute_redovisat_varde(block_title, visible, 'previous_amount')
            elif _is_s2(style):
                cur = _sum_group_above(visible, i, 'current_amount')
                prev = _sum_group_above(visible, i, 'previous_amount')
            else:
                cur = _num(it.get('current_amount', 0))
                prev = _num(it.get('previous_amount', 0))
            
            curr_fmt = _fmt_int(cur)
            prev_fmt = _fmt_int(prev)
        
        table_data.append([row_title, curr_fmt, prev_fmt])
        r = len(table_data) - 1  # Current row index
        
        # Apply semibold to headings
        if _is_heading_style(style):
            note_style.append(('FONT', (0,r), (0,r), 'Roboto-Medium', 10))
            # 10 pt space before sub-headings
            title = lbl
            if style in {'H1', 'H2', 'H3'} and title in heading_kick:
                note_style.append(('TOPPADDING', (0,r), (-1,r), 10))
        
        # Sums semibold + 10 pt before / 0 pt after "Redovisat värde"
        is_sum_label = (lbl.startswith('utgående ') or lbl.startswith('utgaende ') or 
                       lbl.startswith('summa ') or _is_s2(style))
        is_redv = ('redovisat värde' in lbl) or ('redovisat varde' in lbl)
        
        if is_sum_label or is_redv:
            note_style.append(('FONT', (0,r), (0,r), 'Roboto-Medium', 10))
            note_style.append(('FONT', (1,r), (2,r), 'Roboto-Medium', 10))
        
        if is_redv:
            note_style.append(('TOPPADDING', (0,r), (-1,r), 10))
            note_style.append(('BOTTOMPADDING', (0,r), (-1,r), 0))
    
    if len(table_data) > 1:
        # Column widths: mirror BR/RR (269, 80, 80) - no note number column
        col_widths = [269, 80, 80]
        
        t = Table(table_data, hAlign='LEFT', colWidths=col_widths)
        t.setStyle(TableStyle(note_style))
        note_flow.append(t)
        
        # Keep note together and add proper spacing
        elems.append(KeepTogether(note_flow))
        elems.append(Spacer(1, 16))  # gap to next note
