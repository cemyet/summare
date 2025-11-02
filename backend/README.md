# Raketrapport Backend API

FastAPI-backend för att generera årsredovisningar enligt K2-standard.

## 🚀 Installation

1. **Installera dependencies:**
```bash
pip install -r requirements.txt
```

2. **Konfigurera miljövariabler:**
```bash
cp env.example .env
# Redigera .env med dina Supabase-credentials
```

### TellusTalk Digital Signing Configuration

For digital signature functionality using TellusTalk, add these environment variables:

```bash
# TellusTalk eBox API credentials (required)
TELLUSTALK_USERNAME=your_tellustalk_username
TELLUSTALK_PASSWORD=your_tellustalk_password

# Optional: Redirect URLs after signing
TELLUSTALK_SUCCESS_REDIRECT_URL=https://summare.se/app?signing=success
TELLUSTALK_FAIL_REDIRECT_URL=https://summare.se/app?signing=failed

# Optional: Webhook URL for signing status updates
TELLUSTALK_REPORT_TO_URL=https://api.summare.se/webhooks/tellustalk-status
```

3. **Starta servern:**
```bash
python main.py
# eller
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 📚 API Endpoints

### Grundläggande
- `GET /` - API-status
- `GET /health` - Hälsokontroll

### Filhantering
- `POST /upload-se-file` - Ladda upp .SE-fil
- `GET /download-report/{report_id}` - Ladda ner PDF-rapport

### Rapportgenerering
- `POST /generate-report` - Generera årsredovisning
- `GET /user-reports/{user_id}` - Hämta användarens rapporter

### Företagsinformation
- `GET /company-info/{org_number}` - Hämta från Allabolag.se

## 🗄️ Supabase Setup

Skapa följande tabeller i Supabase:

### `reports` tabell:
```sql
CREATE TABLE reports (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id TEXT NOT NULL,
  report_id TEXT NOT NULL,
  company_name TEXT NOT NULL,
  fiscal_year INTEGER NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  pdf_path TEXT
);
```

### `user_preferences` tabell:
```sql
CREATE TABLE user_preferences (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id TEXT UNIQUE NOT NULL,
  preferences JSONB,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### `signing_status` tabell:
```sql
CREATE TABLE signing_status (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  job_uuid TEXT NOT NULL UNIQUE,
  organization_number TEXT,
  job_name TEXT,
  ebox_job_key TEXT,
  event TEXT NOT NULL, -- 'created', 'job_started', 'signature_completed', 'job_completed'
  signing_details JSONB, -- Contains member info, signed/pending counts, etc.
  signed_pdf_download_url TEXT,
  status_data JSONB, -- Full status data from webhook
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_signing_status_job_uuid ON signing_status(job_uuid);
CREATE INDEX idx_signing_status_org_number ON signing_status(organization_number);
CREATE INDEX idx_signing_status_event ON signing_status(event);
```

## 🔧 Utveckling

### Projektstruktur:
```
raketrapport-backend/
├── main.py                 # FastAPI app
├── models/
│   └── schemas.py          # Pydantic schemas
├── services/
│   ├── report_generator.py # PDF-generering
│   └── supabase_service.py # Database operations
├── utils/                  # Hjälpfunktioner
├── reports/                # Genererade PDF:er
└── temp/                   # Temporära filer
```

### Använder befintlig Python-kod:
Backend använder din befintliga Python-kod från `/Users/cem/Desktop/ÅR/merged_rr_br_not.py` för att generera rapporter.

## 🌐 CORS
API:et är konfigurerat för att acceptera requests från:
- `http://localhost:3000` (React dev)
- `https://raketrapport.se` (produktion)

## 📝 Exempel-användning

### Ladda upp .SE-fil:
```bash
curl -X POST "http://localhost:8000/upload-se-file" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@din_fil.se"
```

### Generera rapport:
```bash
curl -X POST "http://localhost:8000/generate-report" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "se_file_path": "/path/to/file.se",
    "company_data": {...},
    "yearly_result": 1000000,
    "employee_count": 5,
    "location": "Stockholm"
  }'
``` 