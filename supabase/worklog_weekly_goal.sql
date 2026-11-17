-- Apply before deploying the weekly Work Log progress feature.
alter table public.user_settings
    add column if not exists work_weekly_goal_hours smallint
    check (work_weekly_goal_hours between 1 and 168);
