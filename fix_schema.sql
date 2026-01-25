-- MASTER FIX: Run this once to fix ALL missing columns

-- 1. Add model_name
ALTER TABLE public.tasks 
ADD COLUMN IF NOT EXISTS model_name TEXT DEFAULT 'kling-v1';

-- 2. Add aspect_ratio
ALTER TABLE public.tasks 
ADD COLUMN IF NOT EXISTS aspect_ratio TEXT DEFAULT '16:9';

-- 3. Add options (JSONB for duration, etc.)
ALTER TABLE public.tasks 
ADD COLUMN IF NOT EXISTS options JSONB DEFAULT '{}'::jsonb;

-- 4. Add error column (for failure logs)
ALTER TABLE public.tasks 
ADD COLUMN IF NOT EXISTS error TEXT;

-- 5. Fix Status Constraint (Allow 'failed')
-- We drop the old one and add the new one
ALTER TABLE public.tasks 
DROP CONSTRAINT IF EXISTS tasks_status_check;

ALTER TABLE public.tasks 
ADD CONSTRAINT tasks_status_check 
CHECK (status IN ('pending', 'processing', 'completed', 'failed'));

-- 6. Fix Generations Table (Add source column)
ALTER TABLE public.generations 
ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'web';

-- Comments for clarity
COMMENT ON COLUMN public.tasks.model_name IS 'Model ID used (e.g. kling-v1)';
COMMENT ON COLUMN public.tasks.aspect_ratio IS 'Video aspect ratio (16:9, etc)';
COMMENT ON COLUMN public.tasks.options IS 'Flexible JSON options (duration, metadata)';
COMMENT ON COLUMN public.tasks.error IS 'Error message if task failed';
COMMENT ON COLUMN public.generations.source IS 'Platform source (web, telegram)';
