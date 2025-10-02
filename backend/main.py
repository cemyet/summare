from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import os
import tempfile
import shutil
from datetime import datetime
import json
# --- STRIPE INIT (robust) ---
import os, logging, stripe, requests
logger = logging.getLogger("uvicorn")

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
if not STRIPE_SECRET_KEY:
    # Don't crash app; just log. The step-505 handler will raise a friendly error if needed.
    logger.warning("STRIPE_SECRET_KEY not set at startup")

# Keep legacy helpers working
stripe.api_key = STRIPE_SECRET_KEY

# IMPORTANT: never shadow these names elsewhere in your code
StripeClientClass = getattr(stripe, "StripeClient", None)  # may be None on odd installs
_has_checkout_sessions = bool(getattr(getattr(stripe, "checkout", None), "sessions", None))

logger.info("Stripe version: %s", getattr(stripe, "__version__", "?"))
logger.info("Stripe module file: %s", getattr(stripe, "__file__", "?"))
logger.info("Has StripeClient: %s", callable(StripeClientClass))
logger.info("Has checkout.sessions: %s", _has_checkout_sessions)

SUCCESS_URL = os.getenv("STRIPE_SUCCESS_URL", "https://summare.se/app?payment=success") + "?session_id={CHECKOUT_SESSION_ID}"
CANCEL_URL = os.getenv("STRIPE_CANCEL_URL", "https://summare.se/app?payment=cancelled")

def create_checkout_session_url(amount_ore: int,
                                email: str | None = None,
                                metadata: dict | None = None) -> str:
    key = os.getenv("STRIPE_SECRET_KEY")
    if not key:
        raise RuntimeError("Stripe not configured (STRIPE_SECRET_KEY missing)")

    success_url = os.getenv("STRIPE_SUCCESS_URL", "https://summare.se/app?payment=success") + "?session_id={CHECKOUT_SESSION_ID}"
    cancel_url  = os.getenv("STRIPE_CANCEL_URL",  "https://summare.se/app?payment=cancelled")

    # 1) Typed client (Stripe v7+)
    StripeClientClass = getattr(stripe, "StripeClient", None)
    if callable(StripeClientClass):
        client = StripeClientClass(key)
        s = client.checkout.sessions.create(
            mode="payment",
            line_items=[{
                "price_data": {
                    "currency": "sek",
                    "product_data": {"name": "Årsredovisning – Summare"},
                    "unit_amount": int(amount_ore),
                },
                "quantity": 1,
            }],
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=email,
            metadata=metadata or {},
            allow_promotion_codes=True,
        )
        return s.url

    # 2) Module helper (only if actually present)
    checkout = getattr(stripe, "checkout", None)
    sessions = getattr(checkout, "sessions", None) if checkout else None
    if callable(getattr(sessions, "create", None)):
        s = sessions.create(
            mode="payment",
            line_items=[{
                "price_data": {
                    "currency": "sek",
                    "product_data": {"name": "Årsredovisning – Summare"},
                    "unit_amount": int(amount_ore),
                },
                "quantity": 1,
            }],
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=email,
            metadata=metadata or {},
            allow_promotion_codes=True,
        )
        return s.url

    # 3) Raw HTTPS fallback (cannot be shadowed)
    form = {
        "mode": "payment",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "allow_promotion_codes": "true",
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": "sek",
        "line_items[0][price_data][product_data][name]": "Årsredovisning – Summare",
        "line_items[0][price_data][unit_amount]": str(int(amount_ore)),
    }
    if email:
        form["customer_email"] = email
    if metadata:
        for k, v in metadata.items():
            form[f"metadata[{k}]"] = str(v)

    r = requests.post(
        "https://api.stripe.com/v1/checkout/sessions",
        data=form,
        auth=(key, ""),  # Basic auth with secret key
        timeout=20,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"Stripe REST error {r.status_code}: {r.text}")
    return r.json()["url"]


# Importera våra moduler
# from services.report_generator import ReportGenerator  # Disabled - using DatabaseParser instead
from services.supabase_service import SupabaseService
from services.database_parser import DatabaseParser
from services.supabase_database import db
from services.bolagsverket_service import BolagsverketService
from services.fb import ForvaltningsberattelseFB
from rating_bolag_scraper import get_company_info_with_search
from models.schemas import (
    ReportRequest, ReportResponse, CompanyData, 
    ManagementReportRequest, ManagementReportResponse, 
    BolagsverketCompanyInfo, ManagementReportData
)

app = FastAPI(
    title="Raketrapport API",
    description="API för att generera årsredovisningar enligt K2",
    version="1.0.0"
)

# Configure CORS for embedded checkout
ALLOWED_ORIGINS = [
    "https://www.summare.se",
    "https://summare.se",
    "http://localhost:5173",   # vite dev, if needed
    "http://localhost:3000",   # next dev, if needed
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],   # includes POST/GET/OPTIONS
    allow_headers=["*"],   # include Authorization, Content-Type, etc.
)

# Note: CORS middleware configured above with comprehensive origins list

# Initiera services
# report_generator = ReportGenerator()  # Disabled - using DatabaseParser instead
supabase_service = SupabaseService()
bolagsverket_service = BolagsverketService()

def get_supabase_client():
    """Get Supabase client from the service"""
    if not supabase_service.client:
        print("Warning: Supabase client not available - using mock mode")
        return None
    return supabase_service.client

@app.get("/")
async def root():
    return {"message": "Raketrapport API är igång! 🚀"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# --- Embedded Checkout endpoint (pure HTTP, no SDK issues) - v2 ---
import os
import requests
from fastapi import Request, HTTPException

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")  # sk_test_xxx
if not STRIPE_SECRET_KEY:
    print("⚠️  STRIPE_SECRET_KEY missing at startup")

# Optional: dynamic price; we'll just send an amount
AMOUNT_SEK = int(os.getenv("STRIPE_AMOUNT_SEK", "699"))

def _stripe_post(path: str, form: dict):
    """Internal helper to call Stripe REST with form-encoded body."""
    url = f"https://api.stripe.com{path}"
    r = requests.post(url, data=form, auth=(STRIPE_SECRET_KEY, ""))
    if r.status_code >= 400:
        raise HTTPException(status_code=500, detail=r.text)
    return r.json()

@app.post("/api/payments/create-embedded-checkout")
async def create_embedded_checkout(request: Request):
    """
    Creates an *embedded* Checkout session and returns {client_secret, session_id}.
    Frontend will call stripe.initEmbeddedCheckout({ clientSecret }).
    """
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")

    # you can read payload if you wish:
    try:
        _ = await request.json()
    except Exception:
        _ = None

    # Build Stripe form for an embedded checkout session
    form = {
        "mode": "payment",
        "ui_mode": "embedded",
        # Use inline price_data so you don't need a Price in the dashboard
        "line_items[0][price_data][currency]": "sek",
        "line_items[0][price_data][product_data][name]": "Årsredovisning",
        "line_items[0][price_data][unit_amount]": str(AMOUNT_SEK * 100),  # öre
        "line_items[0][quantity]": "1",
        # Disable redirects completely - completion handled by JavaScript onComplete only
        "redirect_on_completion": "never",
        "automatic_tax[enabled]": "true",
    }

    try:
        session = _stripe_post("/v1/checkout/sessions", form)
        # Respond with exactly what the frontend needs
        return {
            "client_secret": session["client_secret"],
            "session_id": session["id"],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stripe/verify")
async def verify_stripe_session(session_id: str):
    """Verify payment status using direct HTTP call."""
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    
    try:
        session = _stripe_post(f"/v1/checkout/sessions/{session_id}", {})
        return {"paid": session["payment_status"] == "paid", "id": session["id"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/create-stripe-session")
async def create_stripe_session():
    """Create a Stripe checkout session for annual report payment"""
    try:
        amount_sek = int(os.getenv("STRIPE_AMOUNT_SEK", "299"))
        url = create_checkout_session_url(
            amount_ore=amount_sek * 100,
            metadata={"source": "api_endpoint"}
        )
        
        return {
            "checkout_url": url,
            "amount_sek": amount_sek
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create Stripe session: {str(e)}")

@app.post("/stripe-webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events for payment confirmation"""
    try:
        import stripe
        
        # Get the raw body and signature
        body = await request.body()
        sig_header = request.headers.get('stripe-signature')
        webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
        
        if not webhook_secret:
            print("⚠️ STRIPE_WEBHOOK_SECRET not configured - skipping signature verification")
            # Parse JSON directly for development
            import json
            event = json.loads(body.decode('utf-8'))
        else:
            # Verify webhook signature
            try:
                event = stripe.Webhook.construct_event(
                    body, sig_header, webhook_secret
                )
            except ValueError as e:
                print(f"❌ Invalid payload: {e}")
                raise HTTPException(status_code=400, detail="Invalid payload")
            except stripe.error.SignatureVerificationError as e:
                print(f"❌ Invalid signature: {e}")
                raise HTTPException(status_code=400, detail="Invalid signature")
        
        event_type = event.get('type')
        event_data = event.get('data', {}).get('object', {})
        
        print(f"🔔 Stripe webhook received: {event_type}")
        
        if event_type == 'checkout.session.completed':
            # Payment was successful
            session_id = event_data.get('id')
            customer_email = event_data.get('customer_details', {}).get('email')
            amount_total = event_data.get('amount_total', 0)
            customer_name = event_data.get('customer_details', {}).get('name', 'Unknown')
            
            print(f"✅ Payment successful: {session_id}, email: {customer_email}, name: {customer_name}, amount: {amount_total}")
            
            # Here you could:
            # 1. Update database to mark payment as completed
            # 2. Send confirmation email
            # 3. Trigger next steps in the annual report process
            # 4. Generate and send the final report
            
            # TODO: Add your business logic here
            # Example: Store payment in database, send email, etc.
            
            return {"status": "success", "message": "Payment processed successfully"}
            
        elif event_type == 'checkout.session.expired':
            # Payment session expired
            session_id = event_data.get('id')
            print(f"⏰ Payment session expired: {session_id}")
            
            return {"status": "expired", "message": "Payment session expired"}
            
        else:
            print(f"ℹ️ Unhandled webhook event: {event_type}")
            return {"status": "ignored", "message": f"Event {event_type} ignored"}
            
    except Exception as e:
        print(f"❌ Error processing Stripe webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")

@app.post("/upload-se-file", response_model=dict)
async def upload_se_file(file: UploadFile = File(...)):
    """
    Laddar upp en .SE-fil och extraherar grundläggande information
    """
    if not file.filename.lower().endswith('.se'):
        raise HTTPException(status_code=400, detail="Endast .SE-filer accepteras")
    
    try:
        # Skapa temporär fil
        with tempfile.NamedTemporaryFile(delete=False, suffix='.se') as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_path = temp_file.name
        
        # Read SE file content with encoding detection including PC8 format
        def detect_sie_encoding(file_path: str) -> str:
            """Detect SIE file encoding based on FORMAT header"""
            try:
                # Read first 200 bytes to check format
                with open(file_path, "rb") as f:
                    head = f.read(200).decode("latin-1", errors="ignore")
                
                if "#FORMAT PC8" in head:
                    return "cp437"  # IBM CP437 for PC8
                elif "#FORMAT UTF8" in head:
                    return "utf-8"
                else:
                    return "iso-8859-1"  # Default for older SIE files
            except Exception:
                return "iso-8859-1"  # Safe fallback
        
        # Try detected encoding first, then fallbacks
        detected_encoding = detect_sie_encoding(temp_path)
        encodings = [detected_encoding, 'cp437', 'iso-8859-1', 'windows-1252', 'utf-8', 'cp1252']
        se_content = None
        
        for encoding in encodings:
            try:
                with open(temp_path, 'r', encoding=encoding) as f:
                    content = f.read()
                    # Apply unicode normalization after reading
                    import unicodedata
                    se_content = unicodedata.normalize("NFKC", content)
                    se_content = se_content.replace("\u00A0", " ").replace("\u200B", "")
                break
            except UnicodeDecodeError:
                continue
        
        if se_content is None:
            raise HTTPException(status_code=500, detail="Kunde inte läsa SE-filen med någon av de försökta kodningarna")
        
        # Use the new database-driven parser
        parser = DatabaseParser()
        current_accounts, previous_accounts, current_ib_accounts, previous_ib_accounts = parser.parse_account_balances(se_content)
        company_info = parser.extract_company_info(se_content)
        
        # Scrape additional company information from rating.se
        scraped_company_data = {}
        try:

            scraped_company_data = get_company_info_with_search(
                orgnr=company_info.get('organization_number'),
                company_name=company_info.get('company_name')
            )

            

        except Exception as e:

            scraped_company_data = {"error": str(e)}
        
        rr_data = parser.parse_rr_data(current_accounts, previous_accounts)
        
        # Pass RR data to BR parsing so calculated values from RR are available
        # Use koncern-aware BR parsing for automatic reconciliation with K2 notes
        br_data = parser.parse_br_data_with_koncern(se_content, current_accounts, previous_accounts, rr_data)
        
        # Parse INK2 data (tax calculations) - pass RR data, BR data, SIE content, and previous accounts for account descriptions
        ink2_data = parser.parse_ink2_data(current_accounts, company_info.get('fiscal_year'), rr_data, br_data, se_content, previous_accounts)
        
        # Parse Noter data (notes) - pass SE content and user toggles if needed
        try:
            noter_data = parser.parse_noter_data(se_content, two_files_flag=False, previous_year_se_content=None)

        except Exception as e:

            noter_data = []
        
        # Parse Förvaltningsberättelse data (FB) - Förändring i eget kapital
        try:
            print(f"DEBUG: Starting FB calculation with br_data type: {type(br_data)}, length: {len(br_data) if br_data else 0}")
            if br_data and len(br_data) > 0:
                print(f"DEBUG: First BR item keys: {list(br_data[0].keys())}")
                print(f"DEBUG: Sample BR variable names: {[item.get('variable_name') for item in br_data[:5]]}")
            fb_module = ForvaltningsberattelseFB()
            fb_variables = fb_module.calculate_forandring_eget_kapital(se_content, br_data)
            print(f"DEBUG: FB variables calculated: {fb_variables}")
            fb_table = fb_module.generate_forandring_eget_kapital_table(fb_variables)
            print(f"DEBUG: FB table generated with {len(fb_table)} rows")
        except Exception as e:
            print(f"Error parsing FB data: {e}")
            import traceback
            traceback.print_exc()
            fb_variables = {}
            fb_table = []
        
        # Calculate pension tax variables for frontend
        pension_premier = abs(float(current_accounts.get('7410', 0.0)))
        # Särskild löneskatt can be booked in multiple accounts: 7530, 7531, 7532, 7533
        sarskild_loneskatt_pension = (
            abs(float(current_accounts.get('7530', 0.0))) +
            abs(float(current_accounts.get('7531', 0.0))) +
            abs(float(current_accounts.get('7532', 0.0))) +
            abs(float(current_accounts.get('7533', 0.0)))
        )
        # Get sarskild_loneskatt rate from global variables
        sarskild_loneskatt_rate = float(parser.global_variables.get('sarskild_loneskatt', 0.0))
        sarskild_loneskatt_pension_calculated = pension_premier * sarskild_loneskatt_rate
        
        # Store financial data in database (but don't fail if storage fails)
        stored_ids = {}
        if company_info.get('organization_number'):
            company_id = company_info['organization_number']
            fiscal_year = company_info.get('fiscal_year', datetime.now().year)
            
            try:
                # Store the parsed financial data
                stored_ids = parser.store_financial_data(company_id, fiscal_year, rr_data, br_data)

            except Exception as e:

                stored_ids = {}
        
        # Rensa upp temporär fil
        os.unlink(temp_path)
        
        return {
            "success": True,
            "data": {
                "company_info": company_info,
                "scraped_company_data": scraped_company_data,  # Add scraped company data
                "current_accounts_count": len(current_accounts),
                "previous_accounts_count": len(previous_accounts),
                "current_accounts_sample": dict(list(current_accounts.items())[:10]),
                "previous_accounts_sample": dict(list(previous_accounts.items())[:10]),
                "current_accounts": current_accounts,  # Add full accounts for recalculation
                "rr_data": rr_data,
                "br_data": br_data,
                "ink2_data": ink2_data,
                "noter_data": noter_data,
                "fb_variables": fb_variables,
                "fb_table": fb_table,
                "rr_count": len(rr_data),
                "br_count": len(br_data),
                "ink2_count": len(ink2_data),
                "noter_count": len(noter_data),
                "fb_count": len(fb_table),
                "pension_premier": pension_premier,
                "sarskild_loneskatt_pension": sarskild_loneskatt_pension,
                "sarskild_loneskatt_pension_calculated": sarskild_loneskatt_pension_calculated
            },
            "message": "SE-fil laddad framgångsrikt"
        }
        
    except Exception as e:
        import traceback
        error_detail = f"Fel vid laddning av fil: {str(e)}"
        full_traceback = traceback.format_exc()

        # Return more detailed error for debugging (you may want to remove this in production)
        raise HTTPException(status_code=500, detail=f"Fel vid laddning av fil: {str(e)} | Traceback: {full_traceback}")

@app.post("/upload-two-se-files", response_model=dict)
async def upload_two_se_files(
    current_year_file: UploadFile = File(...),
    previous_year_file: UploadFile = File(...)
):
    """
    Laddar upp två .SE-filer (nuvarande år + föregående år) och extraherar information
    """
    # Validate both files
    if not current_year_file.filename.lower().endswith('.se'):
        raise HTTPException(status_code=400, detail="Nuvarande års fil måste vara en .SE-fil")
    if not previous_year_file.filename.lower().endswith('.se'):
        raise HTTPException(status_code=400, detail="Föregående års fil måste vara en .SE-fil")
    
    try:
        # Process current year file (same as single file upload)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.se') as temp_file:
            shutil.copyfileobj(current_year_file.file, temp_file)
            current_temp_path = temp_file.name
        
        # Process previous year file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.se') as temp_file:
            shutil.copyfileobj(previous_year_file.file, temp_file)
            previous_temp_path = temp_file.name
        
        # Read both SE file contents with proper PC8 encoding detection
        def detect_sie_encoding(file_path: str) -> str:
            """Detect SIE file encoding based on FORMAT header"""
            try:
                # Read first 200 bytes to check format
                with open(file_path, "rb") as f:
                    head = f.read(200).decode("latin-1", errors="ignore")
                
                if "#FORMAT PC8" in head:
                    return "cp437"  # IBM CP437 for PC8
                elif "#FORMAT UTF8" in head:
                    return "utf-8"
                else:
                    return "iso-8859-1"  # Default for older SIE files
            except Exception:
                return "iso-8859-1"  # Safe fallback
        
        # Read current year file
        current_detected_encoding = detect_sie_encoding(current_temp_path)
        current_encodings = [current_detected_encoding, 'cp437', 'iso-8859-1', 'windows-1252', 'utf-8', 'cp1252']
        current_se_content = None
        
        for encoding in current_encodings:
            try:
                with open(current_temp_path, 'r', encoding=encoding) as f:
                    content = f.read()
                    # Apply unicode normalization after reading
                    import unicodedata
                    current_se_content = unicodedata.normalize("NFKC", content)
                    current_se_content = current_se_content.replace("\u00A0", " ").replace("\u200B", "")
                break
            except UnicodeDecodeError:
                continue
        
        # Read previous year file  
        previous_detected_encoding = detect_sie_encoding(previous_temp_path)
        previous_encodings = [previous_detected_encoding, 'cp437', 'iso-8859-1', 'windows-1252', 'utf-8', 'cp1252']
        previous_se_content = None
        
        for encoding in previous_encodings:
            try:
                with open(previous_temp_path, 'r', encoding=encoding) as f:
                    content = f.read()
                    # Apply unicode normalization after reading
                    import unicodedata
                    previous_se_content = unicodedata.normalize("NFKC", content)
                    previous_se_content = previous_se_content.replace("\u00A0", " ").replace("\u200B", "")
                break
            except UnicodeDecodeError:
                continue
        
        if current_se_content is None:
            raise HTTPException(status_code=500, detail="Kunde inte läsa nuvarande års SE-fil")
        if previous_se_content is None:
            raise HTTPException(status_code=500, detail="Kunde inte läsa föregående års SE-fil")
        
        # Use the new database-driven parser with two files flag
        parser = DatabaseParser()
        
        # Extract company info from both files to validate years
        current_company_info = parser.extract_company_info(current_se_content)
        previous_company_info = parser.extract_company_info(previous_se_content)
        
        # Validate that both files belong to the same company
        current_org_number = current_company_info.get('organization_number')
        previous_org_number = previous_company_info.get('organization_number')
        current_company_name = current_company_info.get('company_name')
        previous_company_name = previous_company_info.get('company_name')
        
        # Check organization numbers first (primary method)
        if current_org_number and previous_org_number:
            if current_org_number != previous_org_number:
                raise HTTPException(
                    status_code=400,
                    detail="SIE-filerna verkar vara från olika bolag. Kontrollera att båda filerna tillhör samma företag."
                )
        # Fallback to company names if organization numbers are missing
        elif current_company_name and previous_company_name:
            if current_company_name.strip().lower() != previous_company_name.strip().lower():
                raise HTTPException(
                    status_code=400,
                    detail="SIE-filerna verkar vara från olika bolag. Kontrollera att båda filerna tillhör samma företag."
                )
        # If we can't validate company match, proceed with warning (could add logging here)
        
        # Validate that the years are consecutive
        current_fiscal_year = current_company_info.get('fiscal_year')
        previous_fiscal_year = previous_company_info.get('fiscal_year')
        
        if current_fiscal_year and previous_fiscal_year:
            # Determine which is the newer and older year
            fiscal_year = max(current_fiscal_year, previous_fiscal_year)
            previous_year = min(current_fiscal_year, previous_fiscal_year)
            
            # Check that they are consecutive years
            if fiscal_year - previous_year != 1:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Filerna måste avse två på varandra följande räkenskapsår. Du har laddat upp filer från {fiscal_year} och {previous_year}."
                )
            
            # Ensure we always use the newer year as "current" for annual report generation
            if current_fiscal_year < previous_fiscal_year:
                # User uploaded files in reverse order - swap them
                current_se_content, previous_se_content = previous_se_content, current_se_content
                current_company_info, previous_company_info = previous_company_info, current_company_info
        
        current_accounts, previous_accounts, current_ib_accounts, previous_ib_accounts = parser.parse_account_balances(current_se_content)
        company_info = current_company_info
        
        # Scrape additional company information from rating.se
        scraped_company_data = {}
        try:
            scraped_company_data = get_company_info_with_search(
                orgnr=company_info.get('organization_number'),
                company_name=company_info.get('company_name')
            )
        except Exception as e:
            scraped_company_data = {"error": str(e)}
        
        rr_data = parser.parse_rr_data(current_accounts, previous_accounts)
        
        # Pass RR data to BR parsing with two files flag and previous year SE content
        br_data = parser.parse_br_data_with_koncern(
            current_se_content, 
            current_accounts, 
            previous_accounts, 
            rr_data,
            two_files_flag=True,
            previous_year_se_content=previous_se_content
        )
        
        # Parse INK2 data (tax calculations) - pass RR data, BR data, SIE content, and previous accounts for account descriptions
        ink2_data = parser.parse_ink2_data(current_accounts, company_info.get('fiscal_year'), rr_data, br_data, current_se_content, previous_accounts)
        
        # Parse Noter data (notes) - pass SE content and user toggles if needed
        try:
            noter_data = parser.parse_noter_data(
                current_se_content, 
                two_files_flag=True, 
                previous_year_se_content=previous_se_content
            )
        except Exception as e:
            noter_data = []
        
        # Parse Förvaltningsberättelse data (FB) - Förändring i eget kapital
        try:
            print(f"DEBUG: Starting FB calculation with br_data type: {type(br_data)}, length: {len(br_data) if br_data else 0}")
            if br_data and len(br_data) > 0:
                print(f"DEBUG: First BR item keys: {list(br_data[0].keys())}")
                print(f"DEBUG: Sample BR variable names: {[item.get('variable_name') for item in br_data[:5]]}")
            fb_module = ForvaltningsberattelseFB()
            fb_variables = fb_module.calculate_forandring_eget_kapital(current_se_content, br_data)
            print(f"DEBUG: FB variables calculated: {fb_variables}")
            fb_table = fb_module.generate_forandring_eget_kapital_table(fb_variables)
            print(f"DEBUG: FB table generated with {len(fb_table)} rows")
        except Exception as e:
            print(f"Error parsing FB data: {e}")
            import traceback
            traceback.print_exc()
            fb_variables = {}
            fb_table = []
        
        # Calculate pension tax variables for frontend
        pension_premier = abs(float(current_accounts.get('7410', 0.0)))
        # Särskild löneskatt can be booked in multiple accounts: 7530, 7531, 7532, 7533
        sarskild_loneskatt_pension = (
            abs(float(current_accounts.get('7530', 0.0))) +
            abs(float(current_accounts.get('7531', 0.0))) +
            abs(float(current_accounts.get('7532', 0.0))) +
            abs(float(current_accounts.get('7533', 0.0)))
        )
        # Get sarskild_loneskatt rate from global variables
        sarskild_loneskatt_pension_calculated = pension_premier * 0.2431
        
        # Cleanup temporary files
        os.unlink(current_temp_path)
        os.unlink(previous_temp_path)
        
        return {
            "success": True,
            "data": {
                "company_info": company_info,
                "scraped_company_data": scraped_company_data,
                "current_accounts_count": len(current_accounts),
                "previous_accounts_count": len(previous_accounts),
                "current_accounts_sample": dict(list(current_accounts.items())[:10]),
                "previous_accounts_sample": dict(list(previous_accounts.items())[:10]),
                "current_accounts": current_accounts,
                "rr_data": rr_data,
                "br_data": br_data,
                "ink2_data": ink2_data,
                "noter_data": noter_data,
                "fb_variables": fb_variables,
                "fb_table": fb_table,
                "rr_count": len(rr_data),
                "br_count": len(br_data),
                "ink2_count": len(ink2_data),
                "noter_count": len(noter_data),
                "fb_count": len(fb_table),
                "pension_premier": pension_premier,
                "sarskild_loneskatt_pension": sarskild_loneskatt_pension,
                "sarskild_loneskatt_pension_calculated": sarskild_loneskatt_pension_calculated,
                "two_files_used": True  # Flag to indicate two files were processed
            },
            "message": "Båda SE-filerna laddades framgångsrikt"
        }
        
    except HTTPException:
        # Re-raise HTTPExceptions (like our validation errors) without modification
        raise
    except Exception as e:
        import traceback
        error_detail = f"Fel vid laddning av filer: {str(e)}"
        full_traceback = traceback.format_exc()
        raise HTTPException(status_code=500, detail=f"Fel vid laddning av filer: {str(e)} | Traceback: {full_traceback}")

@app.post("/generate-report", response_model=ReportResponse)
async def generate_report(
    request: ReportRequest,
    background_tasks: BackgroundTasks
):
    """
    Genererar årsredovisning baserat på .SE-fil och användarinput
    """
    try:
        # Generera rapport
        report_data = await report_generator.generate_full_report(request)
        
        # Spara till Supabase (i bakgrunden)
        background_tasks.add_task(
            supabase_service.save_report,
            request.user_id,
            report_data
        )
        
        return ReportResponse(
            success=True,
            report_id=report_data["report_id"],
            download_url=f"/download-report/{report_data['report_id']}",
            message="Rapport genererad framgångsrikt!"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fel vid generering av rapport: {str(e)}")

@app.get("/download-report/{report_id}")
async def download_report(report_id: str):
    """
    Laddar ner genererad PDF-rapport
    """
    try:
        file_path = report_generator.get_report_path(report_id)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Rapport hittades inte")
        
        return FileResponse(
            path=file_path,
            filename=f"arsredovisning_{report_id}.pdf",
            media_type="application/pdf"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fel vid nedladdning: {str(e)}")

@app.get("/user-reports/{user_id}")
async def get_user_reports(user_id: str):
    """
    Hämtar användarens tidigare rapporter
    """
    try:
        reports = await supabase_service.get_user_reports(user_id)
        return {"reports": reports}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fel vid hämtning av rapporter: {str(e)}")

@app.get("/company-info/{organization_number}")
async def get_company_info(organization_number: str):
    """
    Hämtar företagsinformation från Allabolag.se
    """
    try:
        company_info = await report_generator.scrape_company_info(organization_number)
        return company_info
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fel vid hämtning av företagsinfo: {str(e)}")

@app.get("/api/bolagsverket/officers/{organization_number}")
async def get_bolagsverket_officers(organization_number: str):
    """
    Fetch company officers from Bolagsverket for pre-filling Signering module
    Returns formatted officer data ready for the signing interface
    """
    try:
        from services.bolagsverket_service import BolagsverketService
        from services.bolagsverket_officers_extractor import extract_officers_for_signing
        
        # Initialize service and fetch company info
        service = BolagsverketService()
        company_info = await service.get_company_info(organization_number)
        
        if not company_info:
            return {
                "success": False,
                "message": "No company information found",
                "officers": {
                    "UnderskriftForetradare": [],
                    "UnderskriftAvRevisor": []
                }
            }
        
        # Extract and format officers
        officers_data = extract_officers_for_signing(company_info)
        
        return {
            "success": True,
            "message": f"Found {len(officers_data['UnderskriftForetradare'])} företrädare and {len(officers_data['UnderskriftAvRevisor'])} revisorer",
            "officers": officers_data
        }
        
    except Exception as e:
        logger.error(f"Error fetching Bolagsverket officers: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Fel vid hämtning av företagsinformation från Bolagsverket: {str(e)}"
        )

@app.post("/update-formula/{row_id}")
async def update_formula(row_id: int, formula: str):
    """
    Updates calculation formula for a specific row in the database
    """
    try:
        parser = DatabaseParser()
        success = parser.update_calculation_formula(row_id, formula)
        
        if success:
            return {"success": True, "message": f"Formula updated for row {row_id}"}
        else:
            raise HTTPException(status_code=500, detail="Failed to update formula")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating formula: {str(e)}")

@app.post("/test-parser", response_model=dict)
async def test_parser(file: UploadFile = File(...)):
    """
    Test endpoint for the new database-driven parser
    """
    print(f"Received file: {file.filename}, size: {file.size if hasattr(file, 'size') else 'unknown'}")
    
    if not file.filename.lower().endswith('.se'):
        raise HTTPException(status_code=400, detail=f"Endast .SE-filer accepteras. Fick: {file.filename}")
    
    try:
        # Skapa temporär fil
        with tempfile.NamedTemporaryFile(delete=False, suffix='.se') as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_path = temp_file.name
        
        print(f"Created temp file: {temp_path}")
        
        # Read SE file content - try different encodings
        se_content = None
        encodings_to_try = ['iso-8859-1', 'windows-1252', 'utf-8', 'cp1252']
        
        for encoding in encodings_to_try:
            try:
                with open(temp_path, 'r', encoding=encoding) as f:
                    se_content = f.read()
                print(f"Successfully read file with {encoding} encoding")
                break
            except UnicodeDecodeError as e:
                print(f"Failed to read with {encoding} encoding: {e}")
                continue
        
        if se_content is None:
            raise Exception("Could not read file with any supported encoding")
        
        print(f"Read {len(se_content)} characters from file")
        
        # Initialize parser
        parser = DatabaseParser()
        
        # Parse data
        current_accounts, previous_accounts, current_ib_accounts, previous_ib_accounts = parser.parse_account_balances(se_content)
        company_info = parser.extract_company_info(se_content)
        
        # Scrape additional company information from rating.se
        scraped_company_data = {}
        try:

            scraped_company_data = get_company_info_with_search(
                orgnr=company_info.get('organization_number'),
                company_name=company_info.get('company_name')
            )

            

        except Exception as e:

            scraped_company_data = {"error": str(e)}
        
        rr_data = parser.parse_rr_data(current_accounts, previous_accounts)
        # Use koncern-aware BR parsing for automatic reconciliation with K2 notes
        br_data = parser.parse_br_data_with_koncern(se_content, current_accounts, previous_accounts, rr_data)
        
        print(f"Parsed {len(current_accounts)} current year accounts, {len(previous_accounts)} previous year accounts")
        print(f"Generated {len(rr_data)} RR items, {len(br_data)} BR items")
        
        # Store financial data in database (but don't fail if storage fails)
        stored_ids = {}
        if company_info.get('organization_number'):
            company_id = company_info['organization_number']
            fiscal_year = company_info.get('fiscal_year', datetime.now().year)
            
            try:
                # Store the parsed financial data
                stored_ids = parser.store_financial_data(company_id, fiscal_year, rr_data, br_data)

            except Exception as e:

                stored_ids = {}
        
        # Rensa upp temporär fil
        os.unlink(temp_path)
        
        return {
            "success": True,
            "company_info": company_info,
            "scraped_company_data": scraped_company_data,  # Add scraped company data
            "current_accounts_count": len(current_accounts),
            "previous_accounts_count": len(previous_accounts),
            "current_accounts_sample": dict(list(current_accounts.items())[:10]),  # First 10 current accounts
            "previous_accounts_sample": dict(list(previous_accounts.items())[:10]),  # First 10 previous accounts
            "rr_count": len(rr_data),
            "rr_sample": rr_data[:5],  # First 5 RR items
            "br_count": len(br_data),
            "br_sample": br_data[:5],  # First 5 BR items
            "message": "Parser test completed successfully"
        }
        
    except Exception as e:
        print(f"Error in test_parser: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fel vid parser test: {str(e)}")

@app.get("/financial-data/{company_id}/{fiscal_year}")
async def get_financial_data(company_id: str, fiscal_year: int):
    """
    Retrieve stored financial data for a specific company and fiscal year
    """
    try:
        parser = DatabaseParser()
        data = parser.get_financial_data(company_id, fiscal_year)
        
        return {
            "success": True,
            "company_id": company_id,
            "fiscal_year": fiscal_year,
            "data": data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving financial data: {str(e)}")

@app.get("/financial-data/companies")
async def list_companies_with_data():
    """
    List all companies that have financial data stored
    """
    try:
        result = supabase.table('financial_data').select('company_id, fiscal_year, report_type').execute()
        
        # Group by company
        companies = {}
        for record in result.data:
            company_id = record['company_id']
            if company_id not in companies:
                companies[company_id] = []
            companies[company_id].append({
                'fiscal_year': record['fiscal_year'],
                'report_type': record['report_type']
            })
        
        return {
            "success": True,
            "companies": companies
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing companies: {str(e)}")



@app.get("/api/database/tables/{table_name}")
async def read_database_table(table_name: str, columns: str = "*", order_by: str = None):
    """
    Read data from a database table
    """
    try:
        data = db.read_table(table_name, columns=columns, order_by=order_by)
        return {
            "success": True,
            "table": table_name,
            "count": len(data),
            "data": data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading table {table_name}: {str(e)}")

@app.post("/api/database/tables/{table_name}")
async def write_database_table(table_name: str, data: dict):
    """
    Insert data into a database table
    """
    try:
        rows = data.get('rows', [])
        success = db.write_table(table_name, rows)
        return {
            "success": success,
            "table": table_name,
            "inserted": len(rows) if success else 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error writing to table {table_name}: {str(e)}")

@app.get("/api/database/ink2-mappings")
async def get_ink2_mappings():
    """
    Get all INK2 variable mappings
    """
    try:
        mappings = db.get_ink2_mappings()
        return {
            "success": True,
            "count": len(mappings),
            "data": mappings
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting INK2 mappings: {str(e)}")

@app.get("/api/database/check-sarskild-loneskatt")
async def check_sarskild_loneskatt():
    """
    Check if INK_sarskild_loneskatt mapping exists
    """
    try:
        exists = db.check_ink_sarskild_loneskatt_exists()
        mapping = db.get_ink_sarskild_loneskatt_mapping() if exists else None
        return {
            "success": True,
            "exists": exists,
            "mapping": mapping
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking sarskild loneskatt: {str(e)}")

@app.post("/api/database/add-sarskild-loneskatt")
async def add_sarskild_loneskatt_mapping():
    """
    Add INK_sarskild_loneskatt mapping if it doesn't exist
    """
    try:
        # Check if it already exists
        if db.check_ink_sarskild_loneskatt_exists():
            return {
                "success": True,
                "message": "INK_sarskild_loneskatt mapping already exists",
                "created": False
            }
        
        # Add the mapping
        success = db.add_ink2_mapping(
            variable_name='INK_sarskild_loneskatt',
            row_title='Justering särskild löneskatt pensionspremier',
            accounts_included=None,
            calculation_formula='justering_sarskild_loneskatt',
            show_amount='TRUE',
            is_calculated='FALSE',
            always_show=None,  # Show only if amount != 0
            style='NORMAL',
            show_tag='FALSE',
            explainer='Justering av särskild löneskatt på pensionförsäkringspremier för att korrigera eventuella skillnader mellan bokfört och beräknat belopp.',
            block='INK4',
            header='FALSE'
        )
        
        return {
            "success": success,
            "message": "INK_sarskild_loneskatt mapping created" if success else "Failed to create mapping",
            "created": success
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding sarskild loneskatt mapping: {str(e)}")

class RecalculateRequest(BaseModel):
    current_accounts: dict
    fiscal_year: Optional[int] = None
    rr_data: List[dict]
    br_data: List[dict]
    manual_amounts: dict
    justering_sarskild_loneskatt: Optional[float] = 0.0
    ink4_14a_outnyttjat_underskott: Optional[float] = 0.0
    ink4_16_underskott_adjustment: Optional[float] = 0.0
    is_chat_injection: Optional[bool] = False

@app.get("/api/chat-flow/{step_number}")
async def get_chat_flow_step(step_number: int):
    """
    Get chat flow step by step number
    """
    try:
        supabase = get_supabase_client()
        
        if not supabase:
            # Return mock data for step 505 if Supabase is not available
            if step_number == 505:
                return {
                    "success": True,
                    "step_number": 505,
                    "block": "PAYMENT",
                    "question_text": "Genom att klicka på Betala kan du påbörja betalningen, så att vi därefter kan slutföra årsredovisingen för signering och digital inlämning till Bolagsverket.",
                    "question_icon": "👤",
                    "question_type": "options",
                    "options": [{
                        "option_order": 1,
                        "option_text": "Betala",
                        "option_value": "stripe_payment",
                        "next_step": 505,
                        "action_type": "external_redirect",
                        "action_data": {"url": "DYNAMIC_STRIPE_URL", "target": "_blank"}
                    }]
                }
            else:
                raise HTTPException(status_code=503, detail="Database service temporarily unavailable")
        
        # Query the chat_flow table with new structure
        result = supabase.table('chat_flow').select('*').eq('step_number', step_number).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Step not found")
        
        step_data = result.data[0]
        
        # Convert to new format with options array
        options = []
        
        # Add no_option if it exists
        if step_data.get('no_option_value'):
            options.append({
                "option_order": 0,
                "option_text": None,
                "option_value": step_data['no_option_value'],
                "next_step": step_data.get('no_option_next_step'),
                "action_type": step_data.get('no_option_action_type'),
                "action_data": step_data.get('no_option_action_data')
            })
        
        # Add regular options
        for i in range(1, 5):
            option_text = step_data.get(f'option{i}_text')
            option_value = step_data.get(f'option{i}_value')
            
            if option_text and option_value:
                options.append({
                    "option_order": i,
                    "option_text": option_text,
                    "option_value": option_value,
                    "next_step": step_data.get(f'option{i}_next_step'),
                    "action_type": step_data.get(f'option{i}_action_type'),
                    "action_data": step_data.get(f'option{i}_action_data')
                })
        
        # Return the step data with new structure
        return {
            "success": True,
            "step_number": step_data['step_number'],
            "block": step_data.get('block'),
            "question_text": step_data['question_text'],
            "question_icon": step_data.get('question_icon'),
            "question_type": step_data['question_type'],
            "input_type": step_data.get('input_type'),
            "input_placeholder": step_data.get('input_placeholder'),
            "show_conditions": step_data.get('show_conditions'),
            "options": options
        }
        
    except Exception as e:
        print(f"Error getting chat flow step: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting chat flow step: {str(e)}")

@app.get("/api/chat-flow/next/{current_step}")
async def get_next_chat_flow_step(current_step: int):
    """
    Get the next chat flow step in sequence
    """
    try:
        supabase = get_supabase_client()
        
        # Find the next step number greater than current_step
        result = supabase.table('chat_flow').select('step_number').gt('step_number', current_step).order('step_number').limit(1).execute()
        
        if not result.data:
            return {"success": True, "next_step": None}  # End of flow
        
        next_step = result.data[0]['step_number']
        return await get_chat_flow_step(next_step)
        
    except Exception as e:
        print(f"Error getting next chat flow step: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting next chat flow step: {str(e)}")

@app.post("/api/chat-flow/process-choice")
async def process_chat_choice(request: dict):
    """
    Process user choice and return next action
    """
    try:
        step_number = request.get("step_number")
        option_value = request.get("option_value")
        context = request.get("context", {})
        
        print(f"🔍 Processing choice: step={step_number}, option={option_value}, context={context}")
        
        # Get the current step to find the selected option
        step_data = await get_chat_flow_step(step_number)
        print(f"🔍 Step data for {step_number}: {step_data}")
        if not step_data or not step_data.get("success"):
            raise HTTPException(status_code=404, detail="Step not found")
        
        # Find the selected option
        selected_option = None
        print(f"🔍 Available options: {[opt['option_value'] for opt in step_data['options']]}")
        for option in step_data["options"]:
            if option["option_value"] == option_value:
                selected_option = option
                break
        
        print(f"🔍 Selected option: {selected_option}")
        if not selected_option:
            raise HTTPException(status_code=400, detail=f"Invalid option '{option_value}'. Available: {[opt['option_value'] for opt in step_data['options']]}")
        
        # Process variable substitution in the result
        result = {
            "action_type": selected_option["action_type"],
            "action_data": selected_option["action_data"],
            "next_step": selected_option["next_step"]
        }
        
        # Special handling for Stripe payment (step 505) - REMOVED
        # The frontend now handles embedded checkout via the /api/payments/create-embedded-checkout endpoint
        # This allows the frontend to choose between embedded and redirect modes
        
        # Apply variable substitution if context is provided
        if context:
            result = substitute_variables(result, context)
        
        return {"success": True, "result": result}
        
    except Exception as e:
        print(f"Error processing chat choice: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing chat choice: {str(e)}")

@app.post("/api/send-for-digital-signing")
async def send_for_digital_signing(request: dict):
    """
    Send annual report for digital signing with BankID
    """
    try:
        signering_data = request.get("signeringData", {})
        organization_number = request.get("organizationNumber")
        
        print(f"🖊️ Sending for digital signing: org={organization_number}")
        print(f"🖊️ Signering data: {signering_data}")
        
        # Extract företrädare (company representatives) data
        foretradare = signering_data.get("UnderskriftForetradare", [])
        revisor = signering_data.get("UnderskriftAvRevisor", [])
        
        print(f"📋 Found {len(foretradare)} företrädare and {len(revisor)} revisors")
        
        # TODO: Implement actual BankID integration
        # For now, return a success response
        
        # Log the signing request
        signing_summary = []
        for i, person in enumerate(foretradare):
            name = f"{person.get('UnderskriftHandlingTilltalsnamn', '')} {person.get('UnderskriftHandlingEfternamn', '')}"
            role = person.get('UnderskriftHandlingRoll', '')
            signing_summary.append(f"  {i+1}. {name} ({role})")
        
        for i, person in enumerate(revisor):
            name = f"{person.get('UnderskriftHandlingTilltalsnamn', '')} {person.get('UnderskriftHandlingEfternamn', '')}"
            title = person.get('UnderskriftHandlingTitel', '')
            is_main = person.get('UnderskriftRevisorspateckningRevisorHuvudansvarig', False)
            main_text = " - Huvudansvarig" if is_main else ""
            signing_summary.append(f"  R{i+1}. {name} ({title}){main_text}")
        
        print(f"📝 Sending signing invitations to:")
        for line in signing_summary:
            print(line)
        
        # Return success response
        return {
            "success": True,
            "message": "Signing invitations sent successfully",
            "signing_summary": signing_summary,
            "organization_number": organization_number
        }
        
    except Exception as e:
        print(f"Error sending for digital signing: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error sending for digital signing: {str(e)}")

def substitute_variables(data, context):
    """Replace {variable} placeholders with actual values"""
    import json
    data_str = json.dumps(data) if data else "{}"
    
    import re
    for key, value in context.items():
        placeholder = f"{{{key}}}"
        # Use regex to ensure exact placeholder match (though curly braces make this safer already)
        if isinstance(value, (int, float)):
            # Format numbers with Swedish locale
            formatted_value = f"{value:,.0f}".replace(',', ' ')
            data_str = re.sub(re.escape(placeholder), formatted_value, data_str)
        else:
            data_str = re.sub(re.escape(placeholder), str(value), data_str)
    
    return json.loads(data_str)

@app.post("/api/recalculate-ink2")
async def recalculate_ink2(request: RecalculateRequest):
    """
    Recalculate INK2 data with manual amounts and adjustments
    """
    try:
        parser = DatabaseParser()
        
        # Convert current_accounts to have float values
        current_accounts = {k: float(v) for k, v in request.current_accounts.items()}
        
        # Inject special adjustment values into manual_amounts
        manual_amounts = dict(request.manual_amounts)
        if request.ink4_14a_outnyttjat_underskott and request.ink4_14a_outnyttjat_underskott > 0:
            manual_amounts['INK4.14a'] = request.ink4_14a_outnyttjat_underskott
            print(f"🔥 Injecting INK4.14a unused tax loss: {request.ink4_14a_outnyttjat_underskott}")
        if request.ink4_16_underskott_adjustment and request.ink4_16_underskott_adjustment != 0:
            manual_amounts['ink4_16_underskott_adjustment'] = request.ink4_16_underskott_adjustment
            print(f"📊 Injecting ink4_16_underskott_adjustment: {request.ink4_16_underskott_adjustment}")
        if request.justering_sarskild_loneskatt and request.justering_sarskild_loneskatt != 0:
            manual_amounts['justering_sarskild_loneskatt'] = request.justering_sarskild_loneskatt
            print(f"💰 Injecting pension tax adjustment: {request.justering_sarskild_loneskatt}")
        
        # Preserve INK4.6d if it exists in manual_amounts (sticky value from original calculation)
        if 'INK4.6d' in request.manual_amounts:
            manual_amounts['INK4.6d'] = request.manual_amounts['INK4.6d']
            print(f"📋 Preserving INK4.6d återföring tax: {manual_amounts['INK4.6d']}")

        # STATELESS FIX: If SLP has already been booked to RR (after approval),
        # zero out the INK adjustment so it isn't counted twice in skattemässigt resultat
        # BUT: preserve SLP for chat injections (they need the full calculation)
        rr_252_has_slp = False
        if request.rr_data and not getattr(request, 'is_chat_injection', False):
            for rr_item in request.rr_data:
                if (str(rr_item.get("row_id")) == "252" or 
                    rr_item.get("variable_name") == "PersonalKostnader"):
                    if rr_item.get("slp_injected") or rr_item.get("__slp_applied"):
                        rr_252_has_slp = True
                        break
        
        if rr_252_has_slp:
            manual_amounts['justering_sarskild_loneskatt'] = 0.0
            print(f"🔄 SLP already booked to RR 252, zeroing INK adjustment to prevent double-counting")
        elif getattr(request, 'is_chat_injection', False):
            print(f"💬 Chat injection mode: preserving SLP in calculation")
        
        # Parse INK2 data with manual overrides
        ink2_data = parser.parse_ink2_data_with_overrides(
            current_accounts=current_accounts,
            fiscal_year=request.fiscal_year or datetime.now().year,
            rr_data=request.rr_data,
            br_data=request.br_data,
            manual_amounts=manual_amounts
        )
        
        # Fix Årets_resultat_justerat (row_id 78) formula
        try:
            def _find_amt(rows, name):
                for r in rows:
                    if r.get('variable_name') == name:
                        return float(r.get('amount') or 0)
                return 0.0

            # SumResultatForeSkatt is RR row_id 275 in your model (prefer row_id)
            rr_275 = next((x for x in request.rr_data or [] if str(x.get('row_id')) == '275'), None) \
                or next((x for x in request.rr_data or [] if str(x.get('id')) == '275'), None)
            sum_resultat_fore_skatt = float(rr_275.get('current_amount') or 0) if rr_275 else 0.0

            # SLP can come in as a manual override or dedicated field; both are positive by design
            slp = 0.0
            if hasattr(request, 'manual_amounts') and request.manual_amounts and isinstance(request.manual_amounts, dict):
                slp = abs(float(request.manual_amounts.get('justering_sarskild_loneskatt', 0) or 0))
            if hasattr(request, 'justering_sarskild_loneskatt') and request.justering_sarskild_loneskatt:
                slp = max(slp, abs(float(request.justering_sarskild_loneskatt or 0)))

            ink_beraknad = _find_amt(ink2_data, 'INK_beraknad_skatt')

            # If SLP already booked to RR, don't subtract again (RR 275 already includes SLP effect)
            if rr_252_has_slp:
                arets_resultat_justerat = sum_resultat_fore_skatt - ink_beraknad
                print(f"🔄 SLP already in RR 275, formula: {sum_resultat_fore_skatt} - {ink_beraknad}")
            else:
                # SLP lowers the result: Årets_resultat_justerat = SumResultatForeSkatt - SLP - INK_beraknad_skatt
                arets_resultat_justerat = sum_resultat_fore_skatt - slp - ink_beraknad
                print(f"🔧 SLP not yet in RR, formula: {sum_resultat_fore_skatt} - {slp} - {ink_beraknad}")

            # write back into ink2_data (update or append)
            wrote = False
            for r in ink2_data:
                if r.get('variable_name') == 'Arets_resultat_justerat':
                    r['amount'] = round(arets_resultat_justerat)
                    wrote = True
                    break
            if not wrote:
                ink2_data.append({
                    'variable_name': 'Arets_resultat_justerat',
                    'row_title': 'Årets resultat (justerat)',
                    'header': False, 'show_amount': True, 'always_show': True, 'is_calculated': True,
                    'amount': round(arets_resultat_justerat),
                })
            
            print(f"🔧 Fixed Årets_resultat_justerat: {arets_resultat_justerat} (SumResultatForeSkatt: {sum_resultat_fore_skatt} - SLP: {slp} - INK_beraknad: {ink_beraknad})")
        except Exception as e:
            print(f"⚠️ Warning: Could not fix Årets_resultat_justerat: {str(e)}")
            # Continue without failing the entire request
        
        return {
            "success": True,
            "ink2_data": ink2_data
        }
        
    except Exception as e:
        print(f"Error in recalculate_ink2: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error recalculating INK2: {str(e)}")

@app.post("/api/calculate-periodiseringsfonder")
async def calculate_periodiseringsfonder(request: dict):
    """
    Calculate periodiseringsfonder data from SE file accounts
    """
    try:
        supabase = get_supabase_client()
        current_accounts = request.get('current_accounts', {})
        
        # Get mapping data from database
        result = supabase.table('periodiseringsfond_mapping').select('*').order('row_id').execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Periodiseringsfond mapping not found")
        
        periodiseringsfonder_data = []
        calculated_values = {}
        
        # Process each row
        for row in result.data:
            item = {
                'variable_name': row['variable_name'],
                'row_title': row['row_title'],
                'header': row['header'],
                'always_show': row['always_show'],
                'show_amount': row['show_amount'],
                'is_calculated': row['is_calculated'],
                'amount': 0
            }
            
            if row['is_calculated'] and row['calculation_formula']:
                # Handle calculated fields (like Pfonder_sum and Schablonranta)
                formula = row['calculation_formula']
                
                if 'Pfonder_sum*statslaneranta' in formula:
                    # Calculate schablonranta (need statslaneranta from somewhere)
                    pfonder_sum = calculated_values.get('Pfonder_sum', 0)
                    statslaneranta = 0.016  # 1.6% - this should come from settings/config
                    item['amount'] = pfonder_sum * statslaneranta
                    calculated_values[row['variable_name']] = item['amount']
                elif '+' in formula:
                    # Sum formula like Pfonder_minus1+Pfonder_minus2+...
                    total = 0
                    for var_name in formula.split('+'):
                        var_name = var_name.strip()
                        total += calculated_values.get(var_name, 0)
                    item['amount'] = total
                    calculated_values[row['variable_name']] = item['amount']
                    
            elif row['accounts_included']:
                # Get account balance from SE file
                account_number = row['accounts_included']
                account_balance = current_accounts.get(account_number, 0)
                item['amount'] = float(account_balance)
                calculated_values[row['variable_name']] = item['amount']
            
            periodiseringsfonder_data.append(item)
        
        return {
            "success": True,
            "periodiseringsfonder_data": periodiseringsfonder_data
        }
        
    except Exception as e:
        print(f"Error calculating periodiseringsfonder: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error calculating periodiseringsfonder: {str(e)}")

# Förvaltningsberättelse endpoints

@app.get("/forvaltningsberattelse/template")
async def get_management_report_template():
    """
    Hämta mall för förvaltningsberättelse
    """
    try:
        template = bolagsverket_service.get_management_report_template()
        return {
            "success": True,
            "template": template,
            "message": "Template hämtad framgångsrikt"
        }
    except Exception as e:
        print(f"Error getting template: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/forvaltningsberattelse/validate", response_model=dict)
async def validate_management_report(management_report: ManagementReportData):
    """
    Validera förvaltningsberättelse data
    """
    try:
        validation_result = await bolagsverket_service.validate_management_report(
            management_report.dict()
        )
        
        return {
            "success": True,
            "validation_result": validation_result,
            "message": "Validation completed"
        }
    except Exception as e:
        print(f"Error validating management report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/bolagsverket/company/{org_number}", response_model=dict)
async def get_company_info_from_bolagsverket(org_number: str):
    """
    Hämta företagsinformation från Bolagsverket API
    """
    try:
        # Validate org number format (should be 10 digits)
        if not org_number.isdigit() or len(org_number) != 10:
            raise HTTPException(
                status_code=400, 
                detail="Organization number must be 10 digits"
            )
        
        company_info = await bolagsverket_service.get_company_info(org_number)
        
        if not company_info:
            raise HTTPException(
                status_code=404, 
                detail=f"No information found for organization {org_number}"
            )
        
        return {
            "success": True,
            "company_info": company_info,
            "message": "Företagsinformation hämtad från Bolagsverket"
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching company info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/bolagsverket/documents/{org_number}", response_model=dict)
async def get_company_documents_from_bolagsverket(org_number: str):
    """
    Hämta dokumentlista för företag från Bolagsverket API
    """
    try:
        # Validate org number format (should be 10 digits)
        if not org_number.isdigit() or len(org_number) != 10:
            raise HTTPException(
                status_code=400, 
                detail="Organization number must be 10 digits"
            )
        
        document_list = await bolagsverket_service.get_document_list(org_number)
        
        if document_list is None:
            raise HTTPException(
                status_code=404, 
                detail=f"No documents found for organization {org_number}"
            )
        
        return {
            "success": True,
            "document_list": document_list,
            "message": "Dokumentlista hämtad från Bolagsverket"
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching document list: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/bolagsverket/document/{document_id}", response_model=dict)
async def get_document_from_bolagsverket(document_id: str):
    """
    Hämta specifikt dokument från Bolagsverket API
    """
    try:
        document = await bolagsverket_service.get_document(document_id)
        
        if not document:
            raise HTTPException(
                status_code=404, 
                detail=f"Document {document_id} not found"
            )
        
        return {
            "success": True,
            "document": document,
            "message": "Dokument hämtat från Bolagsverket"
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/bolagsverket/health", response_model=dict)
async def check_bolagsverket_health():
    """
    Kontrollera hälsa för Bolagsverket API
    """
    try:
        is_healthy = await bolagsverket_service.check_api_health()
        
        return {
            "success": True,
            "healthy": is_healthy,
            "message": "Bolagsverket API health check completed"
        }
    except Exception as e:
        print(f"Error checking Bolagsverket health: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/forvaltningsberattelse/submit", response_model=ManagementReportResponse)
async def submit_management_report(report_request: ManagementReportRequest):
    """
    Skicka in förvaltningsberättelse till Bolagsverket
    """
    try:
        # First validate the management report
        validation_result = await bolagsverket_service.validate_management_report(
            report_request.management_report.dict()
        )
        
        if not validation_result["valid"]:
            return ManagementReportResponse(
                success=False,
                validation_result=validation_result,
                message="Validation failed. Please correct the errors before submitting."
            )
        
        # Prepare the complete annual report data structure
        annual_report_data = {
            "organizationNumber": report_request.organization_number,
            "companyName": report_request.company_name,
            "fiscalYear": report_request.fiscal_year,
            "managementReport": report_request.management_report.dict(),
            "submissionDate": datetime.now().isoformat()
        }
        
        # Submit to Bolagsverket
        submission_result = await bolagsverket_service.submit_annual_report(
            report_request.organization_number,
            annual_report_data
        )
        
        if submission_result:
            return ManagementReportResponse(
                success=True,
                validation_result=validation_result,
                submission_id=submission_result.get("submissionId"),
                message="Förvaltningsberättelse submitted successfully to Bolagsverket"
            )
        else:
            return ManagementReportResponse(
                success=False,
                validation_result=validation_result,
                message="Failed to submit to Bolagsverket. Please try again later."
            )
            
    except Exception as e:
        print(f"Error submitting management report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/add-note-numbers-to-br")
async def add_note_numbers_to_br(request: dict):
    """
    Add note numbers to both BR and RR data based on mappings.
    Uses dynamic note numbering from frontend - only visible notes get numbers.
    
    Expected request format:
    {
        "br_data": [...],  # BR data array
        "rr_data": [...],  # RR data array (optional)
        "note_numbers": {  # Dynamic note numbers from frontend (only for visible notes)
            "BYGG": 3,
            "KONCERN": 5,
            "NOT2": 2,  # Goes to RR Personalkostnader
            ...
        }
    }
    """
    try:
        br_data = request.get('br_data', [])
        rr_data = request.get('rr_data', [])
        note_numbers = request.get('note_numbers', {})
        
        if not br_data and not rr_data:
            raise HTTPException(status_code=400, detail="Either br_data or rr_data is required")
        
        # Initialize parser and add note numbers to both BR and RR
        parser = DatabaseParser()
        
        # If only BR data provided, use old function for backward compatibility
        if br_data and not rr_data:
            updated_br_data = parser.add_note_numbers_to_br_data(br_data, note_numbers)
            return {
                "success": True,
                "br_data": updated_br_data
            }
        
        # Use new function that handles both BR and RR
        result = parser.add_note_numbers_to_financial_data(br_data, rr_data, note_numbers)
        
        return {
            "success": True,
            "br_data": result['br_data'],
            "rr_data": result['rr_data']
        }
        
    except Exception as e:
        print(f"Error adding note numbers to financial data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

class TaxUpdateRequest(BaseModel):
    inkBeraknadSkatt: float
    inkBokfordSkatt: float
    taxDifference: float
    rr_data: List[dict]
    br_data: List[dict]
    organizationNumber: Optional[str] = None
    fiscalYear: Optional[int] = None
    # NEW: accepted SLP (Särskild löneskatt). Pass 0 or omit if not accepted/entered.
    inkSarskildLoneskatt: Optional[float] = 0.0

@app.get("/api/test-tax-endpoint")
async def test_tax_endpoint():
    """Test endpoint to verify deployment is working"""
    return {"success": True, "message": "Tax endpoint is available", "timestamp": datetime.now().isoformat()}

@app.post("/api/update-tax-in-financial-data")
async def update_tax_in_financial_data(request: TaxUpdateRequest):
    """
    Update RR and BR data when tax calculations change.
    
    When INK_beraknad_skatt != INK_bokford_skatt:
    1. Update RR row_id 277 "Skatt på årets resultat" (SkattAretsResultat) = INK_beraknad_skatt
    2. Recalculate RR row_id 279 "Årets resultat" (SumAretsResultat)
    3. Update BR row_id 380 "Årets resultat" (AretsResultat) = new SumAretsResultat
    4. Update BR row_id 413 "Skatteskulder" = Skatteskulder + (INK_beraknad_skatt - INK_bokford_skatt)
    """
    print(
        f"🚀 Tax update endpoint called with: "
        f"inkBeraknadSkatt={request.inkBeraknadSkatt}, "
        f"inkBokfordSkatt={request.inkBokfordSkatt}, "
        f"inkSarskildLoneskatt={getattr(request, 'inkSarskildLoneskatt', None)}"
    )
    try:
        # Helper functions for robust data manipulation
        def _eq(a, b):
            return str(a) == str(b)

        def _get(items, *, row_id=None, id=None, name=None, label_contains=None):
            # 1) Prefer canonical row_id
            if row_id is not None:
                for x in items:
                    if _eq(x.get("row_id"), row_id):
                        return x
            # 2) Fallback to legacy id
            if id is not None:
                for x in items:
                    if _eq(x.get("id"), id):
                        return x
            # 3) Exact variable_name match
            if name is not None:
                for x in items:
                    if str(x.get("variable_name")) == name:
                        return x
            # 4) Best-effort label contains
            if label_contains:
                lc = label_contains.lower()
                for x in items:
                    if lc in str(x.get("label", "")).lower():
                        return x
            return None

        def _num(v):
            try:
                return float(v or 0)
            except Exception:
                return 0.0

        def _delta_set(item, new_val):
            old = float(item.get("current_amount") or 0)
            item["current_amount"] = float(new_val)
            return float(new_val) - old

        def _add(item, add_val):
            old = float(item.get("current_amount") or 0)
            item["current_amount"] = old + float(add_val)
            return float(item["current_amount"]) - old  # == add_val

        def _set(item, new_val):
            old = float(item.get("current_amount") or 0)
            item["current_amount"] = float(new_val)
            return float(item["current_amount"]) - old  # delta

        # Current-amount-only helpers (explicit names for clarity)
        def _set_current(item, new_val: float):
            return _set(item, new_val)

        def _add_current(item, add_val: float):
            return _add(item, add_val)

        def _find_rr_personalkostnader(rr_items: list):
            # 1) variable_name exact
            for x in rr_items:
                if (x.get("variable_name") or "") == "PersonalKostnader":
                    return x
            # 2) label exact (Swedish)
            for x in rr_items:
                if (x.get("label") or "") == "Personalkostnader":
                    return x
            # 3) row_id = 252
            for x in rr_items:
                if str(x.get("row_id")) == "252":
                    return x
            # 4) id = 13 (canonical) or sometimes 252 (seen in payloads)
            for candidate in ("13", "252"):
                for x in rr_items:
                    if str(x.get("id")) == candidate:
                        return x
            return None

        def _find_by_row_id(rr_items: list, rid: int, *, varname: str = None, label: str = None):
            if varname:
                for x in rr_items:
                    if (x.get("variable_name") or "") == varname:
                        return x
            if label:
                for x in rr_items:
                    if (x.get("label") or "") == label:
                        return x
            for x in rr_items:
                if str(x.get("row_id")) == str(rid):
                    return x
            return None

        # --- inputs from request ---
        ink_calc = float(abs(request.inkBeraknadSkatt or 0))     # INK_beraknad_skatt (always +)
        ink_booked = float(request.inkBokfordSkatt or 0)         # INK_bokford_skatt (may be 0)
        tax_diff = ink_calc - ink_booked                         # used for BR 413

        rr = [dict(item) for item in request.rr_data] or []
        br = [dict(item) for item in request.br_data] or []

        # ------------------------------
        # 1) APPLY SÄRSKILD LÖNESKATT TO RR
        # ------------------------------
        slp_raw = float(request.inkSarskildLoneskatt or 0.0)
        slp_accepted = abs(slp_raw)  # backend expects +SLP always
        d_slp = 0.0
        print(f"🧾 SLP accepted (positive): {slp_accepted}; rr items: {len(rr)}; br items: {len(br)}")

        if slp_accepted > 0:
            rr_personal = _find_rr_personalkostnader(rr)
            if not rr_personal:
                print("WARN: RR PersonalKostnader not found by var/label/row_id/id.")
            else:
                # Establish stable base once (idempotent across calls). Support both legacy and new base keys.
                already = _num(rr_personal.get("slp_injected"))
                if "__base_personalkostnader" not in rr_personal and "_base_personalkostnader" in rr_personal:
                    rr_personal["__base_personalkostnader"] = _num(rr_personal.get("_base_personalkostnader"))
                if "__base_personalkostnader" not in rr_personal:
                    rr_personal["__base_personalkostnader"] = _num(rr_personal.get("current_amount")) - already

                base = _num(rr_personal.get("__base_personalkostnader"))

                before = _num(rr_personal.get("current_amount"))
                new_rr252 = base - slp_accepted
                delta_rr252 = _set_current(rr_personal, new_rr252)
                after = _num(rr_personal.get("current_amount"))
                rr_personal["slp_injected"] = slp_accepted
                print(f"RR 252 Personalkostnader: {before} -> {after} (base {base}, SLP {slp_accepted}, delta {delta_rr252})")

                # Ripple only by the applied magnitude
                applied_slp = abs(delta_rr252)
                if applied_slp > 0:
                    def row(rr_list, rid, var=None, label=None):
                        for r in rr_list:
                            if str(r.get("row_id")) == str(rid):
                                return r
                        if var:    # fallbacks if row_id differs in some files
                            for r in rr_list:
                                if r.get("variable_name") == var:
                                    return r
                        if label:
                            for r in rr_list:
                                if label.lower() in (r.get("label","").lower()):
                                    return r
                        return None

                    def add(r, d):
                        if not r:
                            return 0.0
                        cur = _num(r.get("current_amount"))
                        r["current_amount"] = cur + float(d)
                        return float(d)

                    # --- SLP booked as extra cost ---
                    # sums must move in the SAME direction as the cost (down)
                    add(row(rr, 256, var="SumRorelsekostnader", label="Summa rörelsekostnader"), -applied_slp)

                    # SumRorelseresultat must DECREASE by the cost
                    add(row(rr, 257, var="SumRorelseresultat", label="Summa rörelseresultat"), -applied_slp)

                    # Rörelseresultat must DECREASE by the cost
                    add(row(rr, 260, var="Rorelseresultat", label="Rörelseresultat"), -applied_slp)

                    # Keep existing ripples (down) for these:
                    add(row(rr, 267, var="SumResultatEfterFinansiellaPoster", label="Resultat efter finansiella poster"), -applied_slp)
                    add(row(rr, 275, var="SumResultatForeSkatt", label="Resultat före skatt"), -applied_slp)
                    add(row(rr, 279, var="SumAretsResultat", label="Årets resultat"), -applied_slp)

        # ------------------------------
        # 2) (existing) CORPORATE TAX LOGIC
        #     - set RR 277 to NEGATIVE inkBeraknadSkatt
        #     - adjust RR 279 by delta of tax
        # ------------------------------
        
        # --- RR: set tax NEGATIVE and ripple to Årets resultat ---
        rr_tax = _find_by_row_id(rr, 277, varname="SkattAretsResultat", label="Skatt på årets resultat")
        if not rr_tax:
            raise HTTPException(400, "RR row 277 (SkattAretsResultat) missing")

        rr_tax_new = -ink_calc  # << negative in RR
        d_rr_tax = _delta_set(rr_tax, rr_tax_new)
        # Derive previous calculated tax (absolute) to compute deltas idempotently
        rr_tax_old = rr_tax_new - d_rr_tax
        prev_calc = abs(rr_tax_old)
        d_calc = ink_calc - prev_calc
        print(f"Updated RR SkattAretsResultat: prev={rr_tax_old} new={rr_tax_new} (delta={d_rr_tax})")

        rr_result = _find_by_row_id(rr, 279, varname="SumAretsResultat", label="Årets resultat")
        if not rr_result:
            raise HTTPException(400, "RR row 279 (SumAretsResultat) missing")

        # Safe delta update for RR 279 (only tax changed at this step):
        rr_result_new = float(rr_result.get("current_amount") or 0) + d_rr_tax
        _ = _delta_set(rr_result, rr_result_new)
        print(f"Updated RR SumAretsResultat by tax delta: +{d_rr_tax}; new={rr_result_new}")

        # --- BR: sync Årets resultat (380) to RR result, update equity sums ---
        br_result = _get(br, id=380) or _get(br, name="AretsResultat")
        if not br_result:
            raise HTTPException(400, "BR row 380 (AretsResultat) missing")

        d_br_result = _delta_set(br_result, rr_result_new)  # returns delta vs old
        print(f"Updated BR AretsResultat: {br_result.get('current_amount', 0)} -> {rr_result_new}")

        # Note: Let 381/382/417 be recomputed by your BR formula pass; avoid accumulating here

        # --- BR: update Skatteskulder (413) by the tax DIFF, then roll up short-term debts (416) ---
        br_tax_liab = _get(br, id=413) or _get(br, name="Skatteskulder")
        if not br_tax_liab:
            raise HTTPException(400, "BR row 413 (Skatteskulder) missing")

        # Idempotent liabilities update: apply only the change in calculated tax
        d_tax_liab = _add(br_tax_liab, d_calc)
        print(f"Updated BR Skatteskulder by tax delta: +{d_calc}; total={br_tax_liab.get('current_amount', 0)}")

        br_sum_short = _get(br, id=416) or _get(br, name="SumKortfristigaSkulder")
        if br_sum_short:
            _add(br_sum_short, d_tax_liab)
            print(f"Updated BR SumKortfristigaSkulder by tax delta: +{d_tax_liab}")

        # --- BR: total liabilities + equity (417). Recalculate conservatively via deltas. ---
        # Avoid accumulating 417 here; let BR recompute totals downstream if needed

        # return updated arrays
        return {
            "success": True,
            "message": "Successfully updated RR and BR data with tax changes",
            "rr_data": rr,
            "br_data": br,
            "changes": {
                "slp_accepted": slp_accepted,
                "slp_delta": d_slp,
                "rr_tax_neg": rr_tax_new,
                "rr_delta_tax": d_rr_tax,
                "rr_sum_arets_resultat": rr_result_new,
                "br_delta_arets_resultat": d_br_result,
                "br_delta_skatteskulder": d_tax_liab,
            }
        }
        
    except Exception as e:
        print(f"Error updating tax in financial data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating tax in financial data: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    import os
    
    # Get port from environment variable (Railway sets this)
    port = int(os.environ.get("PORT", 8080))
    
    uvicorn.run(app, host="0.0.0.0", port=port) 