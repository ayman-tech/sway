"""FastAPI application for Sway web."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from api.auth import CurrentUser, get_current_user
from api.availability_shares import create_share, get_share
from api.config import get_settings
from api.google_integration import (
    connect_url,
    disconnect,
    google_status,
    oauth_callback,
    sync_google,
)
from api.schemas import (
    AvailabilityShareCreate,
    AvailabilityShareCreatedOut,
    AvailabilityShareOut,
    GoogleConnectUrlOut,
    GoogleStatusOut,
    GoogleSyncOut,
    MeOut,
    ReminderOut,
    SettingsOut,
    SettingsUpdate,
    TaskCreate,
    TaskGroupOut,
    TaskOut,
    TaskUpdate,
)
from api.settings import get_user_settings, update_user_settings
from api.tasks import (
    TaskStore,
    calendar_for,
    complete_task,
    completed_for,
    create_task,
    delete_task,
    groups_for,
    skip_occurrence,
    task_out,
    uncomplete_task,
    update_task,
)
from sway_core.datetime_utils import from_iso, utc_now
from sway_core.reminders import reminder_events_between

app = FastAPI(title="Sway API")

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_public_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"ok": "true"}


@app.get("/auth/me", response_model=MeOut)
def me(user: CurrentUser = Depends(get_current_user)) -> MeOut:
    return MeOut(id=user.id, email=user.email)


@app.get("/tasks", response_model=list[TaskOut])
def list_tasks(user: CurrentUser = Depends(get_current_user)) -> list[TaskOut]:
    return [task_out(task) for task in TaskStore(user).list_active()]


@app.post("/tasks", response_model=TaskOut)
def post_task(payload: TaskCreate, user: CurrentUser = Depends(get_current_user)) -> TaskOut:
    return task_out(create_task(user, payload))


@app.patch("/tasks/{task_id}", response_model=TaskOut)
def patch_task(task_id: str, payload: TaskUpdate, user: CurrentUser = Depends(get_current_user)) -> TaskOut:
    return task_out(update_task(user, task_id, payload))


@app.delete("/tasks/{task_id}", status_code=204)
def remove_task(task_id: str, user: CurrentUser = Depends(get_current_user)) -> None:
    delete_task(user, task_id)


@app.post("/tasks/{task_id}/complete", response_model=TaskOut)
def post_complete(task_id: str, user: CurrentUser = Depends(get_current_user)) -> TaskOut:
    return task_out(complete_task(user, task_id))


@app.post("/tasks/{task_id}/uncomplete", response_model=TaskOut)
def post_uncomplete(task_id: str, user: CurrentUser = Depends(get_current_user)) -> TaskOut:
    return task_out(uncomplete_task(user, task_id))


@app.post("/tasks/{task_id}/skip-occurrence", status_code=204)
def post_skip(task_id: str, user: CurrentUser = Depends(get_current_user)) -> None:
    skip_occurrence(user, task_id)


@app.get("/tasks/groups", response_model=list[TaskGroupOut])
def get_groups(user: CurrentUser = Depends(get_current_user)) -> list[TaskGroupOut]:
    return [
        TaskGroupOut(label=group.label, overdue=group.overdue, tasks=[task_out(t) for t in group.tasks])
        for group in groups_for(user)
    ]


@app.get("/tasks/completed", response_model=list[TaskGroupOut])
def get_completed(user: CurrentUser = Depends(get_current_user)) -> list[TaskGroupOut]:
    return [
        TaskGroupOut(label=group.label, overdue=group.overdue, tasks=[task_out(t) for t in group.tasks])
        for group in completed_for(user)
    ]


@app.get("/tasks/calendar", response_model=list[TaskOut])
def get_calendar(start: datetime, end: datetime, user: CurrentUser = Depends(get_current_user)) -> list[TaskOut]:
    return [task_out(task) for task in calendar_for(user, start, end)]


@app.post("/availability-shares", response_model=AvailabilityShareCreatedOut)
def post_availability_share(
    payload: AvailabilityShareCreate,
    user: CurrentUser = Depends(get_current_user),
) -> AvailabilityShareCreatedOut:
    return create_share(user, payload)


@app.get("/availability-shares/{token}", response_model=AvailabilityShareOut)
def get_availability_share(token: str) -> AvailabilityShareOut:
    return get_share(token)


@app.get("/settings", response_model=SettingsOut)
def get_settings_endpoint(user: CurrentUser = Depends(get_current_user)) -> SettingsOut:
    return get_user_settings(user)


@app.patch("/settings", response_model=SettingsOut)
def patch_settings(payload: SettingsUpdate, user: CurrentUser = Depends(get_current_user)) -> SettingsOut:
    return update_user_settings(user, payload)


@app.get("/reminders/due", response_model=list[ReminderOut])
def due_reminders(since: str | None = None, user: CurrentUser = Depends(get_current_user)) -> list[ReminderOut]:
    start = from_iso(since) or (utc_now() - timedelta(minutes=1))
    end = utc_now() + timedelta(days=1)
    events = [
        event for event in reminder_events_between(TaskStore(user).list_active(), start, end)
        if start < event.fire_at <= utc_now()
    ]
    return [
        ReminderOut(
            fire_at=event.fire_at,
            occurrence=event.occurrence,
            kind=event.kind,
            task=task_out(event.task),
        )
        for event in sorted(events, key=lambda e: e.fire_at)
    ]


@app.get("/integrations/google/status", response_model=GoogleStatusOut)
def get_google_status(user: CurrentUser = Depends(get_current_user)) -> GoogleStatusOut:
    connected, account = google_status(user)
    return GoogleStatusOut(connected=connected, account=account)


@app.get("/integrations/google/connect-url", response_model=GoogleConnectUrlOut)
def get_google_connect_url(user: CurrentUser = Depends(get_current_user)) -> GoogleConnectUrlOut:
    return GoogleConnectUrlOut(url=connect_url(user))


@app.get("/integrations/google/callback")
def google_callback(code: str, state: str):
    return RedirectResponse(oauth_callback(code, state))


@app.post("/integrations/google/sync", response_model=GoogleSyncOut)
def post_google_sync(user: CurrentUser = Depends(get_current_user)) -> GoogleSyncOut:
    return GoogleSyncOut(imported=sync_google(user))


@app.delete("/integrations/google", status_code=204)
def delete_google(user: CurrentUser = Depends(get_current_user)) -> None:
    disconnect(user)
