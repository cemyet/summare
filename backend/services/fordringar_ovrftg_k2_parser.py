import re
import unicodedata
from collections import defaultdict

def parse_fordringar_ovrftg_k2_from_sie_text(sie_text: str, debug: bool = False) -> dict:
    """
    FORDRINGAR ÖVRIGA FÖRETAG-note (K2) parser — Långfristiga fordringar hos övriga företag som det finns ett ägarintresse i
    
    Handles long-term receivables from other companies with ownership interest with the following business rules:
    
    Asset inclusion filter:
      • Include account 1346 WITH SRU = 7235 (both conditions must be met)
      • EXCLUDE from assets if account name contains both an 'ack*' token AND a 'ned*' token
        (e.g., 'Ack nedskrivningar ...').
    
    Impairment accounts:
      • 1347 (primary impairment account)
      • Any 134x whose name clearly says 'nedskr' or 'ackum' AND has SRU = 7235
      
    This handles companies with ownership interest that are not koncern or intresse companies.
    
    Returns dict with cost roll-forward, impairment movements, and book value calculations.
    """
    
    # ---------- Helper functions ----------
    def _normalize(s: str) -> str:
        """Normalize string for text matching"""
        if not s:
            return ""
        s = unicodedata.normalize("NFKD", s)
        s = "".join(ch for ch in s if not unicodedata.combining(ch))
        s = s.lower().replace("\u00a0", " ").replace("\t", " ")
        s = re.sub(r"[^a-z0-9 ]+", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def _to_float(s: str) -> float:
        """Convert string to float, handling spaces and commas"""
        return float((s or "0").replace(" ", "").replace(",", "."))

    def _parse_accounts_and_sru(sie_text: str):
        """Parse account names and SRU codes from SIE text"""
        names, sru = {}, {}
        rx_konto = re.compile(r'^#KONTO\s+(\d{4})\s+"(.*)"\s*$')
        rx_sru   = re.compile(r'^#SRU\s+(\d{4})\s+(\d+)\s*$')
        
        for raw in sie_text.splitlines():
            t = raw.strip()
            mk = rx_konto.match(t)
            if mk:
                names[int(mk.group(1))] = _normalize(mk.group(2))
                continue
            ms = rx_sru.match(t)
            if ms:
                sru[int(ms.group(1))] = int(ms.group(2))
        return names, sru

    def _get_balance(lines, kind_flag: str, accounts: set) -> float:
        """Get IB or UB balance for specified accounts"""
        if not accounts: 
            return 0.0
        rx = re.compile(rf'^#(?:{kind_flag})\s+0\s+(\d+)\s+(-?[0-9][0-9\s.,]*)')
        acct_set = set(accounts)
        tot = 0.0
        for raw in lines:
            m = rx.match(raw.strip())
            if not m: 
                continue
            a = int(m.group(1))
            if a in acct_set:
                tot += _to_float(m.group(2))
        return tot

    def _parse_vouchers(lines):
        """Parse vouchers from SIE lines"""
        rx_ver = re.compile(r'^#VER\s+(\S+)\s+(\d+)\s+(\d{8})(?:\s+(?:"([^"]*)"|.+))?\s*$')
        rx_tx  = re.compile(
            r'^#(?:BTRANS|RTRANS|TRANS)\s+'
            r'(\d{3,4})(?:\s+\{.*?\})?\s+'
            r'(-?(?:\d{1,3}(?:[ \u00A0]?\d{3})*|\d+)(?:[.,]\d+)?)'
            r'(?:\s+\d{8})?(?:\s+".*?")?\s*$'
        )
        trans_by_ver = defaultdict(list)
        text_by_ver = {}
        cur = None
        in_block = False
        
        for raw in lines:
            t = raw.strip()
            mh = rx_ver.match(t)
            if mh:
                cur = (mh.group(1), int(mh.group(2)))
                text_by_ver[cur] = _normalize(mh.group(4) or "")
                continue
            if t == "{": 
                in_block = True
                continue
            if t == "}": 
                in_block = False
                cur = None
                continue
            if in_block and cur:
                mt = rx_tx.match(t)
                if mt:
                    trans_by_ver[cur].append((int(mt.group(1)), _to_float(mt.group(2))))
        return trans_by_ver, text_by_ver

    # ---------- Main parsing logic ----------
    sie_text = sie_text.replace("\u00A0", " ").replace("\t", " ")
    lines = sie_text.splitlines()

    # Parse accounts and SRU codes
    names, sru = _parse_accounts_and_sru(sie_text)

    # Name detectors (on normalized text)
    ACK_TOK = re.compile(r'\b(?:ack\w*|ackum\w*)\b')
    NED_TOK = re.compile(r'\b(?:nedskr\w*|vardened\w*)\b')
    
    def has_ack_and_ned(nm: str) -> bool:
        return bool(ACK_TOK.search(nm)) and bool(NED_TOK.search(nm))
    
    def is_imp_name(nm: str) -> bool:
        return ("nedskr" in nm) or ("ackum" in nm)

    # Build asset and impairment sets
    ASSET_SET = set()
    
    # Only account 1346 with SRU 7235, excluding names with both ack+ned tokens
    if sru.get(1346) == 7235 and not has_ack_and_ned(names.get(1346, "")):
        ASSET_SET.add(1346)

    # Impairment set: 1347 + any 134x with nedskr/ackum in name AND SRU 7235
    IMP_SET = {1347}
    
    for a, nm in names.items():
        if 1340 <= a <= 1349 and sru.get(a) == 7235 and a != 1347 and is_imp_name(nm):
            IMP_SET.add(a)

    if debug:
        pass

    # Get IB/UB factual balances
    fordr_ovrigaftg_ib = _get_balance(lines, "IB", ASSET_SET)
    ack_nedskr_fordr_ovrigaftg_ib = _get_balance(lines, "IB", IMP_SET)
    fordr_ovrigaftg_ub_actual = _get_balance(lines, "UB", ASSET_SET)
    ack_nedskr_fordr_ovrigaftg_ub_act = _get_balance(lines, "UB", IMP_SET)

    # Initialize flow accumulators
    nya_fordr_ovrigaftg = 0.0
    fusion_fordr_ovrigaftg = 0.0
    reglerade_fordr_ovrigaftg = 0.0
    bortskrivna_fordr_ovrigaftg = 0.0
    omklass_fordr_ovrigaftg = 0.0

    aterfor_nedskr_reglerade_fordr_ovrigaftg = 0.0
    aterfor_nedskr_fusion_fordr_ovrigaftg = 0.0
    aterfor_nedskr_bortskrivna_fordr_ovrigaftg = 0.0
    aterfor_nedskr_fordr_ovrigaftg = 0.0  # General reversal bucket
    omklass_nedskr_fordr_ovrigaftg = 0.0
    arets_nedskr_fordr_ovrigaftg = 0.0

    # Classification helpers
    def _is_bank(a: int) -> bool:    
        return 1900 <= a <= 1999
    
    def _is_st_ic(a: int) -> bool:   
        return 1680 <= a <= 1689   # short-term related receivables
    
    def _is_expense(a: int) -> bool: 
        return 6000 <= a <= 8999 and not (8120 <= a <= 8139 or a in (8240,))

    # Parse vouchers
    trans_by_ver, text_by_ver = _parse_vouchers(lines)

    # Classify each voucher
    for key, txs in trans_by_ver.items():
        text = text_by_ver.get(key, "")

        R_D = sum(amt  for a, amt in txs if a in ASSET_SET and amt > 0)
        R_K = sum(-amt for a, amt in txs if a in ASSET_SET and amt < 0)

        IMP_D = sum(amt  for a, amt in txs if a in IMP_SET and amt > 0)   # reversal
        IMP_K = sum(-amt for a, amt in txs if a in IMP_SET and amt < 0)   # new impairment

        other = {a for a, _ in txs if a not in ASSET_SET and a not in IMP_SET}
        only_bank_or_stic = len(other) > 0 and all(_is_bank(a) or _is_st_ic(a) for a in other)
        any_expense = any(_is_expense(a) for a, _ in txs)
        is_fusion = ("fusion" in text)
        is_writeoff = any(k in text for k in ("bortskriv", "avskriv", "efterskank")) or any_expense

        # 1) New receivables / fusion (debet)
        if R_D > 0:
            if is_fusion:
                fusion_fordr_ovrigaftg += R_D
            else:
                nya_fordr_ovrigaftg += R_D

        # 2) Credits on receivables → classify
        if R_K > 0:
            if is_writeoff:
                bortskrivna_fordr_ovrigaftg += R_K
                if IMP_D > 0:
                    aterfor_nedskr_bortskrivna_fordr_ovrigaftg += IMP_D
                    IMP_D = 0.0
            elif is_fusion:
                reglerade_fordr_ovrigaftg += R_K  # fusion outflow counts as regulated
                if IMP_D > 0:
                    aterfor_nedskr_fusion_fordr_ovrigaftg += IMP_D
                    IMP_D = 0.0
            elif only_bank_or_stic:
                reglerade_fordr_ovrigaftg += R_K
                if IMP_D > 0:
                    aterfor_nedskr_reglerade_fordr_ovrigaftg += IMP_D
                    IMP_D = 0.0
            else:
                # No clear signal → treat as reclassification
                if R_D > 0:
                    omklass_fordr_ovrigaftg += (R_D - R_K)
                else:
                    omklass_fordr_ovrigaftg -= R_K

        # 3) Remaining impairment not tied above
        if IMP_D > 0:
            # generic reversal not linked to settlement / fusion / write-off
            aterfor_nedskr_fordr_ovrigaftg += IMP_D
            IMP_D = 0.0
        if IMP_K > 0:
            arets_nedskr_fordr_ovrigaftg += IMP_K

        # 4) Omklass av ack nedskr (båda sidor på IMP_SET i samma verifikat utan asset-signal)
        imp_d_orig = sum(amt  for a, amt in txs if a in IMP_SET and amt > 0)
        imp_k_orig = sum(-amt for a, amt in txs if a in IMP_SET and amt < 0)
        if imp_d_orig > 0 and imp_k_orig > 0 and R_D == 0 and R_K == 0:
            omklass_nedskr_fordr_ovrigaftg += (imp_d_orig - imp_k_orig)

    # Calculate UB/Book value (prefer factual UB from SIE)
    fordr_ovrigaftg_ub = fordr_ovrigaftg_ub_actual
    ack_nedskr_fordr_ovrigaftg_ub = ack_nedskr_fordr_ovrigaftg_ub_act  # prefer factual UB on 1347

    red_varde_fordr_ovrigaftg = fordr_ovrigaftg_ub + ack_nedskr_fordr_ovrigaftg_ub

    # =========================
    # PREVIOUS YEAR (FROM SAME SIE; NO VOUCHERS)
    # =========================

    def _get_balance_prev(lines, kind_flag: str, accounts: set[int] | None) -> float:
        if not accounts:
            return 0.0
        total = 0.0
        rx = re.compile(rf'^#(?:{kind_flag})\s+-1\s+(\d+)\s+(-?[0-9][0-9\s.,]*)(?:\s+.*)?$')
        for raw in lines:
            s = raw.strip()
            m = rx.match(s)
            if not m:
                continue
            acct = int(m.group(1))
            if acct in accounts:
                total += _to_float(m.group(2))
        return total

    ASSET_SET_SAFE     = ASSET_SET if 'ASSET_SET' in locals() else None
    ACC_IMP_SET_SAFE   = IMP_SET if 'IMP_SET' in locals() else None
    ACC_AVSKR_SET_SAFE = locals().get("ACC_AVSKR_SET")
    UPP_SET_SAFE       = locals().get("UPP_SET")

    fordr_ovrftg_ib_prev  = _get_balance_prev(lines, 'IB', ASSET_SET_SAFE)
    fordr_ovrftg_ub_prev  = _get_balance_prev(lines, 'UB', ASSET_SET_SAFE)

    ack_nedskr_fordr_ovrftg_ib_prev = _get_balance_prev(lines, 'IB', ACC_IMP_SET_SAFE)
    ack_nedskr_fordr_ovrftg_ub_prev = _get_balance_prev(lines, 'UB', ACC_IMP_SET_SAFE)

    # optional
    ack_avskr_fordr_ovrftg_ib_prev = _get_balance_prev(lines, 'IB', ACC_AVSKR_SET_SAFE)
    ack_avskr_fordr_ovrftg_ub_prev = _get_balance_prev(lines, 'UB', ACC_AVSKR_SET_SAFE)
    uppskr_fordr_ovrftg_ib_prev    = _get_balance_prev(lines, 'IB', UPP_SET_SAFE)
    uppskr_fordr_ovrftg_ub_prev    = _get_balance_prev(lines, 'UB', UPP_SET_SAFE)

    red_varde_fordr_ovrftg_prev = (
        (fordr_ovrftg_ub_prev or 0.0)
        + (uppskr_fordr_ovrftg_ub_prev or 0.0)
        + (ack_nedskr_fordr_ovrftg_ub_prev or 0.0)
        + (ack_avskr_fordr_ovrftg_ub_prev or 0.0)
    )

    # Movements
    delta_prev = (fordr_ovrftg_ub_prev or 0.0) - (fordr_ovrftg_ib_prev or 0.0)
    fsg_fordr_ovrftg_prev         = 0.0
    arets_inkop_fordr_ovrftg_prev = 0.0
    if fordr_ovrftg_ub_prev < fordr_ovrftg_ib_prev:
        fsg_fordr_ovrftg_prev = delta_prev
    elif fordr_ovrftg_ub_prev > fordr_ovrftg_ib_prev:
        arets_inkop_fordr_ovrftg_prev = delta_prev

    abs_imp_ib = abs(ack_nedskr_fordr_ovrftg_ib_prev or 0.0)
    abs_imp_ub = abs(ack_nedskr_fordr_ovrftg_ub_prev or 0.0)

    aterfor_nedskr_fordr_ovrftg_prev = 0.0
    arets_nedskr_fordr_ovrftg_prev   = 0.0
    if abs_imp_ib > abs_imp_ub:
        aterfor_nedskr_fordr_ovrftg_prev = abs_imp_ib - abs_imp_ub
    elif abs_imp_ib < abs_imp_ub:
        arets_nedskr_fordr_ovrftg_prev = abs_imp_ib - abs_imp_ub

    # Debug
    if debug:
        try:   print(f"[FORDR-OVRFTG-DEBUG] asset_set = {sorted(list(ASSET_SET_SAFE))}")
        except: print("[FORDR-OVRFTG-DEBUG] asset_set = <unavailable>")
        try:   print(f"[FORDR-OVRFTG-DEBUG] acc_imp_set = {sorted(list(ACC_IMP_SET_SAFE))}")
        except: print("[FORDR-OVRFTG-DEBUG] acc_imp_set = <unavailable>")
        try:   print(f"[FORDR-OVRFTG-DEBUG] acc_avskr_set = {sorted(list(ACC_AVSKR_SET_SAFE))}")
        except: print("[FORDR-OVRFTG-DEBUG] acc_avskr_set = <unavailable>")
        try:   print(f"[FORDR-OVRFTG-DEBUG] uppskr_set = {sorted(list(UPP_SET_SAFE))}")
        except: print("[FORDR-OVRFTG-DEBUG] uppskr_set = <unavailable>")

        print(f"[FORDR-OVRFTG-DEBUG] IB prev={fordr_ovrftg_ib_prev}  UB prev={fordr_ovrftg_ub_prev}")
        print(f"[FORDR-OVRFTG-DEBUG] ack_nedskr IB prev={ack_nedskr_fordr_ovrftg_ib_prev}  UB prev={ack_nedskr_fordr_ovrftg_ub_prev}")
        print(f"[FORDR-OVRFTG-DEBUG] red_varde prev={red_varde_fordr_ovrftg_prev}")
        print(f"[FORDR-OVRFTG-DEBUG] delta prev={delta_prev}  inkop_prev={arets_inkop_fordr_ovrftg_prev}  fsg_prev={fsg_fordr_ovrftg_prev}")
        print(f"[FORDR-OVRFTG-DEBUG] aterfor_nedskr_prev={aterfor_nedskr_fordr_ovrftg_prev}  arets_nedskr_prev={arets_nedskr_fordr_ovrftg_prev}")

    if debug:
        pass

    result = {
        # Cost roll-forward
        "fordr_ovrigaftg_ib": fordr_ovrigaftg_ib,
        "nya_fordr_ovrigaftg": nya_fordr_ovrigaftg,
        "fusion_fordr_ovrigaftg": fusion_fordr_ovrigaftg,
        "reglerade_fordr_ovrigaftg": reglerade_fordr_ovrigaftg,
        "bortskrivna_fordr_ovrigaftg": bortskrivna_fordr_ovrigaftg,
        "omklass_fordr_ovrigaftg": omklass_fordr_ovrigaftg,
        "fordr_ovrigaftg_ub": fordr_ovrigaftg_ub,

        # Impairments
        "ack_nedskr_fordr_ovrigaftg_ib": ack_nedskr_fordr_ovrigaftg_ib,
        "aterfor_nedskr_reglerade_fordr_ovrigaftg": aterfor_nedskr_reglerade_fordr_ovrigaftg,
        "aterfor_nedskr_fusion_fordr_ovrigaftg": aterfor_nedskr_fusion_fordr_ovrigaftg,
        "aterfor_nedskr_bortskrivna_fordr_ovrigaftg": aterfor_nedskr_bortskrivna_fordr_ovrigaftg,
        "aterfor_nedskr_fordr_ovrigaftg": aterfor_nedskr_fordr_ovrigaftg,
        "omklass_nedskr_fordr_ovrigaftg": omklass_nedskr_fordr_ovrigaftg,
        "arets_nedskr_fordr_ovrigaftg": arets_nedskr_fordr_ovrigaftg,
        "ack_nedskr_fordr_ovrigaftg_ub": ack_nedskr_fordr_ovrigaftg_ub,

        # Book value
        "red_varde_fordr_ovrigaftg": red_varde_fordr_ovrigaftg,

        # Previous year values (for preview display)
        "fordr_ovrftg_ib_prev": fordr_ovrftg_ib_prev,
        "fordr_ovrftg_ub_prev": fordr_ovrftg_ub_prev,
        "ack_nedskr_fordr_ovrftg_ib_prev": ack_nedskr_fordr_ovrftg_ib_prev,
        "ack_nedskr_fordr_ovrftg_ub_prev": ack_nedskr_fordr_ovrftg_ub_prev,
        "ack_avskr_fordr_ovrftg_ib_prev": ack_avskr_fordr_ovrftg_ib_prev,
        "ack_avskr_fordr_ovrftg_ub_prev": ack_avskr_fordr_ovrftg_ub_prev,
        "uppskr_fordr_ovrftg_ib_prev": uppskr_fordr_ovrftg_ib_prev,
        "uppskr_fordr_ovrftg_ub_prev": uppskr_fordr_ovrftg_ub_prev,
        "red_varde_fordr_ovrftg_prev": red_varde_fordr_ovrftg_prev,
        "arets_inkop_fordr_ovrftg_prev": arets_inkop_fordr_ovrftg_prev,
        "fsg_fordr_ovrftg_prev": fsg_fordr_ovrftg_prev,
        "aterfor_nedskr_fordr_ovrftg_prev": aterfor_nedskr_fordr_ovrftg_prev,
        "arets_nedskr_fordr_ovrftg_prev": arets_nedskr_fordr_ovrftg_prev,
    }
    
    return result
