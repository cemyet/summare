import re
from collections import defaultdict

def parse_bygg_k2_from_sie_text(sie_text: str, debug: bool = False, two_files_flag: bool = False, previous_year_sie_text: str = None) -> dict:
    """
    BYGG-note (K2) parser.

    Handles:
      - #VER with/without quoted titles; extra tokens after date.
      - #TRANS/#BTRANS/#RTRANS with or without "{}", optional date and trailing text.
      - IB/UB numbers with thousand spaces and commas (e.g. "-58 216 440,00").

    K2 business rules:
      • Uppskrivning (revaluation):          D building asset + K 2085
      • Depreciation on revaluation:         K 1119/1159 + D 2085
      • Ordinary depreciation:               K 1119/1159 + D 7820/7821/7824/7829 (and no D 2085)
      • Disposal:                            K building asset AND (D 1119/1159 OR 3972/7972 OR D 2085)
      • Nedskrivning (impairment):           D 7720 + K 1158
        Återföring (no disposal):            K 7770 + D 1158
        Återföring at disposal:              D 1158 within a disposal voucher
      • Inköp vs uppskrivning split per voucher:
            uppskr_del  = min(D asset, K 2085)
            inköp_del   = max(0, D asset - uppskr_del)

    Returns dict with:
      bygg_ib, arets_inkop_bygg, arets_fsg_bygg, arets_omklass_bygg, bygg_ub,
      ack_avskr_bygg_ib, aterfor_avskr_fsg_bygg, arets_avskr_bygg, ack_avskr_bygg_ub,
      ack_uppskr_bygg_ib, arets_uppskr_bygg, arets_avskr_uppskr_bygg, aterfor_uppskr_fsg_bygg, ack_uppskr_bygg_ub,
      ack_nedskr_bygg_ib, arets_nedskr_bygg, aterfor_nedskr_bygg, aterfor_nedskr_fsg_bygg, ack_nedskr_bygg_ub
    """
    # Normalize whitespace and NBSP so numbers like "58 216 440,00" parse
    sie_text = sie_text.replace("\u00A0", " ").replace("\t", " ")
    lines = sie_text.splitlines()

    # --- Parse SRU codes and account descriptions ---
    sru_codes = {}
    account_descriptions = {}
    
    sru_re = re.compile(r'^#SRU\s+(\d+)\s+(\d+)\s*$')
    konto_re = re.compile(r'^#KONTO\s+(\d+)\s+"([^"]*)"')
    
    for raw in lines:
        s = raw.strip()
        # Parse SRU codes
        m = sru_re.match(s)
        if m:
            account = int(m.group(1))
            sru = int(m.group(2))
            sru_codes[account] = sru
        
        # Parse account descriptions
        m = konto_re.match(s)
        if m:
            account = int(m.group(1))
            description = m.group(2)
            account_descriptions[account] = description

    # --- CONFIG (K2 – bygg/mark) ---
    # Use original base logic - no SRU integration here
    BUILDING_ASSET_RANGES = [(1110,1117),(1130,1139),(1140,1149),(1150,1157),(1180,1189)]
    ACC_DEP_BYGG = {1119, 1159}
    ACC_IMP_BYGG = {1158}
    
    UPSKR_FOND = 2085
    DISPOSAL_PL = {3972, 7972}
    DEPR_COST = {7820, 7821, 7824, 7829}
    IMPAIR_COST = 7720
    IMPAIR_REV  = 7770
    


    # --- Helpers ---
    def in_building_assets(acct: int) -> bool:
        return any(lo <= acct <= hi for lo,hi in BUILDING_ASSET_RANGES)

    def _to_float(s: str) -> float:
        # tolerant for "123 456,78" and "123,456.78"
        return float(s.strip().replace(" ", "").replace(",", "."))

    def get_balance(kind_flag: str, accounts):
        """Sum #IB or #UB for the given account set/ranges (current year '0' rows)."""
        total = 0.0
        # allow thousand spaces; allow optional trailing text after number
        bal_re = re.compile(rf'^#(?:{kind_flag})\s+0\s+(\d+)\s+(-?[0-9][0-9\s.,]*)(?:\s+.*)?$')
        for raw in lines:
            s = raw.strip()
            m = bal_re.match(s)
            if not m:
                continue
            acct = int(m.group(1))
            amount = _to_float(m.group(2))
            if isinstance(accounts, (set, frozenset)):
                ok = acct in accounts
            else:
                ok = any(lo <= acct <= hi for lo,hi in accounts)
            if ok:
                total += amount
        return total

    # --- Parse vouchers ---
    ver_header_re = re.compile(
        r'^#VER\s+(\S+)\s+(\d+)\s+(\d{8})(?:\s+(?:"[^"]*"|.+))?\s*$'
    )
    trans_re = re.compile(
        r'^#(?:BTRANS|RTRANS|TRANS)\s+'
        r'(\d{3,4})'                            
        r'(?:\s+\{.*?\})?'                      
        r'\s+(-?(?:\d{1,3}(?:[ \u00A0]?\d{3})*|\d+)(?:[.,]\d+)?)'  # amount only
        r'(?:\s+\d{8})?'                        
        r'(?:\s+".*?")?'                        
        r'\s*$'
    )

    trans_by_ver = defaultdict(list)
    current_ver = None
    in_block = False

    for raw in lines:
        t = raw.strip()
        mh = ver_header_re.match(t)
        if mh:
            current_ver = (mh.group(1), int(mh.group(2)))
            continue
        if t == "{":
            in_block = True
            continue
        if t == "}":
            in_block = False
            current_ver = None
            continue
        if in_block and current_ver:
            mt = trans_re.match(t)
            if mt:
                acct = int(mt.group(1))
                amt = _to_float(mt.group(2))
                trans_by_ver[current_ver].append((acct, amt))

    # --- IB balances ---
    bygg_ib               = get_balance('IB', BUILDING_ASSET_RANGES)  # asset (incl. uppskrivning since posted on asset)
    ack_avskr_bygg_ib     = get_balance('IB', ACC_DEP_BYGG)
    ack_nedskr_bygg_ib    = get_balance('IB', ACC_IMP_BYGG)
    ack_uppskr_bygg_ib    = get_balance('IB', {UPSKR_FOND})           # IB on 2085 (can be negative/credit)

    # --- Accumulators ---
    arets_inkop_bygg           = 0.0
    arets_fsg_bygg             = 0.0
    arets_omklass_bygg         = 0.0

    arets_avskr_bygg           = 0.0
    aterfor_avskr_fsg_bygg     = 0.0

    arets_uppskr_bygg          = 0.0
    arets_avskr_uppskr_bygg    = 0.0
    aterfor_uppskr_fsg_bygg    = 0.0

    arets_nedskr_bygg          = 0.0
    aterfor_nedskr_bygg        = 0.0
    aterfor_nedskr_fsg_bygg    = 0.0



    # --- Per voucher classification ---
    for key, txs in trans_by_ver.items():

        # Aggregate per voucher
        A_D  = sum(amt for a,amt in txs if in_building_assets(a) and amt > 0)     # Debet asset
        A_K  = sum(-amt for a,amt in txs if in_building_assets(a) and amt < 0)    # Kredit asset (abs)
        F2085_D = sum(amt for a,amt in txs if a == UPSKR_FOND and amt > 0)        # Debet 2085
        F2085_K = sum(-amt for a,amt in txs if a == UPSKR_FOND and amt < 0)       # Kredit 2085
        DEP_D = sum(amt for a,amt in txs if a in ACC_DEP_BYGG and amt > 0)        # Debet 1119/1159
        DEP_K = sum(-amt for a,amt in txs if a in ACC_DEP_BYGG and amt < 0)       # Kredit 1119/1159
        IMP_D = sum(amt for a,amt in txs if a in ACC_IMP_BYGG and amt > 0)        # Debet 1158
        IMP_K = sum(-amt for a,amt in txs if a in ACC_IMP_BYGG and amt < 0)       # Kredit 1158
        has_PL_disposal = any(a in DISPOSAL_PL for a,_ in txs)
        has_depr_cost = any((a in DEPR_COST and amt > 0) for a,amt in txs)
        has_imp_cost  = any((a == IMPAIR_COST and amt > 0) for a,amt in txs)
        has_imp_rev   = any((a == IMPAIR_REV  and amt < 0) for a,amt in txs)

        # 1) Disposal
        is_disposal = (A_K > 0) and (DEP_D > 0 or has_PL_disposal or F2085_D > 0)
        if is_disposal:
            arets_fsg_bygg         += A_K
            aterfor_avskr_fsg_bygg += DEP_D
            aterfor_uppskr_fsg_bygg+= F2085_D
            aterfor_nedskr_fsg_bygg+= IMP_D

        # 2) Split D asset into uppskrivning vs inköp
        uppskr_amount = min(A_D, F2085_K)  # part of D asset backed by K 2085
        if uppskr_amount > 0:
            arets_uppskr_bygg += uppskr_amount

        inkop_amount = max(0.0, A_D - uppskr_amount)
        if inkop_amount > 0:
            arets_inkop_bygg += inkop_amount

        # 3) Depreciations
        #    a) Depreciation on revaluation (K 1119/1159 + D 2085)
        if DEP_K > 0 and F2085_D > 0:
            inc = min(DEP_K, F2085_D)
            arets_avskr_uppskr_bygg += inc

        #    b) Ordinary depreciation (K 1119/1159 + D 78xx, but no D 2085)
        if DEP_K > 0 and has_depr_cost and F2085_D == 0:
            arets_avskr_bygg += DEP_K

        # 4) Impairments (non-disposal)
        if has_imp_cost and IMP_K > 0:
            arets_nedskr_bygg += sum(amt for a,amt in txs if a == IMPAIR_COST and amt > 0)
        if has_imp_rev and IMP_D > 0 and A_K == 0:
            aterfor_nedskr_bygg += IMP_D

        # 5) Omklass (both D & K asset, no signals)
        signals = (F2085_D+F2085_K+DEP_D+DEP_K+IMP_D+IMP_K) > 0 or has_PL_disposal or has_depr_cost or has_imp_cost or has_imp_rev
        if A_D > 0 and A_K > 0 and not signals:
            arets_omklass_bygg += (A_D - A_K)

    # --- UB formulas ---
    bygg_ub = bygg_ib + arets_inkop_bygg - arets_fsg_bygg + arets_omklass_bygg

    ack_avskr_bygg_ub = (
        ack_avskr_bygg_ib
      + aterfor_avskr_fsg_bygg
      - arets_avskr_bygg
    )

    ack_uppskr_bygg_ub = (
        ack_uppskr_bygg_ib       # IB on 2085 (credit balance shows as negative)
      + arets_uppskr_bygg
      - arets_avskr_uppskr_bygg
      - aterfor_uppskr_fsg_bygg
    )

    ack_nedskr_bygg_ub = (
        ack_nedskr_bygg_ib
      + aterfor_nedskr_fsg_bygg
      + aterfor_nedskr_bygg
      - arets_nedskr_bygg
    )

    # --- Derived calculations ---
    red_varde_bygg = bygg_ub + ack_avskr_bygg_ub + ack_nedskr_bygg_ub + ack_uppskr_bygg_ub  # Book value

    # --- SRU ADDITION: Handle rare cases of accounts from other ranges with SRU 7214 ---
    # This is a separate addition to the base logic, not integrated into it
    if sru_codes:
        additional_bygg_ib = 0.0
        additional_avskr_ib = 0.0
        additional_nedskr_ib = 0.0
        
        for account, sru in sru_codes.items():
            # Check if this account is from the 1200-1299 range with SRU 7214
            in_other_ranges = 1200 <= account <= 1299
            
            if in_other_ranges and sru == 7214:
                # Get the IB balance for this account
                account_ib = get_balance('IB', {account})
                
                # Use account description to determine BYGG categorization
                description = account_descriptions.get(account, "").lower()
                
                if "avskr" in description:  # Contains "avskr" (avskrivning, avskrivningar, etc.)
                    additional_avskr_ib += account_ib
                elif "nedskr" in description:  # Contains "nedskr" (nedskrivning, nedskrivningar, etc.)
                    additional_nedskr_ib += account_ib
                else:  # No special keywords or "uppskr" - treat as main asset
                    additional_bygg_ib += account_ib
        
        # Add the additional amounts to the results
        if additional_bygg_ib != 0 or additional_avskr_ib != 0 or additional_nedskr_ib != 0:
            bygg_ib += additional_bygg_ib
            ack_avskr_bygg_ib += additional_avskr_ib
            ack_nedskr_bygg_ib += additional_nedskr_ib
            
            # Recalculate UB values with the additions
            bygg_ub = bygg_ib + arets_inkop_bygg - arets_fsg_bygg + arets_omklass_bygg
            ack_avskr_bygg_ub = ack_avskr_bygg_ib + aterfor_avskr_fsg_bygg - arets_avskr_bygg
            ack_nedskr_bygg_ub = ack_nedskr_bygg_ib + aterfor_nedskr_fsg_bygg + aterfor_nedskr_bygg - arets_nedskr_bygg
            red_varde_bygg = bygg_ub + ack_avskr_bygg_ub + ack_nedskr_bygg_ub + ack_uppskr_bygg_ub

    # =========================
    # PREVIOUS YEAR FORK LOGIC
    # =========================
    # Debug: Log the fork decision
    print(f"[BYGG-DEBUG] Fork decision: two_files_flag={two_files_flag}, has_previous_text={previous_year_sie_text is not None}")
    if previous_year_sie_text:
        print(f"[BYGG-DEBUG] Previous year text length: {len(previous_year_sie_text)} characters")
    
    if two_files_flag and previous_year_sie_text:
        # ========================================
        # TWO FILES MODE: Run full parser on previous year SE file
        # ========================================
        if debug:
            print("[BYGG-DEBUG] Two files mode: Running full parser on previous year SE file")
        
        # Recursively call the parser on the previous year SE file
        prev_year_result = parse_bygg_k2_from_sie_text(
            previous_year_sie_text, 
            debug=debug, 
            two_files_flag=False,  # Prevent infinite recursion
            previous_year_sie_text=None
        )
        
        # Extract ALL previous year values from the full parser result
        # Asset movements and balances
        bygg_ib_prev = prev_year_result.get('bygg_ib', 0.0)
        bygg_ub_prev = prev_year_result.get('bygg_ub', 0.0)
        red_varde_bygg_prev = prev_year_result.get('red_varde_bygg', 0.0)
        
        # ALL asset movements from full parser
        arets_inkop_bygg_prev = prev_year_result.get('arets_inkop_bygg', 0.0)
        fsg_bygg_prev = prev_year_result.get('arets_fsg_bygg', 0.0)
        
        # ALL depreciation movements from full parser
        ack_avskr_bygg_ib_prev = prev_year_result.get('ack_avskr_bygg_ib', 0.0)
        ack_avskr_bygg_ub_prev = prev_year_result.get('ack_avskr_bygg_ub', 0.0)
        arets_avskr_bygg_prev = prev_year_result.get('arets_avskr_bygg', 0.0)
        
        # ALL impairment movements from full parser
        ack_nedskr_bygg_ib_prev = prev_year_result.get('ack_nedskr_bygg_ib', 0.0)
        ack_nedskr_bygg_ub_prev = prev_year_result.get('ack_nedskr_bygg_ub', 0.0)
        arets_nedskr_bygg_prev = prev_year_result.get('arets_nedskr_bygg', 0.0)
        aterfor_nedskr_bygg_prev = prev_year_result.get('aterfor_nedskr_bygg', 0.0)
        
        # ALL revaluation movements from full parser
        uppskr_bygg_ib_prev = prev_year_result.get('ack_uppskr_bygg_ib', 0.0)
        uppskr_bygg_ub_prev = prev_year_result.get('ack_uppskr_bygg_ub', 0.0)
        arets_uppskr_bygg_prev = prev_year_result.get('arets_uppskr_bygg', 0.0)
        aterfor_uppskr_bygg_prev = prev_year_result.get('aterfor_uppskr_bygg', 0.0)
        
    else:
        # ========================================
        # FALLBACK MODE: Balance-only calculation (original logic)
        # ========================================
        if debug:
            print("[BYGG-DEBUG] Fallback mode: Using balance-only calculation for previous year")
        
        # Initialize ALL movement variables to 0.0 for fallback mode
        arets_inkop_bygg_prev = 0.0
        fsg_bygg_prev = 0.0
        arets_avskr_bygg_prev = 0.0
        arets_nedskr_bygg_prev = 0.0
        aterfor_nedskr_bygg_prev = 0.0
        arets_uppskr_bygg_prev = 0.0
        aterfor_uppskr_bygg_prev = 0.0
        
        # =========================
        # PREVIOUS YEAR (FROM SAME SIE; NO VOUCHERS)
        # =========================
        # Reuse the *exact* account sets discovered for current year:
        #   - BUILDING_ASSET_RANGES : cost accounts (e.g., 1110, 1150, etc.)
        #   - ACC_DEP_BYGG         : accumulated depreciation accounts (e.g., 1119, 1159, etc.)
        #   - ACC_IMP_BYGG         : accumulated impairment accounts (e.g., 1158, etc.)
        #   - UPSKR_FOND           : asset-side revaluation adjustment account (2085)

        def _get_balance_prev(lines, kind_flag: str, accounts) -> float:
            """
            Sum #IB -1 or #UB -1 for the given accounts (set or ranges).
            kind_flag ∈ {"IB", "UB"}.
            If 'accounts' is None or empty, returns 0.0.
            """
            if not accounts:
                return 0.0
            total = 0.0
            bal_re_prev = re.compile(rf'^#(?:{kind_flag})\s+-1\s+(\d+)\s+(-?[0-9][0-9\s.,]*)(?:\s+.*)?$')
            for raw in lines:
                s = raw.strip()
                m = bal_re_prev.match(s)
                if not m:
                    continue
                acct = int(m.group(1))
                # Handle both sets and ranges like the original get_balance function
                if isinstance(accounts, (set, frozenset)):
                    ok = acct in accounts
                elif isinstance(accounts, int):
                    ok = acct == accounts
                else:
                    ok = any(lo <= acct <= hi for lo, hi in accounts)
                if ok:
                    total += _to_float(m.group(2))
            return total

        # --- Previous-year balances using SAME sets as current year ---
        bygg_ib_prev  = _get_balance_prev(lines, 'IB', BUILDING_ASSET_RANGES)
        bygg_ub_prev  = _get_balance_prev(lines, 'UB', BUILDING_ASSET_RANGES)

        ack_avskr_bygg_ib_prev = _get_balance_prev(lines, 'IB', ACC_DEP_BYGG)
        ack_avskr_bygg_ub_prev = _get_balance_prev(lines, 'UB', ACC_DEP_BYGG)

        ack_nedskr_bygg_ib_prev = _get_balance_prev(lines, 'IB', ACC_IMP_BYGG)
        ack_nedskr_bygg_ub_prev = _get_balance_prev(lines, 'UB', ACC_IMP_BYGG)

        uppskr_bygg_ib_prev = _get_balance_prev(lines, 'IB', UPSKR_FOND)
        uppskr_bygg_ub_prev = _get_balance_prev(lines, 'UB', UPSKR_FOND)

        # Redovisat värde (prev) = UB cost + UB uppskr + UB acc. impairments + UB acc. depreciation
        red_varde_bygg_prev = (
            (bygg_ub_prev or 0.0)
            + (uppskr_bygg_ub_prev or 0.0)
            + (ack_nedskr_bygg_ub_prev or 0.0)
            + (ack_avskr_bygg_ub_prev or 0.0)
        )

        # Cost delta(prev) = UB(prev) - IB(prev) → negative = sales, positive = purchases
        delta_prev = (bygg_ub_prev or 0.0) - (bygg_ib_prev or 0.0)
        
        if bygg_ub_prev < bygg_ib_prev:
            fsg_bygg_prev = delta_prev
        elif bygg_ub_prev > bygg_ib_prev:
            arets_inkop_bygg_prev = delta_prev

        # Impairment movement (magnitudes)
        abs_imp_ib = abs(ack_nedskr_bygg_ib_prev or 0.0)
        abs_imp_ub = abs(ack_nedskr_bygg_ub_prev or 0.0)

        if abs_imp_ib > abs_imp_ub:
            aterfor_nedskr_bygg_prev = abs_imp_ib - abs_imp_ub        # positive
        elif abs_imp_ib < abs_imp_ub:
            arets_nedskr_bygg_prev = abs_imp_ib - abs_imp_ub          # negative by definition

        # Depreciation movement
        if ACC_DEP_BYGG:
            abs_avskr_ib = abs(ack_avskr_bygg_ib_prev or 0.0)
            abs_avskr_ub = abs(ack_avskr_bygg_ub_prev or 0.0)
            arets_avskr_bygg_prev = abs_avskr_ub - abs_avskr_ib

    # --- Backend debug (one line per variable) ---
    if debug:
        try:
            print(f"[BYGG-DEBUG] accounts_used.asset = {BUILDING_ASSET_RANGES}")
        except Exception:
            print("[BYGG-DEBUG] accounts_used.asset = <unavailable>")

        try:
            print(f"[BYGG-DEBUG] accounts_used.acc_avskr = {sorted(list(ACC_DEP_BYGG))}")
        except Exception:
            print("[BYGG-DEBUG] accounts_used.acc_avskr = <unavailable>")

        try:
            print(f"[BYGG-DEBUG] accounts_used.acc_imp = {sorted(list(ACC_IMP_BYGG))}")
        except Exception:
            print("[BYGG-DEBUG] accounts_used.acc_imp = <unavailable>")

        try:
            print(f"[BYGG-DEBUG] accounts_used.uppskr = {UPSKR_FOND}")
        except Exception:
            print("[BYGG-DEBUG] accounts_used.uppskr = <unavailable>")

        print(f"[BYGG-DEBUG] bygg_ib current={bygg_ib} previous={bygg_ib_prev}")
        print(f"[BYGG-DEBUG] bygg_ub current={bygg_ub} previous={bygg_ub_prev}")
        print(f"[BYGG-DEBUG] ack_avskr_ib current={ack_avskr_bygg_ib} previous={ack_avskr_bygg_ib_prev}")
        print(f"[BYGG-DEBUG] ack_avskr_ub current={ack_avskr_bygg_ub} previous={ack_avskr_bygg_ub_prev}")
        print(f"[BYGG-DEBUG] ack_nedskr_ib current={ack_nedskr_bygg_ib} previous={ack_nedskr_bygg_ib_prev}")
        print(f"[BYGG-DEBUG] ack_nedskr_ub current={ack_nedskr_bygg_ub} previous={ack_nedskr_bygg_ub_prev}")
        print(f"[BYGG-DEBUG] uppskr_ib current={ack_uppskr_bygg_ib} previous={uppskr_bygg_ib_prev}")
        print(f"[BYGG-DEBUG] uppskr_ub current={ack_uppskr_bygg_ub} previous={uppskr_bygg_ub_prev}")
        print(f"[BYGG-DEBUG] red_varde current={red_varde_bygg} previous={red_varde_bygg_prev}")
        print(f"[BYGG-DEBUG] inkop_prev={arets_inkop_bygg_prev}  fsg_prev={fsg_bygg_prev}")
        print(f"[BYGG-DEBUG] aterfor_nedskr_prev={aterfor_nedskr_bygg_prev} arets_nedskr_prev={arets_nedskr_bygg_prev}")
        print(f"[BYGG-DEBUG] arets_avskr_prev={arets_avskr_bygg_prev}")

    return {
        # IB/UB assets
        "bygg_ib": bygg_ib,
        "arets_inkop_bygg": arets_inkop_bygg,
        "arets_fsg_bygg": arets_fsg_bygg,
        "arets_omklass_bygg": arets_omklass_bygg,
        "bygg_ub": bygg_ub,

        # Depreciations (historical cost)
        "ack_avskr_bygg_ib": ack_avskr_bygg_ib,
        "aterfor_avskr_fsg_bygg": aterfor_avskr_fsg_bygg,
        "arets_avskr_bygg": arets_avskr_bygg,
        "ack_avskr_bygg_ub": ack_avskr_bygg_ub,

        # Revaluations (via 2085)
        "ack_uppskr_bygg_ib": ack_uppskr_bygg_ib,
        "arets_uppskr_bygg": arets_uppskr_bygg,
        "arets_avskr_uppskr_bygg": arets_avskr_uppskr_bygg,
        "aterfor_uppskr_fsg_bygg": aterfor_uppskr_fsg_bygg,
        "ack_uppskr_bygg_ub": ack_uppskr_bygg_ub,

        # Impairments
        "ack_nedskr_bygg_ib": ack_nedskr_bygg_ib,
        "arets_nedskr_bygg": arets_nedskr_bygg,
        "aterfor_nedskr_bygg": aterfor_nedskr_bygg,
        "aterfor_nedskr_fsg_bygg": aterfor_nedskr_fsg_bygg,
        "ack_nedskr_bygg_ub": ack_nedskr_bygg_ub,

        # Derived book value
        "red_varde_bygg": red_varde_bygg,

        # Previous year values (for preview display)
        "bygg_ib_prev": bygg_ib_prev,
        "bygg_ub_prev": bygg_ub_prev,
        "ack_avskr_bygg_ib_prev": ack_avskr_bygg_ib_prev,
        "ack_avskr_bygg_ub_prev": ack_avskr_bygg_ub_prev,
        "ack_nedskr_bygg_ib_prev": ack_nedskr_bygg_ib_prev,
        "ack_nedskr_bygg_ub_prev": ack_nedskr_bygg_ub_prev,
        "uppskr_bygg_ib_prev": uppskr_bygg_ib_prev,
        "uppskr_bygg_ub_prev": uppskr_bygg_ub_prev,
        "red_varde_bygg_prev": red_varde_bygg_prev,
        "fsg_bygg_prev": fsg_bygg_prev,
        "arets_inkop_bygg_prev": arets_inkop_bygg_prev,
        "aterfor_nedskr_bygg_prev": aterfor_nedskr_bygg_prev,
        "arets_nedskr_bygg_prev": arets_nedskr_bygg_prev,
        "arets_avskr_bygg_prev": arets_avskr_bygg_prev,
    }

