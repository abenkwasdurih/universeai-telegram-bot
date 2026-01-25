-- Migration to add missing columns to generations table for Telegram bot queue system
-- This allows the generations table to be used for both queueing and historical logs.

ALTER TABLE public.generations 
ADD COLUMN IF NOT EXISTS aspect_ratio TEXT DEFAULT '16:9',
ADD COLUMN IF NOT EXISTS options JSONB DEFAULT '{}'::jsonb,
ADD COLUMN IF NOT EXISTS telegram_chat_id TEXT,
ADD COLUMN IF NOT EXISTS error TEXT;

-- Recommended: Add index for performance when fetching pending tasks
CREATE INDEX IF NOT EXISTS idx_generations_status_source ON public.generations(status, source);

COMMENT ON COLUMN public.generations.aspect_ratio IS 'Aspect ratio for video generation (16:9, 9:16, 1:1)';
COMMENT ON COLUMN public.generations.options IS 'Options for generation e.g. duration, msg_id';
COMMENT ON COLUMN public.generations.telegram_chat_id IS 'Chat ID for sending notifications';
COMMENT ON COLUMN public.generations.error IS 'Error message if generation failed';
