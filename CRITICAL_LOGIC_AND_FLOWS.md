# Critical Logic and Flows - DO NOT BREAK

**Last Updated:** 2025-01-19  
**Purpose:** This document captures critical business logic, data flows, and "gotchas" that must be preserved when making code changes.

---

## 🚨 CRITICAL RULES - NEVER BREAK THESE

### 1. Step 405 Must Only Trigger ONCE
**Location:** `frontend/src/components/DatabaseDrivenChat.tsx` + `AnnualReportPreview.tsx`

**Rule:** After the user sees step 405 ("Nu är årets skatt beräknad...") the FIRST time, subsequent manual edits in the INK2 module should update data silently WITHOUT triggering step 405 again.

**Protection Layers:**
1. **Flag Check in `handleApproveChanges()`** (`AnnualReportPreview.tsx`)
   - Check `isFirstTimeClick = !companyData.taxButtonClickedBefore`
   - Only set `triggerChatStep: 405` if `isFirstTimeClick === true`
   - Set `taxButtonClickedBefore: true` FIRST in separate `onDataUpdate()` call

2. **Navigation Guard in `handleOptionClick()`** (`DatabaseDrivenChat.tsx`)
   - Before navigating, check: `if (next_step === 405 && companyData.taxButtonClickedBefore)`
   - If true, return early and skip navigation

3. **useEffect Guard for `triggerChatStep`** (`DatabaseDrivenChat.tsx`)
   - In the `useEffect` that watches `companyData.triggerChatStep`
   - Check: `if (triggerChatStep === 405 && taxButtonClickedBefore)`
   - If true, clear trigger and return early

**Why 3 Layers?**
- Layer 1: Prevents setting the trigger in the first place
- Layer 2: Catches chat flow navigation attempts
- Layer 3: Catches direct `triggerChatStep` assignments

**Test Case:**
1. Go through chat flow → Step 401 → "Godkänn beräknad skatt" → Step 405 ✓
2. Make manual edit in INK2 → Click "Godkänn och uppdatera skatt" → Should NOT show step 405 ✓
3. Data should still update (RR/BR/PDFs) ✓

---

### 2. Manual Edits Must Always Have Highest Priority
**Location:** `backend/services/ink2_pdf_filler.py` - `build_override_map()`

**Rule:** Manual edits stored in `acceptedInk2Manuals` must ALWAYS win over any other data source.

**Priority Order (later overwrites earlier):**
```
1. seFileData.ink2_data (original baseline from SIE file)
2. ink2Data (latest calculated values including INK4.15, INK4.16)
3. acceptedInk2Manuals (user manual edits) ← HIGHEST PRIORITY
4. RR/BR current_amount values
5. Noter/FB variables
6. Misc singletons (inkBeraknadSkatt, unusedTaxLossAmount, etc.)
7. Special mappings (e.g., unusedTaxLossAmount → INK4.14a)
```

**CRITICAL:** Step 7 (special mappings) must check if the target field already has a manual override before applying!

**Example - unusedTaxLossAmount Mapping:**
```python
# WRONG - overwrites manual edits:
if "unusedTaxLossAmount" in company_data:
    M[_norm("INK4.14a")] = company_data["unusedTaxLossAmount"]

# CORRECT - respects manual edits:
accepted_manuals = company_data.get("acceptedInk2Manuals") or {}
ink4_14a_has_manual = "INK4.14a" in accepted_manuals
if "unusedTaxLossAmount" in company_data and not ink4_14a_has_manual:
    M[_norm("INK4.14a")] = company_data["unusedTaxLossAmount"]
```

**Test Case:**
1. Chat injects `unusedTaxLossAmount=340000` → INK4.14a shows 340000 ✓
2. User manually edits INK4.14a to 1340000 → Preview shows 1340000 ✓
3. Download INK2 PDF → PDF shows 1340000 (not 340000) ✓

---

### 3. INK2 Update Flow and RR/BR Linking
**Location:** `frontend/src/components/AnnualReportPreview.tsx`

**Rule:** INK2 module is the source of truth for tax calculations. Changes in INK2 must automatically flow to RR (Resultaträkning) and BR (Balansräkning), and all three outputs (Preview, Annual Report PDF, INK2 PDF) must always mirror the same values.

#### 3.1 How INK2 is Updated

**Three Ways to Update INK2:**

1. **Chat Injection** (e.g., SLP, unused tax loss)
   ```
   Chat → onDataUpdate({ unusedTaxLossAmount: 340000 })
   → Triggers recalculation
   → Updates ink2Data
   → Updates RR/BR via updateRrBrWithSlp()
   ```

2. **Manual Edit by User**
   ```
   User edits field → onChange in Ink2AmountInput
   → Updates manualEdits state
   → Triggers recalcWithManuals()
   → Updates recalculatedData (preview)
   ```

3. **Automatic Recalculation** (derived fields like INK4.15, INK4.16)
   ```
   Any change → recalcWithManuals()
   → Backend calculates derived fields
   → Returns updated ink2Data
   → Selective merge (CALC_ONLY fields always updated)
   ```

#### 3.2 INK2 → RR/BR Linking

**When INK2 Changes, RR/BR Must Update:**

```
INK2 Change (tax or SLP)
    ↓
handleTaxUpdateLogic() in AnnualReportPreview.tsx
    ↓
Calculate differences:
    - taxDifference = inkBeraknadSkatt - inkBokfordSkatt
    - slpDelta = current SLP - previous SLP
    ↓
API: POST /api/update-tax-in-financial-data
    ↓
Backend updates RR:
    - Row 277: Skatt på årets resultat = inkBeraknadSkatt
    - Row 279: Årets resultat (adjusted for tax)
    - Row 252: Personalkostnader (if SLP changed)
    - Rows 256, 257, 260, 267, 275: Ripple SLP effects
    ↓
Backend updates BR:
    - Row 413: Skatteskulder (tax + SLP liabilities)
    - Row 416: Summa kortfristiga skulder
    - Row 418: Summa skulder
    - Row 420: Summa skulder och eget kapital
    - Row 366: Balanserat resultat
    - Row 368: Årets resultat
    ↓
Response: { rr_data, br_data, changes }
    ↓
onDataUpdate({ rr_data, br_data, seFileData })
    ↓
Preview updates immediately ✓
```

**Key Fields That Link INK2 to RR/BR:**
- `INK_beraknad_skatt` → RR row 277 "Skatt på årets resultat"
- `INK_sarskild_loneskatt` → RR row 252 "Personalkostnader" (adds to costs)
- Tax difference → BR row 413 "Skatteskulder"
- SLP → BR row 413 "Skatteskulder" (tax liability)
- Adjusted result → RR row 279 "Årets resultat" → BR row 368 "Årets resultat"

#### 3.3 "Godkänn" Button Behavior

**Location:** `handleApproveChanges()` in `AnnualReportPreview.tsx`

**What Happens When User Clicks "Godkänn och uppdatera skatt":**

```typescript
1. Capture Current State
   - Get all manualEdits from current session
   - Get chatOverrides (SLP, unused tax loss)
   - Merge with previous acceptedInk2Manuals

2. Set Flag (if first time)
   if (isFirstTimeClick) {
     onDataUpdate({ taxButtonClickedBefore: true });
   }

3. Update Company Data
   onDataUpdate({
     acceptedInk2Manuals: nextAccepted,  // Store manual edits permanently
     ink2Data: updatedInk2Data,          // Update with new amounts
     chatApplied: { ...appliedKeys }     // Mark chat keys as applied
   });

4. Trigger Step 405 (first time only)
   if (isFirstTimeClick) {
     onDataUpdate({ triggerChatStep: 405 });
   }

5. Update RR/BR
   await handleTaxUpdateLogic(nextAccepted, updatedInk2Data, true);
   // forceUpdate=true ensures RR/BR always update

6. Clean Up
   - Clear manualEdits state (now in acceptedInk2Manuals)
   - Clear recalculatedData
   - Close edit mode
   - Auto-scroll to tax module

7. Recalculate Derived Fields
   await recalcWithManuals(nextAccepted, { 
     includeAccepted: false, 
     baselineSource: 'current' 
   });
   // Ensures INK4.15, INK4.16 always up-to-date
```

**Critical: Godkänn Must:**
- ✅ Store manual edits in `acceptedInk2Manuals` (permanent)
- ✅ Update `ink2Data` with new amounts
- ✅ Trigger RR/BR update via `handleTaxUpdateLogic()`
- ✅ Recalculate derived fields (INK4.15, INK4.16)
- ✅ Only trigger step 405 on FIRST click
- ✅ Close edit mode and clear temporary state

#### 3.4 "Ångra" Button Behavior

**Location:** `handleUndo()` in `AnnualReportPreview.tsx`

**What Happens When User Clicks "Ångra":**

```typescript
1. Discard Session Edits
   setManualEdits({});  // Clear all edits from current session

2. Mark for Reset
   clearAcceptedOnNextApproveRef.current = true;
   // Next approve will clear old acceptedInk2Manuals

3. Restore Original Values
   await recalcWithManuals({}, { 
     includeAccepted: false,      // Don't include previous accepted edits
     baselineSource: 'original'   // Use original baseline from SIE file
   });
   // This restores INK2 to original state from SIE file
```

**Critical: Ångra Must:**
- ✅ Clear current session edits (`manualEdits`)
- ✅ Restore original values from baseline (`originalInk2BaselineRef`)
- ✅ NOT clear `acceptedInk2Manuals` immediately (only on next approve)
- ✅ Recalculate with original baseline
- ✅ Update preview to show original values

**Ångra vs Godkänn Interaction:**
```
Session 1:
  Edit INK4.5c: 212 → 0
  Click Godkänn → Stored in acceptedInk2Manuals ✓

Session 2:
  Click "Redigera manuellt" (edit mode opens)
  Edit INK4.6a: 100000 → 50000
  Click Ångra → INK4.6a reverts to 100000 ✓
              → INK4.5c stays at 0 (from session 1) ✓
```

#### 3.5 Preview ↔ PDF Mirroring

**CRITICAL RULE:** All three outputs must show EXACTLY the same values at all times.

**Three Outputs:**
1. **Preview** (on screen)
   - Source: `recalculatedData` (during edit) or `ink2Data` (read-only)
   - Applies: `manualEdits` (current session) + `acceptedInk2Manuals` (previous sessions)

2. **Annual Report PDF** (Årsredovisning)
   - Source: `rr_data` and `br_data` from `companyData`
   - Generated: Backend combines RR + BR + Noter + FB
   - Tax values: From RR row 277 (linked to INK2)

3. **INK2 PDF** (Inkomstdeklaration 2)
   - Source: `build_override_map()` in backend
   - Priority: acceptedInk2Manuals > ink2Data > seFileData
   - Generated: Fills INK2_form.pdf template

**How Mirroring Works:**

```
User makes edit in INK2 module
    ↓
Preview updates immediately (via recalculatedData)
    ↓
User clicks Godkänn
    ↓
acceptedInk2Manuals updated ✓
ink2Data updated ✓
    ↓
handleTaxUpdateLogic() called
    ↓
RR/BR updated via API ✓
    ↓
onDataUpdate({ rr_data, br_data, ink2Data, acceptedInk2Manuals })
    ↓
ALL THREE SOURCES NOW IN SYNC:
    1. Preview: Uses ink2Data + acceptedInk2Manuals ✓
    2. Annual Report PDF: Uses updated rr_data/br_data ✓
    3. INK2 PDF: Uses acceptedInk2Manuals (highest priority) ✓
```

**Verification Checklist:**
```
After any INK2 change:
□ Preview shows new value
□ Download Annual Report PDF → RR/BR reflect change
□ Download INK2 PDF → field shows new value

Example - Change INK4.14a from 340000 to 1340000:
□ Preview: INK4.14a shows 1340000 ✓
□ Preview: INK4.16 (Underskott) shows 1340000 ✓
□ Preview: RR "Årets resultat" updated (tax changed) ✓
□ Annual Report PDF: RR shows updated result ✓
□ INK2 PDF: Field 4.14a shows 1340000 ✓
```

**Common Mirroring Bugs:**
1. **Preview shows X, PDF shows Y**
   - Cause: `acceptedInk2Manuals` not being used in PDF generation
   - Fix: Ensure `build_override_map()` applies manual edits last

2. **RR/BR not updating**
   - Cause: `handleTaxUpdateLogic()` not called or empty rr_data/br_data
   - Fix: Always call after approve, use actual rendered data

3. **Chat-injected value overwrites manual edit**
   - Cause: Mapping (e.g., unusedTaxLossAmount → INK4.14a) applied after manual edits
   - Fix: Check for manual override before applying mapping

---

### 4. Data Ripple Flow - Changes Must Propagate Everywhere
**Rule:** When user makes changes in INK2 module, they must ripple through to ALL outputs.

**Data Flow:**
```
User Edit in INK2 Module
    ↓
handleApproveChanges() in AnnualReportPreview.tsx
    ↓
onDataUpdate({ 
    acceptedInk2Manuals: {...},  ← Stores manual edits
    ink2Data: [...]              ← Updates with new amounts
})
    ↓
handleTaxUpdateLogic()
    ↓
API: /api/update-tax-in-financial-data
    ↓
RR/BR data updated with tax differences
    ↓
onDataUpdate({ rr_data, br_data, seFileData })
    ↓
ALL THREE OUTPUTS MUST REFLECT CHANGES:
    1. Preview (uses ink2Data + acceptedInk2Manuals) ✓
    2. Annual Report PDF (uses rr_data/br_data) ✓
    3. INK2 PDF (uses build_override_map() with acceptedInk2Manuals) ✓
```

**Test Case:**
1. Make manual edit to any INK2 field
2. Click "Godkänn och uppdatera skatt"
3. Check Preview → should show new value ✓
4. Download Annual Report PDF → should show updated RR/BR ✓
5. Download INK2 PDF → should show new value ✓

---

### 4. Download Module Visibility After Payment
**Location:** `frontend/src/components/AnnualReportPreview.tsx`

**Rule:** Once user reaches step 510 (after payment), the download module must ALWAYS remain visible, even when making subsequent edits.

**Logic:**
```typescript
{currentStep >= 510 && (
  <div data-section="download">
    <Download companyData={companyData} />
  </div>
)}
```

**Why This Works:**
- `currentStep` is managed by parent (DatabaseDrivenChat)
- After payment success, `currentStep` is set to 510
- Step 405 guard prevents navigation away from 510
- Download module stays visible ✓

**Test Case:**
1. Complete payment → currentStep = 510 → Download module visible ✓
2. Make manual edit in INK2 → Click approve → Step 405 NOT triggered ✓
3. Download module still visible ✓
4. Payment button NOT visible again ✓

---

## 📊 Data Structure Reference

### companyData Key Fields
```typescript
{
  // Tax calculation
  ink2Data: Array<{variable_name: string, amount: number}>,
  acceptedInk2Manuals: Record<string, number>,  // Manual edits
  taxButtonClickedBefore: boolean,               // Step 405 guard
  
  // Chat flow
  currentStep: number,
  triggerChatStep: number | null,
  
  // Chat injections
  unusedTaxLossAmount: number,                   // Maps to INK4.14a
  justeringSarskildLoneskatt: string,            // Maps to INK_sarskild_loneskatt
  
  // Financial data
  seFileData: {
    rr_data: Array<{variable_name, current_amount}>,
    br_data: Array<{variable_name, current_amount}>,
    ink2_data: Array<{variable_name, amount}>
  },
  rr_data: Array,  // Also stored at top level
  br_data: Array,  // Also stored at top level
  
  // Payment
  paymentCompleted: boolean
}
```

---

## 🔄 Critical State Update Patterns

### Pattern 1: Setting taxButtonClickedBefore
```typescript
// WRONG - sets flag and trigger together (race condition):
onDataUpdate({ 
  taxButtonClickedBefore: true,
  triggerChatStep: 405 
});

// CORRECT - set flag FIRST, then trigger:
if (isFirstTimeClick) {
  onDataUpdate({ taxButtonClickedBefore: true });
}
onDataUpdate({ acceptedInk2Manuals, ink2Data });
if (isFirstTimeClick) {
  onDataUpdate({ triggerChatStep: 405 });
}
```

### Pattern 2: Syncing RR/BR Data
```typescript
// WRONG - only updates seFileData:
onDataUpdate({
  seFileData: { ...seFileData, rr_data, br_data }
});

// CORRECT - updates both top-level and seFileData:
onDataUpdate({
  rr_data: result.rr_data,
  br_data: result.br_data,
  seFileData: {
    ...companyData.seFileData,
    rr_data: result.rr_data,
    br_data: result.br_data
  }
});
```

---

## 🎯 Chat Flow Critical Steps

### Step Flow (from chat_flow_rows.csv)
```
101 → Upload SIE file
103 → Show results
104 → Tax decision point
  ├─ "Ja, godkänn bokförd skatt" → 420 (skip tax calc)
  ├─ "Låt oss se över skatten" → 201 (SLP check)
  └─ "Gå till nedladdning" → 510 (skip to download)

201 → SLP adjustment (if needed)
301 → Unused tax loss (underskott)
401 → Final tax approval decision
  ├─ "Godkänn beräknad skatt" → 405 ✓ FIRST TIME ONLY
  └─ "Gör manuella ändringar" → 402 (manual edit mode)

402 → Manual edit mode
  └─ "Godkänn och uppdatera skatt" → 405 ✓ FIRST TIME ONLY

405 → Confirmation message (should only show ONCE)
420 → Noter review
505 → Payment
510 → Download (stays visible forever)
515 → Signering
```

**Critical:** Steps 401 and 402 both lead to 405, but 405 should only show ONCE total.

---

## 🐛 Common Bugs and How to Avoid Them

### Bug 1: Step 405 Triggering Multiple Times
**Symptoms:** User makes manual edit → Step 405 message appears again
**Root Cause:** Not checking `taxButtonClickedBefore` before navigation
**Fix:** Add guards in all 3 layers (see Rule #1)

### Bug 2: Manual Edits Not in PDF
**Symptoms:** Preview shows correct value, PDF shows old value
**Root Cause:** Something overwrites `acceptedInk2Manuals` in `build_override_map()`
**Fix:** Ensure manual edits are applied LAST, check for manual overrides before mappings

### Bug 3: RR/BR Not Updating
**Symptoms:** INK2 changes don't flow to RR/BR
**Root Cause:** Empty `rr_data`/`br_data` arrays sent to backend
**Fix:** Use actual rendered data, not just `seFileData` (see Pattern 2)

### Bug 4: Download Module Disappears
**Symptoms:** After payment, download module disappears when making edits
**Root Cause:** Step 405 navigation changes `currentStep` away from 510
**Fix:** Prevent step 405 navigation (see Rule #1)

---

## 🔍 Debugging Checklist

When investigating issues, check these in order:

1. **Console Logs** - Look for these key messages:
   - `🎯 First time clicking tax approve button - triggering step 405`
   - `✅ Subsequent tax approve - NOT triggering step 405`
   - `✅ Skipping navigation to step 405 - already shown before`
   - `✅ Mapped unusedTaxLossAmount to INK4.14a`
   - `ℹ️ Skipping unusedTaxLossAmount mapping - INK4.14a has manual override`

2. **State Values** - Verify these in console:
   - `companyData.taxButtonClickedBefore` (should be true after first approve)
   - `companyData.acceptedInk2Manuals` (should contain manual edits)
   - `companyData.ink2Data` (should be updated array)
   - `companyData.currentStep` (should be 510 after payment)

3. **API Calls** - Check network tab:
   - `/api/recalculate-ink2` - Returns calculated values
   - `/api/update-tax-in-financial-data` - Updates RR/BR
   - `/api/pdf/ink2-form` - Generates INK2 PDF

4. **PDF Generation** - Backend logs:
   - Look for priority order logs in `build_override_map()`
   - Check if manual overrides are being applied
   - Verify mappings are being skipped when appropriate

---

## 📝 Code Review Checklist

Before merging changes that touch these areas:

- [ ] Does this change affect step 405 navigation?
  - If yes, verify all 3 guard layers still work
  
- [ ] Does this change affect `build_override_map()`?
  - If yes, verify manual edits still have highest priority
  - Check if any new mappings need manual override checks
  
- [ ] Does this change affect `onDataUpdate()` calls?
  - If yes, verify both `rr_data` and `seFileData.rr_data` are updated
  - Check if `taxButtonClickedBefore` is set correctly
  
- [ ] Does this change affect INK2 data flow?
  - If yes, test that changes appear in Preview, Annual Report PDF, AND INK2 PDF
  
- [ ] Does this change affect chat flow navigation?
  - If yes, verify download module stays visible after step 510

---

## 🧪 Critical Test Scenarios

### Test 1: Complete Flow with Manual Edits
1. Upload SIE file
2. Go through chat flow (SLP, underskott, etc.)
3. At step 401, choose "Godkänn beräknad skatt"
4. Verify step 405 appears ✓
5. Continue to step 420 (Noter)
6. Go back to INK2, click manual edit
7. Change any value (e.g., INK4.5c)
8. Click "Godkänn och uppdatera skatt"
9. Verify step 405 does NOT appear again ✓
10. Verify Preview shows new value ✓
11. Continue to payment and complete
12. Verify download module appears ✓
13. Make another manual edit in INK2
14. Verify download module stays visible ✓
15. Download Annual Report PDF → verify updated RR/BR ✓
16. Download INK2 PDF → verify manual edit appears ✓

### Test 2: Chat-Injected Value Manual Edit
1. Upload SIE file
2. At step 302, enter unusedTaxLossAmount = 340000
3. Verify INK4.14a shows 340000 in preview ✓
4. Complete flow to step 405
5. Make manual edit: change INK4.14a to 1340000
6. Click approve
7. Verify step 405 does NOT appear again ✓
8. Verify preview shows 1340000 ✓
9. Download INK2 PDF
10. Verify PDF shows 1340000 (not 340000) ✓

### Test 3: Multiple Manual Edit Sessions
1. Complete flow to step 510 (after payment)
2. Make manual edit #1 in INK2
3. Approve → verify no step 405 ✓
4. Make manual edit #2 in INK2
5. Approve → verify no step 405 ✓
6. Make manual edit #3 in INK2
7. Approve → verify no step 405 ✓
8. Download INK2 PDF → verify all 3 edits appear ✓

---

## 🔧 Quick Reference - Where to Find Things

### Frontend Files
- **AnnualReportPreview.tsx** - Main preview component, INK2 module, manual edit handling
- **DatabaseDrivenChat.tsx** - Chat flow logic, step navigation, guards
- **Download.tsx** - PDF download handling
- **AnnualReportChat.tsx** - Top-level component, state management

### Backend Files
- **main.py** - API endpoints (`/api/recalculate-ink2`, `/api/update-tax-in-financial-data`, `/api/pdf/ink2-form`)
- **services/ink2_pdf_filler.py** - INK2 PDF generation, `build_override_map()` priority logic
- **services/DatabaseParser.py** - INK2 calculation logic

### Key Functions
- `handleApproveChanges()` - Approves manual edits, triggers step 405 (first time only)
- `handleTaxUpdateLogic()` - Updates RR/BR based on tax changes
- `recalcWithManuals()` - Recalculates INK2 with manual overrides
- `build_override_map()` - Determines priority order for PDF generation
- `loadChatStep()` - Navigates to chat step
- `handleOptionClick()` - Handles chat option clicks, navigation guard

---

## 📚 Related Documentation
- Chat flow: `chat_flow_rows (3).csv` on Desktop
- Database schema: Check SQL migrations
- API documentation: See backend/main.py docstrings

---

## ✅ Last Known Good State
**Commit:** `238f6ed` - "Fix: Prevent unusedTaxLossAmount from overwriting manual INK4.14a edits"
**Date:** 2025-01-19
**Status:** All critical flows working correctly

**Working Features:**
✅ Step 405 only triggers once
✅ Manual edits have highest priority
✅ Changes ripple to Preview, Annual Report PDF, and INK2 PDF
✅ Download module stays visible after payment
✅ Payment never triggers again after success
✅ Chat-injected values respect manual overrides

---

**END OF CRITICAL LOGIC DOCUMENTATION**

