-- Add step 510 - Download module
-- This step displays the Download component with 4 download frames

-- First, remove any existing step 510 to start fresh
DELETE FROM public.chat_flow WHERE step_number = 510;

-- Add step 510 exactly as defined in CSV but with options type
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
    510,
    'DOWNLOAD',
    'Toppen! Nu är betalningen gjord och kvittot har skickats till din mail. Du kan nu ladda ner pdf på den färdiga årsredovisningen och SRU filer för inkomstdeklarationen. I fönstret till höger hittar du länkar för nedladdningar.',
    '✏️',
    'options',
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    'Fortsätt till signering',
    'continue',
    515,
    'navigate',
    NULL,
    NULL,
    NOW(),
    NOW()
);

