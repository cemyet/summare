"""
Test för Bolagsverkets API - Kontrollera årsredovisning

Skickar en årsredovisning (iXBRL) för kontroll innan uppladdning till eget utrymme.
"""
import requests
import json
import os
import base64
from pprint import pprint

# Path to TeliaSonera Root CA v1 certificate
CERT_PATH = os.path.join(os.path.dirname(__file__), "teliasonera_root_ca_v1.pem")


def kontrollera_arsredovisning(kontrolltoken: str, filepath: str, typ: str = "arsredovisning_komplett"):
    """
    Kontrollera årsredovisning innan uppladdning till eget utrymme
    
    Args:
        kontrolltoken: Token för kontroll (UUID)
        filepath: Sökväg till årsredovisningsfil (iXBRL .xhtml)
        typ: Typ av handling
            - "arsredovisning_komplett": Årsredovisning med revisionsberättelse i samma fil 
                                         eller utan revisionsberättelse
            - "arsredovisning_kompletteras": Årsredovisning som ska kompletteras med 
                                             separat revisionsberättelse
            - "revisionsberattelse": Separat revisionsberättelse
    
    Returns:
        API response från Bolagsverket
    """
    url = f"https://api-accept2.bolagsverket.se/testapi/lamna-in-arsredovisning/v2.1/kontrollera/{kontrolltoken}"
    
    print("=" * 80)
    print("Kontrollerar Årsredovisning via Bolagsverkets API")
    print("=" * 80)
    print(f"\nURL: {url}")
    print(f"Token: {kontrolltoken}")
    print(f"Fil: {filepath}")
    print(f"Typ: {typ}")
    
    # Läs och base64-encoda filen
    try:
        with open(filepath, 'rb') as f:
            fil_innehall = f.read()
        
        # Kontrollera att det är UTF-8
        try:
            fil_innehall.decode('utf-8')
            print(f"✅ Filen är UTF-8 encoded")
        except UnicodeDecodeError:
            print(f"⚠️  VARNING: Filen är inte UTF-8 encoded")
        
        # Base64-encoda
        fil_base64 = base64.b64encode(fil_innehall).decode('ascii')
        
        print(f"\nFilstorlek: {len(fil_innehall)} bytes")
        print(f"Base64-storlek: {len(fil_base64)} tecken")
        
    except FileNotFoundError:
        print(f"\n❌ ERROR: Filen '{filepath}' hittades inte!")
        return None
    except Exception as e:
        print(f"\n❌ ERROR vid filläsning: {e}")
        return None
    
    # Skapa anropsobjekt
    anropsobjekt = {
        "handling": {
            "fil": fil_base64,
            "typ": typ
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    print("\n" + "-" * 80)
    print("Skickar årsredovisning för kontroll...")
    print("-" * 80)
    
    try:
        # Skicka request med TeliaSonera certifikat
        response = requests.post(url, json=anropsobjekt, headers=headers, timeout=60, verify=CERT_PATH)
        
        print(f"\n✅ Status Code: {response.status_code}")
        print(f"\nResponse Headers:")
        for key, value in response.headers.items():
            print(f"  {key}: {value}")
        
        print("\n" + "=" * 80)
        print("KONTROLLRESULTAT")
        print("=" * 80)
        
        # Försök att visa svar som JSON
        try:
            response_json = response.json()
            print("\nJSON Response:")
            pprint(response_json, width=100, indent=2)
            return response_json
        except json.JSONDecodeError:
            print("\nText Response:")
            print(response.text)
            return response.text
            
    except requests.exceptions.Timeout:
        print(f"\n⚠️  TIMEOUT: API:et svarade inte inom 60 sekunder")
        return None
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Exception when calling KontrollApi->kontrollera: {e}")
        return None


if __name__ == "__main__":
    # Test med angivna uppgifter
    kontrolltoken = "de3929f7-c2df-4298-ba5d-e028d4947a5b"
    filepath = "/Users/cemyeter/Desktop/arsredovisning.xhtml"
    organisationsnummer = "5566103643"
    
    print("\n")
    print("🔍 Testar kontroll av årsredovisning med:")
    print(f"   Token: {kontrolltoken}")
    print(f"   Organisationsnummer: {organisationsnummer}")
    print(f"   Fil: {filepath}")
    print("")
    
    result = kontrollera_arsredovisning(
        kontrolltoken=kontrolltoken,
        filepath=filepath,
        typ="arsredovisning_komplett"
    )
    
    print("\n" + "=" * 80)
    print("Test slutfört")
    print("=" * 80 + "\n")

