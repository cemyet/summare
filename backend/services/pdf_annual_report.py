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
    Typography styles for PDF generation (19.2mm top margin, 24mm other margins, compact spacing)
    H0: 16pt semibold, 0pt before, 0pt after (main titles like "Förvaltningsberättelse")
    H1: 12pt semibold, 18pt before, 0pt after (subsections like "Verksamheten", "Flerårsöversikt")
    H2: 15pt semibold, 18pt before, 0pt after (major section headings - overridden in BR to 12pt/10pt)
    P: 10pt regular, 12pt leading, 2pt after
    SMALL: 8pt for "Belopp i tkr"
    Note: BR uses custom BR_H1 (10pt) and BR_H2 (12pt) for its headings
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
    # Header: Post (no text), Not, years (right-aligned)
    br_assets_table = [["", "Not", str(fiscal_year), str(prev_year)]]
    sum_rows_br_assets = []
    
    # Create BR H1 and H2 styles with correct font sizes
    from reportlab.platypus import Paragraph as RLParagraph
    BR_H1 = ParagraphStyle('BR_H1', parent=H1, fontSize=10, fontName='Roboto-Medium', spaceBefore=18, spaceAfter=0)
    BR_H2 = ParagraphStyle('BR_H2', parent=H2, fontSize=12, fontName='Roboto-Medium', spaceBefore=18, spaceAfter=0)
    
    for row in br_assets:
        if row.get('show_tag') == False:
            continue
        
        label = row.get('label', '')
        block_group = row.get('block_group', '')
        
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
        
        # Block hiding logic
        if block_group and not block_has_content_br_assets(block_group):
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
        
        # Swap order: Post (label), Not (note), amounts
        # Apply semibold style directly to label if it's a heading or sum
        if is_h2_heading:
            # H2 style for major headings (12pt)
            label_para = RLParagraph(label, BR_H2)
            br_assets_table.append([label_para, note, curr_fmt, prev_fmt])
        elif is_h1_heading:
            # H1 style for section headings (10pt)
            label_para = RLParagraph(label, BR_H1)
            br_assets_table.append([label_para, note, curr_fmt, prev_fmt])
        elif is_sum:
            # Semibold for sum rows (both label and amounts)
            label_style = ParagraphStyle('SemiboldLabel', parent=P, fontName='Roboto-Medium')
            label_para = RLParagraph(label, label_style)
            if curr_fmt:
                amount_style = ParagraphStyle('SemiboldAmount', parent=P, fontName='Roboto-Medium', alignment=2)
                curr_para = RLParagraph(curr_fmt, amount_style)
                prev_para = RLParagraph(prev_fmt, amount_style)
                br_assets_table.append([label_para, note, curr_para, prev_para])
            else:
                br_assets_table.append([label_para, note, curr_fmt, prev_fmt])
        else:
            label_para = RLParagraph(label, P)
            br_assets_table.append([label_para, note, curr_fmt, prev_fmt])
        
        # Track sum rows for spacing
        if is_sum:
            sum_rows_br_assets.append(len(br_assets_table) - 1)
    
    if len(br_assets_table) > 1:
        # Col widths: Post (269pt fixed with wrap), Not (30pt), Year1 (80pt), Year2 (80pt)
        t = Table(br_assets_table, hAlign='LEFT', colWidths=[269, 30, 80, 80])
        # Custom style with right-aligned year headers
        style = TableStyle([
            ('FONT', (0,0), (-1,0), 'Roboto-Medium', 10),  # Semibold header row
            ('LINEBELOW', (0,0), (-1,0), 0.5, colors.Color(0, 0, 0, alpha=0.7)),  # Header underline
            ('ALIGN', (1,0), (1,-1), 'CENTER'),  # Center "Not" column
            ('ALIGN', (2,0), (3,0), 'RIGHT'),  # Right-align year headers
            ('ALIGN', (2,1), (3,-1), 'RIGHT'),  # Right-align amounts
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('ROWSPACING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ])
        # Add 10pt space after sum rows
        for row_idx in sum_rows_br_assets:
            style.add('BOTTOMPADDING', (0, row_idx), (-1, row_idx), 10)
        t.setStyle(style)
        elems.append(t)
    else:
        elems.append(Paragraph("Ingen data tillgänglig", P))
    
    # ===== 4. BALANSRÄKNING (EGET KAPITAL OCH SKULDER) =====
    elems.append(PageBreak())
    elems.append(Paragraph("Balansräkning", H0))
    elems.append(Spacer(1, 16))  # 2 line breaks
    
    # Define H2 headings for BR Eget kapital och skulder (12pt semibold, no amounts)
    br_equity_liab_h2_headings = [
        'Eget kapital och skulder'
    ]
    # Define H1 headings for BR Eget kapital och skulder (10pt semibold, no amounts)
    br_equity_liab_h1_headings = [
        'Eget kapital', 'Bundet eget kapital', 'Fritt eget kapital',
        'Obeskattade reserver', 'Avsättningar',
        'Långfristiga skulder', 'Kortfristiga skulder'
    ]
    # All headings combined
    br_equity_liab_headings = br_equity_liab_h2_headings + br_equity_liab_h1_headings
    
    # Define sum rows for BR Eget kapital och skulder (semibold for both text and amounts)
    br_equity_liab_sum_rows = [
        'Summa bundet eget kapital', 'Summa fritt eget kapital', 'Summa eget kapital',
        'Summa obeskattade reserver', 'Summa avsättningar',
        'Summa långfristiga skulder', 'Summa kortfristiga skulder',
        'Summa eget kapital och skulder'
    ]
    
    # Helper function to check if a block_group has content (same as RR)
    def block_has_content_br_equity_liab(block_group: str) -> bool:
        """Check if any non-heading row in this block has non-zero amounts"""
        if not block_group:
            return True  # Items without block_group always show
        
        for row in br_data:
            if row.get('type') not in ['equity', 'liability']:
                continue
            if row.get('block_group') != block_group:
                continue
            label = row.get('label', '')
            
            # Skip headings and sums
            row_is_heading = any(h == label for h in br_equity_liab_headings)
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
    
    br_equity_liab = [r for r in br_data if r.get('type') in ['equity', 'liability']]
    # Header: Post (no text), Not, years (right-aligned)
    br_eq_table = [["", "Not", str(fiscal_year), str(prev_year)]]
    sum_rows_br_equity_liab = []
    
    # Create BR H1 and H2 styles with correct font sizes
    from reportlab.platypus import Paragraph as RLParagraph
    BR_H1 = ParagraphStyle('BR_H1', parent=H1, fontSize=10, fontName='Roboto-Medium', spaceBefore=18, spaceAfter=0)
    BR_H2 = ParagraphStyle('BR_H2', parent=H2, fontSize=12, fontName='Roboto-Medium', spaceBefore=18, spaceAfter=0)
    
    # Helper: Check if row should show (same logic as frontend)
    def should_show_row_br_equity(item: dict) -> bool:
        """Determine if a row should be shown based on frontend logic"""
        # Check if this is a heading
        is_heading = False
        is_h2_heading = item.get('label') in br_equity_liab_h2_headings
        is_h1_heading = item.get('label') in br_equity_liab_h1_headings
        is_heading = is_h2_heading or is_h1_heading
        
        if is_heading:
            # For headings, check if their block group has content
            block_group = item.get('block_group', '')
            if block_group:
                return block_has_content_br_equity_liab(block_group)
            # Headings without block_group: show if always_show OR if it's a major structural heading
            # Major headings like "Eget kapital och skulder", "Eget kapital" should always show
            if item.get('always_show') == True:
                return True
            # Show major structural headings even if always_show is not set
            if is_h2_heading or item.get('label') in ['Eget kapital', 'Bundet eget kapital', 
                                                        'Fritt eget kapital', 'Obeskattade reserver',
                                                        'Avsättningar', 'Långfristiga skulder', 
                                                        'Kortfristiga skulder']:
                return True
            return False
        
        # For non-headings, check amounts or always_show
        has_non_zero = (item.get('current_amount') not in [None, 0]) or \
                      (item.get('previous_amount') not in [None, 0])
        is_always_show = item.get('always_show') == True
        has_note = item.get('note_number') is not None
        
        return has_non_zero or is_always_show or has_note
    
    for row in br_equity_liab:
        if row.get('show_tag') == False:
            continue
        
        # Use frontend logic to determine if row should show
        if not should_show_row_br_equity(row):
            continue
        
        label = row.get('label', '')
        note = str(row.get('note_number', '')) if row.get('note_number') else ''
        
        # Check if this is a heading or sum row
        is_h2_heading = label in br_equity_liab_h2_headings
        is_h1_heading = label in br_equity_liab_h1_headings
        is_heading = is_h2_heading or is_h1_heading
        
        is_sum = any(sum_label == label or (sum_label in label and label.startswith('Summa')) 
                    for sum_label in br_equity_liab_sum_rows)
        
        # Format amounts
        if is_heading:
            curr_fmt = ''
            prev_fmt = ''
        else:
            curr_fmt = _fmt_int(_num(row.get('current_amount', 0)))
            prev_fmt = _fmt_int(_num(row.get('previous_amount', 0)))
        
        # Build row with appropriate styling
        if is_h2_heading:
            # H2 style for major headings (12pt)
            label_para = RLParagraph(label, BR_H2)
            br_eq_table.append([label_para, note, curr_fmt, prev_fmt])
        elif is_h1_heading:
            # H1 style for section headings (10pt)
            label_para = RLParagraph(label, BR_H1)
            br_eq_table.append([label_para, note, curr_fmt, prev_fmt])
        elif is_sum:
            # Semibold for sum rows (both label and amounts)
            label_style = ParagraphStyle('SemiboldLabel', parent=P, fontName='Roboto-Medium')
            label_para = RLParagraph(label, label_style)
            if curr_fmt:
                amount_style = ParagraphStyle('SemiboldAmount', parent=P, fontName='Roboto-Medium', alignment=2)
                curr_para = RLParagraph(curr_fmt, amount_style)
                prev_para = RLParagraph(prev_fmt, amount_style)
                br_eq_table.append([label_para, note, curr_para, prev_para])
            else:
                br_eq_table.append([label_para, note, curr_fmt, prev_fmt])
        else:
            # Regular row
            label_para = RLParagraph(label, P)
            br_eq_table.append([label_para, note, curr_fmt, prev_fmt])
        
        # Track sum rows for spacing
        if is_sum:
            sum_rows_br_equity_liab.append(len(br_eq_table) - 1)
    
    if len(br_eq_table) > 1:
        # Col widths: Post (269pt fixed with wrap), Not (30pt), Year1 (80pt), Year2 (80pt)
        t = Table(br_eq_table, hAlign='LEFT', colWidths=[269, 30, 80, 80])
        # Custom style with right-aligned year headers
        style = TableStyle([
            ('FONT', (0,0), (-1,0), 'Roboto-Medium', 10),  # Semibold header row
            ('LINEBELOW', (0,0), (-1,0), 0.5, colors.Color(0, 0, 0, alpha=0.7)),  # Header underline
            ('ALIGN', (1,0), (1,-1), 'CENTER'),  # Center "Not" column
            ('ALIGN', (2,0), (3,0), 'RIGHT'),  # Right-align year headers
            ('ALIGN', (2,1), (3,-1), 'RIGHT'),  # Right-align amounts
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('ROWSPACING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ])
        # Add 10pt space after sum rows
        for row_idx in sum_rows_br_equity_liab:
            style.add('BOTTOMPADDING', (0, row_idx), (-1, row_idx), 10)
        t.setStyle(style)
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
