# Explanation: Voucher-Based "Balanseras i ny räkning" Logic

## The Original Logic

The code used a **voucher-based pattern matching** approach to find "Balanseras i ny räkning" transactions. Here's how it worked:

### Pattern Matching Logic

The function `_calculate_balanseras_nyrakning_from_verifications()` looked for vouchers that match this pattern:
- **Account 2091** (Balanserat resultat) with a **DEBET** entry (positive amount)
- **Account 2099** (Årets resultat) with a **KREDIT** entry (negative amount)

When both conditions are met in the same voucher, it assumes this is a "balanseras i ny räkning" transaction.

### What It Found in Voucher 319

Looking at voucher 319 in the SIE file:

```
#VER A 319 20241231 "Omföring balanserad vinst"
{
#BTRANS 2091 {} -51893.74 20250725 "" "" "Cem Yeter"   ← KREDIT (negative)
#BTRANS 2091 {} 51893.74 20250730 "" "" "Cem Yeter"   ← DEBET (positive) ✓
#BTRANS 2099 {} -51893.74 20250730 "" "" "Cem Yeter"  ← KREDIT (negative) ✓
#BTRANS 2099 {} 51893.74 20250725 "" "" "Cem Yeter"   ← DEBET (positive)
}
```

**Note:** The `fb.py` parser includes `BTRANS` in its regex pattern (line 38: `r'^#(?:BTRANS|RTRANS|TRANS)\s+'`), unlike other parsers in the codebase that explicitly ignore BTRANS transactions. This is why it found this voucher.

**How the pattern matched:**
1. Found account 2091 with DEBET (positive): `51893.74` ✓
2. Found account 2099 with KREDIT (negative): `-51893.74` ✓
3. Both conditions met → This is a "balanseras" transaction
4. Takes the DEBET amount from 2091: `51893.74`
5. Returns the negative: `-51893.74`

### Why This Was Wrong

**The Problem:**
- Voucher 319 only transfers **51,894.74** from 2099 to 2091
- But the **previous year's "Årets resultat"** was **196,089.02** (from `#UB -1 2099 196089.02`)
- The full amount that should be "balanseras" is **196,089.02 minus any dividends**

**Why Voucher 319 is Incomplete:**
Voucher 319 appears to be a **partial correction/adjustment** voucher, not the main "balanseras i ny räkning" transaction. It has both positive and negative entries for the same accounts, suggesting it's correcting or adjusting a previous entry.

The voucher structure shows:
- Two entries for 2091 (one positive, one negative)
- Two entries for 2099 (one positive, one negative)
- This is typical of correction vouchers that reverse and re-enter amounts

### The Correct Logic

"Balanseras i ny räkning" should represent:
- **How much of the previous year's "Årets resultat" is transferred to "Balanserat resultat"**
- Formula: `Previous year's "Årets resultat" - Dividends paid`

In this case:
- Previous year's result: **196,089.02**
- Dividends: **0** (no dividends found)
- Should be: **196,089.02** (not 51,894.74)

### The Fix

The code now:
1. **Calculates the expected value** from BR data: `arets_resultat_prev_ub - utdelning`
2. **Validates voucher values** against the expected value
3. **Uses the expected value** if vouchers don't match (within tolerance)

This ensures the table always shows the correct amount based on the previous year's result, regardless of how the vouchers are structured.

