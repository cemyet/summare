# Bokföringsinstruktion PDF API

## Overview
The Bokföringsinstruktion (Accounting Instruction) PDF is automatically generated when financial adjustments need to be made. This feature provides a professional accounting instruction document for companies when there are discrepancies between calculated and booked values.

## When is it generated?

The PDF is generated when **ANY** of the following conditions are met:

1. **SLP ≠ 0** - Special payroll tax for pension costs differs from zero
2. **Beräknad skatt ≠ Bokförd skatt** - Calculated tax differs from booked tax  
3. **Justerat årets resultat ≠ Årets resultat** - Adjusted yearly result differs from yearly result

## API Endpoints

### 1. Check if PDF should be generated

**Endpoint:** `POST /api/pdf/bokforing-instruktion/check`

**Request Body:**
```json
{
  "companyData": {
    "ink2Data": [...],
    "rrData": [...],
    "seFileData": {...}
  }
}
```

**Response:**
```json
{
  "shouldGenerate": true
}
```

Use this endpoint to determine if the fourth button in the download manual should be displayed.

### 2. Generate the PDF

**Endpoint:** `POST /api/pdf/bokforing-instruktion`

**Request Body:**
```json
{
  "companyData": {
    "ink2Data": [...],
    "rrData": [...],
    "seFileData": {
      "company_info": {
        "end_date": "20241231",
        "company_name": "Företag AB",
        "fiscal_year": 2024
      }
    }
  }
}
```

**Response:** PDF file download with filename `bokforingsinstruktion_{company_name}_{fiscal_year}.pdf`

**Error Response (400):** If no adjustments are needed:
```json
{
  "detail": "Bokföringsinstruktion not needed - no adjustments required"
}
```

## PDF Content

The generated PDF includes:

### Header
- **H1 Title:** "Bokföringsinstruktion"
- **Booking Date:** End date of current fiscal year

### Table
3-column table with headers:
- Konto (Account)
- Debet (Debit)
- Kredit (Credit)

### Rows Generated Based on Conditions

#### 1. If abs(SLP) > 0:
```
7533 Särskild löneskatt för pensionskostnader    |  abs(SLP)  |
2514 Beräknad särskild löneskatt på pensionskostnader  |     |  abs(SLP)
```

#### 2. If Beräknad skatt > Bokförd skatt:
```
8910 Skatt som belastar årets resultat      |  delta  |
2512 Beräknad inkomstskatt                  |         |  delta
```

#### 3. If Beräknad skatt < Bokförd skatt:
```
8910 Skatt som belastar årets resultat      |         |  delta
2512 Beräknad inkomstskatt                  |  delta  |
```

#### 4. If Justerat årets resultat > Årets resultat:
```
2099 Årets resultat                         |         |  delta
8999 Årets resultat                         |  delta  |
```

#### 5. If Justerat årets resultat < Årets resultat:
```
2099 Årets resultat                         |  delta  |
8999 Årets resultat                         |         |  delta
```

Where `delta` is the absolute difference between the values.

## Data Sources

The following values are extracted from the company data:

- **SLP:** `ink2Data` → variable_name: `'SLP'`
- **Beräknad skatt:** `ink2Data` → variable_name: `'INK_beraknad_skatt'`
- **Bokförd skatt:** `rrData` → variable_name: `'SkattAretsResultat'` (absolute value)
- **Justerat årets resultat:** `ink2Data` → variable_name: `'Arets_resultat_justerat'`
- **Årets resultat:** `rrData` → variable_name: `'SumAretsResultat'`
- **End date:** `seFileData.company_info.end_date`

## Frontend Integration Example

```typescript
// Check if button should be shown
const checkBokforingInstruktion = async (companyData: any) => {
  const response = await fetch('/api/pdf/bokforing-instruktion/check', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ companyData })
  });
  const result = await response.json();
  return result.shouldGenerate;
};

// Download the PDF
const downloadBokforingInstruktion = async (companyData: any) => {
  const response = await fetch('/api/pdf/bokforing-instruktion', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ companyData })
  });
  
  if (!response.ok) {
    throw new Error('Bokföringsinstruktion not needed');
  }
  
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `bokforingsinstruktion_${companyName}_${fiscalYear}.pdf`;
  a.click();
};

// Usage in component
const showButton = await checkBokforingInstruktion(companyData);
if (showButton) {
  // Display fourth button in download manual
  // On click, call downloadBokforingInstruktion(companyData)
}
```

## Testing

All tests have passed successfully:
- ✅ Conditional logic (6 test cases)
- ✅ PDF generation with all adjustments
- ✅ Table formatting and layout
- ✅ Date formatting

## Files Modified/Created

1. **Created:** `/backend/services/pdf_bokforing_instruktion.py` - PDF generation service
2. **Modified:** `/backend/main.py` - Added two new endpoints

## Notes

- The PDF uses the same styling and fonts as the annual report (Roboto font family)
- All amounts are formatted in Swedish kronor (e.g., "12 345 kr")
- The fiscal year end date is formatted as YYYY-MM-DD
- Empty values in table cells are shown as empty strings (not "0 kr")

