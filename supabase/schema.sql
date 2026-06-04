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
    has_time boolean not null default false,
    start_at timestamptz,
    end_at timestamptz,

    reminder_minutes_before int,
    recurrence_rule text,
    recurrence_parent_id text,

    google_event_id text,
    source text not null default 'sway',

    completed_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    deleted_at timestamptz
);

create index if not exists idx_tasks_user_updated on public.tasks (user_id, updated_at);

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
