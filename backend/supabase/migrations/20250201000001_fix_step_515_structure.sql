-- Update step 515 - Signering module to match CSV structure exactly
-- This corrects the structure to match the chat_flow_rows (3).csv file

-- First, remove any existing step 515 to start fresh
DELETE FROM public.chat_flow WHERE step_number IN (515, 520);

-- Add step 515 exactly as defined in CSV (row 26)
INSERT INTO public.chat_flow (
    step_number,
    block,
    question_text,
    question_icon,
    question_type,
    input_type,
    input_placeholder,
    no_option_value,
    no_option_next_step,
    no_option_action_type,
    no_option_action_data,
    option1_text,
    option1_value,
    option1_next_step,
    option1_action_type,
    option1_action_data,
    show_conditions,
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
    NULL,
    NULL,
    NULL,
    'Skicka för signering',
    'send_for_signing',
    520,
    'api_call',
    '{"endpoint": "send_for_digital_signing", "params": {"signeringData": "from_state"}}',
    NULL,
    NOW(),
    NOW()
);

-- Add step 520 exactly as defined in CSV (row 27) 
INSERT INTO public.chat_flow (
    step_number,
    block,
    question_text,
    question_icon,
    question_type,
    input_type,
    input_placeholder,
    no_option_value,
    no_option_next_step,
    no_option_action_type,
    no_option_action_data,
    show_conditions,
    created_at,
    updated_at
) VALUES (
    520,
    'SIGNERING',
    'Nu har årsredovisningen skickats för signering. Du kommer att få bekräftelse på mail när alla befattningshavare har signerat.',
    '✏️',
    'message',
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NOW(),
    NOW()
);

-- Ensure step 510 goes to 515 (from CSV row 25)
UPDATE public.chat_flow 
SET 
    no_option_value = 'continue',
    no_option_next_step = 515,
    no_option_action_type = 'navigate',
    updated_at = NOW()
WHERE step_number = 510;

-- If step 510 doesn't exist, create it from CSV
INSERT INTO public.chat_flow (
    step_number,
    block,
    question_text,
    question_icon,
    question_type,
    no_option_value,
    no_option_next_step,
    no_option_action_type,
    created_at,
    updated_at
) VALUES (
    510,
    'PAYMENT',
    'Toppen! Nu är betalningen gjord och kvittot har skickats till din mail. Du kan nu ladda ner pdf på den färdiga årsredovisningen och SRU filer för inkomstdeklarationen. I fönstret till höger hittar du länkar för nedladdningar.',
    '✏️',
    'message',
    'continue',
    515,
    'navigate',
    NOW(),
    NOW()
) ON CONFLICT (step_number) DO UPDATE SET
    no_option_next_step = 515,
    no_option_action_type = 'navigate',
    updated_at = NOW();
