# pdf_annual_report.py
# Server-side PDF generation for full annual report using ReportLab
from io import BytesIO
from typing import Any, Dict, List, Tuple
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
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

def _num(v):
    try:
        if v is None: return 0
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
    Typography styles for PDF generation (24mm margins, compact spacing)
    H0: 16pt semibold, 0pt before, 4pt after (main titles like "Förvaltningsberättelse")
    H1: 12pt semibold, 14pt before, 6pt after (subsections like "Verksamheten", "Flerårsöversikt")
    P: 10pt regular, 12pt leading, 2pt after
    """
    ss = getSampleStyleSheet()
    
    # H0 - Main section titles (semibold)
    h0 = ParagraphStyle(
        'H0', 
        parent=ss['Heading1'], 
        fontName='Roboto-Medium', 
        fontSize=16, 
        spaceBefore=0, 
        spaceAfter=4
    )
    
    # H1 - Subsection headings (semibold)
    h1 = ParagraphStyle(
        'H1', 
        parent=ss['Heading2'], 
        fontName='Roboto-Medium', 
        fontSize=12, 
        spaceBefore=14, 
        spaceAfter=6
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
    
    small = ParagraphStyle('SMALL', parent=p, fontSize=9, textColor=colors.grey)
    return h0, h1, p, small

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

def _render_flerarsoversikt(elems, company_data, fiscal_year, H1, P):
    """Render Flerårsöversikt exactly as shown in frontend - 3 years from scraped data"""
    elems.append(Paragraph("Flerårsöversikt", H1))
    elems.append(Paragraph("Belopp i tkr", P))
    
    # Get flerårsöversikt data from companyData (comes from frontend state)
    flerars = company_data.get('flerarsoversikt', {})
    
    # If we have structured flerårsöversikt data, use it
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
            
            # Calculate current year values from rr/br data
            rr_data = company_data.get('seFileData', {}).get('rr_data', [])
            br_data = company_data.get('seFileData', {}).get('br_data', [])
            
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
    """Render Resultatdisposition section with correct row structure"""
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
    
    t = Table(table_data, hAlign='LEFT', colWidths=[280, 120])
    # Custom style for Resultatdisposition (no header underline, 0pt spacing, semibold Summa rows)
    style = TableStyle([
        ('FONT', (0,0), (-1,-1), 'Roboto', 10),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
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
        leftMargin=68,  # 24mm
        rightMargin=68, 
        topMargin=68, 
        bottomMargin=68
    )
    
    H0, H1, P, SMALL = _styles()
    elems: List[Any] = []
    
    # Extract company metadata
    name, orgnr, fiscal_year = _company_meta(company_data)
    prev_year = fiscal_year - 1 if fiscal_year else 0
    
    # Extract data sections
    se_data = company_data.get('seFileData', {})
    rr_data = se_data.get('rr_data', [])
    br_data = se_data.get('br_data', [])
    noter_data = company_data.get('noterData', [])
    
    # ===== 1. FÖRVALTNINGSBERÄTTELSE =====
    elems.append(Paragraph("Förvaltningsberättelse", H0))
    elems.append(Spacer(1, 8))
    
    verksamhet_text, vasentliga_text = _extract_fb_texts(company_data)
    
    elems.append(Paragraph("Verksamheten", H1))
    elems.append(Paragraph(verksamhet_text, P))
    elems.append(Spacer(1, 4))
    
    elems.append(Paragraph("Väsentliga händelser under räkenskapsåret", H1))
    elems.append(Paragraph(vasentliga_text, P))
    elems.append(Spacer(1, 8))
    
    # Flerårsöversikt
    _render_flerarsoversikt(elems, company_data, fiscal_year, H1, P)
    
    # Förändringar i eget kapital
    _render_forandringar_i_eget_kapital(elems, company_data, fiscal_year, prev_year, H1)
    
    # Resultatdisposition
    _render_resultatdisposition(elems, company_data, H1, P)
    
    # ===== 2. RESULTATRÄKNING =====
    elems.append(PageBreak())
    elems.append(Paragraph("Resultaträkning", H0))
    elems.append(Spacer(1, 8))
    
    rr_table_data = [["Not", "Post", str(fiscal_year), str(prev_year)]]
    for row in rr_data:
        # Filter logic: respect show_tag, always_show, hide zero rows
        if row.get('show_tag') == False:
            continue
        if not row.get('always_show'):
            curr = _num(row.get('current_amount', 0))
            prev = _num(row.get('previous_amount', 0))
            if curr == 0 and prev == 0:
                continue
        
        note = str(row.get('note_number', '')) if row.get('note_number') else ''
        label = row.get('label', '')
        curr_fmt = _fmt_int(_num(row.get('current_amount', 0)))
        prev_fmt = _fmt_int(_num(row.get('previous_amount', 0)))
        rr_table_data.append([note, label, curr_fmt, prev_fmt])
    
    if len(rr_table_data) > 1:  # Has data beyond header
        t = Table(rr_table_data, hAlign='LEFT', colWidths=[30, None, 80, 80])
        t.setStyle(_table_style())
        elems.append(t)
    else:
        elems.append(Paragraph("Ingen data tillgänglig", P))
    
    # ===== 3. BALANSRÄKNING (TILLGÅNGAR) =====
    elems.append(PageBreak())
    elems.append(Paragraph("Balansräkning (Tillgångar)", H0))
    elems.append(Spacer(1, 8))
    
    br_assets = [r for r in br_data if r.get('type') == 'asset']
    br_assets_table = [["Not", "Post", str(fiscal_year), str(prev_year)]]
    for row in br_assets:
        if row.get('show_tag') == False:
            continue
        if not row.get('always_show'):
            curr = _num(row.get('current_amount', 0))
            prev = _num(row.get('previous_amount', 0))
            if curr == 0 and prev == 0:
                continue
        
        note = str(row.get('note_number', '')) if row.get('note_number') else ''
        label = row.get('label', '')
        curr_fmt = _fmt_int(_num(row.get('current_amount', 0)))
        prev_fmt = _fmt_int(_num(row.get('previous_amount', 0)))
        br_assets_table.append([note, label, curr_fmt, prev_fmt])
    
    if len(br_assets_table) > 1:
        t = Table(br_assets_table, hAlign='LEFT', colWidths=[30, None, 80, 80])
        t.setStyle(_table_style())
        elems.append(t)
    else:
        elems.append(Paragraph("Ingen data tillgänglig", P))
    
    # ===== 4. BALANSRÄKNING (EGET KAPITAL OCH SKULDER) =====
    elems.append(PageBreak())
    elems.append(Paragraph("Balansräkning (Eget kapital och skulder)", H0))
    elems.append(Spacer(1, 8))
    
    br_equity_liab = [r for r in br_data if r.get('type') in ['equity', 'liability']]
    br_eq_table = [["Not", "Post", str(fiscal_year), str(prev_year)]]
    for row in br_equity_liab:
        if row.get('show_tag') == False:
            continue
        if not row.get('always_show'):
            curr = _num(row.get('current_amount', 0))
            prev = _num(row.get('previous_amount', 0))
            if curr == 0 and prev == 0:
                continue
        
        note = str(row.get('note_number', '')) if row.get('note_number') else ''
        label = row.get('label', '')
        curr_fmt = _fmt_int(_num(row.get('current_amount', 0)))
        prev_fmt = _fmt_int(_num(row.get('previous_amount', 0)))
        br_eq_table.append([note, label, curr_fmt, prev_fmt])
    
    if len(br_eq_table) > 1:
        t = Table(br_eq_table, hAlign='LEFT', colWidths=[30, None, 80, 80])
        t.setStyle(_table_style())
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
    
    # Render blocks (NOT1, NOT2 first, then others)
    priority_blocks = ['NOT1', 'NOT2']
    for block_name in priority_blocks:
        if block_name in blocks:
            _render_note_block(elems, block_name, blocks[block_name], fiscal_year, prev_year, H1, P)
    
    # Sort remaining blocks, filtering out None values
    remaining_blocks = [b for b in blocks.keys() if b and b not in priority_blocks]
    for block_name in sorted(remaining_blocks):
        _render_note_block(elems, block_name, blocks[block_name], fiscal_year, prev_year, H1, P)
    
    # Build PDF
    doc.build(elems)
    return buf.getvalue()

def _render_note_block(elems, block_name, notes, fiscal_year, prev_year, H1, P):
    """Render a single note block with its table"""
    # Filter visible notes
    visible = []
    for n in notes:
        if n.get('show_tag') == False or n.get('toggle_show') == False:
            continue
        if n.get('always_show'):
            visible.append(n)
            continue
        curr = _num(n.get('current_amount', 0))
        prev = _num(n.get('previous_amount', 0))
        if curr != 0 or prev != 0:
            visible.append(n)
    
    if not visible:
        return
    
    # Block title
    block_labels = {
        'NOT1': 'Not 1 – Redovisningsprinciper',
        'NOT2': 'Not 2 – Medeltal anställda',
    }
    title = block_labels.get(block_name, f"Not – {block_name}")
    elems.append(Paragraph(title, H1))
    
    # For NOT1 (text note), render as paragraphs
    if block_name == 'NOT1':
        for note in visible:
            text = note.get('variable_text', note.get('row_title', ''))
            if text:
                elems.append(Paragraph(text, P))
        elems.append(Spacer(1, 6))
        return
    
    # For other notes, render as table
    table_data = [["Post", str(fiscal_year), str(prev_year)]]
    for note in visible:
        row_title = note.get('row_title', '')
        curr_fmt = _fmt_int(_num(note.get('current_amount', 0)))
        prev_fmt = _fmt_int(_num(note.get('previous_amount', 0)))
        table_data.append([row_title, curr_fmt, prev_fmt])
    
    if len(table_data) > 1:
        t = Table(table_data, hAlign='LEFT', colWidths=[None, 80, 80])
        t.setStyle(_table_style())
        elems.append(t)
        elems.append(Spacer(1, 6))
