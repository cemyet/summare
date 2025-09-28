# Stripe Integration for Step 505 - Embedded Checkout

This document describes the Stripe payment integration implemented for step 505 of the chat flow, which supports both traditional redirect checkout and embedded checkout within the application.

## Overview

The integration supports two payment modes:
1. **Traditional Redirect**: Opens Stripe checkout in a new tab (default)
2. **Embedded Checkout**: Renders Stripe checkout within the application's preview pane

Both modes use dynamic Stripe checkout sessions for better security, session management, and payment tracking.

## Implementation Details

### Backend Changes

#### 1. Dynamic Stripe Session Creation
- **File**: `backend/main.py`
- **Function**: `process_chat_choice()` (lines 995-1042)
- **Purpose**: When step 505 with option `stripe_payment` is selected, dynamically create a Stripe checkout session

#### 2. Stripe Webhook Handler
- **File**: `backend/main.py`
- **Function**: `stripe_webhook()` (lines 108-153)
- **Purpose**: Handle Stripe webhook events for payment confirmation and status updates

#### 3. Database Migration
- **File**: `backend/supabase/migrations/20250122000000_update_step_505_stripe_integration.sql`
- **Purpose**: Update step 505 to use dynamic Stripe checkout instead of hardcoded URL

### Frontend Integration

The frontend (`DatabaseDrivenChat.tsx`) already handles the `external_redirect` action type (lines 998-1005), which will automatically open the dynamic Stripe checkout URL in a new tab.

## Configuration

### Environment Variables

Add these environment variables to your deployment:

**Backend:**
```bash
# Stripe Configuration
STRIPE_SECRET_KEY=sk_test_...  # Your Stripe secret key (from Dashboard > API keys)
STRIPE_WEBHOOK_SECRET=whsec_...  # Your webhook signing secret (from Dashboard > Webhooks)
STRIPE_AMOUNT_SEK=699  # Payment amount in SEK
STRIPE_SUCCESS_URL=https://summare.se/app?payment=success
STRIPE_CANCEL_URL=https://summare.se/app?payment=cancelled
```

**Frontend:**
```bash
# Stripe Configuration
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_...  # Your Stripe publishable key
NEXT_PUBLIC_USE_EMBEDDED_CHECKOUT=true  # Set to true for embedded checkout, false for redirect
```

**How to get these values:**

1. **STRIPE_SECRET_KEY**: 
   - Go to [Stripe Dashboard](https://dashboard.stripe.com) > Developers > API keys
   - Copy the "Secret key" (starts with `sk_test_` for test mode or `sk_live_` for live mode)

2. **STRIPE_WEBHOOK_SECRET**:
   - Go to [Stripe Dashboard](https://dashboard.stripe.com) > Developers > Webhooks
   - Click "Add endpoint" and set URL to: `https://your-backend-url.com/stripe-webhook`
   - Select events: `checkout.session.completed`, `checkout.session.expired`
   - Copy the "Signing secret" (starts with `whsec_`)

### Stripe Dashboard Setup

1. **Webhook Endpoint**: Configure a webhook endpoint in your Stripe dashboard:
   - URL: `https://your-backend-url.com/stripe-webhook`
   - Events: `checkout.session.completed`, `checkout.session.expired`

2. **Product Configuration**: The integration uses:
   - Product: "Årsredovisning - Summare"
   - Price: 299 SEK (29900 öre)
   - Currency: SEK

## Flow Description

1. **User reaches step 505**: The payment step is displayed with a "Betala" button
2. **User clicks "Betala"**: Frontend sends request to `/api/chat-flow/process-choice`
3. **Backend processes choice**: Detects `stripe_payment` option for step 505
4. **Stripe session created**: Backend creates a new Stripe checkout session
5. **Dynamic URL returned**: Backend returns the checkout URL in the response
6. **User redirected**: Frontend opens the Stripe checkout in a new tab
7. **Payment processed**: User completes payment on Stripe
8. **Webhook received**: Stripe sends webhook to confirm payment
9. **Success/cancel handling**: User is redirected back to the app

## Testing

### Manual Testing

1. **Start the backend server**:
   ```bash
   cd backend
   python main.py
   ```

2. **Run the test script**:
   ```bash
   python test_stripe_integration.py
   ```

3. **Test the complete flow**:
   - Navigate to step 505 in the chat
   - Click "Betala"
   - Verify that a Stripe checkout session opens
   - Complete or cancel the payment
   - Verify webhook events are received

### Test Script

The `test_stripe_integration.py` script tests:
- Step 505 data retrieval
- Stripe payment choice processing
- Dynamic checkout URL generation
- Direct Stripe session creation

## Security Considerations

1. **Webhook Signature Verification**: The current implementation doesn't verify webhook signatures. In production, you should:
   ```python
   # Verify webhook signature
   payload = request.body
   sig_header = request.headers.get('stripe-signature')
   event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
   ```

2. **Environment Variables**: Ensure Stripe keys are properly secured and not exposed in client-side code.

3. **HTTPS**: Always use HTTPS in production for webhook endpoints.

## Error Handling

The integration includes error handling for:
- Missing Stripe API key
- Stripe API failures
- Invalid webhook events
- Network timeouts

## Monitoring

Monitor these aspects in production:
- Stripe checkout session creation success rate
- Webhook delivery success rate
- Payment completion rate
- Error logs for failed payments

## Future Enhancements

Potential improvements:
1. **Payment Status Tracking**: Store payment status in database
2. **Email Notifications**: Send confirmation emails after successful payment
3. **Retry Logic**: Implement retry logic for failed webhook deliveries
4. **Analytics**: Track payment conversion rates and user behavior
5. **Multiple Payment Methods**: Support additional payment methods beyond cards

## Troubleshooting

### Common Issues

1. **"Stripe API key not configured"**
   - Ensure `STRIPE_SECRET_KEY` environment variable is set
   - Verify the key is valid and has the correct permissions

2. **Webhook not receiving events**
   - Check webhook URL is accessible from Stripe
   - Verify webhook endpoint is configured in Stripe dashboard
   - Check server logs for webhook processing errors

3. **Checkout session creation fails**
   - Verify Stripe account is active
   - Check if test/live mode matches your API key
   - Review Stripe dashboard for any account issues

### Debug Mode

Enable debug logging by setting:
```bash
STRIPE_DEBUG=true
```

This will provide more detailed logging for troubleshooting.
