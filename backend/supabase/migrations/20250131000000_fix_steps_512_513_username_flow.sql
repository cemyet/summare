-- Fix steps 512 and 513 for username/email registration flow
-- This migration fixes issues found in the CSV and ensures proper variable mapping

-- Step 512: Fix option 2 placeholder (should be "Ange email..." not "Ange belopp...")
UPDATE public.chat_flow
SET option2_action_data = jsonb_set(
    option2_action_data,
    '{placeholder}',
    '"Ange email..."'::jsonb
)
WHERE step_number = 512 
  AND option2_action_data IS NOT NULL
  AND option2_action_data->>'placeholder' = 'Ange belopp...';

-- Step 513: Ensure action_type and action_data are properly set (fix line break issue)
-- Update step 513 to ensure process_input action is properly configured
UPDATE public.chat_flow
SET 
    no_option_action_type = 'process_input',
    no_option_action_data = '{"variable": "username"}'::jsonb
WHERE step_number = 513
  AND (no_option_action_type IS NULL OR no_option_action_type != 'process_input');

-- Ensure step 513 has correct structure
-- If step doesn't exist, it should be created from CSV import, but this ensures consistency
UPDATE public.chat_flow
SET 
    input_type = 'string',
    input_placeholder = 'Ange email...'
WHERE step_number = 513
  AND (input_type IS NULL OR input_placeholder != 'Ange email...');

-- Verify step 512 option 1 has set_variable action with correct structure
-- The value "customer_email" will be dynamically resolved by frontend
UPDATE public.chat_flow
SET option1_action_type = 'set_variable',
    option1_action_data = '{"value": "customer_email", "variable": "username"}'::jsonb
WHERE step_number = 512
  AND option1_value = 'approve_calculated'
  AND (option1_action_type IS NULL OR option1_action_data IS NULL);

