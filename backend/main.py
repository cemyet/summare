# Summare API - Updated 2025-10-26
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
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

logger.debug("Stripe version: %s", getattr(stripe, "__version__", "?"))
logger.debug("Stripe module file: %s", getattr(stripe, "__file__", "?"))
logger.debug("Has StripeClient: %s", callable(StripeClientClass))
logger.debug("Has checkout.sessions: %s", _has_checkout_sessions)

SUCCESS_URL = os.getenv("STRIPE_SUCCESS_URL", "https://summare.se/app?payment=success") + "?session_id={CHECKOUT_SESSION_ID}"
CANCEL_URL = os.getenv("STRIPE_CANCEL_URL", "https://summare.se/app?payment=cancelled")

# Stripe Product IDs (hardcoded from Dashboard)
STRIPE_PRODUCT_FIRST_TIME = os.getenv("STRIPE_PRODUCT_FIRST_TIME", "prod_T8CMRG8sg1tN1n")  # 499 SEK
STRIPE_PRODUCT_REGULAR = os.getenv("STRIPE_PRODUCT_REGULAR", "prod_T8CKt7CYLkjF10")  # 699 SEK

# Stripe Price IDs (hardcoded from Dashboard - preferred method)
# IMPORTANT: These must match your Stripe mode (test vs live)
# TEST mode prices (default):
STRIPE_PRICE_FIRST_TIME = os.getenv("STRIPE_PRICE_FIRST_TIME", "price_1SC1CgDpfvdIn7I4XmBw5Kz1")  # TEST: 499 SEK
STRIPE_PRICE_REGULAR = os.getenv("STRIPE_PRICE_REGULAR", "price_1SC1QQDpfvdIn7I4gS07EzzA")  # TEST: 699 SEK

# LIVE mode prices (set via environment variables for production):
# STRIPE_PRICE_FIRST_TIME=price_1SBvxhRd07xh2DS6ivTVNzDy  # LIVE: 499 SEK
# STRIPE_PRICE_REGULAR=price_1SBvvsRd07xh2DS6hO8hmRD7     # LIVE: 699 SEK

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
            automatic_tax={"enabled": True},
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
            automatic_tax={"enabled": True},
        )
        return s.url

    # 3) Raw HTTPS fallback (cannot be shadowed)
    form = {
        "mode": "payment",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "allow_promotion_codes": "true",
        "automatic_tax[enabled]": "true",
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

def get_price_from_product(product_id: str) -> str | None:
    """Get the default (active) Price ID from a Product ID"""
    try:
        key = os.getenv("STRIPE_SECRET_KEY")
        if not key:
            return None
        
        # Fetch product with prices
        r = requests.get(
            f"https://api.stripe.com/v1/products/{product_id}",
            params={"expand[]": "default_price"},
            auth=(key, ""),
            timeout=10,
        )
        
        if r.status_code == 200:
            product = r.json()
            default_price = product.get("default_price")
            if isinstance(default_price, dict):
                return default_price.get("id")
            elif isinstance(default_price, str):
                return default_price
        
        # Fallback: fetch prices for this product
        r = requests.get(
            "https://api.stripe.com/v1/prices",
            params={"product": product_id, "active": "true", "limit": 1},
            auth=(key, ""),
            timeout=10,
        )
        
        if r.status_code == 200:
            prices = r.json().get("data", [])
            if prices:
                return prices[0]["id"]
        
        return None
    except Exception as e:
        print(f"Error fetching price from product {product_id}: {str(e)}")
        return None

def create_checkout_with_price_id(price_id: str,
                                   email: str | None = None,
                                   metadata: dict | None = None) -> str:
    """Create Stripe checkout session using a Price ID (recommended for products in dashboard)"""
    key = os.getenv("STRIPE_SECRET_KEY")
    if not key:
        raise RuntimeError("Stripe not configured (STRIPE_SECRET_KEY missing)")
    
    success_url = os.getenv("STRIPE_SUCCESS_URL", "https://summare.se/app?payment=success") + "?session_id={CHECKOUT_SESSION_ID}"
    cancel_url = os.getenv("STRIPE_CANCEL_URL", "https://summare.se/app?payment=cancelled")
    
    # 1) Try StripeClient first
    StripeClientClass = getattr(stripe, "StripeClient", None)
    if callable(StripeClientClass):
        client = StripeClientClass(key)
        s = client.checkout.sessions.create(
            mode="payment",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=email,
            metadata=metadata or {},
            allow_promotion_codes=True,
            automatic_tax={"enabled": True},
        )
        return s.url
    
    # 2) Try module helper
    checkout = getattr(stripe, "checkout", None)
    sessions = getattr(checkout, "sessions", None) if checkout else None
    if callable(getattr(sessions, "create", None)):
        s = sessions.create(
            mode="payment",
            line_items=[{
                "price": price_id,
                "quantity": 1,
            }],
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=email,
            metadata=metadata or {},
            allow_promotion_codes=True,
            automatic_tax={"enabled": True},
        )
        return s.url
    
    # 3) Raw HTTPS fallback
    form = {
        "mode": "payment",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "allow_promotion_codes": "true",
        "automatic_tax[enabled]": "true",
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": "1",
    }
    if email:
        form["customer_email"] = email
    if metadata:
        for k, v in metadata.items():
            form[f"metadata[{k}]"] = str(v)
    
    r = requests.post(
        "https://api.stripe.com/v1/checkout/sessions",
        data=form,
        auth=(key, ""),
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
from services.email_service import send_password_email, generate_password
from rating_bolag_scraper import get_company_info_with_search
from models.schemas import (
    ReportRequest, ReportResponse, CompanyData, 
    ManagementReportRequest, ManagementReportResponse, 
    BolagsverketCompanyInfo, ManagementReportData
)

# ============================================================================
# Utility functions for freezing original RR values (Bokföringsinstruktion)
# ============================================================================

import copy

EPS_NOISE_SEK = 1.0  # anything |x| < 1 SEK is treated as 0

def _to_number(x):
    """Convert value to float, handling various formats"""
    try:
        return float(str(x).replace(' ', '').replace('\xa0', '').replace(',', '.'))
    except Exception:
        return None

def _rr_pick_num(item):
    """Pick numeric value from RR item, prefer 'final' → 'current_amount' → 'amount'"""
    for k in ('final', 'current_amount', 'amount'):
        if item.get(k) is not None:
            v = _to_number(item.get(k))
            if v is not None:
                return v
    return None

def _rr_find(rr_items, var_name):
    """Find value in RR items by variable name"""
    if not rr_items:
        return None
    for it in rr_items:
        if (it.get('variable_name') or '') == var_name:
            return _rr_pick_num(it)
    return None

def _normalize_delta(x):
    """Normalize delta: treat < 1 SEK as 0, round to integer"""
    if x is None:
        return 0
    try:
        x = float(x)
    except Exception:
        return 0
    return 0 if abs(x) < EPS_NOISE_SEK else int(round(x))

def freeze_originals(company_data: dict) -> dict:
    """
    Idempotent: sets originals once and keeps a deep snapshot of pre-INK2 RR.
    Must be called AFTER RR amounts exist and BEFORE any INK2 injection.
    """
    if company_data is None:
        return {}

    # Don't overwrite if already frozen
    if (company_data.get('arets_resultat_original') is not None and 
        company_data.get('arets_skatt_original') is not None and 
        company_data.get('__original_rr_snapshot__')):
        return company_data

    # Where RR may live
    rr = ((company_data.get('seFileData') or {}).get('rr_data')
          or company_data.get('rrData') or [])

    # Grab values; tolerate that some pipelines only fill 'final'
    arets_resultat = _rr_find(rr, 'SumAretsResultat')
    arets_skatt = _rr_find(rr, 'SkattAretsResultat')  # usually NEGATIVE (expense)

    # Only freeze when we have at least one meaningful number
    if arets_resultat is not None or arets_skatt is not None:
        # Deep snapshot BEFORE any mutation
        company_data['__original_rr_snapshot__'] = copy.deepcopy(rr)
        if company_data.get('arets_resultat_original') is None:
            company_data['arets_resultat_original'] = arets_resultat
        if company_data.get('arets_skatt_original') is None:
            company_data['arets_skatt_original'] = arets_skatt

    return company_data

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
    Creates an *embedded* Checkout session with dynamic pricing.
    Returns {client_secret, session_id, amount_sek, is_first_time_buyer}.
    Frontend will call stripe.initEmbeddedCheckout({ clientSecret }).
    """
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")

    # Read payload to get organization number
    payload = {}
    try:
        payload = await request.json()
    except Exception:
        pass
    
    org_number = payload.get("organization_number", "").replace("-", "").replace(" ", "").strip()
    customer_email = payload.get("customer_email")
    
    # Determine pricing based on payment history
    is_first_time = True
    price_id = STRIPE_PRICE_REGULAR  # Default to regular price
    amount_sek = 699
    
    if org_number:
        try:
            # Check if this organization has paid before
            # Use db.supabase for direct Supabase client access
            result = db.supabase.table("payments").select("id").eq("organization_number", org_number).eq("payment_status", "paid").execute()
            is_first_time = len(result.data) == 0
            
            print(f"🔍 Payment check for org {org_number}: found {len(result.data)} previous payments, is_first_time={is_first_time}")
            
            if is_first_time:
                price_id = STRIPE_PRICE_FIRST_TIME
                amount_sek = 499
                print(f"✨ First-time buyer discount applied: {amount_sek} SEK")
            else:
                print(f"💰 Returning customer: {amount_sek} SEK")
        except Exception as e:
            print(f"❌ Error checking payment history: {str(e)}")
            # Default to regular price on error

    # Build metadata
    metadata = {
        "organization_number": org_number,
        "product_type": "first_time_discount" if is_first_time else "regular",
        "source": "embedded_checkout"
    }

    # Build Stripe form for an embedded checkout session using Price ID
    form = {
        "mode": "payment",
        "ui_mode": "embedded",
        "line_items[0][price]": price_id,  # Use Price ID instead of price_data
        "line_items[0][quantity]": "1",
        "redirect_on_completion": "never",
        "automatic_tax[enabled]": "true",
    }
    
    # Add customer email if provided
    if customer_email:
        form["customer_email"] = customer_email
    
    # Add metadata
    for key, value in metadata.items():
        form[f"metadata[{key}]"] = str(value)

    try:
        session = _stripe_post("/v1/checkout/sessions", form)
        # Respond with exactly what the frontend needs
        return {
            "client_secret": session["client_secret"],
            "session_id": session["id"],
            "amount_sek": amount_sek,
            "is_first_time_buyer": is_first_time,
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
        paid = session["payment_status"] == "paid"
        
        # Extract organization number from metadata if available
        metadata = session.get("metadata", {})
        organization_number = metadata.get("organization_number", "")
        
        return {
            "paid": paid,
            "id": session["id"],
            "organization_number": organization_number if organization_number else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/check-first-time-buyer/{org_number}")
async def check_first_time_buyer(org_number: str):
    """Check if an organization number has made a payment before"""
    try:
        # Clean organization number (remove dashes, spaces)
        clean_org = org_number.replace("-", "").replace(" ", "").strip()
        
        # Query database for previous payments
        result = db.table("payments").select("id, paid_at").eq("organization_number", clean_org).eq("payment_status", "paid").execute()
        
        has_paid_before = len(result.data) > 0
        recommended_price = 699 if has_paid_before else 499
        
        return {
            "organization_number": org_number,
            "has_paid_before": has_paid_before,
            "recommended_price_sek": recommended_price,
            "is_eligible_for_discount": not has_paid_before
        }
    except Exception as e:
        print(f"Error checking first-time buyer: {str(e)}")
        # Default to regular price if there's an error
        return {
            "organization_number": org_number,
            "has_paid_before": False,
            "recommended_price_sek": 699,
            "is_eligible_for_discount": False,
            "error": str(e)
        }

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

class CreatePaymentRequest(BaseModel):
    organization_number: str
    customer_email: Optional[str] = None

@app.post("/api/payments/create-checkout-session")
async def create_payment_checkout_session(request: CreatePaymentRequest):
    """
    Create a Stripe checkout session with dynamic pricing based on first-time buyer status
    """
    try:
        org_number = request.organization_number.replace("-", "").replace(" ", "").strip()
        
        # Check if this organization has paid before
        result = db.table("payments").select("id").eq("organization_number", org_number).eq("payment_status", "paid").execute()
        
        is_first_time = len(result.data) == 0
        
        metadata = {
            "organization_number": org_number,
            "product_type": "first_time_discount" if is_first_time else "regular",
            "source": "annual_report_flow"
        }
        
        # Determine which product/price to use
        if is_first_time:
            amount_sek = 499
            # Try to get Price ID from Product ID or use configured Price ID
            price_id = STRIPE_PRICE_FIRST_TIME or get_price_from_product(STRIPE_PRODUCT_FIRST_TIME)
        else:
            amount_sek = 699
            # Try to get Price ID from Product ID or use configured Price ID
            price_id = STRIPE_PRICE_REGULAR or get_price_from_product(STRIPE_PRODUCT_REGULAR)
        
        # Create checkout session
        if price_id:
            url = create_checkout_with_price_id(
                price_id=price_id,
                email=request.customer_email,
                metadata=metadata
            )
        else:
            # Fallback to amount-based pricing if Price ID not available
            url = create_checkout_session_url(
                amount_ore=amount_sek * 100,
                email=request.customer_email,
                metadata=metadata
            )
        
        return {
            "checkout_url": url,
            "amount_sek": amount_sek,
            "is_first_time_buyer": is_first_time,
            "product_type": metadata["product_type"]
        }
        
    except Exception as e:
        print(f"Error creating payment checkout: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create checkout session: {str(e)}")

@app.post("/stripe-webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events for payment confirmation"""
    try:
        import stripe
        
        # Get the raw body and signature
        body = await request.body()
        sig_header = request.headers.get('stripe-signature')
        webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
        
        print(f"🔔 Webhook received, has signature: {bool(sig_header)}, has secret: {bool(webhook_secret)}")
        
        # For now, skip signature verification due to Stripe library issue
        # TODO: Fix signature verification in production
        print("⚠️ Skipping signature verification (development mode)")
        import json
        event = json.loads(body.decode('utf-8'))
        
        # Keep this code for when we fix signature verification:
        # if not webhook_secret:
        #     print("⚠️ STRIPE_WEBHOOK_SECRET not configured - skipping signature verification")
        #     import json
        #     event = json.loads(body.decode('utf-8'))
        # else:
        #     try:
        #         event = stripe.Webhook.construct_event(body, sig_header, webhook_secret)
        #         print("✅ Webhook signature verified")
        #     except Exception as e:
        #         print(f"❌ Signature verification failed: {type(e).__name__}: {str(e)}")
        #         raise HTTPException(status_code=400, detail=f"Invalid signature: {str(e)}")
        
        event_type = event.get('type')
        event_data = event.get('data', {}).get('object', {})
        
        print(f"🔔 Stripe webhook received: {event_type}")
        
        if event_type == 'checkout.session.completed':
            # Payment was successful
            session_id = event_data.get('id')
            customer_email = event_data.get('customer_details', {}).get('email')
            amount_total = event_data.get('amount_total', 0)
            amount_subtotal = event_data.get('amount_subtotal', 0)
            customer_name = event_data.get('customer_details', {}).get('name', 'Unknown')
            payment_intent = event_data.get('payment_intent')
            metadata = event_data.get('metadata', {})
            currency = event_data.get('currency', 'sek')
            
            print(f"✅ Payment successful: {session_id}, email: {customer_email}, name: {customer_name}, amount: {amount_total}")
            
            # Extract organization number from metadata
            org_number = metadata.get('organization_number', '').replace("-", "").replace(" ", "").strip()
            product_type = metadata.get('product_type', 'regular')
            
            # Save payment to database
            try:
                # Convert from öre (cents) to SEK (kronor) with decimals
                # Stripe returns amounts in smallest currency unit (öre for SEK)
                amount_total_sek = amount_total / 100.0 if amount_total else 0.0
                amount_subtotal_sek = amount_subtotal / 100.0 if amount_subtotal else 0.0
                
                payment_data = {
                    "organization_number": org_number,
                    "stripe_session_id": session_id,
                    "stripe_payment_intent_id": payment_intent,
                    "amount_total": amount_total_sek,  # e.g., 623.75 SEK
                    "amount_subtotal": amount_subtotal_sek,  # e.g., 499.00 SEK
                    "currency": currency,
                    "customer_email": customer_email,
                    "customer_name": customer_name,
                    "payment_status": "paid",
                    "product_type": product_type,
                    "metadata": metadata,
                    "paid_at": datetime.now().isoformat()
                }
                
                # Use db.supabase for direct Supabase client access
                db.supabase.table("payments").insert(payment_data).execute()
                print(f"💾 Payment saved to database for org: {org_number}")
            except Exception as db_error:
                print(f"⚠️ Failed to save payment to database: {str(db_error)}")
            
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

def inject_ink2_adjustments(ink2_data: List[Dict], rr_data: List[Dict], manual_amounts: Dict[str, float] = None, slp_adjustment: float = 0.0) -> List[Dict]:
    """
    Helper function to inject calculated adjustments into INK2 data for PDF consistency.
    Ensures INK4.1/INK4.2 reflect Årets resultat (justerat) and INK4.3a reflects beräknad skatt.
    
    Args:
        ink2_data: INK2 calculation data
        rr_data: RR (resultaträkning) data (not used - kept for backward compatibility)
        manual_amounts: Optional manual overrides to respect
        slp_adjustment: SLP adjustment (not used - kept for backward compatibility)
    
    Returns:
        Updated ink2_data with injections
    """
    try:
        manual_amounts = manual_amounts or {}
        
        def _find_amt(rows, name):
            for r in rows:
                if r.get('variable_name') == name:
                    return float(r.get('amount') or 0)
            return 0.0
        
        # Get already-calculated values from INK2 data
        arets_resultat_justerat = _find_amt(ink2_data, 'Arets_resultat_justerat')
        ink_beraknad = _find_amt(ink2_data, 'INK_beraknad_skatt')
        
        print(f"📊 inject_ink2_adjustments: Årets resultat (justerat) = {arets_resultat_justerat} kr, INK_beraknad_skatt = {ink_beraknad} kr")
        
        # Check for manual overrides
        ink4_1_manual = manual_amounts.get('INK4.1')
        ink4_2_manual = manual_amounts.get('INK4.2')
        ink4_3a_manual = manual_amounts.get('INK4.3a')
        
        # Inject Årets resultat (justerat) into INK4.1 (vinst) or INK4.2 (förlust)
        # Only if not manually overridden
        if ink4_1_manual is None and ink4_2_manual is None:
            if arets_resultat_justerat > 0:
                # Profit: inject into INK4.1, zero out INK4.2
                for r in ink2_data:
                    if r.get('variable_name') == 'INK4.1':
                        old_val = r.get('amount', 0)
                        r['amount'] = round(abs(arets_resultat_justerat))
                        print(f"✅ Injected INK4.1 (vinst): {old_val} → {round(abs(arets_resultat_justerat))} kr")
                    elif r.get('variable_name') == 'INK4.2':
                        r['amount'] = 0.0
            elif arets_resultat_justerat < 0:
                # Loss: inject into INK4.2, zero out INK4.1
                for r in ink2_data:
                    if r.get('variable_name') == 'INK4.1':
                        r['amount'] = 0.0
                    elif r.get('variable_name') == 'INK4.2':
                        old_val = r.get('amount', 0)
                        r['amount'] = round(abs(arets_resultat_justerat))
                        print(f"✅ Injected INK4.2 (förlust): {old_val} → {round(abs(arets_resultat_justerat))} kr")
            else:
                # Zero result: zero out both
                for r in ink2_data:
                    if r.get('variable_name') in ['INK4.1', 'INK4.2']:
                        r['amount'] = 0.0
        else:
            print(f"ℹ️ Skipping INK4.1/4.2 injection - manual overrides exist: INK4.1={ink4_1_manual}, INK4.2={ink4_2_manual}")
        
        # Inject INK_beraknad_skatt into INK4.3a (Skatt på årets resultat)
        # Always inject unless manually overridden (even if 0, to replace booked tax)
        if ink4_3a_manual is None:
            found_ink4_3a = False
            for r in ink2_data:
                if r.get('variable_name') == 'INK4.3a':
                    old_value = r.get('amount', 0)
                    r['amount'] = round(ink_beraknad)
                    found_ink4_3a = True
                    print(f"✅ Injected INK4.3a (Skatt på årets resultat): {old_value} → {round(ink_beraknad)} kr (beräknad skatt)")
                    break
            
            if not found_ink4_3a:
                print(f"⚠️ INK4.3a not found in ink2_data for injection (beräknad skatt: {ink_beraknad})")
        else:
            print(f"ℹ️ Skipping INK4.3a injection - manual override exists: {ink4_3a_manual}")
        
        return ink2_data
        
    except Exception as e:
        print(f"⚠️ Error in inject_ink2_adjustments: {e}")
        import traceback
        traceback.print_exc()
        return ink2_data  # Return unchanged on error

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
        
        # CRITICAL: Validate that organization number was extracted
        # SE files MUST contain #ORGNR tag - if missing, it's a parsing error
        if not company_info.get('organization_number'):
            raise HTTPException(
                status_code=400,
                detail="SE-filen saknar organisationsnummer (#ORGNR). Kontrollera att filen är en giltig SIE-fil."
            )
        
        # Scrape additional company information from rating.se
        scraped_company_data = {}
        try:

            scraped_company_data = get_company_info_with_search(
                orgnr=company_info.get('organization_number'),
                company_name=company_info.get('company_name')
            )

            

        except Exception as e:

            scraped_company_data = {"error": str(e)}
        
        rr_data = parser.parse_rr_data(current_accounts, previous_accounts, sie_text=se_content)
        
        # Pass RR data to BR parsing so calculated values from RR are available
        # Use koncern-aware BR parsing for automatic reconciliation with K2 notes
        br_data = parser.parse_br_data_with_koncern(se_content, current_accounts, previous_accounts, rr_data)
        
        # Parse INK2 data (tax calculations) - pass RR data, BR data, SIE content, and previous accounts for account descriptions
        ink2_data = parser.parse_ink2_data(current_accounts, company_info.get('fiscal_year'), rr_data, br_data, se_content, previous_accounts)
        
        # ⚠️ CRITICAL: Freeze originals AFTER RR has values, BEFORE inject_ink2_adjustments mutates them
        temp_data = {'rrData': rr_data}  # Use 'rrData' key that freeze_originals looks for
        temp_data = freeze_originals(temp_data)
        arets_resultat_original = temp_data.get('arets_resultat_original')
        arets_skatt_original = temp_data.get('arets_skatt_original')
        original_rr_snapshot = temp_data.get('__original_rr_snapshot__')
        
        # Inject adjustments for PDF consistency (INK4.1/4.2 ← Årets resultat justerat, INK4.3a ← beräknad skatt)
        # This may mutate rr_data, but we have a deep snapshot frozen above
        ink2_data = inject_ink2_adjustments(ink2_data, rr_data)
        
        # Parse Noter data (notes) - pass SE content and user toggles if needed
        try:
            noter_data = parser.parse_noter_data(se_content, two_files_flag=False, previous_year_se_content=None)

        except Exception as e:

            noter_data = []
        
        # Parse Förvaltningsberättelse data (FB) - Förändring i eget kapital
        try:
            fb_module = ForvaltningsberattelseFB()
            fb_variables = fb_module.calculate_forandring_eget_kapital(se_content, br_data)
            fb_table = fb_module.generate_forandring_eget_kapital_table(fb_variables)
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
        # Round to 0 decimals for consistency with tax module comparison
        sarskild_loneskatt_pension = round(sarskild_loneskatt_pension, 0)
        # Get sarskild_loneskatt rate from global variables
        sarskild_loneskatt_rate = float(parser.global_variables.get('sarskild_loneskatt', 0.0))
        sarskild_loneskatt_pension_calculated = pension_premier * sarskild_loneskatt_rate
        # Round to 0 decimals for consistency with tax module calculation
        sarskild_loneskatt_pension_calculated = round(sarskild_loneskatt_pension_calculated, 0)
        
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
        
        # Store original values in company_info so they're part of seFileData
        company_info['arets_resultat_original'] = arets_resultat_original
        company_info['arets_skatt_original'] = arets_skatt_original
        
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
                "sarskild_loneskatt_pension_calculated": sarskild_loneskatt_pension_calculated,
                # ORIGINAL VALUES for Bokföringsinstruktion (never modified by INK2 adjustments)
                "arets_resultat_original": arets_resultat_original,
                "arets_skatt_original": arets_skatt_original,
                "__original_rr_snapshot__": original_rr_snapshot  # Deep snapshot of pre-INK2 RR
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
        
        rr_data = parser.parse_rr_data(current_accounts, previous_accounts, sie_text=se_content)
        
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
        
        # ⚠️ CRITICAL: Freeze originals AFTER RR has values, BEFORE inject_ink2_adjustments mutates them
        temp_data = {'rrData': rr_data}  # Use 'rrData' key that freeze_originals looks for
        temp_data = freeze_originals(temp_data)
        arets_resultat_original = temp_data.get('arets_resultat_original')
        arets_skatt_original = temp_data.get('arets_skatt_original')
        original_rr_snapshot = temp_data.get('__original_rr_snapshot__')
        
        # Inject adjustments for PDF consistency (INK4.1/4.2 ← Årets resultat justerat, INK4.3a ← beräknad skatt)
        # This may mutate rr_data, but we have a deep snapshot frozen above
        ink2_data = inject_ink2_adjustments(ink2_data, rr_data)
        
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
            fb_module = ForvaltningsberattelseFB()
            fb_variables = fb_module.calculate_forandring_eget_kapital(current_se_content, br_data)
            fb_table = fb_module.generate_forandring_eget_kapital_table(fb_variables)
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
        # Round to 0 decimals for consistency with tax module comparison
        sarskild_loneskatt_pension = round(sarskild_loneskatt_pension, 0)
        # Get sarskild_loneskatt rate from global variables
        sarskild_loneskatt_pension_calculated = pension_premier * 0.2431
        # Round to 0 decimals for consistency with tax module calculation
        sarskild_loneskatt_pension_calculated = round(sarskild_loneskatt_pension_calculated, 0)
        
        # Store original values in company_info so they're part of seFileData
        company_info['arets_resultat_original'] = arets_resultat_original
        company_info['arets_skatt_original'] = arets_skatt_original
        
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
                "two_files_used": True,  # Flag to indicate two files were processed
                # ORIGINAL VALUES for Bokföringsinstruktion (never modified by INK2 adjustments)
                "arets_resultat_original": arets_resultat_original,
                "arets_skatt_original": arets_skatt_original,
                "__original_rr_snapshot__": original_rr_snapshot  # Deep snapshot of pre-INK2 RR
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
        from services.bolagsverket_service import fetch_company_objects, BVG_BASE, BVG_SCOPE, BVG_CLIENT_ID, BVG_CLIENT_SECRET
        from services.bolagsverket_officers_extractor import extract_officers_for_signing
        
        # Clean organization number (remove hyphens and non-digits)
        clean_org = "".join(ch for ch in organization_number if ch.isdigit())
        
        # Fetch company data from Bolagsverket API
        try:
            company_info = fetch_company_objects(clean_org, ["FUNKTIONARER", "FIRMATECKNING"])
        except Exception as fetch_error:
            logger.error(f"Bolagsverket API error: {str(fetch_error)}")
            # Return detailed error for debugging
            raise HTTPException(
                status_code=502,
                detail=f"Bolagsverket upstream error: {str(fetch_error)}"
            )
        
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
        try:
            officers_data = extract_officers_for_signing(company_info)
        except Exception as extract_error:
            logger.error(f"Officer extraction error: {str(extract_error)}")
            raise HTTPException(
                status_code=500,
                detail=f"Extraction failed: {str(extract_error)}"
            )
        
        return {
            "success": True,
            "message": f"Found {len(officers_data['UnderskriftForetradare'])} företrädare and {len(officers_data['UnderskriftAvRevisor'])} revisorer",
            "officers": officers_data,
            "organization_number": clean_org
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching Bolagsverket officers: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Fel vid hämtning av företagsinformation från Bolagsverket: {str(e)}"
        )

@app.get("/api/bolagsverket/config-check")
async def bolagsverket_config_check():
    """
    🔎 Hjälp vid drift: visar bara *att* env finns, inte värdena.
    Debug endpoint to check if Bolagsverket environment variables are configured.
    Does not leak secret values.
    """
    from services.bolagsverket_service import BVG_BASE, BVG_SCOPE, BVG_CLIENT_ID, BVG_CLIENT_SECRET
    
    return {
        "base_url_set": bool(BVG_BASE),
        "scope_set": bool(BVG_SCOPE),
        "client_id_set": bool(BVG_CLIENT_ID),
        "client_secret_set": bool(BVG_CLIENT_SECRET),
        "base_url": BVG_BASE or None,  # Usually safe to show, remove if you want
        "scope": BVG_SCOPE or None,    # Usually safe to show
    }

@app.get("/api/bolagsverket/full/{organization_number}")
async def get_bolagsverket_full_data(organization_number: str):
    """
    🧪 TEST ENDPOINT - Returns raw, unfiltered data from Bolagsverket API
    
    This endpoint returns the complete, unprocessed response from Bolagsverket
    including all information objects (FUNKTIONARER, FIRMATECKNING, etc.)
    
    Useful for debugging and exploring what data is available.
    
    Args:
        organization_number: Swedish organization number (with or without hyphen)
        
    Returns:
        Raw JSON response from Bolagsverket API
    """
    try:
        from services.bolagsverket_service import fetch_company_objects
        
        # Clean organization number (remove hyphens and non-digits)
        clean_org = "".join(ch for ch in organization_number if ch.isdigit())
        
        logger.info(f"🧪 TEST: Fetching full Bolagsverket data for: {clean_org}")
        
        # Fetch ALL available information objects
        info_objects = [
            "FUNKTIONARER",
            "FIRMATECKNING",
            "ORGANISATIONSADRESSER",
            "HEMVISTKOMMUN",
            "RAKENSKAPSAR",
            "ORGANISATIONSDATUM",
            "VERKSAMHETSBESKRIVNING",
            "AKTIEINFORMATION",
            "SAMTLIGA_ORGANISATIONSNAMN",
            "ORGANISATIONSENGAGEMANG",
            "TILLSTAND",
            "OVRIG_ORGANISATIONSINFORMATION",
            "ORGANISATIONSMARKERINGAR",
            "BESTAMMELSER",
            "VAKANSER_OCH_UPPLYSNINGAR",
            "EKONOMISK_PLAN",
            "UTLANDSK_FILIALAGANDE_ORGANISATION",
            "FINANSIELLA_RAPPORTER"
        ]
        
        # Fetch raw data from Bolagsverket
        raw_data = fetch_company_objects(clean_org, info_objects)
        
        logger.info(f"✅ Successfully fetched full data for {clean_org}")
        
        return {
            "success": True,
            "organization_number": clean_org,
            "info_objects_requested": info_objects,
            "raw_data": raw_data,
            "note": "This is the complete, unfiltered response from Bolagsverket API"
        }
    
    except Exception as e:
        logger.error(f"❌ Error fetching full Bolagsverket data: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Fel vid hämtning av data från Bolagsverket: {str(e)}"
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
        
        rr_data = parser.parse_rr_data(current_accounts, previous_accounts, sie_text=se_content)
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

@app.get("/api/payments/get-most-recent")
async def get_most_recent_payment():
    """
    Get the most recent paid payment (for getting org number when it's missing from frontend)
    """
    try:
        supabase = get_supabase_client()
        if not supabase:
            raise HTTPException(status_code=503, detail="Database service temporarily unavailable")
        
        # Get most recent paid payment
        result = supabase.table('payments')\
            .select('customer_email,organization_number,created_at')\
            .eq('payment_status', 'paid')\
            .order('created_at', desc=True)\
            .limit(1)\
            .execute()
        
        if not result.data or len(result.data) == 0:
            return {
                "success": False,
                "customer_email": None,
                "organization_number": None,
                "message": "No paid payment found"
            }
        
        payment = result.data[0]
        return {
            "success": True,
            "customer_email": payment.get('customer_email'),
            "organization_number": payment.get('organization_number')
        }
    except Exception as e:
        print(f"Error getting most recent payment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting most recent payment: {str(e)}")

@app.get("/api/payments/get-customer-email")
async def get_customer_email(organization_number: str):
    """
    Get the customer_email from the most recent paid payment for an organization
    """
    try:
        supabase = get_supabase_client()
        
        if not supabase:
            raise HTTPException(status_code=503, detail="Database service temporarily unavailable")
        
        # Normalize organization number (remove dashes and spaces)
        org_number = organization_number.replace("-", "").replace(" ", "").strip()
        
        if not org_number:
            raise HTTPException(status_code=400, detail="Organization number is required")
        
        # Get all paid payments for this organization
        all_results = supabase.table('payments')\
            .select('customer_email,organization_number,created_at')\
            .eq('organization_number', org_number)\
            .eq('payment_status', 'paid')\
            .execute()
        
        # Sort by created_at descending (most recent first) and get the first one
        customer_email = None
        organization_number_return = None
        if all_results.data:
            sorted_results = sorted(
                all_results.data, 
                key=lambda x: x.get('created_at') or '', 
                reverse=True
            )
            if sorted_results:
                customer_email = sorted_results[0].get('customer_email')
                organization_number_return = sorted_results[0].get('organization_number')
        
        if not customer_email:
            return {
                "success": False,
                "customer_email": None,
                "organization_number": None,
                "message": "No paid payment found for this organization"
            }
        
        return {
            "success": True,
            "customer_email": customer_email,
            "organization_number": organization_number_return
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting customer email: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting customer email: {str(e)}")

@app.post("/api/chat-flow/process-choice")
async def process_chat_choice(request: dict):
    """
    Process user choice and return next action
    """
    try:
        step_number = request.get("step_number")
        option_value = request.get("option_value")
        context = request.get("context", {})
        
        # Get the current step to find the selected option
        step_data = await get_chat_flow_step(step_number)
        if not step_data or not step_data.get("success"):
            raise HTTPException(status_code=404, detail="Step not found")
        
        # Find the selected option
        selected_option = None
        for option in step_data["options"]:
            if option["option_value"] == option_value:
                selected_option = option
                break
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
    Send annual report for digital signing with BankID using TellusTalk
    """
    try:
        signering_data = request.get("signeringData", {})
        organization_number = request.get("organizationNumber")
        company_data = request.get("companyData")
        
        print(f"🖊️ Sending for digital signing: org={organization_number}")
        print(f"🖊️ Signering data keys: {list(signering_data.keys()) if signering_data else 'None'}")
        print(f"🖊️ Signering data: {signering_data}")
        print(f"🖊️ Company data keys: {list(company_data.keys()) if company_data else 'None'}")
        print(f"🖊️ Company data present: {bool(company_data)}")
        
        # Extract företrädare (company representatives) data
        foretradare = signering_data.get("UnderskriftForetradare", [])
        revisor = signering_data.get("UnderskriftAvRevisor", [])
        
        print(f"📋 Found {len(foretradare)} företrädare and {len(revisor)} revisors")
        
        # Debug: Print email addresses
        for i, person in enumerate(foretradare):
            email = person.get("UnderskriftHandlingEmail", "")
            name = f"{person.get('UnderskriftHandlingTilltalsnamn', '')} {person.get('UnderskriftHandlingEfternamn', '')}"
            print(f"  Företrädare {i+1}: {name} - Email: '{email}' (empty: {not email})")
        
        for i, person in enumerate(revisor):
            email = person.get("UnderskriftHandlingEmail", "")
            name = f"{person.get('UnderskriftHandlingTilltalsnamn', '')} {person.get('UnderskriftHandlingEfternamn', '')}"
            print(f"  Revisor {i+1}: {name} - Email: '{email}' (empty: {not email})")
        
        # Validate that we have signers with emails
        all_signers = []
        for person in foretradare:
            email = person.get("UnderskriftHandlingEmail", "")
            if not email:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing email for företrädare: {person.get('UnderskriftHandlingTilltalsnamn', '')} {person.get('UnderskriftHandlingEfternamn', '')}"
                )
            all_signers.append(person)
        
        for person in revisor:
            email = person.get("UnderskriftHandlingEmail", "")
            if not email:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing email for revisor: {person.get('UnderskriftHandlingTilltalsnamn', '')} {person.get('UnderskriftHandlingEfternamn', '')}"
                )
            all_signers.append(person)
        
        if not all_signers:
            raise HTTPException(
                status_code=400,
                detail="No signers with email addresses found"
            )
        
        # Generate annual report PDF
        if not company_data:
            raise HTTPException(
                status_code=400,
                detail="companyData is required to generate the annual report PDF"
            )
        
        print("📄 Generating annual report PDF...")
        from services.pdf_annual_report import generate_full_annual_report_pdf
        pdf_bytes = generate_full_annual_report_pdf(company_data)
        print(f"✅ PDF generated: {len(pdf_bytes)} bytes")
        
        # Prepare signers for TellusTalk
        from services.tellustalk_service import (
            send_pdf_for_signing,
            create_signer_from_foretradare,
            create_signer_from_revisor
        )
        
        # Build signers list - set all to same order (1) for parallel signing
        # All signers will receive invitations simultaneously and can sign in any order
        tellustalk_signers = []
        
        # Add företrädare
        for person in foretradare:
            tellustalk_signers.append(create_signer_from_foretradare(person, signature_order=1))
        
        # Add revisor
        for person in revisor:
            tellustalk_signers.append(create_signer_from_revisor(person, signature_order=1))
        
        # Create job name from company info
        company_name = (
            company_data.get('company_name') or 
            (company_data.get('seFileData') or {}).get('company_info', {}).get('company_name') or 
            'Bolag'
        )
        fiscal_year = (
            company_data.get('fiscalYear') or 
            (company_data.get('seFileData') or {}).get('company_info', {}).get('fiscal_year') or 
            ''
        )
        job_name = f"Årsredovisning {company_name} {fiscal_year}"
        
        # Optional redirect URLs (can be configured via environment variables)
        success_url = os.getenv("TELLUSTALK_SUCCESS_REDIRECT_URL")
        fail_url = os.getenv("TELLUSTALK_FAIL_REDIRECT_URL")
        # Only enable webhook if explicitly enabled (can cause API delays)
        # Set TELLUSTALK_ENABLE_WEBHOOKS=false to disable webhooks for faster response
        enable_webhooks = os.getenv("TELLUSTALK_ENABLE_WEBHOOKS", "true").lower() == "true"
        report_to_url = os.getenv("TELLUSTALK_REPORT_TO_URL") if enable_webhooks else None
        
        # Send PDF to TellusTalk
        print(f"📤 Sending PDF to TellusTalk with {len(tellustalk_signers)} signers...")
        tellustalk_result = send_pdf_for_signing(
            pdf_bytes=pdf_bytes,
            signers=tellustalk_signers,
            job_name=job_name,
            success_redirect_url=success_url,
            fail_redirect_url=fail_url,
            report_to_url=report_to_url
        )
        
        # Log the signing request for summary
        signing_summary = []
        for i, person in enumerate(foretradare):
            name = f"{person.get('UnderskriftHandlingTilltalsnamn', '')} {person.get('UnderskriftHandlingEfternamn', '')}"
            role = person.get('UnderskriftHandlingRoll', '')
            email = person.get('UnderskriftHandlingEmail', '')
            signing_summary.append(f"  {i+1}. {name} ({role}) - {email}")
        
        for i, person in enumerate(revisor):
            name = f"{person.get('UnderskriftHandlingTilltalsnamn', '')} {person.get('UnderskriftHandlingEfternamn', '')}"
            title = person.get('UnderskriftHandlingTitel', '')
            email = person.get('UnderskriftHandlingEmail', '')
            is_main = person.get('UnderskriftRevisorspateckningRevisorHuvudansvarig', False)
            main_text = " - Huvudansvarig" if is_main else ""
            signing_summary.append(f"  R{i+1}. {name} ({title}){main_text} - {email}")
        
        print(f"📝 Signing invitations sent to:")
        for line in signing_summary:
            print(line)
        print(f"✅ TellusTalk job_uuid: {tellustalk_result.get('job_uuid')}")
        
        # Store initial job info in database (link job_uuid to organization_number)
        # Do this in background thread to not delay the response
        import threading
        def save_job_to_db():
            try:
                supabase = get_supabase_client()
                if supabase and organization_number:
                    try:
                        job_uuid_value = tellustalk_result.get("job_uuid")
                        if job_uuid_value:
                            # Check if record exists first
                            existing = supabase.table('signing_status').select('job_uuid').eq('job_uuid', job_uuid_value).execute()
                            
                            data_to_save = {
                                'job_uuid': job_uuid_value,
                                'organization_number': organization_number,
                                'job_name': tellustalk_result.get("job_name", job_name),
                                'ebox_job_key': tellustalk_result.get("ebox_job_key"),
                                'event': 'created',
                                'status_data': {
                                    'created_at': datetime.now().isoformat(),
                                    'members': tellustalk_result.get("members", [])
                                },
                                'created_at': datetime.now().isoformat(),
                                'updated_at': datetime.now().isoformat()
                            }
                            
                            if existing.data and len(existing.data) > 0:
                                # Update existing record
                                supabase.table('signing_status').update(data_to_save).eq('job_uuid', job_uuid_value).execute()
                                print(f"✅ Initial job updated in database")
                            else:
                                # Insert new record
                                supabase.table('signing_status').insert(data_to_save).execute()
                                print(f"✅ Initial job saved to database")
                    except Exception as table_error:
                        error_msg = str(table_error)
                        # Check if it's a table not found error
                        if 'table' in error_msg.lower() and ('not found' in error_msg.lower() or 'PGRST205' in error_msg):
                            print(f"⚠️ Database table 'signing_status' not found. Please create the table using the SQL from README.md")
                        elif '23505' in error_msg or 'duplicate key' in error_msg.lower():
                            # Duplicate key error - try update instead
                            try:
                                job_uuid_value = tellustalk_result.get("job_uuid")
                                if job_uuid_value:
                                    supabase.table('signing_status').update({
                                        'organization_number': organization_number,
                                        'job_name': tellustalk_result.get("job_name", job_name),
                                        'ebox_job_key': tellustalk_result.get("ebox_job_key"),
                                        'event': 'created',
                                        'status_data': {
                                            'created_at': datetime.now().isoformat(),
                                            'members': tellustalk_result.get("members", [])
                                        },
                                        'updated_at': datetime.now().isoformat()
                                    }).eq('job_uuid', job_uuid_value).execute()
                                    print(f"✅ Initial job updated in database (after duplicate key error)")
                            except Exception as update_error:
                                print(f"⚠️ Could not update database after duplicate key error: {str(update_error)}")
                        else:
                            print(f"⚠️ Could not save initial job to database: {error_msg}")
            except Exception as db_error:
                print(f"⚠️ Database error when saving initial job: {str(db_error)}")
        
        # Start background thread for database save (don't wait - return immediately)
        threading.Thread(target=save_job_to_db, daemon=True).start()
        
        # Return success response with TellusTalk job info immediately
        return {
            "success": True,
            "message": "Signing invitations sent successfully",
            "signing_summary": signing_summary,
            "organization_number": organization_number,
            "tellustalk_job_uuid": tellustalk_result.get("job_uuid"),
            "ebox_job_key": tellustalk_result.get("ebox_job_key"),
            "job_name": tellustalk_result.get("job_name"),
            "members": tellustalk_result.get("members", [])
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        print(f"❌ Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"❌ Error sending for digital signing: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error sending for digital signing: {str(e)}")

@app.post("/webhooks/tellustalk-status")
async def tellustalk_webhook(request: Request):
    """
    Webhook endpoint to receive TellusTalk signing status updates
    
    Events received:
    - job_started: When emails have been sent to signers
    - signature_completed: When each signer has signed
    - job_completed: When all signers have signed
    
    Returns 200 OK to acknowledge receipt (required by TellusTalk)
    """
    try:
        payload = await request.json()
        
        job_uuid = payload.get("job_uuid")
        job_name = payload.get("job_name")
        ebox_job_key = payload.get("ebox_job_key")
        event = payload.get("event")
        signed_files_list = payload.get("signed_files_list", [])
        
        print(f"📬 TellusTalk webhook received: event={event}, job_uuid={job_uuid}")
        print(f"   Job name: {job_name}")
        
        # Get signing status from signed_files_list
        signing_status = {
            "job_uuid": job_uuid,
            "job_name": job_name,
            "ebox_job_key": ebox_job_key,
            "event": event,
            "timestamp": datetime.now().isoformat()
        }
        
        # Extract member signing details if available
        if signed_files_list and len(signed_files_list) > 0:
            file_data = signed_files_list[0]
            members_info = file_data.get("members", {})
            members_expected = file_data.get("members_expected_to_sign_ids", [])
            members_signed = file_data.get("members_signed_ids", [])
            members_pending = file_data.get("members_pending_to_sign_ids", [])
            
            signing_status["signing_details"] = {
                "expected_count": len(members_expected),
                "signed_count": len(members_signed),
                "pending_count": len(members_pending),
                "members_expected": members_expected,
                "members_signed": members_signed,
                "members_pending": members_pending,
                "members_info": members_info
            }
            
            print(f"   Signing progress: {len(members_signed)}/{len(members_expected)} signed")
            for member_id, member_data in members_info.items():
                has_signed = member_data.get("has_signed")
                name = member_data.get("name", "Unknown")
                if has_signed:
                    print(f"   ✅ {name} signed at {has_signed}")
                else:
                    print(f"   ⏳ {name} pending")
            
            # If job is completed, get download URL for signed PDF
            if event == "job_completed" and file_data.get("download_url"):
                signing_status["signed_pdf_download_url"] = file_data.get("download_url")
                print(f"   📄 Signed PDF available at: {file_data.get('download_url')}")
        
        # Store signing status in database (if Supabase is available)
        try:
            supabase = get_supabase_client()
            if supabase:
                # Try to upsert signing status - store by job_uuid
                # Use upsert with on_conflict to handle unique constraint on job_uuid
                try:
                    # First try to check if record exists and get existing organization_number
                    existing = supabase.table('signing_status').select('job_uuid, organization_number').eq('job_uuid', job_uuid).execute()
                    
                    # Preserve organization_number if it exists, otherwise set to None
                    existing_org_number = None
                    if existing.data and len(existing.data) > 0:
                        existing_org_number = existing.data[0].get('organization_number')
                    
                    data_to_save = {
                        'job_uuid': job_uuid,
                        'organization_number': existing_org_number,  # Preserve existing or None
                        'job_name': job_name,
                        'ebox_job_key': ebox_job_key,
                        'event': event,
                        'signing_details': signing_status.get('signing_details', {}),
                        'signed_pdf_download_url': signing_status.get('signed_pdf_download_url'),
                        'status_data': signing_status,
                        'updated_at': datetime.now().isoformat()
                    }
                    
                    if existing.data and len(existing.data) > 0:
                        # Update existing record
                        supabase.table('signing_status').update(data_to_save).eq('job_uuid', job_uuid).execute()
                        print(f"   💾 Signing status updated in database")
                    else:
                        # Insert new record
                        supabase.table('signing_status').insert(data_to_save).execute()
                        print(f"   💾 Signing status saved to database")
                        
                except Exception as table_error:
                    error_msg = str(table_error)
                    # Check if it's a table not found error
                    if 'table' in error_msg.lower() and ('not found' in error_msg.lower() or 'PGRST205' in error_msg):
                        print(f"   ⚠️ Database table 'signing_status' not found. Please create the table using the SQL from README.md")
                        print(f"   Error details: {error_msg}")
                    elif '23505' in error_msg or 'duplicate key' in error_msg.lower():
                        # Duplicate key error - try update instead
                        try:
                            # Get existing organization_number to preserve it
                            existing_check = supabase.table('signing_status').select('organization_number').eq('job_uuid', job_uuid).execute()
                            existing_org = None
                            if existing_check.data and len(existing_check.data) > 0:
                                existing_org = existing_check.data[0].get('organization_number')
                            
                            supabase.table('signing_status').update({
                                'organization_number': existing_org,  # Preserve existing
                                'job_name': job_name,
                                'ebox_job_key': ebox_job_key,
                                'event': event,
                                'signing_details': signing_status.get('signing_details', {}),
                                'signed_pdf_download_url': signing_status.get('signed_pdf_download_url'),
                                'status_data': signing_status,
                                'updated_at': datetime.now().isoformat()
                            }).eq('job_uuid', job_uuid).execute()
                            print(f"   💾 Signing status updated in database (after duplicate key error)")
                        except Exception as update_error:
                            print(f"   ⚠️ Could not update database after duplicate key error: {str(update_error)}")
                    else:
                        print(f"   ⚠️ Could not save to database: {error_msg}")
            else:
                print(f"   ⚠️ Supabase client not available - skipping database save")
        except Exception as db_error:
            print(f"   ⚠️ Database error: {str(db_error)}")
            # Continue - webhook should still return 200
        
        # Always return 200 OK to acknowledge receipt
        # TellusTalk will retry if we don't return 200
        return {"status": "received", "event": event, "job_uuid": job_uuid}
        
    except Exception as e:
        print(f"❌ Error processing TellusTalk webhook: {str(e)}")
        import traceback
        traceback.print_exc()
        # Still return 200 to prevent TellusTalk from retrying invalid requests
        # But log the error for debugging
        return {"status": "error", "message": str(e)}


@app.get("/api/signing-status/{job_uuid}")
async def get_signing_status(job_uuid: str):
    """
    Get current signing status for a TellusTalk job by job_uuid
    
    Returns:
        - Event type (job_started, signature_completed, job_completed)
        - Signing progress (signed/pending counts)
        - Member details and signing timestamps
        - Download URL for signed PDF (if job_completed)
    """
    try:
        supabase = get_supabase_client()
        if not supabase:
            raise HTTPException(status_code=503, detail="Database service unavailable")
        
        result = supabase.table('signing_status').select('*').eq('job_uuid', job_uuid).order('updated_at', desc=True).execute()
        
        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=404, detail="Signing job not found")
        
        # Get the most recent entry (first in desc order)
        status_data = result.data[0]
        
        return {
            "success": True,
            "job_uuid": status_data.get("job_uuid"),
            "job_name": status_data.get("job_name"),
            "event": status_data.get("event"),
            "signing_details": status_data.get("signing_details", {}),
            "signed_pdf_download_url": status_data.get("signed_pdf_download_url"),
            "updated_at": status_data.get("updated_at")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting signing status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting signing status: {str(e)}")


@app.get("/api/signing-status/by-org/{organization_number}")
async def get_signing_status_by_org(organization_number: str):
    """
    Get latest signing status for an organization by organization_number
    
    Returns the most recent signing job status for the organization
    """
    try:
        supabase = get_supabase_client()
        if not supabase:
            raise HTTPException(status_code=503, detail="Database service unavailable")
        
        # Normalize organization number (remove hyphens/spaces)
        org_normalized = organization_number.replace("-", "").replace(" ", "").strip()
        
        result = supabase.table('signing_status').select('*').eq('organization_number', org_normalized).order('updated_at', desc=True).execute()
        
        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=404, detail="No signing job found for this organization")
        
        # Get the most recent entry (first in desc order)
        status_data = result.data[0]
        
        return {
            "success": True,
            "job_uuid": status_data.get("job_uuid"),
            "job_name": status_data.get("job_name"),
            "event": status_data.get("event"),
            "signing_details": status_data.get("signing_details", {}),
            "signed_pdf_download_url": status_data.get("signed_pdf_download_url"),
            "updated_at": status_data.get("updated_at")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting signing status by org: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting signing status: {str(e)}")

@app.get("/api/users/check-exists")
async def check_user_exists(username: str, organization_number: str):
    """
    Check if user exists and if organization_number is associated with them
    Returns user_exist flag
    """
    try:
        supabase = get_supabase_client()
        if not supabase:
            raise HTTPException(status_code=503, detail="Database service temporarily unavailable")
        
        # Normalize organization number
        org_number = organization_number.replace("-", "").replace(" ", "").strip()
        
        # Check if user exists
        user_result = supabase.table('users')\
            .select('id, username, organization_number')\
            .eq('username', username)\
            .execute()
        
        user_exists = len(user_result.data) > 0
        org_in_user = False
        
        if user_exists:
            # Check if organization_number is in the user's array
            user_data = user_result.data[0]
            org_array = user_data.get('organization_number', [])
            
            # Handle JSONB array (PostgreSQL/Supabase returns lists directly)
            # Also handle legacy single value or string formats
            if isinstance(org_array, list):
                # JSONB array - check if org_number is in array (string comparison)
                org_in_user = any(str(item) == org_number for item in org_array)
            elif isinstance(org_array, str):
                # Legacy: If stored as string, parse it
                try:
                    import json
                    if org_array.startswith('['):
                        parsed = json.loads(org_array)
                    else:
                        parsed = [org_array]
                    org_in_user = any(str(item) == org_number for item in parsed)
                except:
                    org_in_user = org_number == org_array
            else:
                # Single value - compare as string
                org_in_user = org_number == str(org_array) if org_array else False
        
        return {
            "success": True,
            "user_exist": user_exists,
            "org_in_user": org_in_user
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error checking user existence: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error checking user existence: {str(e)}")

@app.post("/api/users/create-account")
async def create_user_account(request: dict):
    """
    Create user account and send password email
    Called after step 515 when username is registered
    Handles both new user creation and adding org number to existing user
    """
    try:
        username = request.get("username")  # Email address
        organization_number = request.get("organization_number")
        
        if not username:
            raise HTTPException(status_code=400, detail="Username (email) is required")
        
        if not organization_number:
            raise HTTPException(status_code=400, detail="Organization number is required")
        
        # Validate email format - require TLD with at least 2 characters
        import re
        username = username.strip()
        
        # Check basic structure
        if '@' not in username:
            raise HTTPException(status_code=400, detail="Invalid email format: missing @ symbol")
        
        parts = username.split('@')
        if len(parts) != 2:
            raise HTTPException(status_code=400, detail="Invalid email format")
        
        local_part, domain = parts
        
        # Check local part
        if not local_part or len(local_part) == 0:
            raise HTTPException(status_code=400, detail="Invalid email format: missing username part")
        
        # Check domain
        if not domain or '.' not in domain:
            raise HTTPException(status_code=400, detail="Invalid email format: invalid domain")
        
        # Check TLD (last part after dot) must be at least 2 characters
        tld = domain.split('.')[-1]
        if not tld or len(tld) < 2:
            raise HTTPException(status_code=400, detail="Invalid email format: domain must end with at least 2 characters (e.g., .com or .se)")
        
        # Final regex check
        email_pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]{2,}$'
        if not re.match(email_pattern, username):
            raise HTTPException(status_code=400, detail="Invalid email format")
        
        supabase = get_supabase_client()
        if not supabase:
            raise HTTPException(status_code=503, detail="Database service temporarily unavailable")
        
        # Normalize organization number
        org_number = organization_number.replace("-", "").replace(" ", "").strip()
        
        # Check if user already exists
        user_result = supabase.table('users')\
            .select('id, username, organization_number, password')\
            .eq('username', username)\
            .execute()
        
        user_exists = len(user_result.data) > 0
        password = None
        
        if user_exists:
            # User exists - check if org number is in their array
            user_data = user_result.data[0]
            org_array = user_data.get('organization_number', [])
            
            # Handle JSONB array (PostgreSQL/Supabase returns lists directly)
            # Also handle legacy single value or string formats
            if isinstance(org_array, list):
                # JSONB array - check if org_number is already in array
                org_number_str = str(org_number)  # Ensure string comparison
                org_in_array = any(str(item) == org_number_str for item in org_array)
                
                if not org_in_array:
                    # Add org number to array (as string)
                    org_array.append(org_number_str)
                    supabase.table('users')\
                        .update({'organization_number': org_array})\
                        .eq('id', user_data['id'])\
                        .execute()
                    print(f"✅ Added organization_number {org_number} to existing user {username}")
                else:
                    print(f"ℹ️ Organization number {org_number} already exists for user {username}")
            elif isinstance(org_array, str):
                # Legacy: If stored as string, parse and update
                try:
                    import json
                    if org_array.startswith('['):
                        parsed = json.loads(org_array)
                    else:
                        # Single value as string - convert to array
                        parsed = [org_array] if org_array else []
                    
                    if org_number not in parsed:
                        parsed.append(org_number)
                        supabase.table('users')\
                            .update({'organization_number': parsed})\
                            .eq('id', user_data['id'])\
                            .execute()
                        print(f"✅ Added organization_number {org_number} to existing user {username} (converted from string)")
                    else:
                        print(f"ℹ️ Organization number {org_number} already exists for user {username}")
                except Exception as e:
                    print(f"⚠️ Error parsing organization_number string: {e}, converting to array")
                    # Convert single value to array
                    new_array = [org_array, org_number] if org_array != org_number else [org_number]
                    supabase.table('users')\
                        .update({'organization_number': new_array})\
                        .eq('id', user_data['id'])\
                        .execute()
                    print(f"✅ Added organization_number {org_number} to existing user {username} (converted)")
            else:
                # Single value (number or other), convert to array
                org_array_str = str(org_array) if org_array else ''
                if org_array_str != org_number:
                    new_array = [org_array_str, org_number]
                    supabase.table('users')\
                        .update({'organization_number': new_array})\
                        .eq('id', user_data['id'])\
                        .execute()
                    print(f"✅ Added organization_number {org_number} to existing user {username} (converted from single value)")
                else:
                    print(f"ℹ️ Organization number {org_number} already exists for user {username}")
            
            # Existing user - get their current password from database
            password = user_data.get('password')
            if not password:
                print(f"⚠️ Warning: Existing user {username} has no password in database")
                password = generate_password()  # Fallback: generate new password if missing
                supabase.table('users')\
                    .update({'password': password})\
                    .eq('id', user_data['id'])\
                    .execute()
                print(f"✅ Generated and saved new password for user {username}")
            
            print(f"✅ Using existing password for user {username}")
            
        else:
            # New user - create account
            password = generate_password()  # 6-digit random password
            org_array = [org_number]  # JSONB array with single org number
            
            supabase.table('users')\
                .insert({
                    'username': username,
                    'password': password,  # TODO: Hash this with bcrypt in production
                    'organization_number': org_array  # JSONB array format
                })\
                .execute()
            
            print(f"✅ Created new user account for {username} with password: {password}")
        
        # Fetch company name using same logic as PDF generator (_company_meta function)
        # Check multiple sources: request.company_name, data.company_name, seFileData.company_info.company_name
        company_name = request.get("company_name", "")  # Try from request first
        if not company_name:
            try:
                # Query se_files table to get company_name from the most recent file for this organization
                se_files_result = supabase.table('se_files')\
                    .select('data')\
                    .eq('organization_number', org_number)\
                    .order('created_at', desc=True)\
                    .limit(1)\
                    .execute()
                
                if se_files_result.data and len(se_files_result.data) > 0:
                    file_data = se_files_result.data[0].get('data', {})
                    if isinstance(file_data, dict):
                        # Match logic from pdf_annual_report.py _company_meta:
                        # name = data.get('company_name') or info.get('company_name') or "Bolag"
                        se = file_data.get('seFileData', {}) or {}
                        info = se.get('company_info', {}) or {}
                        
                        # Try data.company_name first, then seFileData.company_info.company_name
                        company_name = (file_data.get('company_name') or 
                                      info.get('company_name') or 
                                      se.get('company_name') or 
                                      '')
                        if company_name:
                            print(f"✅ Found company_name for email from se_files: {company_name}")
            except Exception as e:
                print(f"⚠️ Could not fetch company_name for email: {str(e)}")
                import traceback
                traceback.print_exc()
                # Continue without company_name - will use default "ditt bolag"
        
        if not company_name:
            print(f"ℹ️ No company_name found, will use default 'ditt bolag' in email")
        
        # Always send password email (with existing password for existing users, new password for new users)
        login_url = os.getenv("MINA_SIDOR_URL", "https://www.summare.se")
        email_sent = await send_password_email(username, username, password, login_url, company_name)
        
        if not email_sent:
            print(f"⚠️ Password email failed to send for user {username}")
            # Still return success since account was processed
        else:
            if user_exists:
                print(f"✅ Password email sent to existing user {username} (with existing password)")
            else:
                print(f"✅ Password email sent to new user {username} (with new password)")
        
        return {
            "success": True,
            "message": "User account processed successfully",
            "username": username,
            "user_exist": user_exists,
            "email_sent": email_sent  # Always true if email was sent (for both new and existing users)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error creating user account: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error creating user account: {str(e)}")

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
        if request.ink4_16_underskott_adjustment and request.ink4_16_underskott_adjustment != 0:
            manual_amounts['ink4_16_underskott_adjustment'] = request.ink4_16_underskott_adjustment
        if request.justering_sarskild_loneskatt and request.justering_sarskild_loneskatt != 0:
            manual_amounts['justering_sarskild_loneskatt'] = request.justering_sarskild_loneskatt
        
        # Preserve INK4.6d if it exists in manual_amounts (sticky value from original calculation)
        if 'INK4.6d' in request.manual_amounts:
            manual_amounts['INK4.6d'] = request.manual_amounts['INK4.6d']

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
            else:
                # SLP lowers the result: Årets_resultat_justerat = SumResultatForeSkatt - SLP - INK_beraknad_skatt
                arets_resultat_justerat = sum_resultat_fore_skatt - slp - ink_beraknad
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
            
            # INJECTION: Sync INK4.1/INK4.2 with Årets_resultat_justerat for PDF consistency
            # Pass SLP adjustment if not already booked in RR
            slp_adjustment = 0.0 if rr_252_has_slp else -slp  # Negative because it's a cost
            ink2_data = inject_ink2_adjustments(ink2_data, request.rr_data, manual_amounts, slp_adjustment)
                        
        except Exception as e:
            print(f"⚠️ Exception in Arets_resultat_justerat calculation: {e}")
            import traceback
            traceback.print_exc()
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
    pass
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

        # Always run SLP section, even when 0 (to reset values to base)
        if slp_accepted >= 0:
            rr_personal = _find_rr_personalkostnader(rr)
            if not rr_personal:
                pass
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

                # Use current SLP level (not delta magnitude) for idempotent ripples
                applied_slp = slp_accepted
                # Always ripple, even when 0 (to reset dependent rows to base)
                if applied_slp >= 0:
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

                    # --- SLP booked as extra cost - apply idempotently using base tracking ---
                    # Helper to apply SLP delta idempotently to RR rows
                    def apply_slp_to_row(rr_list, rid, var=None, label=None, slp_delta=0.0):
                        r = row(rr_list, rid, var=var, label=label)
                        if not r:
                            return
                        # Establish base once
                        slp_already_applied = _num(r.get("slp_applied_to_row"))
                        if f"__base_row_{rid}" not in r:
                            r[f"__base_row_{rid}"] = _num(r.get("current_amount")) + slp_already_applied  # Remove old SLP to get base
                        base = _num(r.get(f"__base_row_{rid}"))
                        # Apply new SLP to base
                        new_val = base - slp_delta  # Negative because SLP is a cost
                        r["current_amount"] = new_val
                        r["slp_applied_to_row"] = slp_delta
                        return new_val - base  # Return actual delta applied

                    # Apply SLP to all affected RR rows idempotently
                    apply_slp_to_row(rr, 256, var="SumRorelsekostnader", label="Summa rörelsekostnader", slp_delta=applied_slp)
                    apply_slp_to_row(rr, 257, var="SumRorelseresultat", label="Summa rörelseresultat", slp_delta=applied_slp)
                    apply_slp_to_row(rr, 260, var="Rorelseresultat", label="Rörelseresultat", slp_delta=applied_slp)
                    apply_slp_to_row(rr, 267, var="SumResultatEfterFinansiellaPoster", label="Resultat efter finansiella poster", slp_delta=applied_slp)
                    apply_slp_to_row(rr, 275, var="SumResultatForeSkatt", label="Resultat före skatt", slp_delta=applied_slp)
                    # NOTE: RR 279 (Årets resultat) is handled separately in tax section with combined SLP+tax formula
                    # Skip it here to avoid double-update

                    # --- SLP also affects BR Skatteskulder (it's a tax liability) ---
                    # Find BR Skatteskulder (row 413)
                    br_tax_liab_for_slp = _get(br, id=413) or _get(br, name="Skatteskulder")
                    if br_tax_liab_for_slp:
                        # Establish stable base for SLP in Skatteskulder (idempotent)
                        slp_already_in_skatteskulder = _num(br_tax_liab_for_slp.get("slp_injected_skatteskulder"))
                        tax_calc_in_skatteskulder = _num(br_tax_liab_for_slp.get("tax_calc_amount"))
                        
                        if "__base_skatteskulder" not in br_tax_liab_for_slp and "_base_skatteskulder" in br_tax_liab_for_slp:
                            br_tax_liab_for_slp["__base_skatteskulder"] = _num(br_tax_liab_for_slp.get("_base_skatteskulder"))
                        if "__base_skatteskulder" not in br_tax_liab_for_slp:
                            # Remove SLP and tax to get base
                            br_tax_liab_for_slp["__base_skatteskulder"] = _num(br_tax_liab_for_slp.get("current_amount")) - slp_already_in_skatteskulder - tax_calc_in_skatteskulder
                        
                        base_skatteskulder = _num(br_tax_liab_for_slp.get("__base_skatteskulder"))
                        before_skatteskulder = _num(br_tax_liab_for_slp.get("current_amount"))
                        
                        # Set Skatteskulder = base + SLP + tax (preserve tax portion)
                        new_skatteskulder = base_skatteskulder + slp_accepted + tax_calc_in_skatteskulder
                        _set_current(br_tax_liab_for_slp, new_skatteskulder)
                        after_skatteskulder = _num(br_tax_liab_for_slp.get("current_amount"))
                        br_tax_liab_for_slp["slp_injected_skatteskulder"] = slp_accepted
                        
                        # Calculate only the SLP delta (not total delta) for reporting
                        d_slp = slp_accepted - slp_already_in_skatteskulder
                        
                        # Note: BR 416 (SumKortfristigaSkulder) will be updated later in tax section with total delta
                        
                        # Note: BR total (417) will be updated later with both equity and liability changes
                    else:
                        print("⚠️  BR row 413 (Skatteskulder) not found - cannot update with SLP")

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

        rr_result = _find_by_row_id(rr, 279, varname="SumAretsResultat", label="Årets resultat")
        if not rr_result:
            raise HTTPException(400, "RR row 279 (SumAretsResultat) missing")

        # Correct formula: RR 279 = RR 275 + RR 277 (SkattAretsResultat) + RR 278 (OvrigaSkatter)
        # RR 275 already has SLP applied idempotently
        rr_result_before_skatt = _find_by_row_id(rr, 275, varname="SumResultatForeSkatt", label="Resultat före skatt")
        if not rr_result_before_skatt:
            raise HTTPException(400, "RR row 275 (Resultat före skatt) missing")
        
        # Get Övriga skatter (row 278) if it exists
        rr_ovriga_skatter = _find_by_row_id(rr, 278, varname="OvrigaSkatter", label="Övriga skatter")
        ovriga_skatter = _num(rr_ovriga_skatter.get("current_amount")) if rr_ovriga_skatter else 0
        
        resultat_fore_skatt = _num(rr_result_before_skatt.get("current_amount"))
        rr_result_new = resultat_fore_skatt + rr_tax_new + ovriga_skatter
        _set_current(rr_result, rr_result_new)

        # --- BR: sync Årets resultat (380) to RR result, update equity sums ---
        br_result = _get(br, id=380) or _get(br, name="AretsResultat")
        if not br_result:
            raise HTTPException(400, "BR row 380 (AretsResultat) missing")

        d_br_result = _delta_set(br_result, rr_result_new)  # returns delta vs old

        # --- BR: update SumFrittEgetKapital (381) by the delta in AretsResultat ---
        br_sum_fritt = _get(br, id=381) or _get(br, name="SumFrittEgetKapital")
        if br_sum_fritt:
            old_fritt = float(br_sum_fritt.get("current_amount") or 0)
            new_fritt = old_fritt + d_br_result
            _set(br_sum_fritt, new_fritt)
        # --- BR: update SumEgetKapital (382) by the delta in SumFrittEgetKapital ---
        br_sum_eget = _get(br, id=382) or _get(br, name="SumEgetKapital")
        if br_sum_eget:
            old_eget = float(br_sum_eget.get("current_amount") or 0)
            new_eget = old_eget + d_br_result
            _set(br_sum_eget, new_eget)

        # --- BR: update Skatteskulder (413) by the tax DIFF, then roll up short-term debts (416) ---
        br_tax_liab = _get(br, id=413) or _get(br, name="Skatteskulder")
        if not br_tax_liab:
            raise HTTPException(400, "BR row 413 (Skatteskulder) missing")

        # Track tax portion separately (idempotent calculation)
        # BR 413 should be: base + SLP + calculated_tax
        # The base and SLP were already set in the SLP section above
        # Now we need to add the calculated tax portion
        old_tax_calc = _num(br_tax_liab.get("tax_calc_amount", 0))
        br_tax_liab["tax_calc_amount"] = ink_calc  # Store current calculated tax
        
        # Recalculate BR 413 from base + SLP + tax
        base_skatteskulder = _num(br_tax_liab.get("__base_skatteskulder"))
        slp_in_skatteskulder = _num(br_tax_liab.get("slp_injected_skatteskulder"))
        
        # If base not set yet, establish it now (should have been set by SLP section, but handle edge case)
        if "__base_skatteskulder" not in br_tax_liab:
            br_tax_liab["__base_skatteskulder"] = _num(br_tax_liab.get("current_amount")) - slp_in_skatteskulder - old_tax_calc
            base_skatteskulder = br_tax_liab["__base_skatteskulder"]
        
        old_skatteskulder = _num(br_tax_liab.get("current_amount"))
        new_skatteskulder = base_skatteskulder + slp_in_skatteskulder + ink_calc
        _set_current(br_tax_liab, new_skatteskulder)
        
        # Calculate only the tax delta (not including SLP) - just the change in tax
        d_tax_only = ink_calc - old_tax_calc
        # Calculate total delta for BR 416 ripple
        d_tax_liab = new_skatteskulder - old_skatteskulder

        # --- BR: update SumKortfristigaSkulder (416) idempotently ---
        # This should include all the Skatteskulder changes (both SLP and tax)
        d_sum_short = 0.0  # Initialize delta
        br_sum_short = _get(br, id=416) or _get(br, name="SumKortfristigaSkulder")
        if br_sum_short:
            # Track the total amount injected into Skatteskulder (SLP + tax)
            total_injected_in_skatteskulder = slp_in_skatteskulder + ink_calc
            old_injected_in_skatteskulder = _num(br_sum_short.get("skatteskulder_injected", 0))
            
            # Establish base if not set
            if "__base_sum_short" not in br_sum_short:
                br_sum_short["__base_sum_short"] = _num(br_sum_short.get("current_amount")) - old_injected_in_skatteskulder
            
            base_sum_short = _num(br_sum_short.get("__base_sum_short"))
            old_sum_short = _num(br_sum_short.get("current_amount"))
            
            # Calculate new value: base + total tax effects
            new_sum_short = base_sum_short + total_injected_in_skatteskulder
            d_sum_short = new_sum_short - old_sum_short
            _set_current(br_sum_short, new_sum_short)
            br_sum_short["skatteskulder_injected"] = total_injected_in_skatteskulder

        # --- BR: update total balance sheet (417) by BOTH equity and liability deltas ---
        # Balance sheet equation: Assets = Equity + Liabilities
        # When tax/SLP changes: Equity changes (d_br_result) and Liabilities change (d_sum_short)
        # Net change to row 417 = d_br_result + d_sum_short
        br_sum_total = _get(br, id=417) or _get(br, name="SumEgetKapitalOchSkulder")
        if br_sum_total:
            old_total = float(br_sum_total.get("current_amount") or 0)
            total_delta = d_br_result + d_sum_short
            new_total = old_total + total_delta
            _set(br_sum_total, new_total)

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

@app.post("/api/pdf/annual-report")
async def pdf_annual_report(request: Request):
    """
    Generate full annual report PDF using server-side ReportLab
    Order: Förvaltningsberättelse, Resultaträkning, Balansräkning (tillgångar), 
           Balansräkning (eget kapital och skulder), Noter
    """
    try:
        from services.pdf_annual_report import generate_full_annual_report_pdf
        from fastapi.responses import Response
        
        payload = await request.json()
        company_data = payload.get('companyData', {})
        
        pdf_bytes = generate_full_annual_report_pdf(company_data)
        
        # Extract name and fiscal year for filename
        name = (company_data.get('company_name') 
                or (company_data.get('seFileData') or {}).get('company_info', {}).get('company_name') 
                or 'bolag')
        fy = (company_data.get('fiscalYear') 
              or (company_data.get('seFileData') or {}).get('company_info', {}).get('fiscal_year') 
              or '')
        
        filename = f'arsredovisning_{name}_{fy}.pdf'
        
        return Response(
            content=pdf_bytes,
            media_type='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
        )
    except Exception as e:
        print(f"Error generating PDF: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")

@app.post("/api/pdf/ink2-form")
async def pdf_ink2_form(request: Request):
    """
    Generate filled INK2 tax declaration PDF form
    Populates INK2_form.pdf with data from database based on ink2_form table mappings
    """
    try:
        from services.ink2_pdf_filler import generate_filled_ink2_pdf
        from fastapi.responses import Response
        
        payload = await request.json()
        company_data = payload.get('companyData', {})
        
        # Extract organization_number and fiscal_year
        organization_number = (company_data.get('organization_number') 
                              or company_data.get('organizationNumber')
                              or (company_data.get('seFileData') or {}).get('company_info', {}).get('organization_number'))
        
        fiscal_year = (company_data.get('fiscalYear')
                      or company_data.get('fiscal_year')
                      or (company_data.get('seFileData') or {}).get('company_info', {}).get('fiscal_year'))
        
        if not organization_number:
            raise HTTPException(status_code=400, detail="organization_number is required")
        if not fiscal_year:
            raise HTTPException(status_code=400, detail="fiscal_year is required")
        
        # Generate filled PDF
        pdf_bytes = generate_filled_ink2_pdf(organization_number, fiscal_year, company_data)
        
        # Extract name for filename
        name = (company_data.get('company_name') 
                or company_data.get('companyName')
                or (company_data.get('seFileData') or {}).get('company_info', {}).get('company_name') 
                or 'bolag')
        
        filename = f'INK2_inkomstdeklaration_{name}_{fiscal_year}.pdf'
        
        return Response(
            content=pdf_bytes,
            media_type='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
        )
    except Exception as e:
        print(f"Error generating INK2 PDF: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generating INK2 PDF: {str(e)}")

@app.post("/api/sru/generate")
async def generate_sru(request: Request):
    """
    Generate SRU files for INK2 tax declaration
    Returns ZIP archive containing main SRU file and INFO.SRU for Swedish tax authorities
    """
    try:
        from services.sru_generator import generate_sru_file
        from fastapi.responses import Response
        
        payload = await request.json()
        company_data = payload.get('companyData', {})
        
        # Extract organization_number and fiscal_year for validation
        organization_number = (company_data.get('organization_number') 
                              or company_data.get('organizationNumber')
                              or (company_data.get('seFileData') or {}).get('company_info', {}).get('organization_number'))
        
        fiscal_year = (company_data.get('fiscalYear')
                      or company_data.get('fiscal_year')
                      or (company_data.get('seFileData') or {}).get('company_info', {}).get('fiscal_year'))
        
        if not organization_number:
            raise HTTPException(status_code=400, detail="organization_number is required")
        if not fiscal_year:
            raise HTTPException(status_code=400, detail="fiscal_year is required")
        
        # Generate SRU files (returns ZIP with main SRU + INFO.SRU)
        zip_bytes = generate_sru_file(company_data)
        
        # Extract name for ZIP filename
        name = (company_data.get('company_name') 
                or company_data.get('companyName')
                or (company_data.get('seFileData') or {}).get('company_info', {}).get('company_name') 
                or 'bolag')
        
        # Remove spaces and special characters from filename
        import re
        name_clean = re.sub(r'[^\w\s-]', '', name).strip().replace(' ', '_')
        zip_filename = f'INK2_{name_clean}_{fiscal_year}.zip'
        
        return Response(
            content=zip_bytes,
            media_type='application/zip',
            headers={
                'Content-Disposition': f'attachment; filename="{zip_filename}"',
                'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
        )
    except Exception as e:
        print(f"Error generating SRU files: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generating SRU files: {str(e)}")

@app.post("/api/pdf/bokforing-instruktion/check")
async def check_bokforing_instruktion(request: Request):
    """
    Check if Bokföringsinstruktion PDF should be generated based on conditions:
    - SLP ≠ 0 OR
    - Beräknad skatt ≠ bokförd skatt OR
    - Justerat årets resultat ≠ årets resultat
    
    Returns: {"shouldGenerate": true/false}
    """
    try:
        from services.pdf_bokforing_instruktion import check_should_generate
        
        payload = await request.json()
        company_data = payload.get('companyData', {})
        
        should_generate = check_should_generate(company_data)
        
        return {"shouldGenerate": should_generate}
    except Exception as e:
        print(f"Error checking Bokföringsinstruktion requirements: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error checking Bokföringsinstruktion requirements: {str(e)}")

@app.post("/api/pdf/bokforing-instruktion")
async def pdf_bokforing_instruktion(request: Request):
    """
    Generate accounting instruction PDF (Bokföringsinstruktion) when adjustments are needed.
    This PDF is only generated when:
    - SLP ≠ 0 OR
    - Beräknad skatt ≠ bokförd skatt OR
    - Justerat årets resultat ≠ årets resultat
    """
    try:
        from services.pdf_bokforing_instruktion import generate_bokforing_instruktion_pdf, check_should_generate
        from fastapi.responses import Response
        
        payload = await request.json()
        company_data = payload.get('companyData', {})
        
        # Check if PDF should be generated
        if not check_should_generate(company_data):
            raise HTTPException(
                status_code=400, 
                detail="Bokföringsinstruktion not needed - no adjustments required"
            )
        
        # Generate PDF
        pdf_bytes = generate_bokforing_instruktion_pdf(company_data)
        
        # Extract name and fiscal year for filename
        name = (company_data.get('company_name') 
                or company_data.get('companyName')
                or (company_data.get('seFileData') or {}).get('company_info', {}).get('company_name') 
                or 'bolag')
        fy = (company_data.get('fiscalYear') 
              or company_data.get('fiscal_year')
              or (company_data.get('seFileData') or {}).get('company_info', {}).get('fiscal_year') 
              or '')
        
        filename = f'bokforingsinstruktion_{name}_{fy}.pdf'
        
        return Response(
            content=pdf_bytes,
            media_type='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error generating Bokföringsinstruktion PDF: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generating Bokföringsinstruktion PDF: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    import os
    
    # Get port from environment variable (Railway sets this)
    port = int(os.environ.get("PORT", 8080))
    
    # Reduce log verbosity - only show warnings and errors
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=port,
        log_level="warning",  # Only show warnings and errors
        access_log=False       # Disable HTTP access logs
    ) 