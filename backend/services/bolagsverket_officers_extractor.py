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

def _clean_id(val: str) -> str:
    """Remove all non-digit characters from ID"""
    return "".join(ch for ch in (val or "") if ch.isdigit())

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

    # Företrädare (styrelse, VD, etc.)
    for f in funktionarer:
        # Strukturen innehåller personnamn/identitet och roller
        person = f.get("personnamn") or {}
        ident = f.get("identitet") or {}
        roles = f.get("funktionarsroller") or []

        first = (person.get("fornamn") or "").strip()
        last = (person.get("efternamn") or "").strip()
        pnr = _clean_id(ident.get("identitetsbeteckning", ""))

        # Hitta bästa roll att visa med stöd för kombinerade roller
        is_vd = False
        is_styrelseledamot = False
        is_styrelseordforande = False
        is_revisor = False
        is_huvudansvarig = False
        is_suppleant = False
        
        for r in roles:
            kod = (r.get("kod") or "").upper().replace(" ", "_")
            klartext = (r.get("klartext") or "").upper().replace(" ", "_")
            
            # Check both kod and klartext
            for check_str in [kod, klartext]:
                if "SUPPLEANT" in check_str:
                    is_suppleant = True
                elif "REVISOR" in check_str:
                    is_revisor = True
                    if "HUVUDANSVAR" in check_str:
                        is_huvudansvarig = True
                elif "VD" in check_str or "VERKSTALLANDE_DIREKTOR" in check_str:
                    is_vd = True
                elif "STYRELSEORDFORANDE" in check_str:
                    is_styrelseordforande = True
                elif "STYRELSELEDAMOT" in check_str:
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
                "UnderskriftHandlingTitel": "Auktoriserad revisor",
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
