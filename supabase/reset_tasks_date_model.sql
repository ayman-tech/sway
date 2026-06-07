-- Destructive one-time reset for the date-only scheduling redesign.
-- This removes task rows only. User accounts, settings, and Google connections remain.
drop table if exists public.tasks cascade;

-- After running this statement, run supabase/schema.sql to recreate public.tasks.
