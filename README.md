# Sway

Sway is a productivity app with a desktop app and a web app. The desktop app is
**offline-first**; the web app is **online-first** with a marketing landing page, Supabase auth,
FastAPI, and a Next.js dashboard. Both share task domain logic through a Python core package.

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
| Desktop UI | PySide6 (Qt for Python) |
| Web UI | Next.js + TypeScript + Tailwind |
| API | FastAPI |
| Shared logic | `packages/core` (`sway-core`) |
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
                   AuthService · centralized Google API client)
                              │
        Repositories  (SqliteRepo · SupabaseRepo · SettingsRepo)
              │                        │
          SQLite (local)        Supabase (cloud) ← FastAPI ← Google Calendar
```

- UI never touches the database directly — it goes through services.
- All datetimes are stored in **UTC**; the UI converts to local time.
- Deletes are **soft** (`deleted_at`); every local change is marked for sync.
- Cloud sync is **last-write-wins** by a **server-set** `updated_at` (a Postgres trigger), with a
  small pull-overlap window so updates can't be missed.

## Project layout

```
apps/
  desktop/                 PySide6 desktop app
    app/
      ui/                  windows, views, dialogs, components, theme
      services/            task / reminder / sync / auth / google calendar / recurrence
      repositories/        sqlite, supabase, settings
      models/              Task dataclass
      db/                  database.py + schema.sql (local)
      notifications/       tray icon + notifier
      utils/               datetime, ids, logging, resources, autostart
      assets/styles/       dark.qss, light.qss
    packaging/             build_macos.sh, icon.icns
    main.py                desktop entry point
    pyproject.toml         desktop Python dependencies
  api/                     FastAPI backend for the web app
  web/                     Next.js + TypeScript web app
packages/
  core/                    shared Python task/domain logic
supabase/                  shared cloud schema + RLS
README.md                  shared product documentation
```

## Getting started

**Prerequisites:** Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
cd apps/desktop
uv sync          # install dependencies
uv run python main.py
```

That's it for **local, offline-only** use — no account or cloud needed.

### Web app + API

Run the FastAPI backend:

```bash
cd apps/api
uv sync
uv run uvicorn api.main:app --reload
```

Run the Next.js frontend:

```bash
cd apps/web
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The first screen is the public landing page;
the CTA goes to `/auth`, and successful auth redirects to `/dashboard`.

### Optional: cloud sync (Supabase)

1. Create a free project at [supabase.com](https://supabase.com).
2. **SQL Editor** → run [`supabase/schema.sql`](supabase/schema.sql) (creates the task, settings,
   Google integration, and expiring availability-share tables + RLS).
3. **Authentication → Sign In / Providers → Email** → turn **off** "Confirm email".
4. **Project Settings → API Keys** → copy the **Project URL** and the **publishable** key into
   `apps/desktop/.env` or the shared root `.env`. You can use [`.env.example`](.env.example)
   as the template:
   ```
   SUPABASE_URL=https://YOURPROJECT.supabase.co
   SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
   SUPABASE_SERVICE_ROLE_KEY=...
   GOOGLE_CREDENTIALS_ENCRYPTION_KEY=...
   NEXT_PUBLIC_SUPABASE_URL=https://YOURPROJECT.supabase.co
   NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
   API_PUBLIC_URL=http://localhost:8000
   WEB_PUBLIC_URL=http://localhost:3000
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```
   The API service-role key is required for Google integration storage and public availability
   share links. The encryption key protects Google OAuth credentials and tokens stored in Supabase.
   `API_PUBLIC_URL` is FastAPI's public server URL and is also used by the desktop
   client; `NEXT_PUBLIC_API_URL` tells the browser where to call FastAPI; `WEB_PUBLIC_URL` tells
   FastAPI which website origin to allow and place in returned share links. Never expose the
   service-role key through a `NEXT_PUBLIC_...` variable.
   (Credentials are also read from `~/Library/Application Support/Sway/supabase.json`, which is what
   the packaged app uses since it can't see local `.env` files. Add an `api_url` field there to
   enable desktop share links.)

Restart the app → you'll get a login screen to create an account, and tasks sync across devices.

### Optional: Google Calendar import

1. Generate `GOOGLE_CREDENTIALS_ENCRYPTION_KEY` with:
   `cd apps/api && uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
2. In [Google Cloud Console](https://console.cloud.google.com): create a project, enable the
   **Google Calendar API**, configure the **OAuth consent screen** (add yourself as a test user),
   and create an **OAuth client ID of type "Web application"**.
3. Add `http://localhost:8000/integrations/google/callback` as an authorized redirect URI.
4. In web or desktop Sway Settings, paste the Client ID + secret and authorize in the browser.
   FastAPI securely stores the shared connection and imports events into Supabase.

## Building the macOS app

```bash
cd apps/desktop
bash packaging/build_macos.sh   # → dist/Sway.app
```

Drag `Sway.app` to `/Applications`. For distribution to *other* machines you'll need to
code-sign + notarize it with an Apple Developer ID (it runs locally without that).

## Configuration & data

- **Config:** `.env` (or env vars `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`,
  `API_PUBLIC_URL`); encrypted Google credentials are saved centrally through the in-app dialog.
- **Data dir:** `~/Library/Application Support/Sway/` — `sway.db`, `supabase.json`,
  and `logs/sway.log`. Override with `SWAY_DATA_DIR` (used by tests).
- **Date-model reset:** upgrading from the legacy `has_time` schema automatically resets
  local SQLite task rows. Run `supabase/reset_tasks_date_model.sql`, then rerun
  `supabase/schema.sql`, and sync Google Calendar to repopulate imported events.
- **Destructive development reset:** run `supabase/reset_all.sql`, then `supabase/schema.sql`;
  delete the desktop `sway.db` before restarting the app.

## Notes & limitations

- **macOS-focused.** The data dir and tray/notifications work cross-platform, but packaging and
  start-at-login are macOS-only here.
- **Single user per account** — no shared/collaborative tasks; concurrent whole-row edits use
  last-write-wins.
- **Google import is one-way** (Google → Sway). Sway tasks are never written back to Google.
- Completed tasks are kept for **30 days** then soft-deleted.
