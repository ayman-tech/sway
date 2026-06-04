# Sway

A desktop productivity app — **offline-first**, with multi-device cloud sync and Google Calendar import. Built with **PySide6 + SQLite + Supabase**.

Local SQLite is the source of fast, always-available app behavior; Supabase is the cloud
sync/backup layer; Google Calendar is a read-only integration — never the source of truth.

## Features

- **Tasks** with due date, optional time, and duration (end time) — create, edit, complete, delete.
- **Grouped list view** — Overdue · Today · Next 7 Days · Untimed · Later, with overdue highlighting.
- **Month calendar** — the same tasks arranged by date; click a day to see it sorted by time.
- **Completed view** — bounded to the last 30 days (older completed tasks are auto-removed).
- **Reminders** — every timed task reminds at its due time, plus an optional earlier reminder.
  Runs in the system tray with native desktop notifications and startup catch-up for missed ones.
- **Recurring tasks** — daily / weekly / every-2-weeks / monthly / yearly, ending never or on a date.
- **Multi-device cloud sync** (Supabase) — email/password account, offline-first, last-write-wins.
- **Google Calendar import** (one-way, read-only) — pulls events from all your selected calendars
  into Sway; Meet link + location are prepended to the description; events can be checked off locally.
- **Dark / light theme**, **start-at-login**, and a packaged **`Sway.app`** for macOS.

## Tech stack

| Layer | Choice |
|---|---|
| UI | PySide6 (Qt for Python) |
| Local store | SQLite (offline-first) |
| Cloud backend | Supabase (Postgres + Auth + Row-Level Security) |
| Calendar | Google Calendar API (read-only import) |
| Scheduling | QTimer-based reminder polling |
| Packaging | PyInstaller (`Sway.app`) |

## Architecture

```
        PySide6 UI  (list · calendar · completed · settings · auth)
                              │
        Services  (TaskService · ReminderService · SyncService ·
                   AuthService · GoogleCalendarService)
                              │
        Repositories  (SqliteRepo · SupabaseRepo · SettingsRepo)
              │                        │                     │
          SQLite (local)        Supabase (cloud)     Google Calendar
```

- UI never touches the database directly — it goes through services.
- All datetimes are stored in **UTC**; the UI converts to local time.
- Deletes are **soft** (`deleted_at`); every local change is marked for sync.
- Cloud sync is **last-write-wins** by a **server-set** `updated_at` (a Postgres trigger), with a
  small pull-overlap window so updates can't be missed.

## Project layout

```
app/
  ui/            windows, views, dialogs, components, theme
  services/      task / reminder / sync / auth / google calendar / recurrence
  repositories/  sqlite, supabase, settings
  models/        Task dataclass
  db/            database.py + schema.sql (local)
  notifications/ tray icon + notifier
  utils/         datetime, ids, logging, resources, autostart
  assets/styles/ dark.qss, light.qss
supabase/        schema.sql (cloud table + RLS — run once in Supabase)
packaging/       build_macos.sh, icon.icns
main.py          entry point
```

## Getting started

**Prerequisites:** Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync          # install dependencies
uv run python main.py
```

That's it for **local, offline-only** use — no account or cloud needed.

### Optional: cloud sync (Supabase)

1. Create a free project at [supabase.com](https://supabase.com).
2. **SQL Editor** → run [`supabase/schema.sql`](supabase/schema.sql) (creates the `tasks` table + RLS).
3. **Authentication → Sign In / Providers → Email** → turn **off** "Confirm email".
4. **Database → triggers** (or SQL Editor) → add a server-timestamp trigger so sync ordering uses
   the server clock:
   ```sql
   create or replace function public.set_updated_at() returns trigger as $$
   begin new.updated_at = now(); return new; end $$ language plpgsql;
   create trigger tasks_set_updated_at before insert or update on public.tasks
     for each row execute function public.set_updated_at();
   ```
5. **Project Settings → API Keys** → copy the **Project URL** and the **publishable** key into a
   `.env` in the project root (see [`.env.example`](.env.example)):
   ```
   SUPABASE_URL=https://YOURPROJECT.supabase.co
   SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
   ```
   (Credentials are also read from `~/Library/Application Support/Sway/supabase.json`, which is what
   the packaged app uses since it can't see the project `.env`.)

Restart the app → you'll get a login screen to create an account, and tasks sync across devices.

### Optional: Google Calendar import

1. In [Google Cloud Console](https://console.cloud.google.com): create a project, enable the
   **Google Calendar API**, configure the **OAuth consent screen** (add yourself as a test user),
   and create an **OAuth client ID of type "Desktop app"**.
2. In Sway: **Settings → Set up Google Calendar** → paste the Client ID + secret → authorize in the
   browser. Events from your visible calendars import as read-only tasks.

## Building the macOS app

```bash
bash packaging/build_macos.sh   # → dist/Sway.app
```

Drag `Sway.app` to `/Applications`. For distribution to *other* machines you'll need to
code-sign + notarize it with an Apple Developer ID (it runs locally without that).

## Configuration & data

- **Config:** `.env` (or env vars `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`); Google credentials
  saved via the in-app dialog.
- **Data dir:** `~/Library/Application Support/Sway/` — `sway.db`, `supabase.json`, `google.json`,
  and `logs/sway.log`. Override with `SWAY_DATA_DIR` (used by tests).

## Notes & limitations

- **macOS-focused.** The data dir and tray/notifications work cross-platform, but packaging and
  start-at-login are macOS-only here.
- **Single user per account** — no shared/collaborative tasks; concurrent whole-row edits use
  last-write-wins.
- **Google import is one-way** (Google → Sway). Sway tasks are never written back to Google.
- Completed tasks are kept for **30 days** then soft-deleted.
