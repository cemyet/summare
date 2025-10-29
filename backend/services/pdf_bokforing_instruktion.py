# pdf_bokforing_instruktion.py
# Server-side PDF generation for accounting instructions (Bokföringsinstruktion) using ReportLab

from io import BytesIO
from typing import Any, Dict, Tuple, Optional
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

# Threshold for meaningful adjustments
EPS = 0.5  # treat < 0.5 kr as zero to avoid 0.16 noise
THRESHOLD = 1.0  # 1 kr minimum for whole-kr deltas

def _to_number(x):
    """Convert value to float, handling various formats"""
    try:
        return float(str(x).replace(' ', '').replace('\xa0', '').replace(',', '.'))
    except Exception:
        return None

def _get_rr_value(rr_items, var_name):
    """Extract value from RR items by variable name"""
    for it in rr_items or []:
        if (it.get('variable_name') or '') == var_name:
            # Prefer 'final' then 'current_amount' then 'amount'
            for k in ('final', 'current_amount', 'amount'):
                if it.get(k) is not None:
                    return _to_number(it.get(k))
    return None

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

def pick_originals(company_data: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    """
    Extract original RR values with multiple fallback strategies.
    Returns: (arets_resultat_original, arets_skatt_original)
    """
    # 1) Prefer explicitly frozen originals (top level)
    orig_res = company_data.get('arets_resultat_original')
    orig_tax = company_data.get('arets_skatt_original')
    
    # 2) Try seFileData.company_info
    if orig_res is None or orig_tax is None:
        se_info = (company_data.get('seFileData') or {}).get('company_info') or {}
        if orig_res is None:
            orig_res = se_info.get('arets_resultat_original')
        if orig_tax is None:
            orig_tax = se_info.get('arets_skatt_original')
    
    # 3) Try original_snapshot (legacy)
    if orig_res is None or orig_tax is None:
        snap = company_data.get('original_snapshot') or {}
        rr0 = snap.get('RR') or []
        if orig_res is None:
            orig_res = _get_rr_value(rr0, 'SumAretsResultat')
        if orig_tax is None:
            orig_tax = _get_rr_value(rr0, 'SkattAretsResultat')
    
    # 4) Last resort fallback to incoming RR (not recommended)
    if orig_res is None or orig_tax is None:
        rr = ((company_data.get('seFileData') or {}).get('rr_data')
              or company_data.get('rrData') or [])
        if orig_res is None:
            orig_res = _get_rr_value(rr, 'SumAretsResultat')
        if orig_tax is None:
            orig_tax = _get_rr_value(rr, 'SkattAretsResultat')
    
    return _to_number(orig_res), _to_number(orig_tax)

def compute_deltas(company_data: Dict[str, Any]) -> Tuple[float, float, Optional[float], Tuple]:
    """
    Compute deltas with proper sign handling and tolerance.
    Returns: (slp, delta_tax, delta_res, (orig_res, orig_tax, adj_res))
    """
    # Extract INK2 variables
    ink2_data = company_data.get('ink2Data') or company_data.get('seFileData', {}).get('ink2_data', [])
    ink_vars = {(x.get('variable_name') or ''): x for x in ink2_data}
    
    # Get SLP (stored as negative, so use abs)
    slp_item = ink_vars.get('INK_sarskild_loneskatt') or {}
    slp = abs(_to_number(slp_item.get('amount') or slp_item.get('final') or 0))
    
    # Get beräknad skatt (calculated tax)
    tax_item = ink_vars.get('INK_beraknad_skatt') or {}
    ink_tax = _to_number(tax_item.get('amount') or tax_item.get('final') or 0)
    
    # Get justerat årets resultat (adjusted result)
    adj_item = ink_vars.get('Arets_resultat_justerat') or {}
    adj_res = _to_number(adj_item.get('amount') or adj_item.get('final'))
    
    # Get original values
    orig_res, orig_tax = pick_originals(company_data)
    
    print(f"📊 DELTA COMPUTATION:")
    print(f"   SLP: {slp}")
    print(f"   INK beräknad skatt: {ink_tax}")
    print(f"   Original bokförd skatt (raw): {orig_tax}")
    print(f"   Original årets resultat: {orig_res}")
    print(f"   Justerat årets resultat: {adj_res}")
    
    # TAX DELTA
    # orig_tax is usually negative (expense). Use its absolute amount when comparing to positive calculated tax.
    booked_tax_abs = abs(orig_tax) if orig_tax is not None else 0.0
    delta_tax = (ink_tax or 0.0) - booked_tax_abs
    if abs(delta_tax) < EPS:
        delta_tax = 0.0
    delta_tax = round(delta_tax)
    
    print(f"   Bokförd skatt (abs): {booked_tax_abs}")
    print(f"   Delta tax: {delta_tax}")
    
    # RESULT DELTA
    # We want how much result changed due to INK2: original - adjusted
    # Positive delta means result decreased; negative means it increased.
    delta_res = None
    if orig_res is not None and adj_res is not None:
        delta_res = round(orig_res - adj_res)
        if abs(delta_res) < THRESHOLD:  # whole-krona threshold
            delta_res = 0
        print(f"   Delta result: {delta_res}")
    
    return slp or 0.0, delta_tax, delta_res, (orig_res, orig_tax, adj_res)

def check_should_generate(company_data: Dict[str, Any]) -> bool:
    """
    Check if bokföringsinstruktion PDF should be generated based on:
    - SLP ≠ 0 OR
    - Delta tax ≠ 0 OR
    - Delta result ≠ 0
    """
    slp, delta_tax, delta_res, (orig_res, orig_tax, adj_res) = compute_deltas(company_data)
    
    should_generate = (
        abs(slp) >= THRESHOLD or 
        abs(delta_tax) >= THRESHOLD or
        (delta_res is not None and abs(delta_res) >= THRESHOLD)
    )
    
    print(f"📋 Bokföringsinstruktion check: SLP={slp}, Delta tax={delta_tax}, Delta result={delta_res} → Should generate: {should_generate}")
    
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
    
    # Compute deltas
    slp, delta_tax, delta_res, (orig_res, orig_tax, adj_res) = compute_deltas(company_data)
    
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
    
    # Add SLP rows if abs(slp) >= threshold
    if abs(slp) >= THRESHOLD:
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
    
    # Add tax adjustment rows if delta_tax >= threshold
    if abs(delta_tax) >= THRESHOLD:
        if delta_tax > 0:
            # Beräknad skatt > bokförd skatt (need to book more tax expense)
            table_data.append([
                "8910 Skatt som belastar årets resultat",
                _fmt_sek(abs(delta_tax)),
                ""
            ])
            table_data.append([
                "2512 Beräknad inkomstskatt",
                "",
                _fmt_sek(abs(delta_tax))
            ])
        else:
            # Beräknad skatt < bokförd skatt (need to reduce tax expense)
            table_data.append([
                "8910 Skatt som belastar årets resultat",
                "",
                _fmt_sek(abs(delta_tax))
            ])
            table_data.append([
                "2512 Beräknad inkomstskatt",
                _fmt_sek(abs(delta_tax)),
                ""
            ])
    
    # Add result adjustment rows if delta_res >= threshold
    if delta_res is not None and abs(delta_res) >= THRESHOLD:
        if delta_res > 0:
            # Result decreased (justerat < original) - debit 8999, credit 2099
            table_data.append([
                "2099 Årets resultat",
                "",
                _fmt_sek(abs(delta_res))
            ])
            table_data.append([
                "8999 Årets resultat",
                _fmt_sek(abs(delta_res)),
                ""
            ])
        else:
            # Result increased (justerat > original) - debit 2099, credit 8999
            table_data.append([
                "2099 Årets resultat",
                _fmt_sek(abs(delta_res)),
                ""
            ])
            table_data.append([
                "8999 Årets resultat",
                "",
                _fmt_sek(abs(delta_res))
            ])
    
    # Check if we have any rows beyond the header
    if len(table_data) <= 1:
        print("⚠️ WARNING: No adjustment rows to display in PDF (all deltas < 1 kr)")
        # Add a note in the PDF
        table_data.append([
            "Ingen bokföringsinstruktion krävs - alla justeringar < 1 kr",
            "",
            ""
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
