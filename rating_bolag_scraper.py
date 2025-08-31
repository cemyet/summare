#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests, re, json
import requests.utils
from bs4 import BeautifulSoup
from typing import Optional, List, Dict

# ---- BASE URLS ----
BASE_NUMBERS = "https://www.rating.se/info1/detail/numbers/{orgnr}"
BASE_PEOPLE = "https://www.rating.se/info1/detail/people/{orgnr}"
BASE_OVERVIEW = "https://www.rating.se/info1/detail/overview/{orgnr}"
BASE_BIZ = "https://www.rating.se/info1/detail/biz/{orgnr}"

HEADERS = {"User-Agent": "Mozilla/5.0"}

# ====================================================
# =============== Rating.se Scraper ==================
# ====================================================

def search_organization_number(company_name: str) -> Optional[str]:
    """
    Search for organization number by company name using allabolag.se
    Returns organization number if found, None otherwise
    """
    try:
        # Clean company name for search
        search_name = company_name.strip()
        
        # Try allabolag.se search first
        search_url = f"https://www.allabolag.se/what/{requests.utils.quote(search_name)}"
        r = requests.get(search_url, timeout=20, headers=HEADERS)
        
        if r.status_code == 200:
            # Look for organization number pattern in response
            orgnr_match = re.search(r'\b(\d{6}-\d{4})\b', r.text)
            if orgnr_match:
                return orgnr_match.group(1)
        
        # Fallback: try ratsit.se search
        ratsit_search_url = f"https://www.ratsit.se/sok/foretag/{requests.utils.quote(search_name)}"
        r2 = requests.get(ratsit_search_url, timeout=20, headers=HEADERS)
        
        if r2.status_code == 200:
            soup = BeautifulSoup(r2.text, "html.parser")
            # Look for organization number in search results
            orgnr_match = re.search(r'\b(\d{6}-\d{4})\b', r2.text)
            if orgnr_match:
                return orgnr_match.group(1)
                
    except Exception as e:
        print(f"Error searching for organization number: {e}")
    
    return None

def clean_number(val: str):
    if not val: return None
    val = val.replace(" ", "").replace(" ", "").replace("\xa0", "")
    try:
        if "," in val: return float(val.replace(",", "."))
        return int(val)
    except ValueError:
        return val

def scrape_numbers(orgnr: str) -> dict:
    url = BASE_NUMBERS.format(orgnr=orgnr)
    r = requests.get(url, timeout=20, headers=HEADERS); r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    nyckeltal = {}
    rows = soup.select("td.label")
    for row in rows:
        label = row.get_text(strip=True)
        values = []
        for td in row.find_next_siblings("td"):
            if "label" in td.get("class", []): break
            values.append(clean_number(td.get_text(strip=True)))
        if not values: continue

        l = label.lower()
        if "total omsättning" in l: nyckeltal["Omsättning"] = values
        elif "resultat efter finansnetto" in l: nyckeltal["Resultat efter finansnetto"] = values
        elif "antal anställda" in l: nyckeltal["Antal anställda"] = values
        elif "summa tillgångar" in l: nyckeltal["Balansomslutning"] = values
        elif "soliditet" in l: nyckeltal["Soliditet"] = values

    return nyckeltal

def scrape_people(orgnr: str) -> dict:
    url = BASE_PEOPLE.format(orgnr=orgnr)
    r = requests.get(url, timeout=20, headers=HEADERS); r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    data = {"styrelse": [], "vd": None}
    styrelse_title = soup.find("div", class_="title", string="Styrelse/Bolagsmän")
    if styrelse_title:
        for div in styrelse_title.find_all_next("div", class_="value"):
            txt = div.get_text(strip=True)
            if "VD" in txt or "Högst Ansvarig" in txt: break
            data["styrelse"].append(txt)
    vd_title = soup.find("div", class_="title", string="VD/Högst Ansvarig")
    if vd_title:
        vd_value = vd_title.find_next("div", class_="value")
        if vd_value: data["vd"] = vd_value.get_text(strip=True)
    return data

def scrape_overview(orgnr: str) -> dict:
    url = BASE_OVERVIEW.format(orgnr=orgnr)
    r = requests.get(url, timeout=20, headers=HEADERS); r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    data = {"company_name": None,"moderbolag": None,"moderbolag_orgnr": None,"antal_dotterbolag": None,"säte": None}

    # name
    header = soup.find("div", class_="detail-header")
    if header: 
        h1 = header.find("h1")
        if h1: data["company_name"] = h1.get_text(strip=True)

    # säte
    visit_label = soup.find("span", class_="label", string=re.compile("BESÖKSADRESS"))
    if visit_label:
        val = visit_label.find_next("span", class_="value")
        if val:
            html_lines = val.decode_contents().split("<br/>")
            for line in html_lines:
                line = BeautifulSoup(line, "html.parser").get_text(strip=True)
                if line.startswith("Kommun:"): 
                    data["säte"] = line.replace("Kommun:", "").strip()

    # moder/dotter
    rows = soup.find_all("td")
    for idx, td in enumerate(rows):
        txt = td.get_text(strip=True)
        if txt == "Moderbolag:":
            link = rows[idx+1].find("a")
            if link: 
                data["moderbolag"] = link.get_text(strip=True)
                if idx+3 < len(rows): data["moderbolag_orgnr"] = rows[idx+3].get_text(strip=True)
        elif txt == "Dotterbolag:":
            val = rows[idx+1].get_text(strip=True).replace("st", "").strip()
            data["antal_dotterbolag"] = clean_number(val)
    return data

def scrape_biz(orgnr: str) -> dict:
    url = BASE_BIZ.format(orgnr=orgnr)
    r = requests.get(url, timeout=20, headers=HEADERS); r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    data = {"verksamhetsbeskrivning": None}
    label = soup.find("div", class_="label", string="Verksamhetsbeskrivning")
    if label:
        val = label.find_next("div", class_="value")
        if val: data["verksamhetsbeskrivning"] = val.get_text(strip=True)
    return data

# ====================================================
# =============== Ratsit Dotterbolag ================
# ====================================================

def fetch_ratsit_page(orgnr: str) -> str:
    url = f"https://www.ratsit.se/{re.sub(r'\\D','',orgnr)}"
    r = requests.get(url, timeout=20, headers=HEADERS)
    if r.status_code == 200:
        return r.text
    return ""

def parse_subsidiaries_from_ratsit(html: str) -> List[Dict]:
    soup = BeautifulSoup(html, "html.parser")
    subs: List[Dict] = []

    heading = soup.find("h2", string=re.compile("Mer om ekonomin", re.I))
    if not heading:
        return subs

    p = heading.find_parent("div").find_next("p")
    if not p:
        return subs

    for a in p.find_all("a", href=True):
        href = a["href"]
        name = a.get_text(strip=True)
        m = re.search(r"/(\d{10})-", href)
        orgnr = None
        if m:
            digits = m.group(1)
            orgnr = digits[:6] + "-" + digits[6:]
        subs.append({"name": name, "org_number": orgnr, "säte": None})

    extra_match = re.search(r"samt\s+(\d+)\s+dotterbolag till", p.get_text())
    if extra_match:
        subs.append({"name": f"{extra_match.group(1)} okända dotterbolag", "org_number": None, "säte": None})

    return subs

def get_sate_from_ratsit(orgnr: str) -> Optional[str]:
    url = f"https://www.ratsit.se/{re.sub(r'\\D','', orgnr)}"
    try:
        r = requests.get(url, timeout=20, headers=HEADERS)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        rows = soup.find_all("div", class_="row")
        for row in rows:
            left = row.find("div", class_="col-12 col-lg-6 color--gray5")
            if left and left.get_text(strip=True) == "Säte:":
                right = row.find("div", class_="col-12 col-lg-6")
                if right:
                    val = right.get_text(strip=True)
                    if "," in val:
                        return val.split(",")[0].strip()
                    return val.strip()
    except Exception:
        return None
    return None

def enrich_subsidiaries(subs: List[Dict]) -> List[Dict]:
    enriched = []
    for s in subs:
        orgnr = s.get("org_number")
        if orgnr:
            seat = None
            try:
                ov = scrape_overview(orgnr)
                seat = ov.get("säte")
                if ov.get("company_name"):
                    s["name"] = ov["company_name"]
            except Exception:
                pass
            # fallback på Ratsit
            if not seat:
                seat = get_sate_from_ratsit(orgnr)
            s["säte"] = seat
        enriched.append(s)
    return enriched

# ====================================================
# =============== Main Orchestration =================
# ====================================================

def get_company_info(orgnr: str) -> Dict:
    nyckeltal = scrape_numbers(orgnr)
    people = scrape_people(orgnr)
    overview = scrape_overview(orgnr)
    biz = scrape_biz(orgnr)

    result = {
        "orgnr": orgnr,
        "company_name": overview.get("company_name"),
        "säte": overview.get("säte"),
        "nyckeltal": nyckeltal,
        "styrelse": people.get("styrelse", []),
        "vd": people.get("vd"),
        "moderbolag": overview.get("moderbolag"),
        "moderbolag_orgnr": overview.get("moderbolag_orgnr"),
        "antal_dotterbolag": overview.get("antal_dotterbolag"),
        "verksamhetsbeskrivning": biz.get("verksamhetsbeskrivning"),
        "dotterbolag": []
    }

    if result["antal_dotterbolag"] and result["antal_dotterbolag"] > 0:
        html = fetch_ratsit_page(orgnr)
        subs = parse_subsidiaries_from_ratsit(html)
        result["dotterbolag"] = enrich_subsidiaries(subs)

    return result

def get_company_info_with_search(orgnr: Optional[str] = None, company_name: Optional[str] = None) -> Dict:
    """
    Get company information with automatic organization number search if needed.
    
    Args:
        orgnr: Organization number (if available)
        company_name: Company name (used for search if orgnr is None)
    
    Returns:
        Dictionary with company information, or empty dict if no data found
    """
    try:
        # If no orgnr provided, try to find it using company name
        if not orgnr and company_name:
            print(f"Searching for organization number for: {company_name}")
            orgnr = search_organization_number(company_name)
            if not orgnr:
                print(f"Could not find organization number for: {company_name}")
                return {
                    "error": "Organization number not found",
                    "company_name": company_name,
                    "orgnr": None
                }
            print(f"Found organization number: {orgnr}")
        
        # If we still don't have orgnr, return error
        if not orgnr:
            return {
                "error": "No organization number or company name provided",
                "orgnr": None
            }
        
        # Get company information using the organization number
        return get_company_info(orgnr)
        
    except Exception as e:
        print(f"Error getting company info: {e}")
        return {
            "error": str(e),
            "orgnr": orgnr,
            "company_name": company_name
        }

# ====================================================
# ===================== Run ==========================
# ====================================================

if __name__ == "__main__":
    orgnr = input("Ange organisationsnummer: ").strip()
    data = get_company_info(orgnr)
    print(json.dumps(data, indent=2, ensure_ascii=False))