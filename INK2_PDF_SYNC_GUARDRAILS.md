
# INK2 PDF Sync — Postmortem & Guardrails
**Last Updated:** 2025-10-26 13:40

This document captures the **root cause**, **fix**, and **do-not-break** rules for the bug where **the first manual edit in INK2 did not show up in the INK2 PDF** (fields **4.15/4.16**) until a *second* edit was made.

---

## TL;DR
- **Symptom:** After step **302** (inject 4.14a) and step **401** (accept tax), a **first** manual edit updated the **INK2 preview** but **not** the **INK2 PDF**. A **second** manual edit suddenly made the PDF correct.
- **Root Cause:** During manual-edit recalculation, we **did not update `companyData.ink2Data`**. The PDF generator reads **`companyData.ink2Data`**, so it used a **stale** snapshot (from step 401).
- **Fix:** **Always** sync `companyData.ink2Data` after every recalculation — including during manual edit. (Optional: add a **preflight** sync right before generating the PDF.)

---

## Reproduction Steps (original bug)
1. Step **302**: Inject a value into **4.14a** (Unused tax loss).
2. Step **401**: Choose **Option 1 – Godkänn beräknad skatt**. This creates a "post‑401" snapshot in `companyData.ink2Data`.
3. Open **manual edit** in the INK2 module; change any field that affects result.
4. **Preview** shows new values (correct), **INK2 PDF** still shows values from the "post‑401" snapshot (**wrong**).
5. Make **another** manual edit.
6. Now the **INK2 PDF** updates and matches the preview (**right**).

---

## Design Constraints (why this matters)
- **Calc‑only fields** (e.g., **4.15/4.16**) are **derived** and **not meant to be manually overridden**.  
- The backend **INK2 PDF filler** takes **4.15/4.16** from **`companyData.ink2Data`** (the latest calculation) and **ignores manual overrides** for these calc‑only fields **by design**.
- Therefore, the frontend must **always** keep `companyData.ink2Data` **fresh** whenever a recalculation happens (including during manual edit).

> If `ink2Data` falls out of sync, the preview can look correct (because it renders from local `recalculatedData`), while the PDF shows **stale** numbers (because it reads `ink2Data`).

---

## Old (Buggy) Version — **Do NOT re‑introduce**
Location: `AnnualReportPreview.tsx` (in the recalc success handler)

```ts
// After: setRecalculatedData(merged);

// ❌ BUG: only writes ink2Data when NOT in manual edit mode
if (!isInk2ManualEdit) {
  onDataUpdate({
    ink2Data: merged,
    inkBeraknadSkatt:
      merged.find((i:any)=>i.variable_name==='INK_beraknad_skatt')?.amount
      ?? companyData.inkBeraknadSkatt
  });
} else {
  // In edit mode we only touched INK_beraknad_skatt, leaving ink2Data stale
  onDataUpdate({
    inkBeraknadSkatt:
      merged.find((i:any)=>i.variable_name==='INK_beraknad_skatt')?.amount
      ?? companyData.inkBeraknadSkatt
  });
}
```

**Why it fails:** During manual edit, `ink2Data` stays **stale** (post‑401 snapshot), so **PDF ≠ Preview**.

---

## New (Fixed) Version — **Keep this**
Location: `AnnualReportPreview.tsx` (in the recalc success handler)

```ts
// After: setRecalculatedData(merged);

// ✅ Always keep companyData.ink2Data fresh (even during manual edit)
onDataUpdate({
  ink2Data: merged,
  inkBeraknadSkatt:
    merged.find((i:any)=>i.variable_name==='INK_beraknad_skatt')?.amount
    ?? companyData.inkBeraknadSkatt
});
```

**Why it works:** PDF filler sees fresh `ink2Data`, so **PDF = Preview on the first edit**.

> **Important:** Ensure only **one** implementation of this recalc success handler exists.  
> Having **duplicate** handlers (one buggy, one correct) can cause inconsistent behavior.

---

## Optional Safety Net (PDF preflight)
If your PDF trigger is in another component (e.g., a `Download` button), add this **just before** calling the backend:

```ts
onDataUpdate?.({
  ink2Data: (recalculatedData?.length ? recalculatedData : companyData.ink2Data)
});
```

This guarantees the backend sees the **freshest** array even if some edge path skipped a recalc write.

---

## Acceptance Tests
**Goal:** 4.15/4.16 in the **INK2 PDF** must match the **preview on the first manual edit**.

1) **First‑edit sync**
- 302 → inject 4.14a
- 401 → accept tax
- Manual edit → change a value that affects result  
- **Expected:** INK2 PDF = Preview (4.15/4.16 match)

2) **Subsequent edits**
- Make two more manual edits and approve each
- **Expected:** INK2 PDF stays in sync every time

3) **End‑to‑end ripple**
- Approve changes → RR/BR update via `handleTaxUpdateLogic()`  
- **Expected:** Annual Report PDF reflects the same tax and result changes

---

## Do‑Not‑Break Rules (for future refactors)
1. **Always** sync `companyData.ink2Data` after **every** recalculation — even in manual edit mode.
2. The preview may render from `recalculatedData`, but the **PDF** reads **`ink2Data`**; keep both aligned.
3. Calc‑only fields (4.15/4.16) are **derived** → PDF must use **`ink2Data`**; manual overrides are **ignored** for these fields.
4. If adding mappings (e.g., chat → INK fields), **never** apply them **after** manual overrides for **non‑calc** fields.
5. Avoid duplicate implementations of the recalc success handler.
6. If in doubt, add the **PDF preflight** sync near the download call.

---

## File & Function Pointers
- **Frontend**
  - `AnnualReportPreview.tsx`
    - `recalcWithManuals()` success → **ALWAYS update `ink2Data`**
    - `handleApproveChanges()` → stores `acceptedInk2Manuals`, triggers RR/BR update
  - `RightPane.tsx` or `Download.tsx` (wherever PDF is triggered)
    - Optional **preflight** sync before calling PDF API
- **Backend**
  - `ink2_pdf_filler.py`
    - Uses **`companyData.ink2Data`** for calc‑only fields (4.15/4.16)
    - Manual overrides are **ignored** for calc‑only fields by design

---

## Quick Diff (apply if needed)
```diff
- if (!isInk2ManualEdit) {
-   onDataUpdate({ ink2Data: merged, inkBeraknadSkatt: calc });
- } else {
-   onDataUpdate({ inkBeraknadSkatt: calc });
- }
+ onDataUpdate({ ink2Data: merged, inkBeraknadSkatt: calc });
```

---

## Known Good State
- **Behavior:** First manual edit updates both Preview and INK2 PDF (4.15/4.16) immediately.
- **Guard:** Optional PDF preflight in the download handler.

---

## Related UX Issue: INK2 Module Disappearing After Approval
**Last Updated:** 2025-10-26 13:40

### Symptom
When user has "Show all rows" toggle ON in INK2 module:
1. User clicks **"Godkänn och uppdatera skatt"** blue button
2. `setShowAllTax(false)` is called → rows collapse (only non-zero rows visible)
3. INK2 module becomes much shorter
4. Module scrolls out of view
5. User has to manually scroll back up to see the module ❌

### Root Cause
- When `showAllTax` is toggled from `true` to `false`, many zero-value rows are hidden
- The INK2 module height shrinks dramatically
- Browser maintains scroll position relative to document, not the module
- Module ends up above the viewport

### Fix
Add autoscroll after `setShowAllTax(false)` in `handleApproveChanges()`:

```ts
setShowAllTax(false);

// Autoscroll to keep INK2 module visible after rows collapse
setTimeout(() => {
  const taxModule = document.querySelector('[data-section="tax-calculation"]');
  const scrollContainer = document.querySelector('.overflow-auto');
  
  if (taxModule && scrollContainer) {
    const containerRect = scrollContainer.getBoundingClientRect();
    const taxRect = taxModule.getBoundingClientRect();
    const scrollTop = scrollContainer.scrollTop + taxRect.top - containerRect.top - 20;
    
    scrollContainer.scrollTo({
      top: scrollTop,
      behavior: 'smooth'
    });
  }
}, 300); // Wait for collapse animation to complete
```

### Why This Works
- **300ms delay:** Waits for CSS transition/collapse animation to complete
- **20px padding:** Provides visual breathing room at the top
- **Smooth behavior:** Better UX than instant jump
- **Selector-based:** Finds INK2 module by `data-section` attribute

### Acceptance Test
1. Toggle "Show all rows" ON in INK2 module
2. Make manual edits
3. Click "Godkänn och uppdatera skatt"
4. **Expected:** Module stays visible with smooth scroll, doesn't disappear

### Do-Not-Break Rule
When calling `setShowAllTax(false)` after user action, **always** add autoscroll to keep the INK2 module visible. The delay should match or exceed the CSS collapse animation duration.

---

*End of document.*

