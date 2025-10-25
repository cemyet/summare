# Stripe Dynamic Pricing Setup Guide

## Overview

This guide explains how to set up dynamic pricing in Stripe for first-time buyers (499 SEK) vs returning customers (699 SEK).

## Prerequisites

You should have already:
- ✅ Created two products in Stripe Dashboard
- ✅ Configured Stripe Tax with Swedish VAT (25%)
- ✅ Set up automatic tax collection

## Products in Stripe Dashboard

You have two products configured:

1. **Digital årsredovisning (rabatterad första året)** - 499 SEK
   - Product ID: `prod_T8CMRG8sg1tN1n`
   - Tax code: `txcd_10000000` (Digital services)
   - For first-time buyers

2. **Digital årsredovisning** - 699 SEK
   - Product ID: `prod_T8CKt7CYLkjF10`
   - Tax code: `txcd_10000000` (Digital services)
   - For returning customers

## Step 1: Get Price IDs from Stripe

1. Go to [Stripe Dashboard → Products](https://dashboard.stripe.com/products)
2. Click on "Digital årsredovisning (rabatterad första året)"
3. Under "Priser" section, click on "499,00 kr"
4. Copy the **Price ID** (starts with `price_...`)
5. Repeat for "Digital årsredovisning" (699 kr product)

## Step 2: Configure Environment Variables

Add these to your backend environment variables (Railway, Render, or .env):

```bash
# Stripe Price IDs for dynamic pricing
STRIPE_PRICE_FIRST_TIME=price_xxxxxxxxxxxxx  # 499 SEK Price ID
STRIPE_PRICE_REGULAR=price_xxxxxxxxxxxxx     # 699 SEK Price ID

# Keep existing Stripe config
STRIPE_SECRET_KEY=sk_live_xxxxxxxxxxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxx
```

## Step 3: Run Database Migration

Apply the payments table migration:

```bash
# If using Supabase locally
supabase migration up

# Or apply directly in Supabase Dashboard SQL Editor
# Run the contents of: backend/supabase/migrations/20250126000000_create_payments_table.sql
```

## How It Works

### 1. **First-Time Buyer Check**

When a customer reaches the payment step, the backend:

```
GET /api/check-first-time-buyer/{org_number}
```

Returns:
```json
{
  "organization_number": "5566103643",
  "has_paid_before": false,
  "recommended_price_sek": 499,
  "is_eligible_for_discount": true
}
```

### 2. **Create Checkout Session**

Frontend calls:

```
POST /api/payments/create-checkout-session
{
  "organization_number": "556610-3643",
  "customer_email": "customer@example.com"
}
```

Backend automatically:
- Checks if org number has paid before
- Selects correct Price ID (499 kr or 699 kr)
- Creates Stripe checkout session with metadata
- Returns checkout URL

Response:
```json
{
  "checkout_url": "https://checkout.stripe.com/c/pay/cs_...",
  "amount_sek": 499,
  "is_first_time_buyer": true,
  "product_type": "first_time_discount"
}
```

### 3. **Webhook Saves Payment**

When payment completes, Stripe webhook saves payment to database:

```sql
INSERT INTO payments (
  organization_number,
  stripe_session_id,
  amount_total,
  amount_subtotal,
  payment_status,
  product_type,
  paid_at
)
```

### 4. **Next Payment**

When same organization pays again, they get 699 SEK price automatically.

## API Endpoints

### Check First-Time Buyer Status

```http
GET /api/check-first-time-buyer/{org_number}
```

**Response:**
```json
{
  "organization_number": "5566103643",
  "has_paid_before": boolean,
  "recommended_price_sek": number,
  "is_eligible_for_discount": boolean
}
```

### Create Checkout Session (Dynamic Pricing)

```http
POST /api/payments/create-checkout-session
Content-Type: application/json

{
  "organization_number": "556610-3643",
  "customer_email": "customer@example.com"
}
```

**Response:**
```json
{
  "checkout_url": "https://checkout.stripe.com/...",
  "amount_sek": 499,
  "is_first_time_buyer": true,
  "product_type": "first_time_discount"
}
```

## Frontend Integration Example

```typescript
// Check if first-time buyer
const checkResponse = await fetch(
  `/api/check-first-time-buyer/${orgNumber}`
);
const { recommended_price_sek, is_eligible_for_discount } = await checkResponse.json();

// Show appropriate message
if (is_eligible_for_discount) {
  showMessage("Första året rabatt! Endast 499 kr (+ moms)");
} else {
  showMessage("Ordinarie pris: 699 kr (+ moms)");
}

// Create checkout session
const sessionResponse = await fetch('/api/payments/create-checkout-session', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    organization_number: orgNumber,
    customer_email: customerEmail
  })
});

const { checkout_url } = await sessionResponse.json();
window.open(checkout_url, '_blank');
```

## Pricing Summary

| Customer Type | Price (ex. VAT) | VAT (25%) | Total |
|--------------|----------------|-----------|--------|
| First-time   | 499 SEK        | 124.75 SEK| **623.75 SEK** |
| Returning    | 699 SEK        | 174.75 SEK| **873.75 SEK** |

## Testing

### Test First-Time Buyer Flow

1. Use organization number that hasn't paid: e.g., `9999999999`
2. Create checkout session
3. Complete payment with Stripe test card: `4242 4242 4242 4242`
4. Verify 499 SEK + VAT charged
5. Check `payments` table has record

### Test Returning Customer Flow

1. Use same organization number from test 1
2. Create checkout session again
3. Verify 699 SEK price shown
4. Complete payment
5. Verify 699 SEK + VAT charged

## Troubleshooting

### Price IDs Not Working

If Price IDs are not set or invalid, system falls back to amount-based pricing (still calculates tax correctly).

### Payment Not Saved to Database

Check webhook logs:
```bash
# In your backend logs, look for:
✅ Payment successful: cs_xxx, email: ..., amount: ...
💾 Payment saved to database for org: 5566103643
```

If missing:
1. Verify `payments` table exists in Supabase
2. Check Stripe webhook is configured correctly
3. Ensure webhook secret is set in environment variables

### Wrong Price Applied

Check:
1. Organization number is being sent correctly (without spaces/dashes)
2. `payments` table query is working
3. Environment variables `STRIPE_PRICE_FIRST_TIME` and `STRIPE_PRICE_REGULAR` are set

## Database Schema

```sql
CREATE TABLE payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_number TEXT NOT NULL,
  stripe_session_id TEXT NOT NULL UNIQUE,
  stripe_payment_intent_id TEXT,
  amount_total INTEGER NOT NULL,
  amount_subtotal INTEGER NOT NULL,
  currency TEXT NOT NULL DEFAULT 'sek',
  customer_email TEXT,
  customer_name TEXT,
  payment_status TEXT NOT NULL,
  product_type TEXT, -- 'first_time_discount' or 'regular'
  metadata JSONB,
  paid_at TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);
```

## Next Steps

1. Get Price IDs from Stripe Dashboard
2. Set environment variables
3. Run database migration
4. Update frontend to use new API endpoints
5. Test both flows (first-time and returning)
6. Deploy to production

## Support

For questions or issues:
- Check Stripe Dashboard → Logs
- Check backend logs for webhook processing
- Query `payments` table in Supabase

