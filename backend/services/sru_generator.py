# -*- coding: utf-8 -*-
"""
SRU generator for INK2R/INK2S, aligned with the INK2 PDF value resolution.

How to use:
    from sru_generator import build_sru_text, generate_sru_file
    text = build_sru_text(company_data)        # -> str
    bytes_data = generate_sru_file(company_data)  # -> bytes

Required data in company_data (same as your PDF filler uses):
- company_data.organizationNumber (or seFileData.company_info.organization_number)
- company_data.system_info (optional; default "Summare 1.0")
- company_data.company_info.start_date / end_date  (or seFileData.company_info.*)
- company_data.acceptedInk2Manuals (dict)         # manual overrides
- company_data.ink2Data (list of row dicts)       # live INK2 rows
- company_data.seFileData.ink2_data / rr_data / br_data (fallbacks)

Mapping source (SRU and variable_map per row):
- Supabase table `ink2_form`, OR
- Local CSV fallback: "ink2_form_rows (1).csv" (in backend/services/ or frontend/public/)
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import os, re, json, datetime as dt
from dataclasses import dataclass

# ---------- Optional: Supabase client (only if env is configured) ----------
def get_supabase_client():
    """Get Supabase client if environment variables are set"""
    from dotenv import load_dotenv
    load_dotenv()
    
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception as e:
        print(f"⚠️  Could not create Supabase client: {e}")
        return None

# ---------- Helpers --------------------------------------------------------
def today_dates():
    now = dt.datetime.now()
    return now.strftime("%Y%m%d"), now.strftime("%H%M%S")

def only_digits(s: str) -> str:
    return re.sub(r"\D", "", str(s or ""))

def to_yyyymmdd(s: str) -> str:
    """Accepts 'YYYY-MM-DD' or 'YYYYMMDD' or mixed separators; returns YYYYMMDD or ''."""
    if not s:
        return ""
    d = re.sub(r"\D", "", str(s))
    return f"{d[:4]}{d[4:6]}{d[6:8]}" if len(d) >= 8 else ""

def parse_number(x: Any) -> Optional[float]:
    """Parse numbers robustly (handles spaces, nbsp, single comma as decimal)."""
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).replace("\u00A0", " ").strip()
    s = s.replace(" ", "")
    if s.count(",") == 1 and s.count(".") == 0:
        s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None

def normalize_key(x: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (x or "").lower())

def build_index_from_rows(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    idx: Dict[str, Dict[str, Any]] = {}
    for row in rows or []:
        for key in ("variable_name", "element_name", "row_title", "name"):
            if key in row and row[key] is not None:
                idx[normalize_key(str(row[key]))] = row
    return idx

def lookup_amount(idx: Dict[str, Dict[str, Any]], name: str) -> Optional[float]:
    row = idx.get(normalize_key(name))
    if not row:
        return None
    # common numeric fields used across your data
    for k in (
        "amount", "current", "current_amount", "value", "belopp",
        "currentValue", "currentAmount"
    ):
        if k in row and row[k] is not None:
            v = parse_number(row[k])
            if v is not None:
                return v
    # generic scan of fields likely to contain values
    for k, v in row.items():
        nk = (k or "").lower()
        if any(tok in nk for tok in ["current", "amount", "value", "belopp"]):
            val = parse_number(v)
            if val is not None:
                return val
    return None

# ---------- Mapping fetch (Supabase + CSV fallback) ------------------------
def get_csv_candidates() -> List[str]:
    """Return list of possible CSV file locations"""
    backend_services = os.path.join(os.path.dirname(__file__), "ink2_form_rows (1).csv")
    frontend_public = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "public", "ink2_form_rows (1).csv")
    
    return [
        backend_services,
        os.path.abspath(frontend_public),
        os.path.join(os.getcwd(), "ink2_form_rows (1).csv"),
        os.path.join("/mnt/data", "ink2_form_rows (1).csv"),
    ]

def read_local_mapping_csv() -> List[Dict[str, Any]]:
    """Try to read CSV from multiple locations"""
    for path in get_csv_candidates():
        if os.path.exists(path):
            try:
                import csv
                with open(path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    data = list(reader)
                    print(f"✅ Loaded {len(data)} mappings from CSV: {path}")
                    return data
            except Exception as e:
                print(f"⚠️  Failed reading CSV {path}: {e}")
    print(f"❌ Could not find CSV in any of these locations:")
    for path in get_csv_candidates():
        print(f"   - {path}")
    return []

def fetch_ink2_form_mappings() -> List[Dict[str, Any]]:
    """Try Supabase first; fall back to local CSV."""
    try:
        client = get_supabase_client()
        if client is None:
            print("ℹ️  Supabase not configured, using CSV fallback")
            return read_local_mapping_csv()
        response = client.table("ink2_form").select("*").execute()
        data = response.data or []
        if not data:
            print("⚠️  Supabase returned no data, using CSV fallback")
            return read_local_mapping_csv()
        print(f"✅ Loaded {len(data)} mappings from Supabase")
        return data
    except Exception as e:
        print(f"⚠️  Supabase error: {e}. Falling back to CSV.")
        import traceback
        traceback.print_exc()
        return read_local_mapping_csv()

# ---------- Variable resolver (aligned with your PDF logic) ----------------
@dataclass
class ResolverContext:
    accepted: Dict[str, Any]
    ink2_rows: List[Dict[str, Any]]
    rr_rows: List[Dict[str, Any]]
    br_rows: List[Dict[str, Any]]

class VarResolver:
    def __init__(self, ctx: ResolverContext):
        self.accepted = ctx.accepted or {}
        self.ink2_idx = build_index_from_rows(ctx.ink2_rows or [])
        self.rr_idx   = build_index_from_rows(ctx.rr_rows or [])
        self.br_idx   = build_index_from_rows(ctx.br_rows or [])

    def _resolve_token(self, tok: str) -> Optional[float]:
        t = re.sub(r"\s*\(IF[<>]=?0\)$", "", tok.strip(), flags=re.I)
        k = normalize_key(t)

        # 1) accepted manuals (by variable_name)
        for kk, vv in self.accepted.items():
            if normalize_key(kk) == k:
                val = parse_number(vv)
                if val is not None:
                    return val

        # 2) INK2 rows (live first)
        v = lookup_amount(self.ink2_idx, t)
        if v is not None: return v

        # 3) RR, BR fallbacks
        v = lookup_amount(self.rr_idx, t)
        if v is not None: return v
        v = lookup_amount(self.br_idx, t)
        if v is not None: return v

        # 4) literal numbers allowed in expressions
        lit = parse_number(t)
        return lit

    def get(self, expr: str) -> Optional[float]:
        """Support 'A + B + C' and trailing guards '(IF>0)' / '(IF<0)'."""
        if not expr or str(expr).lower() == "nan":
            return None

        s = str(expr).strip()
        cond: Optional[str] = None
        m = re.search(r"\(IF([<>]=?0|[<>]0)\)$", s, re.I)
        if m:
            cond = m.group(1).replace("=", "")
            s = re.sub(r"\s*\(IF[<>]=?0\)$|\s*\(IF[<>]0\)$", "", s).strip()

        total = 0.0
        found = False
        for part in [p.strip() for p in s.split("+")]:
            val = self._resolve_token(part)
            if val is None:
                continue
            total += float(val)
            found = True

        if not found:
            return None
        if cond == ">0":
            return total if total > 0 else None
        if cond == "<0":
            return total if total < 0 else None
        return total

# ---------- Main builder ---------------------------------------------------
def _resolve_company_info(company_data: Dict[str, Any]) -> Dict[str, str]:
    ci = (company_data.get("company_info")
          or (company_data.get("seFileData") or {}).get("company_info") or {})
    start = to_yyyymmdd(ci.get("start_date") or company_data.get("start_date"))
    end   = to_yyyymmdd(ci.get("end_date")   or company_data.get("end_date"))
    year  = (end[:4] if end else dt.datetime.now().strftime("%Y"))
    return {"start": start or f"{year}0101", "end": end or f"{year}1231", "year": year}

def _system_info(company_data: Dict[str, Any]) -> str:
    return (company_data.get("system_info")
            or (company_data.get("seFileData") or {}).get("system_info")
            or "Summare 1.0")

def _org_digits(company_data: Dict[str, Any]) -> str:
    org = (company_data.get("organizationNumber")
           or (company_data.get("seFileData") or {}).get("company_info", {}).get("organization_number")
           or "")
    return only_digits(org)

def _choose_rows(company_data: Dict[str, Any]) -> ResolverContext:
    accepted = company_data.get("acceptedInk2Manuals") or {}
    ink2_rows = (
        company_data.get("ink2Data")
        or (company_data.get("seFileData") or {}).get("ink2_data")
        or []
    )
    rr_rows = company_data.get("rr_data") or (company_data.get("seFileData") or {}).get("rr_data") or []
    br_rows = company_data.get("br_data") or (company_data.get("seFileData") or {}).get("br_data") or []
    return ResolverContext(accepted, ink2_rows, rr_rows, br_rows)

def _is_numeric_sru(x: Any) -> bool:
    try:
        int(x)
        return True
    except Exception:
        return False

def build_sru_text(company_data: Dict[str, Any], mappings: Optional[List[Dict[str, Any]]] = None) -> str:
    """Return full SRU content as a string."""
    # identity/system
    ci = _resolve_company_info(company_data)
    year = ci["year"]
    fy_start, fy_end = ci["start"], ci["end"]
    org = _org_digits(company_data)
    today, now_time = today_dates()
    system_info = _system_info(company_data)

    print(f"\n📊 SRU Generator - Building SRU file:")
    print(f"  - Organization: {org}")
    print(f"  - Fiscal year: {year} ({fy_start} - {fy_end})")
    print(f"  - System: {system_info}")

    # value resolver
    ctx = _choose_rows(company_data)
    print(f"  - INK2 rows: {len(ctx.ink2_rows)}")
    print(f"  - RR rows: {len(ctx.rr_rows)}")
    print(f"  - BR rows: {len(ctx.br_rows)}")
    print(f"  - Accepted manuals: {len(ctx.accepted)}")
    
    resolver = VarResolver(ctx)

    # mapping rows (SRU + variable_map + form_field)
    rows = mappings if mappings is not None else fetch_ink2_form_mappings()
    # keep numeric SRU only
    rows = [r for r in rows if _is_numeric_sru(r.get("sru"))]
    print(f"  - Valid SRU mappings: {len(rows)}")

    lines_r: List[str] = []
    lines_s: List[str] = []

    def add_upgift(dst: List[str], sru_code: int, value: Optional[float]):
        if value is None:
            return
        v = parse_number(value)
        if v is None:
            return
        # SRU expects integers (Skatteverket will reject decimals)
        if abs(v) < 0.5:
            return
        dst.append(f"#UPPGIFT {int(sru_code)} {int(round(v))}")

    for r in rows:
        sru = int(r["sru"])
        # 7011/7012 handled explicitly below on both forms
        if sru in (7011, 7012):
            continue

        form_field = str(r.get("form_field") or "")
        vmap = r.get("variable_map")
        value = resolver.get(str(vmap)) if vmap is not None else None

        # Simple partition rule: everything under section "4." → INK2S
        target = "S" if form_field.strip().startswith("4.") else "R"
        if value is not None:
            add_upgift(lines_s if target == "S" else lines_r, sru, value)

    print(f"\n📋 SRU lines generated:")
    print(f"  - INK2R lines: {len(lines_r)}")
    print(f"  - INK2S lines: {len(lines_s)}")

    # Sort SRU lines numerically for readability
    lines_r.sort(key=lambda x: int(x.split()[1]))
    lines_s.sort(key=lambda x: int(x.split()[1]))

    # build file
    out: List[str] = []
    # INK2R
    out.append(f"#BLANKETT INK2R-{year}P4")
    out.append(f"#IDENTITET {org} {today} {now_time}")
    out.append(f"#SYSTEMINFO {system_info}")
    out.append(f"#UPPGIFT 7011 {fy_start}")
    out.append(f"#UPPGIFT 7012 {fy_end}")
    out.extend(lines_r)
    out.append("#BLANKETTSLUT")

    # INK2S
    out.append(f"#BLANKETT INK2S-{year}P4")
    out.append(f"#IDENTITET {org} {today} {now_time}")
    out.append(f"#SYSTEMINFO {system_info}")
    out.append(f"#UPPGIFT 7011 {fy_start}")
    out.append(f"#UPPGIFT 7012 {fy_end}")
    out.extend(lines_s)
    out.append("#BLANKETTSLUT")

    out.append("#FIL_SLUT")
    return "\n".join(out)

def write_sru(company_data: Dict[str, Any], out_path: str = "BLANKETTER.SRU",
              mappings: Optional[List[Dict[str, Any]]] = None) -> str:
    """Write SRU file to disk"""
    text = build_sru_text(company_data, mappings=mappings)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    return out_path

def generate_sru_file(company_data: Dict[str, Any]) -> bytes:
    """Generate SRU file and return as bytes"""
    text = build_sru_text(company_data)
    return text.encode('utf-8')
