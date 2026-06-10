-- Destructive development reset. Deletes Sway public data but leaves auth.users intact.
-- Run this first, then run supabase/schema.sql.

drop table if exists public.availability_shares cascade;
drop table if exists public.google_calendar_connections cascade;
drop table if exists public.user_settings cascade;
drop table if exists public.tasks cascade;
