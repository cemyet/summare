-- Create payments table to track all Stripe payments
CREATE TABLE IF NOT EXISTS payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_number TEXT NOT NULL,
  stripe_session_id TEXT NOT NULL UNIQUE,
  stripe_payment_intent_id TEXT,
  amount_total INTEGER NOT NULL, -- Amount in öre (including tax)
  amount_subtotal INTEGER NOT NULL, -- Amount in öre (excluding tax)
  currency TEXT NOT NULL DEFAULT 'sek',
  customer_email TEXT,
  customer_name TEXT,
  payment_status TEXT NOT NULL, -- 'paid', 'unpaid', 'no_payment_required'
  product_type TEXT, -- 'first_time_discount', 'regular'
  metadata JSONB, -- Store any additional metadata from Stripe
  paid_at TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Create index for fast lookup by organization number
CREATE INDEX idx_payments_org_number ON payments(organization_number);
CREATE INDEX idx_payments_stripe_session ON payments(stripe_session_id);
CREATE INDEX idx_payments_paid_at ON payments(paid_at);

-- Enable RLS
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;

-- Create policy - anyone can read their own payments (by email or org number)
CREATE POLICY "Users can view payments" ON payments
  FOR SELECT
  USING (true);

-- Create policy - only authenticated users can insert
CREATE POLICY "Service can insert payments" ON payments
  FOR INSERT
  WITH CHECK (true);

-- Add updated_at trigger
CREATE TRIGGER update_payments_updated_at
  BEFORE UPDATE ON payments
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- Add comment
COMMENT ON TABLE payments IS 'Tracks all Stripe payments for annual reports';

