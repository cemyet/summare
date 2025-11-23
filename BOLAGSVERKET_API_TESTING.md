# Bolagsverket API Testing Guide

## Översikt

Detta dokument beskriver hur man testar integration med Bolagsverkets API för inlämning av årsredovisningar.

## Viktigt om Brandvägg

Bolagsverkets test-API är skyddat av en brandvägg som endast släpper igenom trafik från whitelistade IP-adresser.

**Railway Backend statisk IP:** `208.77.244.15`

Denna IP måste vara registrerad hos Bolagsverket för att testen ska fungera.

## API-endpoints

### 1. Test Brandväggsåtkomst

**Endpoint:** `GET /api/bolagsverket/test-firewall`

Testar om backend kan nå Bolagsverkets testmiljö genom brandväggen.

**Exempel:**
```bash
curl https://your-backend.railway.app/api/bolagsverket/test-firewall
```

**Response:**
```json
{
  "host": "arsredovisning-accept2.bolagsverket.se",
  "port": 443,
  "external_ip": "208.77.244.15",
  "is_railway_backend": true,
  "socket_test": {
    "success": true,
    "error": null
  },
  "https_test": {
    "success": true,
    "status_code": 200
  }
}
```

### 2. Skapa Inlämningstoken

**Endpoint:** `POST /api/bolagsverket/skapa-inlamningtoken`

Skapar en token för kontroll och inlämning av årsredovisning.

**Request Body:**
```json
{
  "orgnr": "5566103643",
  "pnr": "197212022516"
}
```

**Validering:**
- `orgnr`: Organisationsnummer (10 siffror, inget bindestreck)
- `pnr`: Personnummer inkl sekel (12 siffror, format: (19|20)[0-9]{10})

**Exempel:**
```bash
curl -X POST https://your-backend.railway.app/api/bolagsverket/skapa-inlamningtoken \
  -H "Content-Type: application/json" \
  -d '{
    "orgnr": "5566103643",
    "pnr": "197212022516"
  }'
```

**Success Response:**
```json
{
  "success": true,
  "status_code": 200,
  "data": {
    "token": "...",
    ...
  }
}
```

**Error Response:**
```json
{
  "detail": "Timeout when calling Bolagsverket API. Check firewall access."
}
```

## Testfiler

### Backend-testfiler (Python)

1. **`test_bolagsverket.py`** - Direkttest av API-anrop
   - Använd för lokal utveckling och debugging
   - Kör: `python backend/test_bolagsverket.py`

2. **`test_bolagsverket_firewall.py`** - Brandväggstest
   - Testar socket och HTTPS-anslutning
   - Visar extern IP-adress
   - Kör: `python backend/test_bolagsverket_firewall.py`

3. **`test_bolagsverket_api.sh`** - Shell-script för API-endpoints
   - Testar de nya endpoints i main.py
   - Kör lokalt: `bash backend/test_bolagsverket_api.sh`
   - Kör mot Railway: `BACKEND_URL=https://your-backend.railway.app bash backend/test_bolagsverket_api.sh`

## Testprocedur

### Steg 1: Verifiera Brandväggsåtkomst

Först måste du kontrollera att Railway backend kan nå Bolagsverkets testmiljö:

```bash
# Från Railway backend
curl https://your-backend.railway.app/api/bolagsverket/test-firewall
```

**Förväntat resultat:**
- `is_railway_backend: true`
- `socket_test.success: true`
- `https_test.success: true`

Om något test misslyckas:
1. Kontrollera att IP-adressen `208.77.244.15` är korrekt registrerad hos Bolagsverket
2. Verifiera att brandväggsöppningen är klar
3. Kontakta Bolagsverkets kontaktperson för felsökning

### Steg 2: Testa Skapa Inlämningstoken

När brandväggen fungerar, testa att skapa en inlämningstoken:

```bash
curl -X POST https://your-backend.railway.app/api/bolagsverket/skapa-inlamningtoken \
  -H "Content-Type: application/json" \
  -d '{
    "orgnr": "5566103643",
    "pnr": "197212022516"
  }'
```

**Förväntat resultat:**
- `success: true`
- `status_code: 200` eller `201`
- `data` innehåller token och annan information

## Felsökning

### Problem: Timeout vid API-anrop

**Orsaker:**
1. Brandväggen släpper inte igenom trafik från Railway IP
2. Fel IP-adress registrerad hos Bolagsverket
3. URL:en är felaktig

**Lösning:**
1. Kör brandväggstestet: `/api/bolagsverket/test-firewall`
2. Kontrollera att Railway backend använder rätt statisk IP
3. Kontakta Bolagsverkets support

### Problem: DNS-fel

**Orsaker:**
- Hostname `arsredovisning-accept2.bolagsverket.se` kan inte resolvas

**Lösning:**
- Verifiera hostname med Bolagsverkets dokumentation
- Kontrollera att DNS fungerar på Railway backend

### Problem: SSL-fel

**Orsaker:**
- Bolagsverket kan ha speciell SSL-konfiguration i testmiljön

**Lösning:**
- Detta kan vara normalt för testmiljö
- Kontakta Bolagsverket för information om SSL-certifikat

## Bolagsverkets Dokumentation

**Test-URL:** `https://arsredovisning-accept2.bolagsverket.se`

**API-version:** v2.1

**Endpoint:** `/testapi/lamna-in-arsredovisning/v2.1/skapa-inlamningtoken/`

**Verifiering av brandvägg (telnet):**
- Host: `arsredovisning-accept2.bolagsverket.se`
- Port: `443`

Om telnet-uppkopplingen fungerar utan fel är brandväggsöppningen korrekt konfigurerad.

## Kontakt

Vid problem med brandväggen eller API-åtkomst, kontakta din kontaktperson på Bolagsverket.

