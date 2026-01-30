-- Migration: Add pricing columns for 5s and 10s durations to ai_models
-- Environment: Staging
-- Date: 2026-01-27

-- Add is_free_pro_5s column to determine if 5-second videos are free for Pro users
ALTER TABLE public.ai_models
ADD COLUMN IF NOT EXISTS is_free_pro_5s BOOLEAN DEFAULT FALSE;

-- Add separate cost columns for 5s and 10s durations
ALTER TABLE public.ai_models
ADD COLUMN IF NOT EXISTS cost_pro_5s INTEGER DEFAULT 0;

ALTER TABLE public.ai_models
ADD COLUMN IF NOT EXISTS cost_pro_10s INTEGER DEFAULT 0;

-- Comments for documentation
COMMENT ON COLUMN public.ai_models.is_free_pro_5s IS 'If true, 5-second videos are free for Pro users';
COMMENT ON COLUMN public.ai_models.cost_pro_5s IS 'Credit cost for 5-second videos (Pro tier)';
COMMENT ON COLUMN public.ai_models.cost_pro_10s IS 'Credit cost for 10-second videos (Pro tier)';
