Plan: Python Productivity App Like TickTick ✅

Build a desktop productivity app using:

PySide6 + SQLite + Supabase + Google Calendar API

The app should work offline-first using SQLite, then sync to Supabase and Google Calendar when internet is available.

PySide6 is the official Qt for Python binding for building desktop apps, Supabase provides a Python client for interacting with Postgres/auth/realtime, and Google provides an official Python Calendar API quickstart/client setup.  ￼

⸻

1. Core Goal 🎯

Create a desktop app that lets users:

1. Create tasks
2. Edit tasks
3. Delete tasks
4. Mark tasks as complete
5. Add due date and reminder time
6. Get local desktop notifications
7. Organize tasks into lists/projects
8. Store tasks locally using SQLite
9. Sync tasks to Supabase cloud DB
10. Sync selected tasks to Google Calendar

The most important design decision:

Local SQLite is the source of fast local app behavior.
Supabase is the cloud sync/backup layer.
Google Calendar is an external integration, not the main database.

⸻

2. Architecture Overview 🧱

┌──────────────────────────────────────┐
│              PySide6 UI              │
│  Dashboard / Task Editor / Calendar  │
└──────────────────┬───────────────────┘
                   │
┌──────────────────▼───────────────────┐
│          Application Services         │
│ TaskService / ReminderService / Sync  │
└──────────────────┬───────────────────┘
                   │
┌──────────────────▼───────────────────┐
│          Repository Layer             │
│ SQLiteRepo / SupabaseRepo / GCalRepo │
└──────────────────┬───────────────────┘
                   │
       ┌───────────┼───────────┐
       │           │           │
┌──────▼──────┐ ┌──▼────────┐ ┌▼────────────────┐
│ SQLite DB   │ │ Supabase  │ │ Google Calendar │
│ Local cache │ │ Cloud DB  │ │ Events/Reminders│
└─────────────┘ └───────────┘ └─────────────────┘

⸻

3. Recommended Folder Structure 📁

productivity_app/
│
├── app/
│   ├── main.py
│   ├── config.py
│   ├── constants.py
│   │
│   ├── ui/
│   │   ├── main_window.py
│   │   ├── task_list_view.py
│   │   ├── task_editor_dialog.py
│   │   ├── sidebar.py
│   │   ├── calendar_view.py
│   │   └── components/
│   │       ├── task_card.py
│   │       └── date_picker.py
│   │
│   ├── models/
│   │   ├── task.py
│   │   ├── project.py
│   │   ├── reminder.py
│   │   └── sync_state.py
│   │
│   ├── services/
│   │   ├── task_service.py
│   │   ├── project_service.py
│   │   ├── reminder_service.py
│   │   ├── sync_service.py
│   │   ├── google_calendar_service.py
│   │   └── auth_service.py
│   │
│   ├── repositories/
│   │   ├── sqlite_repo.py
│   │   ├── supabase_repo.py
│   │   └── google_calendar_repo.py
│   │
│   ├── db/
│   │   ├── database.py
│   │   ├── schema.sql
│   │   └── migrations/
│   │
│   ├── notifications/
│   │   ├── notifier.py
│   │   └── scheduler.py
│   │
│   ├── utils/
│   │   ├── datetime_utils.py
│   │   ├── network.py
│   │   ├── ids.py
│   │   └── logger.py
│   │
│   └── assets/
│       ├── icons/
│       └── styles/
│
├── tests/
│   ├── test_task_service.py
│   ├── test_sqlite_repo.py
│   └── test_sync_service.py
│
├── requirements.txt
├── .env.example
├── README.md
└── pyproject.toml

⸻

4. Database Design 🗄️

SQLite Tables

Use SQLite for local offline storage.

tasks

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    cloud_id TEXT,
    google_event_id TEXT,
    title TEXT NOT NULL,
    description TEXT,
    project_id TEXT,
    priority INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    due_at TEXT,
    reminder_at TEXT,
    is_recurring INTEGER DEFAULT 0,
    recurrence_rule TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT,
    sync_status TEXT NOT NULL DEFAULT 'pending',
    last_synced_at TEXT
);

projects

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    cloud_id TEXT,
    name TEXT NOT NULL,
    color TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT,
    sync_status TEXT NOT NULL DEFAULT 'pending',
    last_synced_at TEXT
);

sync_queue

CREATE TABLE IF NOT EXISTS sync_queue (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    created_at TEXT NOT NULL,
    attempted_at TEXT,
    attempts INTEGER DEFAULT 0,
    error_message TEXT
);

settings

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

⸻

5. Supabase Cloud Schema ☁️

Create matching cloud tables.

tasks

CREATE TABLE tasks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    local_id text,
    google_event_id text,
    title text NOT NULL,
    description text,
    project_id uuid,
    priority int DEFAULT 0,
    status text DEFAULT 'pending',
    due_at timestamptz,
    reminder_at timestamptz,
    is_recurring boolean DEFAULT false,
    recurrence_rule text,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    deleted_at timestamptz
);

projects

CREATE TABLE projects (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    local_id text,
    name text NOT NULL,
    color text,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    deleted_at timestamptz
);

For production, enable Row Level Security so users only access their own rows.

⸻

6. Data Model Classes 🧩

Use dataclasses first. Keep it simple.

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
@dataclass
class Task:
    id: str
    title: str
    description: Optional[str]
    project_id: Optional[str]
    priority: int
    status: str
    due_at: Optional[datetime]
    reminder_at: Optional[datetime]
    google_event_id: Optional[str]
    cloud_id: Optional[str]
    sync_status: str
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]

⸻

7. Core Services 🧠

TaskService

Responsible for business logic.

TaskService should:
- create task
- update task
- delete task using soft delete
- mark task complete
- get today tasks
- get upcoming tasks
- get overdue tasks
- add task to sync_queue
- schedule reminder if reminder_at exists

Flow:

User creates task
↓
TaskService validates data
↓
SQLiteRepo saves task
↓
ReminderService schedules reminder
↓
SyncService adds task to sync queue
↓
UI refreshes

⸻

ReminderService

Responsible for local reminders.

ReminderService should:
- load upcoming reminders from SQLite on app start
- schedule reminder jobs
- cancel reminders for completed/deleted tasks
- reschedule reminders when task reminder time changes
- trigger desktop notification

For first version, use Qt timers or APScheduler. APScheduler is good for scheduled Python jobs and supports persistent job stores if needed.

⸻

SyncService

Responsible for cloud sync.

SyncService should:
- check internet availability
- read pending sync_queue items
- push local changes to Supabase
- pull remote changes from Supabase
- resolve conflicts
- update sync_status
- retry failed sync jobs

Start simple:

Conflict rule for V1:
Latest updated_at wins.

Later improve this.

⸻

GoogleCalendarService

Responsible only for Calendar sync.

GoogleCalendarService should:
- authenticate user with Google OAuth
- create calendar event for task
- update calendar event when task changes
- delete/cancel calendar event when task is deleted
- store google_event_id in SQLite

Use Google Calendar only for tasks that have a due time or explicit calendar sync enabled.

⸻

8. Sync Logic 🔄

Local → Cloud

1. User creates/updates/deletes task locally.
2. Task is saved in SQLite.
3. Row is marked sync_status = 'pending'.
4. sync_queue item is created.
5. SyncService uploads change to Supabase.
6. On success:
   - save cloud_id
   - mark sync_status = 'synced'
   - save last_synced_at

Cloud → Local

1. SyncService asks Supabase for rows updated after last_sync_time.
2. For each cloud task:
   - if local copy does not exist, insert it
   - if local copy exists, compare updated_at
   - if cloud is newer, update local copy
   - if local is newer, keep local and push later

Google Calendar Sync

Task due/reminder changed
↓
If google_event_id exists:
    update existing Google Calendar event
Else:
    create new Google Calendar event
    save google_event_id locally and in cloud

⸻

9. Important Design Rules ⚠️

Give these rules to Codex clearly:

1. Do not make Google Calendar the main database.
2. Do not require internet for creating/editing tasks.
3. Always write to SQLite first.
4. Every local change should create a sync_queue entry.
5. Deleting a task should be soft delete using deleted_at.
6. Use UUID strings for local IDs.
7. Store all datetimes in UTC internally.
8. Convert to local timezone only in the UI.
9. Keep UI code separate from business logic.
10. Keep repository code separate from services.

⸻

10. UI Screens 🖥️

Main Window

Left sidebar:

Inbox
Today
Upcoming
Completed
Projects
Settings

Main area:

Task list

Right panel or dialog:

Task details editor

⸻

Task Editor Fields

Title
Description
Due date
Due time
Reminder time
Priority
Project/List
Sync to Google Calendar checkbox
Save button
Cancel button

⸻

11. Suggested MVP Milestones 🚀

Milestone 1: Local Task App

Codex task:

Create a PySide6 desktop app with SQLite storage.
Implement create, edit, delete, complete, and list tasks.
Use a clean architecture with ui, services, repositories, and models folders.

Features:

- Main window
- Task list
- Add task dialog
- Edit task dialog
- SQLite schema
- TaskService
- SQLiteRepo

⸻

Milestone 2: Due Dates and Views

Codex task:

Add due dates, priorities, task status, and filtered views for Inbox, Today, Upcoming, Completed, and Overdue.

Features:

- Today view
- Upcoming view
- Completed view
- Priority sorting
- Overdue highlighting

⸻

Milestone 3: Local Reminders

Codex task:

Add reminder scheduling. On app startup, load all pending reminders from SQLite and schedule desktop notifications.

Features:

- reminder_at field
- local notification
- reschedule on edit
- cancel on complete/delete

⸻

Milestone 4: Supabase Sync

Codex task:

Add Supabase integration using a repository class. Implement local-first sync with a sync_queue table. Push pending local task changes to Supabase and pull cloud changes into SQLite.

Features:

- Supabase auth config
- SupabaseRepo
- SyncService
- sync_queue
- cloud_id mapping
- last_synced_at

⸻

Milestone 5: Google Calendar Sync

Codex task:

Add Google Calendar integration. Allow a task with a due date to be synced as a Google Calendar event. Store google_event_id locally and update/delete the event when the task changes.

Features:

- Google OAuth
- create event
- update event
- delete event
- store google_event_id

⸻

Milestone 6: Polish

Codex task:

Improve UI styling, add system tray behavior, app settings, logging, error messages, and packaging with PyInstaller.

Features:

- tray icon
- minimize to tray
- start on login optional
- dark/light theme
- PyInstaller build

⸻

12. First Codex Prompt You Can Paste 🧾

Use this as your first prompt:

Build a Python desktop productivity app using PySide6 and SQLite.
Architecture requirements:
- Use clean folder structure: ui, models, services, repositories, db, notifications, utils.
- Use SQLite as the local offline-first database.
- Do not put database logic directly in UI files.
- Do not put business logic directly in UI files.
- Use dataclasses for models.
- Use UUID strings for task IDs.
- Store datetime values in UTC ISO format.
- Use soft delete with deleted_at instead of hard delete.
MVP features:
1. Main window with sidebar views:
   - Inbox
   - Today
   - Upcoming
   - Completed
2. Task list in the main area.
3. Add Task button.
4. Add/edit task dialog with:
   - title
   - description
   - due date/time
   - reminder date/time
   - priority
5. SQLite table for tasks.
6. TaskService for create/update/delete/complete operations.
7. SQLiteTaskRepository for database operations.
8. UI should refresh after task changes.
Create all necessary files and provide runnable code.

⸻

13. Second Codex Prompt: Reminders 🔔

Add local reminder support to the existing PySide6 productivity app.
Requirements:
- Add ReminderService.
- On app startup, load all pending tasks with reminder_at in the future.
- Schedule reminders.
- Show desktop notification when reminder time arrives.
- If a task is completed or deleted, cancel its reminder.
- If a task reminder time is edited, reschedule it.
- Keep reminder logic outside the UI layer.

⸻

14. Third Codex Prompt: Supabase Sync ☁️

Add cloud sync using Supabase.
Requirements:
- Add SupabaseTaskRepository.
- Add SyncService.
- Add sync_queue table to SQLite.
- Every local create/update/delete should add a sync_queue item.
- SyncService should push pending local changes to Supabase.
- Store Supabase row ID in tasks.cloud_id.
- Add last_synced_at and sync_status updates.
- Implement simple conflict resolution: latest updated_at wins.
- App must still work without internet.
- Show sync status in the UI.

⸻

15. Fourth Codex Prompt: Google Calendar 📅

Add Google Calendar integration.
Requirements:
- Add GoogleCalendarService.
- Add Google OAuth setup using official Google Calendar Python client.
- Add a "Sync to Google Calendar" checkbox in the task editor.
- If enabled and task has due_at, create a Google Calendar event.
- Save google_event_id in SQLite.
- If task is edited, update the existing Google Calendar event.
- If task is deleted, delete or cancel the Google Calendar event.
- Do not use Google Calendar as the main database.
- Keep all Google Calendar code outside the UI layer.

⸻

16. Final Recommended Build Order 🧭

Do not start with cloud sync first.

Best order:

1. Local SQLite task app
2. Due dates and task filtering
3. Local reminders
4. System tray/background behavior
5. Supabase sync
6. Google Calendar sync
7. Recurring tasks
8. Mobile/web companion later

⸻

My recommendation for your first version 🎯

Make this first:

A PySide6 desktop task manager with SQLite, due dates, reminders, Today/Upcoming views, and clean architecture.

Then add:

Supabase sync

Then add:

Google Calendar sync

This way, even if cloud/calendar becomes complicated, you still have a working app.