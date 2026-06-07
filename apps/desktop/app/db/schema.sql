-- Sway local SQLite schema (offline-first cache; Supabase is the cloud source of truth).
-- All datetimes are UTC ISO-8601 strings. IDs are UUID strings. Deletes are soft.

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    cloud_id TEXT,
    google_event_id TEXT,
    source TEXT NOT NULL DEFAULT 'sway',

    title TEXT NOT NULL,
    description TEXT,
    project_id TEXT,
    priority INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',

    due_at TEXT,
    due_date TEXT,
    start_at TEXT,
    end_at TEXT,
    end_date TEXT,

    reminder_minutes_before INTEGER,

    recurrence_rule TEXT,
    recurrence_timezone TEXT,
    recurrence_parent_id TEXT,

    completed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT,

    sync_status TEXT NOT NULL DEFAULT 'pending',
    last_synced_at TEXT,

    CHECK (NOT (due_at IS NOT NULL AND due_date IS NOT NULL)),
    CHECK (end_at IS NULL OR (due_at IS NOT NULL AND end_at > due_at)),
    CHECK (end_date IS NULL OR (due_date IS NOT NULL AND end_date > due_date))
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_due_at ON tasks(due_at);
CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date);
CREATE INDEX IF NOT EXISTS idx_tasks_deleted_at ON tasks(deleted_at);

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

CREATE TABLE IF NOT EXISTS sync_queue (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    created_at TEXT NOT NULL,
    attempted_at TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
