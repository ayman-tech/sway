-- Sway — Supabase cloud schema.
-- Run this once in your Supabase project: SQL Editor → New query → paste → Run.
-- It creates the cloud `tasks` table and Row-Level Security so each account only
-- sees its own rows. The local SQLite row id is reused as the cloud row id.

create table if not exists public.tasks (
    id uuid primary key,
    user_id uuid not null references auth.users(id) on delete cascade,

    title text not null,
    description text,
    project_id text,
    priority int not null default 0,
    status text not null default 'pending',

    due_at timestamptz,
    due_date date,
    start_at timestamptz,
    end_at timestamptz,
    end_date date,

    reminder_minutes_before int,
    recurrence_rule text,
    recurrence_timezone text,
    recurrence_parent_id text,

    google_event_id text,
    source text not null default 'sway',

    completed_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    deleted_at timestamptz,

    constraint tasks_one_due_kind check (not (due_at is not null and due_date is not null)),
    constraint tasks_timed_end_requires_due check (end_at is null or (due_at is not null and end_at > due_at)),
    constraint tasks_date_end_requires_due check (end_date is null or (due_date is not null and end_date > due_date))
);

create index if not exists idx_tasks_user_updated on public.tasks (user_id, updated_at);
create index if not exists idx_tasks_user_due_at on public.tasks (user_id, due_at);
create index if not exists idx_tasks_user_due_date on public.tasks (user_id, due_date);

alter table public.tasks enable row level security;

drop policy if exists "tasks_select_own" on public.tasks;
drop policy if exists "tasks_insert_own" on public.tasks;
drop policy if exists "tasks_update_own" on public.tasks;
drop policy if exists "tasks_delete_own" on public.tasks;

create policy "tasks_select_own" on public.tasks
    for select using (auth.uid() = user_id);
create policy "tasks_insert_own" on public.tasks
    for insert with check (auth.uid() = user_id);
create policy "tasks_update_own" on public.tasks
    for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "tasks_delete_own" on public.tasks
    for delete using (auth.uid() = user_id);

create table if not exists public.user_settings (
    user_id uuid primary key references auth.users(id) on delete cascade,
    first_name text,
    last_name text,
    theme text not null default 'system',
    reminders_processed_through timestamptz,
    browser_notifications_enabled boolean not null default false,
    updated_at timestamptz not null default now()
);

alter table public.user_settings add column if not exists first_name text;
alter table public.user_settings add column if not exists last_name text;

alter table public.user_settings enable row level security;

drop policy if exists "user_settings_select_own" on public.user_settings;
drop policy if exists "user_settings_insert_own" on public.user_settings;
drop policy if exists "user_settings_update_own" on public.user_settings;
drop policy if exists "user_settings_delete_own" on public.user_settings;

create policy "user_settings_select_own" on public.user_settings
    for select using (auth.uid() = user_id);
create policy "user_settings_insert_own" on public.user_settings
    for insert with check (auth.uid() = user_id);
create policy "user_settings_update_own" on public.user_settings
    for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "user_settings_delete_own" on public.user_settings
    for delete using (auth.uid() = user_id);

create table if not exists public.google_calendar_connections (
    user_id uuid primary key references auth.users(id) on delete cascade,
    token_json jsonb,
    sync_tokens_json jsonb not null default '{}'::jsonb,
    account_email text,
    oauth_state text unique,
    updated_at timestamptz not null default now()
);

alter table public.google_calendar_connections enable row level security;

create table if not exists public.availability_shares (
    id uuid primary key,
    user_id uuid not null references auth.users(id) on delete cascade,
    token_hash text not null unique,
    snapshot jsonb not null,
    first_name text,
    creator_timezone text not null,
    created_at timestamptz not null default now(),
    expires_at timestamptz not null
);

alter table public.availability_shares add column if not exists first_name text;

create index if not exists idx_availability_shares_expires
    on public.availability_shares (expires_at);
create index if not exists idx_availability_shares_user_created
    on public.availability_shares (user_id, created_at desc);

alter table public.availability_shares enable row level security;

-- No RLS policies are intentionally defined for availability_shares. The FastAPI
-- service-role client is the only reader/writer, so public links never expose the
-- table, owner id, or token hash through Supabase's public API.

-- Optional daily cleanup when pg_cron is available in the Supabase project:
-- create extension if not exists pg_cron;
-- select cron.schedule(
--     'delete-expired-availability-shares',
--     '17 3 * * *',
--     $$delete from public.availability_shares where expires_at <= now()$$
-- );
