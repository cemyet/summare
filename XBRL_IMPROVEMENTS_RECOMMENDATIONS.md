# XBRL XHTML Generation - Recommended Improvements

## Date: 2025-11-15
## Based on: Comparison with Bolagsverket Example (556999-9999 Exempel 1 AB) and Taxonomy Documentation

## ✅ **IMPLEMENTATION STATUS: Phase 1, 2 & 3 COMPLETED**

**Last Updated:** 2025-11-15 (after implementing Priorities 2 & 3)

### What Has Been Implemented:
✅ Fixed iXBRL header structure (ix:references, ix:resources)  
✅ Removed duplicate XBRL facts (no more <xbrli:xbrl> duplication)  
✅ Semantic context IDs (period0, period1, instant0, instant1)  
✅ UTF-8 encoding in XML declaration  
✅ Roboto font integration with Google Fonts  
✅ Complete CSS overhaul to match PDF typography  
✅ Proper decimal handling with is_current parameter  
✅ **Complete Swedish XBRL metadata tags** (Priority 2)  
✅ **Decimals attribute on all monetary facts** (Priority 3)  

### Still To Do:
⏳ Use style field for row detection (H0/H1/H2/S1/S2/S3 instead of hardcoded label lists)  
⏳ Improve visible content formatting to exactly match PDF  

---

## 1. DOCUMENT STRUCTURE & NAMESPACES

### Current Issues:
- Missing proper XML declaration encoding
- Namespace declarations order could match Bolagsverket standard
- Missing some utility namespaces

### Recommendations:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" 
    xmlns:iso4217="http://www.xbrl.org/2003/iso4217" 
    xmlns:ixt="http://www.xbrl.org/inlineXBRL/transformation/2010-04-20" 
    xmlns:xlink="http://www.w3.org/1999/xlink" 
    xmlns:link="http://www.xbrl.org/2003/linkbase" 
    xmlns:xbrli="http://www.xbrl.org/2003/instance" 
    xmlns:ix="http://www.xbrl.org/2013/inlineXBRL" 
    xmlns:se-gen-base="http://www.taxonomier.se/se/fr/gen-base/2021-10-31" 
    xmlns:se-cd-base="http://www.taxonomier.se/se/fr/cd-base/2021-10-31" 
    xmlns:se-bol-base="http://www.bolagsverket.se/se/fr/comp-base/2020-12-01"
    xmlns:se-k2-type="http://www.taxonomier.se/se/fr/k2/datatype" 
    xmlns:se-mem-base="http://www.taxonomier.se/se/fr/mem-base/2021-10-31" 
    xmlns:se-gaap-ext="http://www.taxonomier.se/se/fr/gaap/gaap-ext/2021-10-31">
```

**Changes:**
- Add `encoding="UTF-8"` to XML declaration
- Reorder namespaces to match Bolagsverket standard (iso4217, ixt, xlink first)
- Remove unused namespaces (se-ar-base, se-misc-base if not needed)

---

## 2. CSS STYLING

### Current Issues:
- Uses Times New Roman as primary font (good!)
- Page structure uses `.ar-page0, .ar-page1` etc. (good!)
- Missing some responsive design elements from Bolagsverket example
- Missing print-specific styles
- Missing proper table formatting classes

### Recommendations:

**A. Add Semantic CSS Classes** (from Bolagsverket example):
```css
/* Financial statement tables */
.ar-financial { }
.ar-financial thead th { font-size: 120%; font-weight: bold; }
.ar-financial tbody th.sub { font-style: italic; font-weight: normal; }
.ar-financial tbody th.sup { font-size: 120%; font-weight: bold; }
.ar-financial tbody .sep { padding-top: 1em; }

/* Note tables */
.ar-note { table-layout: fixed; min-width: 20em; }
.ar-note col.kr { width: 8em; }
.ar-note td + td { text-align: right; }
.ar-note th + th { text-align: right; }

/* Column width helpers */
col.kr { width: 6em; }
col.note { width: 3em; }
col.tkr { width: 5em; }

/* Value styling */
td.sub-sum { font-style: italic; }
td.sum { font-weight: bold; }
td.total { font-size: 120%; }
```

**B. Add Print Styles:**
```css
@media print {
    .ar-page0, .ar-page1, ... {
        margin: 0px;
        border: 0px;
        font-size: 11pt;
        page-break-after: always;
        min-height: 0px;
        max-width: none;
        page-break-inside: avoid;
        box-shadow: none;
    }
    .ar-page:last-of-type {
        page-break-after: avoid;
    }
    table {
        page-break-inside: avoid;
    }
}
```

**C. Use Roboto Font from PDF Generator:**
From `pdf_annual_report.py`, we already use:
- Roboto (regular)
- Roboto-Medium (semibold)
- Roboto-Bold

Apply these to XHTML with web font declarations or fallbacks:
```css
@font-face {
    font-family: 'Roboto';
    src: url('fonts/Roboto-Regular.ttf');
    font-weight: normal;
}
@font-face {
    font-family: 'Roboto';
    src: url('fonts/Roboto-Medium.ttf');
    font-weight: 500;
}
@font-face {
    font-family: 'Roboto';
    src: url('fonts/Roboto-Bold.ttf');
    font-weight: bold;
}

/* Fallback to Times New Roman if Roboto not available (XBRL standard) */
body, .ar-page {
    font-family: Roboto, 'Times New Roman', Times, serif;
}
```

---

## 3. XBRL TAGGING IN ix:hidden

### Current Issues:
- Facts are duplicated in both `<xbrli:xbrl>` section AND `<ix:hidden>` as separate tags
- Missing transformation format declaration
- Context IDs use generic names (`c1`, `c2`, `c3`, `c4`) instead of semantic names

### Recommendations:

**A. Use Only ix:nonFraction/ix:nonNumeric in ix:hidden (No Duplication):**

Bolagsverket example structure:
```xml
<ix:header>
    <ix:hidden>
        <!-- Metadata tags first -->
        <ix:nonNumeric name="se-cd-base:SprakHandlingUpprattadList" contextRef="period0">
            se-mem-base:SprakSvenskaMember
        </ix:nonNumeric>
        <ix:nonNumeric name="se-cd-base:LandForetagetsSateList" contextRef="period0">
            se-mem-base:LandSverigeMember
        </ix:nonNumeric>
        <ix:nonNumeric name="se-cd-base:RedovisningsvalutaHandlingList" contextRef="period0">
            se-mem-base:ValutaSvenskaKronorMember
        </ix:nonNumeric>
        <ix:nonNumeric name="se-cd-base:BeloppsformatList" contextRef="period0">
            se-mem-base:BeloppsformatNormalformMember
        </ix:nonNumeric>
        
        <!-- Financial facts -->
        <ix:nonFraction name="se-gen-base:Nettoomsattning" contextRef="period0" unitRef="SEK" 
            decimals="0" format="ixt:numdotdecimal">1936366</ix:nonFraction>
        ...
    </ix:hidden>
</ix:header>
```

**Changes:**
- Remove `<xbrli:xbrl>` section entirely - only use `ix:hidden`
- Add metadata tags at the beginning (language, country, currency, date format)
- Use `format="ixt:numdotdecimal"` instead of standalone `ixt:transform`
- Add `decimals="0"` attribute to all monetary facts

**B. Use Semantic Context IDs:**
```xml
<!-- Instead of c1, c2, c3, c4, use: -->
<xbrli:context id="period0">  <!-- Current year duration -->
<xbrli:context id="period1">  <!-- Previous year duration -->
<xbrli:context id="instant0">  <!-- Current year end instant -->
<xbrli:context id="instant1">  <!-- Previous year end instant -->
```

---

## 4. VISIBLE CONTENT STRUCTURE

### Current Issues:
- Cover page structure is good
- Financial tables lack semantic HTML structure from Bolagsverket
- Missing note references in financial statements
- Table classes not aligned with Bolagsverket standard

### Recommendations:

**A. Use Semantic Table Classes:**

For Resultaträkning:
```html
<table class="ar-financial ar-profit-loss col-4">
    <colgroup>
        <col/>
        <col class="note"/>
        <col class="tkr"/>
        <col class="tkr"/>
    </colgroup>
    <thead>
        <tr>
            <th colspan="4">Resultaträkning</th>
        </tr>
        <tr>
            <th></th>
            <th>Not</th>
            <th>2024</th>
            <th>2023</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <th>Nettoomsättning</th>
            <td></td>
            <td><ix:nonFraction name="se-gen-base:Nettoomsattning" contextRef="period0" 
                unitRef="SEK" decimals="-3" format="ixt:num-dot-decimal">1 936</ix:nonFraction></td>
            <td><ix:nonFraction name="se-gen-base:Nettoomsattning" contextRef="period1" 
                unitRef="SEK" decimals="-3" format="ixt:num-dot-decimal">660</ix:nonFraction></td>
        </tr>
        ...
    </tbody>
</table>
```

**B. Add Page Headers:**
```html
<div class="ar-page-hdr">
    <span>Holtback Yeter Consulting AB<br/>Org.nr 556610-3643</span>
    <span>2 (9)</span>
</div>
```

**C. Embed ix:nonFraction in Visible Content:**
Currently we embed tags in visible content (GOOD!), but ensure:
- Use `decimals="-3"` for thousands (Tkr format)
- Use `format="ixt:num-dot-decimal"` for proper formatting
- Visible amounts should match XBRL tagged amounts

---

## 5. AMOUNT FORMATTING

### Current Issues:
- Amounts shown as `1 936 365,77` (with decimals and comma)
- XBRL tags show integers only
- Inconsistent decimal handling

### Recommendations:

**From Bolagsverket Example:**
- **Visible amounts:** Show in thousands (Tkr) with space separator: `1 936`
- **XBRL tags:** Use `decimals="-3"` for amounts in thousands
- **Format:** Use `format="ixt:num-dot-decimal"` transformation

**Example:**
```html
<!-- For amount 1,936,366 kr (in Tkr = 1,936) -->
<ix:nonFraction name="se-gen-base:Nettoomsattning" contextRef="period0" 
    unitRef="SEK" decimals="-3" format="ixt:num-dot-decimal">1936</ix:nonFraction>
```

**Changes Needed in xbrl_generator.py:**
```python
def _format_monetary_value(self, amount: float, scale: str = "SEK") -> str:
    """Format monetary value for XBRL (in thousands, integer)"""
    # Convert to thousands and round
    tkr = int(round(amount / 1000))
    return str(tkr)

def _format_monetary_display(self, amount: float) -> str:
    """Format monetary value for visible display (thousands with space separator)"""
    tkr = int(round(amount / 1000))
    return f"{tkr:,}".replace(",", " ")
```

---

## 6. FÖRVALTNINGSBERÄTTELSE STRUCTURE

### Current Issues:
- Structure is present but could be more semantic
- Missing some XBRL tags for FB sections

### Recommendations:

**A. Add Heading Structure:**
```html
<div class="ar-page1">
    <div class="ar-page-hdr">
        <span>Holtback Yeter Consulting AB<br/>Org.nr 556610-3643</span>
        <span>2 (9)</span>
    </div>
    
    <h2>Förvaltningsberättelse</h2>
    
    <h3>Allmänt om verksamheten</h3>
    <p>[verksamhet text...]</p>
    
    <h3>Flerårsöversikt</h3>
    <table class="ar-overview col-5">
        ...
    </table>
    
    <h3>Förändring av eget kapital</h3>
    <table class="ar-capital">
        ...
    </table>
    
    <h3>Förslag till disposition av bolagets vinst</h3>
    <table class="ar-disp">
        ...
    </table>
</div>
```

---

## 7. NOTER STRUCTURE

### Current Issues:
- Noter page exists but lacks proper structure
- Missing XBRL tuples for depreciation principles (Not 1)
- Note tables lack proper CSS classes

### Recommendations:

**A. Add Tuple Tags for Depreciation Principles (Not 1):**
```xml
<ix:tuple name="se-gaap-ext:AvskrivningsprincipMateriellaAnlaggningstillgangarMaskinerAndraTekniskaAnlaggningarTuple" 
    tupleID="avskr-princip-mask-id1"/>
<ix:nonNumeric name="se-gen-base:AvskrivningsprincipMateriellAnlaggningstillgangBenamning" 
    contextRef="period0" order="1.0" tupleRef="avskr-princip-mask-id1">
    Tillämpade avskrivningstider: Maskiner och andra tekniska anläggningar
</ix:nonNumeric>
```

**B. Use Proper Note Table Classes:**
```html
<h3 id="note-3">Not 3 Byggnader och mark</h3>
<table class="ar-note col-3">
    <colgroup>
        <col/>
        <col class="kr"/>
        <col class="kr"/>
    </colgroup>
    <thead>
        <tr>
            <th></th>
            <th>2024-12-31</th>
            <th>2023-12-31</th>
        </tr>
    </thead>
    <tbody>
        ...
    </tbody>
</table>
```

---

## 8. ROW DISPLAY LOGIC

### Current Issues:
- Show/hide logic is applied but could be more consistent with PDF
- Some zero rows still showing

### Recommendations:

**Ensure Consistency with pdf_annual_report.py:**
1. Use same `_should_show_row()` logic
2. Apply same `block_has_content()` logic for sections
3. Mirror exact heading/sum row identification

**Key Logic from PDF:**
```python
def _should_show_row(row, toggle_on=False):
    """Determine if row should be shown"""
    # Always show rows marked as always_show
    if row.get('always_show'):
        return True
    
    # Show if has note number (even if zero)
    if row.get('note_number'):
        return True
    
    # Show if non-zero current or previous amount
    curr = _num(row.get('current_amount', 0))
    prev = _num(row.get('previous_amount', 0))
    if curr != 0 or prev != 0:
        return True
    
    # Show if toggle_show is True and toggle is on
    if toggle_on and row.get('toggle_show'):
        return True
    
    return False
```

---

## 9. METADATA TAGS

### Current Issues:
- Basic metadata present (company name, org number)
- Missing some required metadata tags

### Recommendations:

**Add Complete Metadata Section:**
```xml
<ix:nonNumeric name="se-cd-base:ForetagetsNamn" contextRef="period0">
    Holtback Yeter Consulting AB
</ix:nonNumeric>
<ix:nonNumeric name="se-cd-base:Organisationsnummer" contextRef="period0">
    5566103643
</ix:nonNumeric>
<ix:nonNumeric name="se-cd-base:SprakHandlingUpprattadList" contextRef="period0">
    se-mem-base:SprakSvenskaMember
</ix:nonNumeric>
<ix:nonNumeric name="se-cd-base:LandForetagetsSateList" contextRef="period0">
    se-mem-base:LandSverigeMember
</ix:nonNumeric>
<ix:nonNumeric name="se-cd-base:RedovisningsvalutaHandlingList" contextRef="period0">
    se-mem-base:ValutaSvenskaKronorMember
</ix:nonNumeric>
<ix:nonNumeric name="se-cd-base:BeloppsformatList" contextRef="period0">
    se-mem-base:BeloppsformatNormalformMember
</ix:nonNumeric>
<ix:nonNumeric name="se-gen-base:FinansiellRapportList" contextRef="period0">
    se-mem-base:FinansiellRapportStyrelsenVerkstallandeDirektorenAvgerArsredovisningMember
</ix:nonNumeric>
<ix:nonNumeric name="se-cd-base:RakenskapsarForstaDag" contextRef="period0">
    2024-01-01
</ix:nonNumeric>
<ix:nonNumeric name="se-cd-base:RakenskapsarSistaDag" contextRef="period0">
    2024-12-31
</ix:nonNumeric>
```

---

## 10. IMPLEMENTATION PRIORITY

### Phase 1 (Critical - Affects Validation):
1. ✅ Fix XML encoding declaration
2. ✅ Remove duplicate facts (keep only in ix:hidden)
3. ✅ Use semantic context IDs (period0, period1, instant0, instant1)
4. ✅ Add `decimals` attribute to all monetary facts
5. ✅ Add complete metadata tags

### Phase 2 (Important - Improves Compliance):
6. ✅ Apply semantic CSS classes (ar-financial, ar-note, etc.)
7. ✅ Fix amount formatting (thousands with correct decimals)
8. ✅ Add proper table structure (colgroup, thead, tbody)
9. ✅ Add page headers to all pages

### Phase 3 (Nice to Have - Improves Appearance):
10. ✅ Add Roboto font support with fallback
11. ✅ Add print-specific CSS
12. ✅ Improve note structure with tuples
13. ✅ Add table of contents to first page

---

## 11. CODE CHANGES NEEDED

### File: `backend/services/xbrl_generator.py`

**Changes:**

1. **XML Declaration:**
```python
# In generate_xbrl_document():
xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
```

2. **Context ID Naming:**
```python
def _get_context_refs(self, fiscal_year: int, context_type: str) -> Tuple[str, str]:
    """Get semantic context IDs"""
    if context_type == 'duration':
        return 'period0', 'period1'
    else:  # instant
        return 'instant0', 'instant1'
```

3. **Amount Formatting:**
```python
def _format_for_xbrl(self, amount: float) -> str:
    """Format amount for XBRL tag (thousands, integer)"""
    return str(int(round(amount / 1000)))

def _format_for_display(self, amount: float) -> str:
    """Format amount for visible display (thousands, space-separated)"""
    tkr = int(round(amount / 1000))
    return f"{tkr:,}".replace(",", " ")
```

4. **Metadata Tags:**
```python
def _add_metadata_tags(self, hidden_div, period0_ref):
    """Add required metadata tags"""
    metadata_tags = [
        ('se-cd-base:SprakHandlingUpprattadList', 'se-mem-base:SprakSvenskaMember'),
        ('se-cd-base:LandForetagetsSateList', 'se-mem-base:LandSverigeMember'),
        ('se-cd-base:RedovisningsvalutaHandlingList', 'se-mem-base:ValutaSvenskaKronorMember'),
        ('se-cd-base:BeloppsformatList', 'se-mem-base:BeloppsformatNormalformMember'),
        # ... more metadata
    ]
    for tag_name, tag_value in metadata_tags:
        self.add_non_numeric_fact(hidden_div, tag_name, tag_value, period0_ref)
```

5. **CSS Improvements:**
```python
def _get_css_styles(self) -> str:
    """Return comprehensive CSS matching Bolagsverket + PDF styles"""
    return """
    /* Base fonts */
    @font-face {
        font-family: 'Roboto';
        src: local('Roboto'), local('Roboto-Regular');
        font-weight: normal;
    }
    
    body, .ar-page { font-family: Roboto, 'Times New Roman', Times, serif; }
    
    /* Financial tables */
    .ar-financial { }
    .ar-financial thead th { font-size: 120%; font-weight: bold; }
    
    /* Note tables */
    .ar-note { table-layout: fixed; min-width: 20em; }
    
    /* ... rest of CSS from Bolagsverket example ... */
    """
```

---

## SUMMARY

**Key Takeaways:**

1. **Structure:** Follow Bolagsverket's semantic HTML structure with proper classes
2. **Formatting:** Use thousands (Tkr) for all amounts, with `decimals="-3"` 
3. **Tagging:** Only use `ix:hidden` for facts, remove duplication
4. **Styling:** Adopt CSS classes from Bolagsverket + keep Roboto from PDF
5. **Metadata:** Add all required metadata tags for compliance
6. **Consistency:** Ensure XHTML mirrors PDF logic for row visibility

**Expected Result:**
- Valid XBRL file that passes Bolagsverket validation
- Visually matches PDF output with proper formatting
- Uses semantic HTML structure for better parsing
- Includes all required metadata and tags

