-- Fix step 505 next_step to stay on 505 instead of going to 506
-- This ensures the backend special handling for step 505 is triggered

UPDATE public.chat_flow 
SET 
    option1_next_step = 505,
    updated_at = NOW()
WHERE step_number = 505 AND option1_next_step = 506;
