-- One-time fix for recurring Google Calendar events that stayed in Sway after
-- being deleted in Calendar. Clearing the stored sync tokens forces the next
-- sync to do a full import, which reconciles and removes orphaned tasks.
-- Safe to run once after deploying the singleEvents/reconciliation fix.

update public.google_calendar_connections set sync_tokens_json = '{}'::jsonb;
