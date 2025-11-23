"""
Test för att verifiera brandväggsåtkomst till Bolagsverkets testmiljö
Detta test måste köras från Railway backend (IP: 208.77.244.15) för att fungera
"""
import socket
import requests


def test_firewall_access():
    """
    Testar om vi kan nå Bolagsverkets testmiljö genom brandväggen
    Simulerar telnet till api-accept2.bolagsverket.se:443
    """
    host = "api-accept2.bolagsverket.se"
    port = 443
    timeout = 10
    
    print("=" * 80)
    print("Test av brandväggsåtkomst till Bolagsverkets testmiljö")
    print("=" * 80)
    print(f"\nHost: {host}")
    print(f"Port: {port}")
    print(f"Timeout: {timeout} sekunder")
    print("\n⚠️  OBS: Detta test fungerar endast från Railway backend (IP: 208.77.244.15)")
    print("-" * 80)
    
    # Test 1: Socket-uppkoppling (telnet-liknande)
    print("\n🔌 Test 1: Socket-uppkoppling (telnet-liknande)...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"   ✅ SUCCESS: Kan ansluta till {host}:{port}")
            print(f"   Brandväggen släpper igenom trafik!")
            return True
        else:
            print(f"   ❌ FAILED: Kan inte ansluta till {host}:{port}")
            print(f"   Error code: {result}")
            return False
            
    except socket.timeout:
        print(f"   ⚠️  TIMEOUT: Ingen respons från {host}:{port}")
        print(f"   Brandväggen blockerar troligen trafiken")
        return False
    except socket.gaierror as e:
        print(f"   ❌ DNS ERROR: Kan inte resolva {host}")
        print(f"   Error: {e}")
        return False
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False


def test_https_connection():
    """
    Testar HTTPS-anslutning till Bolagsverkets API
    """
    host = "api-accept2.bolagsverket.se"
    
    print("\n🌐 Test 2: HTTPS-anslutning...")
    print(f"   Testar: https://{host}/")
    
    try:
        response = requests.get(f"https://{host}/", timeout=10)
        print(f"   ✅ HTTPS-anslutning fungerar!")
        print(f"   Status Code: {response.status_code}")
        return True
    except requests.exceptions.Timeout:
        print(f"   ⚠️  TIMEOUT: HTTPS-anslutningen timeout efter 10 sekunder")
        return False
    except requests.exceptions.SSLError as e:
        print(f"   ⚠️  SSL ERROR: {e}")
        print(f"   (Detta kan vara normalt om servern har speciell SSL-konfiguration)")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"   ❌ CONNECTION ERROR: {e}")
        return False
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False


def get_external_ip():
    """
    Hämtar den externa IP-adressen som används för utgående anrop
    """
    print("\n🌍 Aktuell utgående IP-adress:")
    try:
        response = requests.get("https://api.ipify.org?format=json", timeout=5)
        ip = response.json()["ip"]
        print(f"   IP: {ip}")
        
        if ip == "208.77.244.15":
            print(f"   ✅ Kör från Railway backend (statisk IP)")
        else:
            print(f"   ⚠️  Kör INTE från Railway backend")
            print(f"   Expected: 208.77.244.15")
            print(f"   Got: {ip}")
        
        return ip
    except Exception as e:
        print(f"   ❌ Kunde inte hämta IP: {e}")
        return None


if __name__ == "__main__":
    print("\n")
    
    # Visa aktuell IP
    get_external_ip()
    
    # Test brandväggsåtkomst
    firewall_ok = test_firewall_access()
    
    # Test HTTPS-anslutning
    https_ok = test_https_connection()
    
    # Sammanfattning
    print("\n" + "=" * 80)
    print("SAMMANFATTNING")
    print("=" * 80)
    
    if firewall_ok and https_ok:
        print("✅ Alla tester lyckades!")
        print("   Brandväggen släpper igenom och HTTPS fungerar.")
        print("   Redo att testa API-anrop till Bolagsverket.")
    elif firewall_ok:
        print("⚠️  Socket-anslutning fungerar men HTTPS har problem")
        print("   Brandväggen släpper igenom men det kan finnas SSL-problem")
    else:
        print("❌ Brandväggen blockerar trafiken")
        print("   Möjliga orsaker:")
        print("   - Kör inte från Railway backend (IP: 208.77.244.15)")
        print("   - Brandväggsöppningen är inte klar än")
        print("   - Fel IP-adress angavs till Bolagsverket")
    
    print("=" * 80 + "\n")

