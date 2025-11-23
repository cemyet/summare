# Bolagsverket SSL Certificate

## TeliaSonera Root CA v1

Bolagsverkets testmiljö använder ett SSL-certifikat utfärdat av TeliaSonera Root CA v1.

**Server Certificate DN:**
```
CN = *.BOLAGSVERKET.SE
OU = IT
O = Bolagsverket
L = SUNDSVALL
C = SE
```

**Root Certificate:**
```
CN = TeliaSonera Root CA v1
O = TeliaSonera
```

## Certifikatfiler

Detta repository innehåller följande certifikatfiler:

- **`teliasonera_root_ca_v1.cer`** - Original DER-format certifikat från TeliaSonera
- **`teliasonera_root_ca_v1.pem`** - Konverterat PEM-format för användning med Python requests

## Hämta Certifikat

Certifikatet kan hämtas från TeliaSoneras officiella repository:

https://repository.trust.teliasonera.com/teliasonerarootcav1.cer

## Konvertering

För att konvertera från CER (DER) till PEM-format:

```bash
openssl x509 -inform DER -in teliasonera_root_ca_v1.cer -out teliasonera_root_ca_v1.pem
```

## Användning i Python

Koden använder automatiskt det medföljande certifikatet:

```python
import requests
import os

# Path to certificate
cert_path = os.path.join(os.path.dirname(__file__), "teliasonera_root_ca_v1.pem")

# Make request with certificate verification
response = requests.get(
    "https://api-accept2.bolagsverket.se/...",
    verify=cert_path
)
```

## Varför Behövs Detta?

TeliaSonera Root CA v1 ingår inte i standard certificate trust stores för de flesta programmeringsspråk och verktyg (Java JDK, Python, etc.).

Utan detta certifikat kommer SSL-handshake att misslyckas med fel som:
- `SSLHandshakeException`
- `PKIX path building failed`
- `unable to find valid certification path to requested target`

## Säkerhet

✅ **Säkert:** Använder officiellt root-certifikat från TeliaSonera  
❌ **Osäkert:** Att stänga av SSL-verifiering helt (`verify=False`)

Vår implementation använder det säkra alternativet.

