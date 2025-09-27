-- Update step 505 to use dynamic Stripe checkout integration
-- This migration updates the payment step to trigger dynamic Stripe session creation

-- Update step 505 to use dynamic Stripe checkout
UPDATE public.chat_flow 
SET 
    option1_text = 'Betala',
    option1_value = 'stripe_payment',
    option1_next_step = 505,
    option1_action_type = 'external_redirect',
    option1_action_data = '{"url": "DYNAMIC_STRIPE_URL", "target": "_blank"}',
    updated_at = NOW()
WHERE step_number = 505;

-- If the row doesn't exist, create it
INSERT INTO public.chat_flow (
    step_number, 
    block, 
    question_text, 
    question_icon, 
    question_type,
    option1_text,
    option1_value,
    option1_next_step,
    option1_action_type,
    option1_action_data,
    created_at,
    updated_at
) VALUES (
    505,
    'PAYMENT',
    'Genom att klicka på Betala kan du påbörja betalningen, så att vi därefter kan slutföra årsredovisingen för signering och digital inlämning till Bolagsverket.',
    '💳',
    'options',
    'Betala',
    'stripe_payment',
    505,
    'external_redirect',
    '{"url": "DYNAMIC_STRIPE_URL", "target": "_blank"}',
    NOW(),
    NOW()
) ON CONFLICT (step_number) DO UPDATE SET
    block = EXCLUDED.block,
    question_text = EXCLUDED.question_text,
    question_icon = EXCLUDED.question_icon,
    question_type = EXCLUDED.question_type,
    option1_text = EXCLUDED.option1_text,
    option1_value = EXCLUDED.option1_value,
    option1_next_step = EXCLUDED.option1_next_step,
    option1_action_type = EXCLUDED.option1_action_type,
    option1_action_data = EXCLUDED.option1_action_data,
    updated_at = NOW();
