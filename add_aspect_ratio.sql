-- Run this in your Supabase SQL Editor to fix the error:

ALTER TABLE public.tasks 
ADD COLUMN IF NOT EXISTS aspect_ratio TEXT DEFAULT '16:9';

-- Optional: Add comment
COMMENT ON COLUMN public.tasks.aspect_ratio IS 'Aspect ratio for video generation (16:9, 9:16, 1:1)';
