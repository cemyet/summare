"""
Test för Bolagsverkets API - Skapa inlämningstoken för årsredovisning

Note: Bolagsverket's test environment uses TeliaSonera Root CA v1 SSL certificate.
"""
import requests
import json
import os
from pprint import pprint

# Path to TeliaSonera Root CA v1 certificate
CERT_PATH = os.path.join(os.path.dirname(__file__), "teliasonera_root_ca_v1.pem")


def skapa_inlamningtoken(orgnr: str, pnr: str):
    """
    Skapa token för kontroll och inlämning till eget utrymme
    
    Args:
        orgnr: Organisationsnummer för aktiebolaget (10 siffror, inget bindestreck)
        pnr: Personnummer inkl sekel (12 siffror)
    
    Returns:
        API response
    """
    url = "https://api-accept2.bolagsverket.se/testapi/lamna-in-arsredovisning/v2.1/skapa-inlamningtoken/"
    
    # Anropsobjekt med personnummer och organisationsnummer
    anropsobjekt = {
        "pnr": pnr,
        "orgnr": orgnr
    }
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    print("=" * 80)
    print("Testar Bolagsverkets API - Skapa inlämningstoken")
    print("=" * 80)
    print(f"\nURL: {url}")
    print(f"\nRequest body:")
    pprint(anropsobjekt)
    print("\n" + "-" * 80)
    
    try:
        # Use TeliaSonera Root CA v1 certificate for SSL verification
        response = requests.post(url, json=anropsobjekt, headers=headers, timeout=10, verify=CERT_PATH)
        
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response Headers:")
        pprint(dict(response.headers))
        print("\nResponse Body:")
        
        # Försök att visa svar som JSON om möjligt
        try:
            response_json = response.json()
            pprint(response_json)
            return response_json
        except json.JSONDecodeError:
            print(response.text)
            return response.text
    
    except requests.exceptions.Timeout:
        print(f"\n⚠️  TIMEOUT: API:et svarade inte inom 10 sekunder")
        print(f"   Detta kan bero på:")
        print(f"   - API:et är inte tillgängligt just nu")
        print(f"   - API-accept2 kräver VPN eller speciellt nätverk")
        print(f"   - URL:en är felaktig")
        return None
        
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Exception when calling InlamningApi->skapaInlamningtoken: {e}")
        return None


if __name__ == "__main__":
    # Test med angivna uppgifter
    organisationsnummer = "5566103643"
    personnummer = "197212022516"
    
    print("\n🔍 Testar med:")
    print(f"   Organisationsnummer: {organisationsnummer}")
    print(f"   Personnummer: {personnummer}\n")
    
    result = skapa_inlamningtoken(organisationsnummer, personnummer)
    
    print("\n" + "=" * 80)
    print("Test slutfört")
    print("=" * 80)

