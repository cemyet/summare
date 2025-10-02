from typing import Dict, Any, List

# Roll-mappning till dropdown-texter i Signering.tsx
ROLE_MAP = {
    "STYRELSELEDAMOT": "Styrelseledamot",
    "VERKSTYRELSELEDAMOT": "Styrelseledamot",
    "VERKSTYRELSEORDFORANDE": "Styrelseordförande",
    "STYRELSEORDFORANDE": "Styrelseordförande",
    "VERKSTÄLLANDE_DIREKTÖR": "VD",
    "VERKSTALLANDE_DIREKTOR": "VD",
    "VD": "VD",
    "REVISOR": "Revisor",
    "HUVUDANSVARIG_REVISOR": "Revisor",
    "LEKMANNAREVISOR": "Revisor",
    "AUKTORISERAD_REVISOR": "Revisor",
}

def _format_personnummer(val: str) -> str:
    """Format personnummer as YYYYMMDD-XXXX"""
    # Remove all non-digit characters
    clean = "".join(ch for ch in (val or "") if ch.isdigit())
    # Add hyphen after 8 digits if we have at least 10 digits
    if len(clean) >= 10:
        return f"{clean[:8]}-{clean[8:]}"
    return clean

def extract_officers_for_signing(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tar Bolagsverkets API-svar och returnerar strukturen som Signering.tsx förväntar sig:
    {
      "UnderskriftForetradare": [ ... ],
      "UnderskriftAvRevisor": [ ... ]
    }
    
    Args:
        payload: JSON response from Bolagsverket API
        
    Returns:
        Dict with UnderskriftForetradare and UnderskriftAvRevisor arrays
    """
    result = {
        "UnderskriftForetradare": [],
        "UnderskriftAvRevisor": [],
        "ValtRevisionsbolag": "",
    }

    # Svaren kan komma som en lista av organisationer eller direkt objekt
    if isinstance(payload, dict) and "organisationer" in payload:
        orgs = payload.get("organisationer", [])
    elif isinstance(payload, list):
        orgs = payload
    else:
        orgs = [payload]
    
    # Ta första organisationen
    org = orgs[0] if orgs else {}

    funktionarer = org.get("funktionarer") or org.get("FUNKTIONARER") or []
    
    # Extract revisionsbolag name from REV organization (not REVH person)
    for f in funktionarer:
        # Check if this is an organization (not a person) with REV role
        org_namn = f.get("organisationsnamn") or {}
        org_ident = f.get("identitet") or {}
        roles = f.get("funktionarsroller") or []
        
        # Check if this has REV role and is an organization
        for r in roles:
            kod = (r.get("kod") or "").upper().strip()
            if kod == "REV" and org_namn.get("namn"):
                result["ValtRevisionsbolag"] = org_namn.get("namn", "")
                break
        if result["ValtRevisionsbolag"]:
            break

    # Företrädare (styrelse, VD, etc.)
    for f in funktionarer:
        # Strukturen innehåller personnamn/identitet och roller
        person = f.get("personnamn") or {}
        ident = f.get("identitet") or {}
        roles = f.get("funktionarsroller") or []

        first = (person.get("fornamn") or "").strip()
        last = (person.get("efternamn") or "").strip()
        pnr = _format_personnummer(ident.get("identitetsbeteckning", ""))

        # Hitta bästa roll att visa med stöd för kombinerade roller
        is_vd = False
        is_styrelseledamot = False
        is_styrelseordforande = False
        is_revisor = False
        is_huvudansvarig = False
        is_suppleant = False
        
        for r in roles:
            kod = (r.get("kod") or "").upper().strip()
            klartext = (r.get("klartext") or "").upper().replace(" ", "_")
            
            # First check kod (simpler and more reliable)
            if kod == "OF":
                is_styrelseordforande = True
            elif kod == "LE":
                is_styrelseledamot = True
            elif kod == "VD":
                is_vd = True
            elif "SUPPL" in kod:
                is_suppleant = True
            elif "REV" in kod:
                is_revisor = True
                if "HUVUDANSVAR" in kod:
                    is_huvudansvarig = True
            # Then check klartext as fallback (handle Swedish characters)
            elif "SUPPLEANT" in klartext:
                is_suppleant = True
            elif "REVISOR" in klartext:
                is_revisor = True
                if "HUVUDANSVAR" in klartext:
                    is_huvudansvarig = True
            elif "VD" in klartext or "VERKSTÄLLANDE" in klartext:
                is_vd = True
            elif "ORDFÖRANDE" in klartext or "ORDFORANDE" in klartext:
                is_styrelseordforande = True
            elif "STYRELSELEDAMOT" in klartext:
                is_styrelseledamot = True

        # Determine final role with combined role support
        display_role = ""
        if is_vd and is_styrelseordforande:
            display_role = "VD & styrelseordförande"
        elif is_vd and is_styrelseledamot:
            display_role = "VD & styrelseledamot"
        elif is_vd:
            display_role = "VD"
        elif is_styrelseordforande:
            display_role = "Styrelseordförande"
        elif is_styrelseledamot:
            display_role = "Styrelseledamot"
        
        # Fallback till första rollen om ingen mappning hittades
        if not display_role and roles and not is_revisor:
            display_role = roles[0].get("klartext") or roles[0].get("kod") or ""

        # Hoppa över tomma poster och styrelsesuppleanter
        if not (first or last) or is_suppleant:
            continue

        # Revisorer läggs i separat array
        if is_revisor:
            result["UnderskriftAvRevisor"].append({
                "UnderskriftHandlingTilltalsnamn": first,
                "UnderskriftHandlingEfternamn": last,
                "UnderskriftHandlingPersonnummer": pnr,
                "UnderskriftHandlingEmail": "",
                "UnderskriftHandlingRoll": "Revisor",
                "UnderskriftHandlingTitel": result["ValtRevisionsbolag"] or "Auktoriserad revisor",  # Use company name
                "UnderskriftRevisorspateckningRevisorHuvudansvarig": is_huvudansvarig,
                "RevisionsberattelseTyp": "UTAN_MODIFIERING",
                "RevisionsberattelseDatum": "",
                "UnderskriftHandlingDagForUndertecknande": "",
                "UnderskriftHandlingAvvikandeMening": None,
                "fromBolagsverket": True,
            })
        else:
            # Styrelse/VD
            result["UnderskriftForetradare"].append({
                "UnderskriftHandlingTilltalsnamn": first,
                "UnderskriftHandlingEfternamn": last,
                "UnderskriftHandlingPersonnummer": pnr,
                "UnderskriftHandlingEmail": "",
                "UnderskriftHandlingRoll": display_role or "",
                "UnderskriftHandlingDagForUndertecknande": "",
                "UnderskriftHandlingAvvikandeMening": None,
                "fromBolagsverket": True,
            })

    # Sort företrädare by role priority: VD (and combinations) first, then Ordförande, then Ledamot
    def role_sort_key(foretradare):
        role = foretradare.get("UnderskriftHandlingRoll", "").lower()
        if "vd" in role:
            return 0  # VD, VD & styrelseledamot, VD & styrelseordförande
        elif "ordförande" in role or "ordforande" in role:
            return 1  # Styrelseordförande
        elif "ledamot" in role:
            return 2  # Styrelseledamot
        else:
            return 3  # Others
    
    result["UnderskriftForetradare"].sort(key=role_sort_key)

    return result


def get_officer_summary(company_info: Dict[str, Any]) -> Dict[str, Any]:
    """Provides a summary of officers found."""
    officers_data = extract_officers_for_signing(company_info)
    return {
        "num_foretradare": len(officers_data["UnderskriftForetradare"]),
        "num_revisorer": len(officers_data["UnderskriftAvRevisor"]),
        "foretradare_names": [
            f"{o['UnderskriftHandlingTilltalsnamn']} {o['UnderskriftHandlingEfternamn']} ({o['UnderskriftHandlingRoll']})" 
            for o in officers_data["UnderskriftForetradare"]
        ],
        "revisorer_names": [
            f"{r['UnderskriftHandlingTilltalsnamn']} {r['UnderskriftHandlingEfternamn']} ({r['UnderskriftHandlingRoll']})" 
            for r in officers_data["UnderskriftAvRevisor"]
        ],
    }


def format_officer_for_display(officer: Dict[str, Any]) -> str:
    """Formats an officer's name and role for display."""
    name = f"{officer.get('UnderskriftHandlingTilltalsnamn', '')} {officer.get('UnderskriftHandlingEfternamn', '')}".strip()
    role = officer.get('UnderskriftHandlingRoll', '')
    return f"{name} ({role})"
