import os
import uuid
import time
import requests
from typing import Dict, Any, List, Optional

BVG_BASE = os.getenv("BOLAGSVERKET_BASE_URL")
BVG_CLIENT_ID = os.getenv("BOLAGSVERKET_CLIENT_ID")
BVG_CLIENT_SECRET = os.getenv("BOLAGSVERKET_CLIENT_SECRET")
BVG_SCOPE = os.getenv("BOLAGSVERKET_SCOPE")
# OAuth endpoint is at a different base URL (portal vs gw)
BVG_AUTH_URL = "https://portal.api.bolagsverket.se/oauth2/token"

_token_cache = {"access_token": None, "exp": 0}

def _now() -> int:
    return int(time.time())

def _require_env():
    """
    Validate that all required environment variables are set.
    Raises RuntimeError with clear message if any are missing.
    """
    missing = [k for k, v in {
        "BOLAGSVERKET_BASE_URL": BVG_BASE,
        "BOLAGSVERKET_CLIENT_ID": BVG_CLIENT_ID,
        "BOLAGSVERKET_CLIENT_SECRET": BVG_CLIENT_SECRET,
        "BOLAGSVERKET_SCOPE": BVG_SCOPE,
    }.items() if not v]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

def get_token() -> str:
    """
    Get OAuth2 token with 50-minute cache
    """
    _require_env()
    
    # cache 50 min
    if _token_cache["access_token"] and _token_cache["exp"] - 60 > _now():
        return _token_cache["access_token"]

    token_url = BVG_AUTH_URL
    data = {
        "grant_type": "client_credentials",
        "scope": BVG_SCOPE,
        "client_id": BVG_CLIENT_ID,
        "client_secret": BVG_CLIENT_SECRET,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    r = requests.post(token_url, data=data, headers=headers, timeout=20)
    r.raise_for_status()
    tok = r.json()
    _token_cache["access_token"] = tok["access_token"]
    _token_cache["exp"] = _now() + int(tok.get("expires_in", 3600))
    return _token_cache["access_token"]

def fetch_company_objects(orgnr: str, info_objects: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    POST /organisationer (Bolagsverket API v4)
    Body ska innehålla identitetsbeteckning och önskade informationsobjekt.
    
    Args:
        orgnr: Organization number (without hyphens)
        info_objects: List of information objects to request (FUNKTIONARER, FIRMATECKNING, etc.)
        
    Returns:
        JSON response from Bolagsverket API
    """
    if info_objects is None:
        # Vi vill minst ha funktionärer (FUNKTIONARER) och firmateckning (FIRMATECKNING)
        info_objects = ["FUNKTIONARER", "FIRMATECKNING"]

    token = get_token()
    url = f"{BVG_BASE}/foretagsinformation/v4/organisationer"
    body = {
        "identitetsbeteckning": orgnr,  # utan bindestreck
        "organisationInformationsmangd": info_objects
        # namnskyddslopnummer kan läggas till för enskild firma/flera på samma orgnr
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Request-Id": str(uuid.uuid4()),
    }
    r = requests.post(url, json=body, headers=headers, timeout=30)
    # Om det blir 400 här har vi fel body; logga upp svaret med .text i caller
    r.raise_for_status()
    return r.json()


# Legacy BolagsverketService class for backward compatibility
class BolagsverketService:
    """
    Legacy service wrapper for compatibility with existing code
    """
    
    def __init__(self):
        self.client_id = BVG_CLIENT_ID
        self.client_secret = BVG_CLIENT_SECRET
        self.api_base_url = f"{BVG_BASE}/foretagsinformation/v4"
        
    async def get_company_info(self, org_number: str) -> Optional[Dict[str, Any]]:
        """
        Get company information from Bolagsverket (async wrapper)
        """
        try:
            return fetch_company_objects(org_number, ["FUNKTIONARER", "FIRMATECKNING"])
        except Exception:
            return None
