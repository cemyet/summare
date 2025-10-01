-- Add step 515 - Signering (Digital Signing) module
-- This step triggers after payment completion to initiate digital signing process

INSERT INTO public.chat_flow (
    step_number,
    block,
    question_text,
    question_icon,
    question_type,
    input_type,
    input_placeholder,
    show_conditions,
    option1_text,
    option1_value,
    option1_next_step,
    option1_action_type,
    option1_action_data,
    created_at,
    updated_at
) VALUES (
    515,
    'SIGNERING',
    'Vi har hämtat information om alla befattningshavare som behöver signera årsredovisningen direkt från Bolagsverket. Det enda du behöver göra är att lägga till deras mailadresser så att inbjudan för digital signering kan skickas till dem. Du kan även ta bort eller lägga till befattningshavare om det behövs. Klicka på Skicka för signering när du är klar.',
    '✏️',
    'options',
    NULL,
    NULL,
    NULL,
    'Skicka för signering',
    'send_for_signing',
    520,
    'api_call',
    '{"endpoint": "send_for_digital_signing", "params": {"signeringData": "from_state"}}',
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

-- Add step 520 - Confirmation after signing is sent
INSERT INTO public.chat_flow (
    step_number,
    block,
    question_text,
    question_icon,
    question_type,
    created_at,
    updated_at
) VALUES (
    520,
    'SIGNERING',
    'Nu har årsredovisningen skickats för signering. Du kommer att få bekräftelse på mail när alla befattningshavare har signerat.',
    '✏️',
    'message',
    NOW(),
    NOW()
) ON CONFLICT (step_number) DO UPDATE SET
    block = EXCLUDED.block,
    question_text = EXCLUDED.question_text,
    question_icon = EXCLUDED.question_icon,
    question_type = EXCLUDED.question_type,
    updated_at = NOW();

-- Update step 510 to go to step 515 instead of ending
UPDATE public.chat_flow 
SET 
    option1_next_step = 515,
    updated_at = NOW()
WHERE step_number = 510 AND option1_next_step IS NULL;

-- If step 510 doesn't exist, create it (post-payment confirmation)
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
    created_at,
    updated_at
) VALUES (
    510,
    'PAYMENT',
    'Toppen! Nu är betalningen gjord och kvittot har skickats till din mail. Du kan nu ladda ner pdf på den färdiga årsredovisningen och SRU filer för inkomstdeklarationen. I fönstret till höger hittar du länkar för nedladdningar.',
    '✏️',
    'message',
    'Fortsätt till signering',
    'continue',
    515,
    'navigate',
    NOW(),
    NOW()
) ON CONFLICT (step_number) DO UPDATE SET
    option1_next_step = 515,
    updated_at = NOW();
