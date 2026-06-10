# Sway Database Map

Sway currently uses two databases:

- **Supabase Postgres** is the cloud database used by the web app, API, and desktop sync.
- **Desktop SQLite** is the desktop app's offline-first local database and sync cache.

## Supabase Postgres

```mermaid
erDiagram
    AUTH_USERS ||--o{ TASKS : owns
    AUTH_USERS ||--o| USER_SETTINGS : has
    AUTH_USERS ||--o| GOOGLE_CALENDAR_CONNECTIONS : connects
    AUTH_USERS ||--o{ AVAILABILITY_SHARES : creates

    AUTH_USERS {
        uuid id PK
        text email
        jsonb raw_user_meta_data
    }

    TASKS {
        uuid id PK
        uuid user_id FK
        text title
        text description
        text project_id
        int priority
        text status
        timestamptz due_at
        boolean has_time
        timestamptz start_at
        timestamptz end_at
        int reminder_minutes_before
        text recurrence_rule
        text recurrence_parent_id
        text google_event_id
        text source
        timestamptz completed_at
        timestamptz created_at
        timestamptz updated_at
        timestamptz deleted_at
    }

    USER_SETTINGS {
        uuid user_id PK,FK
        text first_name
        text last_name
        text theme
        timestamptz reminders_processed_through
        boolean browser_notifications_enabled
        timestamptz updated_at
    }

    GOOGLE_CALENDAR_CONNECTIONS {
        uuid user_id PK,FK
        text oauth_client_id
        text oauth_client_secret_ciphertext
        text token_ciphertext
        jsonb sync_tokens_json
        text account_email
        text oauth_state UK
        timestamptz oauth_state_created_at
        timestamptz last_synced_at
        timestamptz sync_lease_until
        text last_sync_error
        timestamptz updated_at
    }

    AVAILABILITY_SHARES {
        uuid id PK
        uuid user_id FK
        text token_hash UK
        jsonb snapshot
        text first_name
        text creator_timezone
        timestamptz created_at
        timestamptz expires_at
    }
```

### Supabase Table Purposes

| Table | Purpose | Access |
|---|---|---|
| `auth.users` | Supabase-managed accounts and authentication data. | Managed by Supabase Auth. |
| `public.tasks` | Cloud copy of Sway and imported Google Calendar tasks. | Users can access only their own rows through RLS. |
| `public.user_settings` | Per-user profile names and web settings such as theme and notification state. | Users can access only their own row through RLS. |
| `public.google_calendar_connections` | Encrypted per-user Google OAuth credentials/tokens and calendar sync state. | API service-role access only; no public RLS policies. |
| `public.availability_shares` | Frozen public availability snapshots that expire after seven days. | API service-role access only; no public RLS policies. |

All public tables referencing `auth.users` use `ON DELETE CASCADE`, so deleting an account
also deletes its cloud tasks, settings, Google connection, and availability shares.

First and last names live on `public.user_settings`; a separate profiles table is not currently needed.
New availability shares freeze only the creator's first name for their public heading.

## Desktop SQLite

```mermaid
erDiagram
    TASKS {
        text id PK
        text cloud_id
        text google_event_id
        text source
        text title
        text description
        text project_id
        integer priority
        text status
        text due_at
        integer has_time
        text start_at
        text end_at
        integer reminder_minutes_before
        text recurrence_rule
        text recurrence_parent_id
        text completed_at
        text created_at
        text updated_at
        text deleted_at
        text sync_status
        text last_synced_at
    }

    PROJECTS {
        text id PK
        text cloud_id
        text name
        text color
        text created_at
        text updated_at
        text deleted_at
        text sync_status
        text last_synced_at
    }

    SYNC_QUEUE {
        text id PK
        text entity_type
        text entity_id
        text operation
        text created_at
        text attempted_at
        integer attempts
        text error_message
    }

    SETTINGS {
        text key PK
        text value
    }
```

### SQLite Table Purposes

| Table | Purpose |
|---|---|
| `tasks` | Offline-first task cache with cloud sync metadata. |
| `projects` | Local project records. A matching Supabase projects table does not currently exist. |
| `sync_queue` | Pending or failed desktop-to-cloud synchronization operations. |
| `settings` | Local desktop key/value settings, including desktop-only configuration. |

SQLite does not currently declare foreign-key constraints between these tables. Fields such as
`tasks.project_id` and `sync_queue.entity_id` are application-managed references.

## Main Data Flows

```mermaid
flowchart LR
    Desktop[Desktop App] -->|offline reads and writes| SQLite[(Desktop SQLite)]
    SQLite <-->|task sync| Supabase[(Supabase Postgres)]
    Web[Web App] -->|authenticated requests| API[FastAPI]
    API -->|user JWT and RLS| Supabase
    API -->|service role| Private[Encrypted Google connections and availability shares]
    Private --> Supabase
    API -->|one-way import| Google[Google Calendar]
    Public[Public availability link] -->|anonymous token request| API
```

The schema sources of truth are:

- Cloud: [`supabase/schema.sql`](supabase/schema.sql)
- Desktop local: [`apps/desktop/app/db/schema.sql`](apps/desktop/app/db/schema.sql)
