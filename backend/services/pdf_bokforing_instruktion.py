# pdf_bokforing_instruktion.py
# Server-side PDF generation for accounting instructions (Bokföringsinstruktion) using ReportLab

from io import BytesIO
from typing import Any, Dict
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

# Register Roboto fonts
FONT_DIR = os.path.join(os.path.dirname(__file__), '..', 'fonts')
pdfmetrics.registerFont(TTFont('Roboto', os.path.join(FONT_DIR, 'Roboto-Regular.ttf')))
pdfmetrics.registerFont(TTFont('Roboto-Medium', os.path.join(FONT_DIR, 'Roboto-Medium.ttf')))
pdfmetrics.registerFont(TTFont('Roboto-Bold', os.path.join(FONT_DIR, 'Roboto-Bold.ttf')))

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

def _format_date(date_str: str) -> str:
    """Format YYYYMMDD to YYYY-MM-DD"""
    if not date_str:
        return ""
    date_str = str(date_str)
    if len(date_str) == 8 and date_str.isdigit():
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    return date_str

def _fmt_sek(n: float) -> str:
    """Format number as Swedish kronor: '12 345 kr'"""
    if n == 0:
        return "0 kr"
    
    is_negative = n < 0
    n = abs(n)
    
    # Round to nearest whole number
    n = round(n)
    
    # Format with spaces as thousands separator
    s = f"{int(n):,}".replace(",", " ")
    
    result = f"{s} kr"
    if is_negative:
        result = f"-{result}"
    
    return result

def _styles():
    """Return custom paragraph styles"""
    H1 = ParagraphStyle(
        'CustomH1',
        fontName='Roboto-Bold',
        fontSize=16,
        leading=20,
        textColor=colors.black,
        alignment=TA_CENTER
    )
    
    P = ParagraphStyle(
        'CustomPara',
        fontName='Roboto',
        fontSize=11,
        leading=14,
        textColor=colors.black,
        alignment=TA_LEFT
    )
    
    return H1, P

def _find_amt(rows, name):
    """Find amount from data rows by variable name"""
    if not rows:
        return 0.0
    for r in rows:
        if r.get('variable_name') == name:
            amt = _num(r.get('amount') or r.get('current_amount') or 0)
            print(f"   🔍 Found {name}: amount={r.get('amount')}, current_amount={r.get('current_amount')}, final={amt}")
            return amt
    return 0.0

def check_should_generate(company_data: Dict[str, Any]) -> bool:
    """
    Check if bokföringsinstruktion PDF should be generated based on:
    - SLP ≠ 0 OR
    - Beräknad skatt ≠ bokförd skatt OR
    - Justerat årets resultat ≠ årets resultat
    """
    # Extract INK2 data
    ink2_data = company_data.get('ink2Data') or company_data.get('seFileData', {}).get('ink2_data', [])
    
    # Extract RR data
    rr_data = (company_data.get('rrData') or 
               company_data.get('rrRows') or 
               company_data.get('seFileData', {}).get('rr_data', []))
    
    # DEBUG: Print available INK2 variable names
    ink2_vars = [item.get('variable_name') for item in ink2_data if item.get('variable_name')]
    print(f"🔍 DEBUG: Available INK2 variables ({len(ink2_vars)} total): {ink2_vars[:20]}...")
    
    # DEBUG: Print sample INK2 items
    if ink2_data and len(ink2_data) > 0:
        print(f"🔍 DEBUG: Sample INK2 item: {ink2_data[0]}")
    
    # DEBUG: Print available RR variable names
    rr_vars = [item.get('variable_name') for item in rr_data if item.get('variable_name')]
    print(f"🔍 DEBUG: Available RR variables ({len(rr_vars)} total): {rr_vars[:20]}...")
    
    # DEBUG: Print sample RR item
    if rr_data and len(rr_data) > 0:
        print(f"🔍 DEBUG: Sample RR item: {rr_data[0]}")
    
    # Get SLP
    slp = _find_amt(ink2_data, 'SLP')
    print(f"🔍 DEBUG: SLP value = {slp}")
    
    # Get beräknad skatt
    beraknad_skatt = _find_amt(ink2_data, 'INK_beraknad_skatt')
    print(f"🔍 DEBUG: INK_beraknad_skatt value = {beraknad_skatt}")
    
    # Get bokförd skatt (from RR - typically negative, so negate it)
    bokford_skatt = abs(_find_amt(rr_data, 'SkattAretsResultat'))
    print(f"🔍 DEBUG: SkattAretsResultat (bokförd) value = {bokford_skatt}")
    
    # Get justerat årets resultat
    justerat_arets_resultat = _find_amt(ink2_data, 'Arets_resultat_justerat')
    print(f"🔍 DEBUG: Arets_resultat_justerat value = {justerat_arets_resultat}")
    
    # Get årets resultat from RR
    arets_resultat = _find_amt(rr_data, 'SumAretsResultat')
    print(f"🔍 DEBUG: SumAretsResultat (årets) value = {arets_resultat}")
    
    # Check conditions
    should_generate = (
        abs(slp) > 0 or 
        abs(beraknad_skatt - bokford_skatt) > 0.01 or  # Use small epsilon for float comparison
        abs(justerat_arets_resultat - arets_resultat) > 0.01
    )
    
    print(f"📋 Bokföringsinstruktion check: SLP={slp}, Beräknad={beraknad_skatt}, Bokförd={bokford_skatt}, "
          f"Justerat={justerat_arets_resultat}, Årets={arets_resultat} → Should generate: {should_generate}")
    
    return should_generate

def generate_bokforing_instruktion_pdf(company_data: Dict[str, Any]) -> bytes:
    """
    Generate accounting instruction PDF (Bokföringsinstruktion) when adjustments are needed
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, 
        pagesize=A4, 
        leftMargin=68,
        rightMargin=68, 
        topMargin=54,
        bottomMargin=68
    )
    
    H1, P = _styles()
    elems = []
    
    # Extract INK2 data
    ink2_data = company_data.get('ink2Data') or company_data.get('seFileData', {}).get('ink2_data', [])
    
    # Extract RR data
    rr_data = (company_data.get('rrData') or 
               company_data.get('rrRows') or 
               company_data.get('seFileData', {}).get('rr_data', []))
    
    # Get values
    slp = _find_amt(ink2_data, 'SLP')
    beraknad_skatt = _find_amt(ink2_data, 'INK_beraknad_skatt')
    bokford_skatt = abs(_find_amt(rr_data, 'SkattAretsResultat'))
    justerat_arets_resultat = _find_amt(ink2_data, 'Arets_resultat_justerat')
    arets_resultat = _find_amt(rr_data, 'SumAretsResultat')
    
    # DEBUG: Print values being used for PDF generation
    print(f"📄 DEBUG PDF Generation:")
    print(f"   SLP: {slp}")
    print(f"   Beräknad skatt: {beraknad_skatt}")
    print(f"   Bokförd skatt: {bokford_skatt}")
    print(f"   Justerat årets resultat: {justerat_arets_resultat}")
    print(f"   Årets resultat: {arets_resultat}")
    print(f"   Delta skatt: {abs(beraknad_skatt - bokford_skatt)}")
    print(f"   Delta resultat: {abs(justerat_arets_resultat - arets_resultat)}")
    
    # Get fiscal year end date
    se = (company_data or {}).get('seFileData') or {}
    info = se.get('company_info') or {}
    end_date = info.get('end_date', '')
    formatted_end_date = _format_date(end_date) if end_date else ""
    
    # Add H1 heading with 2 line breaks
    elems.append(Paragraph("Bokföringsinstruktion", H1))
    elems.append(Spacer(1, 12))  # Line break
    elems.append(Spacer(1, 12))  # Second line break
    
    # Add booking date line
    if formatted_end_date:
        elems.append(Paragraph(f"Bokföringsdatum: {formatted_end_date}", P))
    else:
        elems.append(Paragraph("Bokföringsdatum:", P))
    elems.append(Spacer(1, 12))  # Line break
    
    # Build table data with headers
    table_data = [["Konto", "Debet", "Kredit"]]
    
    # Add SLP rows if abs(slp) > 0
    if abs(slp) > 0:
        table_data.append([
            "7533 Särskild löneskatt för pensionskostnader",
            _fmt_sek(abs(slp)),
            ""
        ])
        table_data.append([
            "2514 Beräknad särskild löneskatt på pensionskostnader",
            "",
            _fmt_sek(abs(slp))
        ])
    
    # Add tax adjustment rows
    if abs(beraknad_skatt - bokford_skatt) > 0.01:
        if beraknad_skatt > bokford_skatt:
            # Beräknad skatt > bokförd skatt
            delta = abs(beraknad_skatt - bokford_skatt)
            table_data.append([
                "8910 Skatt som belastar årets resultat",
                _fmt_sek(delta),
                ""
            ])
            table_data.append([
                "2512 Beräknad inkomstskatt",
                "",
                _fmt_sek(delta)
            ])
        else:
            # Beräknad skatt < bokförd skatt
            delta = abs(bokford_skatt - beraknad_skatt)
            table_data.append([
                "8910 Skatt som belastar årets resultat",
                "",
                _fmt_sek(delta)
            ])
            table_data.append([
                "2512 Beräknad inkomstskatt",
                _fmt_sek(delta),
                ""
            ])
    
    # Add result adjustment rows
    if abs(justerat_arets_resultat - arets_resultat) > 0.01:
        delta = abs(justerat_arets_resultat - arets_resultat)
        if justerat_arets_resultat > arets_resultat:
            # Justerat årets resultat > årets resultat
            table_data.append([
                "2099 Årets resultat",
                "",
                _fmt_sek(delta)
            ])
            table_data.append([
                "8999 Årets resultat",
                _fmt_sek(delta),
                ""
            ])
        else:
            # Justerat årets resultat < årets resultat
            table_data.append([
                "2099 Årets resultat",
                _fmt_sek(delta),
                ""
            ])
            table_data.append([
                "8999 Årets resultat",
                "",
                _fmt_sek(delta)
            ])
    
    # Create table with styling
    # Column widths: Konto (wide), Debet (medium), Kredit (medium)
    available_width = 459  # Page width minus margins
    col_widths = [260, 100, 100]
    
    t = Table(table_data, hAlign='LEFT', colWidths=col_widths)
    
    # Apply table styling
    style = TableStyle([
        # Header row styling
        ('FONT', (0, 0), (-1, 0), 'Roboto-Bold', 11),
        ('FONT', (0, 1), (-1, -1), 'Roboto', 10),
        ('LINEBELOW', (0, 0), (-1, 0), 1.0, colors.black),
        ('LINEBELOW', (0, -1), (-1, -1), 1.0, colors.black),
        
        # Alignment
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),    # Konto column left-aligned
        ('ALIGN', (1, 0), (-1, 0), 'CENTER'),  # Header row centered
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),  # Debet/Kredit values right-aligned
        
        # Valign
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        
        # Padding
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ])
    
    t.setStyle(style)
    elems.append(t)
    
    # Build PDF
    doc.build(elems)
    
    return buf.getvalue()

