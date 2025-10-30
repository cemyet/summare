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

def _rr_pick_num(item):
    """Pick numeric value from RR item, prefer 'final' → 'current_amount' → 'amount'"""
    for k in ('final', 'current_amount', 'amount'):
        if item.get(k) is not None:
            v = _to_number(item.get(k))
            if v is not None:
                return v
    return None

def _rr_find(rr_items, var_name):
    """Find value in RR items by variable name"""
    if not rr_items:
        return None
    for it in rr_items:
        if (it.get('variable_name') or '') == var_name:
            return _rr_pick_num(it)
    return None

def _normalize_delta(x):
    """Normalize delta: treat < 1 SEK as 0, round to integer"""
    if x is None:
        return 0
    try:
        x = float(x)
    except Exception:
        return 0
    return 0 if abs(x) < EPS else int(round(x))

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
        fontName='Roboto-Medium',  # Changed to semibold
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
    
    # Smaller style for booking date (1pt smaller than P)
    DateStyle = ParagraphStyle(
        'DateStyle',
        fontName='Roboto',
        fontSize=10,
        leading=13,
        textColor=colors.black,
        alignment=TA_LEFT
    )
    
    return H1, P, DateStyle

def _pick_originals_from_snapshot(company_data):
    """Extract originals from the immutable __original_rr_snapshot__"""
    snap = (company_data or {}).get('__original_rr_snapshot__') or []
    orig_res = _rr_find(snap, 'SumAretsResultat')
    orig_tax = _rr_find(snap, 'SkattAretsResultat')
    return orig_res, orig_tax

def pick_originals(company_data: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    """
    Extract original RR values with multiple fallback strategies.
    Returns: (arets_resultat_original, arets_skatt_original)
    """
    # 1) Prefer explicitly frozen originals (top level or seFileData)
    orig_res = company_data.get('arets_resultat_original')
    orig_tax = company_data.get('arets_skatt_original')
    
    if orig_res is None or orig_tax is None:
        se_data = (company_data.get('seFileData') or {})
        if orig_res is None:
            orig_res = se_data.get('arets_resultat_original')
        if orig_tax is None:
            orig_tax = se_data.get('arets_skatt_original')
    
    # 2) If missing, use the immutable snapshot (CRITICAL!)
    if orig_res is None or orig_tax is None:
        sr, st = _pick_originals_from_snapshot(company_data)
        if orig_res is None:
            orig_res = sr
        if orig_tax is None:
            orig_tax = st
    
    # 3) LAST resort (discouraged): current RR (may already be mutated)
    if orig_res is None or orig_tax is None:
        rr = ((company_data.get('seFileData') or {}).get('rr_data')
              or company_data.get('rrData') or [])
        if orig_res is None:
            orig_res = _rr_find(rr, 'SumAretsResultat')
        if orig_tax is None:
            orig_tax = _rr_find(rr, 'SkattAretsResultat')
    
    return orig_res, orig_tax

def compute_deltas(company_data: Dict[str, Any]) -> Tuple[int, int, int, Tuple]:
    """
    Compute deltas with proper sign handling and tolerance.
    Returns: (slp, delta_tax, delta_res, (orig_res, orig_tax, adj_res))
    """
    # Extract INK2 variables
    ink2_data = company_data.get('ink2Data') or company_data.get('seFileData', {}).get('ink2_data', [])
    ink_vars = {(x.get('variable_name') or ''): x for x in ink2_data}
    
    def _ink_val(key):
        """Get INK2 value, prefer final over amount"""
        it = ink_vars.get(key) or {}
        val = it.get('final') if it.get('final') is not None else it.get('amount')
        return _to_number(val)
    
    # Get SLP (stored as negative, so use abs)
    slp = abs(_ink_val('INK_sarskild_loneskatt') or 0.0)
    
    # Get beräknad skatt (calculated tax)
    ink_tax = _ink_val('INK_beraknad_skatt') or 0.0
    
    # Get justerat årets resultat (adjusted result)
    adj_res = _ink_val('Arets_resultat_justerat')
    
    # Get original values (THIS NOW READS FROM SNAPSHOT!)
    orig_res, orig_tax = pick_originals(company_data)
    
    # TAX DELTA
    # orig_tax is usually NEGATIVE (expense). Use its absolute amount when comparing to positive calculated tax.
    booked_tax_abs = abs(orig_tax) if orig_tax is not None else 0.0
    delta_tax = _normalize_delta(ink_tax - booked_tax_abs)
    
    # RESULT DELTA
    # We want how much result changed due to INK2: original - adjusted
    # Positive delta means result decreased; negative means it increased.
    delta_res = 0
    if orig_res is not None and adj_res is not None:
        delta_res = _normalize_delta(orig_res - adj_res)  # positive → reduce result via 8999/2099
    
    # Return as integers after normalization
    slp_used = int(round(slp)) if abs(slp) >= EPS else 0
    
    return slp_used, delta_tax, delta_res, (orig_res, orig_tax, adj_res)

def check_should_generate(company_data: Dict[str, Any]) -> bool:
    """
    Check if bokföringsinstruktion PDF should be generated based on:
    - SLP ≠ 0 OR
    - Delta tax ≠ 0 OR
    - Delta result ≠ 0
    
    Note: compute_deltas already applies normalization (< 1 SEK → 0)
    """
    slp, delta_tax, delta_res, (orig_res, orig_tax, adj_res) = compute_deltas(company_data)
    
    # Deltas are already normalized (< 1 SEK treated as 0)
    should_generate = (slp != 0 or delta_tax != 0 or delta_res != 0)
    
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
    
    H1, P, DateStyle = _styles()
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
    
    # Add booking date line with smaller font
    if formatted_end_date:
        elems.append(Paragraph(f"Bokföringsdatum: {formatted_end_date}", DateStyle))
    else:
        elems.append(Paragraph("Bokföringsdatum:", DateStyle))
    elems.append(Spacer(1, 12))  # Line break
    
    # Build table data with headers
    table_data = [["Konto", "Debet", "Kredit"]]
    
    # Track totals for sum row
    total_debet = 0
    total_kredit = 0
    
    # Add SLP rows if non-zero (already normalized)
    if slp != 0:
        table_data.append([
            "7533 Särskild löneskatt för pensionskostnader",
            _fmt_sek(slp),
            ""
        ])
        total_debet += slp
        table_data.append([
            "2514 Beräknad särskild löneskatt på pensionskostnader",
            "",
            _fmt_sek(slp)
        ])
        total_kredit += slp
    
    # Add tax adjustment rows if non-zero (already normalized)
    if delta_tax != 0:
        if delta_tax > 0:
            # Beräknad skatt > bokförd skatt (need to book more tax expense)
            table_data.append([
                "8910 Skatt som belastar årets resultat",
                _fmt_sek(delta_tax),
                ""
            ])
            total_debet += delta_tax
            table_data.append([
                "2512 Beräknad inkomstskatt",
                "",
                _fmt_sek(delta_tax)
            ])
            total_kredit += delta_tax
        else:
            # Beräknad skatt < bokförd skatt (need to reduce tax expense)
            table_data.append([
                "8910 Skatt som belastar årets resultat",
                "",
                _fmt_sek(abs(delta_tax))
            ])
            total_kredit += abs(delta_tax)
            table_data.append([
                "2512 Beräknad inkomstskatt",
                _fmt_sek(abs(delta_tax)),
                ""
            ])
            total_debet += abs(delta_tax)
    
    # Add result adjustment rows if non-zero (already normalized)
    if delta_res != 0:
        if delta_res > 0:
            # Result decreased (justerat < original) - debit 8999, credit 2099
            table_data.append([
                "2099 Årets resultat",
                "",
                _fmt_sek(delta_res)
            ])
            total_kredit += delta_res
            table_data.append([
                "8999 Årets resultat",
                _fmt_sek(delta_res),
                ""
            ])
            total_debet += delta_res
        else:
            # Result increased (justerat > original) - debit 2099, credit 8999
            table_data.append([
                "2099 Årets resultat",
                _fmt_sek(abs(delta_res)),
                ""
            ])
            total_debet += abs(delta_res)
            table_data.append([
                "8999 Årets resultat",
                "",
                _fmt_sek(abs(delta_res))
            ])
            total_kredit += abs(delta_res)
    
    # Check if we have any rows beyond the header
    if len(table_data) <= 1:
        # Add a note in the PDF
        table_data.append([
            "Ingen bokföringsinstruktion krävs - alla justeringar < 1 kr",
            "",
            ""
        ])
    else:
        # Add sum row
        table_data.append([
            "Summa",
            _fmt_sek(total_debet),
            _fmt_sek(total_kredit)
        ])
    
    # Create table with styling
    # Column widths: Konto (wide), Debet (medium), Kredit (medium)
    available_width = 459  # Page width minus margins
    col_widths = [260, 100, 100]
    
    t = Table(table_data, hAlign='LEFT', colWidths=col_widths)
    
    # Apply table styling
    # Create gray color with 50% opacity for lines
    line_color = colors.Color(0, 0, 0, alpha=0.5)  # Black with 50% opacity
    
    style = TableStyle([
        # Header row styling
        ('FONT', (0, 0), (-1, 0), 'Roboto-Medium', 11),  # Semibold header
        ('FONT', (0, 1), (-1, -1), 'Roboto', 10),  # Regular font for content rows
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, line_color),  # 0.5pt line with 50% opacity
        ('LINEBELOW', (0, -1), (-1, -1), 0.5, line_color),  # 0.5pt line with 50% opacity
        
        # Alignment
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),    # Konto column left-aligned
        ('ALIGN', (1, 0), (-1, 0), 'RIGHT'),   # Header row Debet/Kredit right-aligned
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),  # Debet/Kredit values right-aligned
        
        # Valign
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        
        # Padding - reduced from 6 to 3
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ])
    
    # If we have a sum row (more than just header row), make it semibold
    if len(table_data) > 1 and table_data[-1][0] == "Summa":
        style.add('FONT', (0, -1), (-1, -1), 'Roboto-Medium', 10)  # Semibold sum row
        style.add('LINEABOVE', (0, -1), (-1, -1), 0.5, line_color)  # Line above sum row
    
    t.setStyle(style)
    elems.append(t)
    
    # Build PDF
    doc.build(elems)
    
    return buf.getvalue()
