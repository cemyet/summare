
"""
SRU File Generator for INK2 Tax Declaration
Generates SRU format files (INK2R and INK2S) for Swedish tax authorities
"""

import json, os, re, datetime as dt
from typing import Dict, Any, Optional, List
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def is_numeric_sru(x):
    try:
        int(x)
        return True
    except Exception:
        return False

def normalize_key(x: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "", (x or "").lower())

def to_yyyymmdd(s: str) -> str:
    if not s:
        return ""
    import re
    d = re.sub(r"\D", "", s)
    if len(d) >= 8:
        return f"{d[:4]}{d[4:6]}{d[6:8]}"
    return ""

def only_digits(s: str) -> str:
    import re
    return re.sub(r"\D", "", str(s or ""))

def build_index_from_rows(rows):
    idx = {}
    for row in rows or []:
        for key in ("variable_name", "element_name", "row_title", "name"):
            if key in row and row[key] is not None:
                idx[normalize_key(str(row[key]))] = row
    return idx

def lookup_amount(idx, name):
    key = normalize_key(name)
    row = idx.get(key)
    if not row:
        return None
    for k in ("amount", "current", "value", "belopp"):
        if k in row and row[k] is not None:
            try:
                return float(row[k])
            except Exception:
                pass
    for k, v in row.items():
        if isinstance(v, str) and re.fullmatch(r"-?\d+(\.\d+)?", v):
            return float(v)
    return None

def fetch_ink2_form_mappings() -> List[Dict[str, Any]]:
    """Fetch INK2 form mappings from Supabase"""
    try:
        response = supabase.table('ink2_form').select('*').execute()
        return response.data
    except Exception as e:
        print(f"❌ Error fetching ink2_form mappings: {e}")
        return []

def build_sru_text(company_data: dict) -> str:
    # Fetch mappings from Supabase
    mappings = fetch_ink2_form_mappings()
    
    # Filter to only rows with numeric SRU codes
    mappings = [m for m in mappings if m.get('sru') and is_numeric_sru(m.get('sru'))]

    end_date = company_data.get("end_date") or (company_data.get("seFileData") or {}).get("company_info", {}).get("end_date") \
               or (company_data.get("company_info") or {}).get("end_date")
    start_date = company_data.get("start_date") or (company_data.get("seFileData") or {}).get("company_info", {}).get("start_date") \
               or (company_data.get("company_info") or {}).get("start_date")

    fy_year = (to_yyyymmdd(end_date)[:4] or dt.datetime.now().strftime("%Y"))
    fy_start = to_yyyymmdd(start_date) or f"{fy_year}0101"
    fy_end   = to_yyyymmdd(end_date)   or f"{fy_year}1231"

    org = (company_data.get("organizationNumber") or 
           (company_data.get("seFileData") or {}).get("company_info", {}).get("organization_number") or "")
    org_digits = only_digits(org)

    today = dt.datetime.now().strftime("%Y%m%d")
    now_time = dt.datetime.now().strftime("%H%M%S")

    system_info = (
        company_data.get("system_info") or
        (company_data.get("seFileData") or {}).get("system_info") or
        "Summare 1.0"
    )

    accepted = (company_data.get("acceptedInk2Manuals") or {})
    ink2_rows = company_data.get("ink2Data") or (company_data.get("seFileData") or {}).get("ink2_data") or []
    rr_rows  = company_data.get("rr_data") or (company_data.get("seFileData") or {}).get("rr_data") or []
    br_rows  = company_data.get("br_data") or (company_data.get("seFileData") or {}).get("br_data") or []

    ink2_idx = build_index_from_rows(ink2_rows)
    rr_idx   = build_index_from_rows(rr_rows)
    br_idx   = build_index_from_rows(br_rows)

    def resolve_token(tok: str):
        import re
        t = tok.strip()
        t = re.sub(r"\s*\(IF[<>]=?0\)$", "", t, flags=re.I)
        k = normalize_key(t)
        for kk, vv in accepted.items():
            if normalize_key(kk) == k:
                try:
                    return float(vv)
                except Exception:
                    pass
        v = lookup_amount(ink2_idx, t)
        if v is not None: return float(v)
        v = lookup_amount(rr_idx, t)
        if v is not None: return float(v)
        v = lookup_amount(br_idx, t)
        if v is not None: return float(v)
        return None

    def resolve_variable_map(vmap: str):
        if not vmap or str(vmap).lower() == "nan":
            return None
        import re
        cond = None
        m = re.search(r"\(IF([<>]=?0|[<>]0)\)", vmap, re.I)
        if m:
            cond = m.group(1).replace("=", "")
            expr = re.sub(r"\s*\(IF[<>]=?0\)$|\s*\(IF[<>]0\)$", "", vmap).strip()
        else:
            expr = vmap.strip()
        parts = [p.strip() for p in expr.split("+")]
        total = 0.0
        found = False
        for p in parts:
            val = resolve_token(p)
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

    def add_line(dst, sru_code, value):
        if value is None: return
        try:
            val = float(value)
        except Exception:
            return
        if abs(val) < 0.5: return
        dst.append(f"#UPPGIFT {int(sru_code)} {int(round(val))}")

    lines_r, lines_s = [], []
    for mapping in mappings:
        sru = int(mapping['sru'])
        form_field = str(mapping.get("form_field") or "")
        v = resolve_variable_map(str(mapping.get("variable_map") or ""))
        target = "R"
        if form_field.strip().startswith("4."):
            target = "S"
        if sru in (7011,7012):  # handled explicitly
            continue
        if target == "R":
            add_line(lines_r, sru, v)
        else:
            add_line(lines_s, sru, v)

    out = []
    out.append(f"#BLANKETT INK2R-{fy_year}P4")
    out.append(f"#IDENTITET {org_digits} {today} {now_time}")
    out.append(f"#SYSTEMINFO {system_info}")
    out.append(f"#UPPGIFT 7011 {fy_start}")
    out.append(f"#UPPGIFT 7012 {fy_end}")
    out.extend(lines_r)
    out.append("#BLANKETTSLUT")
    out.append(f"#BLANKETT INK2S-{fy_year}P4")
    out.append(f"#IDENTITET {org_digits} {today} {now_time}")
    out.append(f"#SYSTEMINFO {system_info}")
    out.append(f"#UPPGIFT 7011 {fy_start}")
    out.append(f"#UPPGIFT 7012 {fy_end}")
    out.extend(lines_s)
    out.append("#BLANKETTSLUT")
    out.append("#FIL_SLUT")
    return "\n".join(out)

def write_sru(company_data: dict, out_path: str) -> str:
    """Write SRU file to disk"""
    text = build_sru_text(company_data)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    return out_path

def generate_sru_file(company_data: dict) -> bytes:
    """Generate SRU file and return as bytes"""
    text = build_sru_text(company_data)
    return text.encode('utf-8')
