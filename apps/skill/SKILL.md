---
name: sway
description: |
  Sway task manager API integration. Read and manage tasks via direct HTTP calls.
  Use this skill when users want to list, create, update, complete, or delete tasks in Sway.
  Requires a valid Sway API key stored in config.json alongside this skill.
metadata:
  author: sway
  version: "1.0"
  clawdbot:
    emoji: ✓
---

# Sway

Access the Sway task manager API to read and manage tasks. All operations use your personal API key — no OAuth required.

## Configuration

Fill in your API key in `config.json` (distributed alongside this file):

```json
{
  "sway_api_key": "sway_your_key_here"
}
```

### Getting Your API Key

1. Open the Sway web app at [https://sway.aymanai.com](https://sway.aymanai.com) or the desktop app
2. Go to **Settings**
3. Under **Sway API Key**, click **Generate key**
4. Copy the key and paste it into `config.json`

## Base URL

All requests go to:

```
http://localhost:8000/docs
```

## Authentication

All requests require your Sway API key in the Authorization header:

```
Authorization: Bearer <sway_api_key from config.json>
```

## Quick Start

```bash
# Get your tasks grouped by timeline
python <<'EOF'
import urllib.request, json, pathlib

cfg = json.loads(pathlib.Path("config.json").read_text())
API_URL = "https://api.sway.aymanai.com"
req = urllib.request.Request(f"{API_URL}/tasks/groups?timezone_name=America/New_York")
req.add_header("Authorization", f"Bearer {cfg['sway_api_key']}")
print(json.dumps(json.load(urllib.request.urlopen(req)), indent=2))
EOF
```

## Security & Permissions

- Access is scoped to tasks belonging to the authenticated user only.
- **All write operations (create, update, complete, delete) require explicit user approval.** Before executing any write call, confirm the target task and intended effect with the user.

## API Reference

### Task Operations

#### Get Tasks Grouped by Timeline

```
GET /tasks/groups?timezone_name=America/New_York
```

Returns tasks bucketed into **Overdue**, **Today**, **Next 7 Days**, **Untimed**, and **Later** (capped at 30 days out). Use this as the primary endpoint — it gives the agent a focused, time-bounded view without flooding context.

```bash
python <<'EOF'
import urllib.request, json, pathlib

cfg = json.loads(pathlib.Path("config.json").read_text())
API_URL = "https://api.sway.aymanai.com"
tz = "America/New_York"
req = urllib.request.Request(f"{API_URL}/tasks/groups?timezone_name={tz}")
req.add_header("Authorization", f"Bearer {cfg['sway_api_key']}")
print(json.dumps(json.load(urllib.request.urlopen(req)), indent=2))
EOF
```

**Response:**
```json
[
  { "label": "Overdue", "overdue": true, "has_more": false, "tasks": [...] },
  { "label": "Today", "overdue": false, "has_more": false, "tasks": [...] },
  { "label": "Next 7 Days", "overdue": false, "has_more": false, "tasks": [...] },
  { "label": "Later", "overdue": false, "has_more": true, "tasks": [...tasks due within 30 days...] }
]
```

`has_more: true` on the **Later** group means there are additional tasks due beyond 30 days. Use `GET /tasks/calendar` with a specific date range to fetch those if needed.

---

#### Get Tasks in Date Range (Calendar)

```
GET /tasks/calendar?start=<datetime>&end=<datetime>&start_date=<date>&end_date=<date>
```

```bash
python <<'EOF'
import urllib.request, json, pathlib

cfg = json.loads(pathlib.Path("config.json").read_text())
API_URL = "https://api.sway.aymanai.com"
params = "start=2026-06-11T00:00:00Z&end=2026-06-18T23:59:59Z&start_date=2026-06-11&end_date=2026-06-18"
req = urllib.request.Request(f"{API_URL}/tasks/calendar?{params}")
req.add_header("Authorization", f"Bearer {cfg['sway_api_key']}")
print(json.dumps(json.load(urllib.request.urlopen(req)), indent=2))
EOF
```

---

#### Create Task

```
POST /tasks
Content-Type: application/json
```

```bash
python <<'EOF'
import urllib.request, json, pathlib

cfg = json.loads(pathlib.Path("config.json").read_text())
API_URL = "https://api.sway.aymanai.com"
data = json.dumps({
    "title": "Review pull request",
    "description": "Check the auth changes",
    "due_date": "2026-06-15"
}).encode()
req = urllib.request.Request(f"{API_URL}/tasks", data=data, method="POST")
req.add_header("Authorization", f"Bearer {cfg['sway_api_key']}")
req.add_header("Content-Type", "application/json")
print(json.dumps(json.load(urllib.request.urlopen(req)), indent=2))
EOF
```

**Body fields:**

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | **Required.** Task title |
| `description` | string | Optional notes |
| `due_at` | string | ISO 8601 datetime with timezone for a timed task, e.g. `2026-06-15T14:00:00Z` |
| `due_date` | string | ISO 8601 date for an all-day task, e.g. `2026-06-15`. Mutually exclusive with `due_at` |
| `end_at` | string | End datetime for timed tasks (used with `due_at`) |
| `end_date` | string | End date for multi-day all-day tasks (used with `due_date`) |
| `reminder_minutes_before` | integer | Minutes before due time to send a reminder |

---

#### Update Task

```
PATCH /tasks/{task_id}
Content-Type: application/json
```

All fields are optional — only send what needs to change.

```bash
python <<'EOF'
import urllib.request, json, pathlib

cfg = json.loads(pathlib.Path("config.json").read_text())
API_URL = "https://api.sway.aymanai.com"
task_id = "TASK_UUID_HERE"
data = json.dumps({"title": "Updated title", "due_date": "2026-06-20"}).encode()
req = urllib.request.Request(f"{API_URL}/tasks/{task_id}", data=data, method="PATCH")
req.add_header("Authorization", f"Bearer {cfg['sway_api_key']}")
req.add_header("Content-Type", "application/json")
print(json.dumps(json.load(urllib.request.urlopen(req)), indent=2))
EOF
```

> **Note:** Tasks imported from Google Calendar (`"source": "google"`) are read-only. Only `reminder_minutes_before` can be changed on those.

---

#### Complete Task

```
POST /tasks/{task_id}/complete
```

Marks the task as completed. For recurring tasks, this completes the current occurrence and advances the series automatically.

```bash
python <<'EOF'
import urllib.request, json, pathlib

cfg = json.loads(pathlib.Path("config.json").read_text())
API_URL = "https://api.sway.aymanai.com"
task_id = "TASK_UUID_HERE"
req = urllib.request.Request(f"{API_URL}/tasks/{task_id}/complete", data=b"", method="POST")
req.add_header("Authorization", f"Bearer {cfg['sway_api_key']}")
print(json.dumps(json.load(urllib.request.urlopen(req)), indent=2))
EOF
```

---

#### Uncomplete Task

```
POST /tasks/{task_id}/uncomplete
```

```bash
python <<'EOF'
import urllib.request, json, pathlib

cfg = json.loads(pathlib.Path("config.json").read_text())
API_URL = "https://api.sway.aymanai.com"
task_id = "TASK_UUID_HERE"
req = urllib.request.Request(f"{API_URL}/tasks/{task_id}/uncomplete", data=b"", method="POST")
req.add_header("Authorization", f"Bearer {cfg['sway_api_key']}")
print(json.dumps(json.load(urllib.request.urlopen(req)), indent=2))
EOF
```

---

#### Delete Task

```
DELETE /tasks/{task_id}
```

```bash
python <<'EOF'
import urllib.request, json, pathlib

cfg = json.loads(pathlib.Path("config.json").read_text())
API_URL = "https://api.sway.aymanai.com"
task_id = "TASK_UUID_HERE"
req = urllib.request.Request(f"{API_URL}/tasks/{task_id}", method="DELETE")
req.add_header("Authorization", f"Bearer {cfg['sway_api_key']}")
urllib.request.urlopen(req)
print("Deleted.")
EOF
```

---

### Completed Tasks

```
GET /tasks/completed
```

Returns completed tasks grouped by completion date. Tasks older than 30 days are automatically purged.

```bash
python <<'EOF'
import urllib.request, json, pathlib

cfg = json.loads(pathlib.Path("config.json").read_text())
API_URL = "https://api.sway.aymanai.com"
req = urllib.request.Request(f"{API_URL}/tasks/completed")
req.add_header("Authorization", f"Bearer {cfg['sway_api_key']}")
print(json.dumps(json.load(urllib.request.urlopen(req)), indent=2))
EOF
```

---

## Task Fields Reference

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | UUID |
| `title` | string | Task title |
| `description` | string \| null | Notes |
| `status` | string | `"pending"` or `"completed"` |
| `due_at` | string \| null | ISO 8601 datetime (timed task) |
| `due_date` | string \| null | ISO 8601 date (all-day task) |
| `end_at` | string \| null | End datetime |
| `end_date` | string \| null | End date |
| `reminder_minutes_before` | integer \| null | Reminder offset in minutes |
| `recurrence_rule` | string \| null | iCalendar RRULE string |
| `source` | string | `"sway"` (user-created) or `"google"` (imported, read-only) |
| `completed_at` | string \| null | When the task was completed |
| `created_at` | string | ISO 8601 datetime |
| `updated_at` | string | ISO 8601 datetime |

## Error Handling

| Status | Meaning |
|--------|---------|
| 400 | Invalid request (e.g. `due_at` and `due_date` both set) |
| 401 | Missing or invalid API key |
| 403 | API key used to manage API keys (use session token instead) |
| 404 | Task not found |
| 503 | API server unavailable |

## Notes

- `due_at` and `due_date` are mutually exclusive — use one or the other per task.
- Tasks with `"source": "google"` are imported read-only from Google Calendar. Only `reminder_minutes_before` can be patched; other fields are ignored.
- Recurring tasks: completing a recurring task via `/complete` advances the series to the next occurrence automatically.
- Completed tasks are retained for 30 days, then purged automatically.
- The `/tasks/groups` endpoint requires a valid IANA timezone name (e.g. `America/New_York`, `Europe/London`, `Asia/Tokyo`).
