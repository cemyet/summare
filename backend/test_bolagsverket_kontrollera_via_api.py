"""
Test för att kontrollera årsredovisning via Railway backend API
Detta script anropar vår egen API som i sin tur anropar Bolagsverkets API från Railway backend.
"""
import requests
import json
import base64
from pprint import pprint


def kontrollera_via_railway(filepath: str, token: str, typ: str = "arsredovisning_komplett", 
                            backend_url: str = "https://api.summare.se"):
    """
    Kontrollera årsredovisning via Railway backend API
    
    Args:
        filepath: Sökväg till årsredovisningsfil (iXBRL .xhtml)
        token: Token från skapa-inlamningtoken
        typ: Typ av handling (arsredovisning_komplett, arsredovisning_kompletteras, revisionsberattelse)
        backend_url: URL till Railway backend
    """
    print("=" * 80)
    print("Kontrollerar Årsredovisning via Railway Backend")
    print("=" * 80)
    print(f"\nBackend URL: {backend_url}")
    print(f"Token: {token}")
    print(f"Fil: {filepath}")
    print(f"Typ: {typ}\n")
    
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
        
        print(f"Filstorlek: {len(fil_innehall):,} bytes")
        print(f"Base64-storlek: {len(fil_base64):,} tecken")
        
    except FileNotFoundError:
        print(f"\n❌ ERROR: Filen '{filepath}' hittades inte!")
        return None
    except Exception as e:
        print(f"\n❌ ERROR vid filläsning: {e}")
        return None
    
    # Skapa request
    request_data = {
        "token": token,
        "fil_base64": fil_base64,
        "typ": typ
    }
    
    print("\n" + "-" * 80)
    print("Skickar till Railway backend...")
    print("-" * 80)
    
    try:
        response = requests.post(
            f"{backend_url}/api/bolagsverket/kontrollera-arsredovisning",
            json=request_data,
            timeout=90  # Längre timeout för filuppladdning
        )
        
        print(f"\n✅ Status Code: {response.status_code}")
        
        print("\n" + "=" * 80)
        print("KONTROLLRESULTAT FRÅN BOLAGSVERKET")
        print("=" * 80)
        
        # Visa svar
        try:
            response_json = response.json()
            print("\nJSON Response:")
            pprint(response_json, width=100, indent=2)
            
            # Extrahera viktiga delar
            if response_json.get("success"):
                data = response_json.get("data", {})
                if isinstance(data, dict):
                    print("\n" + "-" * 80)
                    print("SAMMANFATTNING")
                    print("-" * 80)
                    
                    # Kolla om det finns fel eller varningar
                    if "fel" in data:
                        print(f"\n❌ FEL: {len(data['fel'])} st")
                        for i, fel in enumerate(data.get("fel", []), 1):
                            print(f"  {i}. {fel}")
                    
                    if "varningar" in data:
                        print(f"\n⚠️  VARNINGAR: {len(data['varningar'])} st")
                        for i, varning in enumerate(data.get("varningar", []), 1):
                            print(f"  {i}. {varning}")
                    
                    if not data.get("fel") and not data.get("varningar"):
                        print("\n✅ Inga fel eller varningar!")
            
            return response_json
            
        except json.JSONDecodeError:
            print("\nText Response:")
            print(response.text)
            return response.text
            
    except requests.exceptions.Timeout:
        print(f"\n⚠️  TIMEOUT: Backend svarade inte inom 90 sekunder")
        return None
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Exception: {e}")
        return None


if __name__ == "__main__":
    # Konfiguration
    filepath = "/Users/cemyeter/Desktop/arsredovisning.xhtml"
    token = "de3929f7-c2df-4298-ba5d-e028d4947a5b"
    organisationsnummer = "5566103643"
    
    print("\n🔍 Testar kontroll av årsredovisning:")
    print(f"   Organisationsnummer: {organisationsnummer}")
    print(f"   Token: {token}")
    print(f"   Fil: {filepath}")
    print("")
    
    result = kontrollera_via_railway(
        filepath=filepath,
        token=token,
        typ="arsredovisning_komplett",
        backend_url="https://api.summare.se"
    )
    
    print("\n" + "=" * 80)
    print("Test slutfört")
    print("=" * 80 + "\n")

