"""Single lightweight push scheduler. Run with `python -m api.push_worker`."""
from __future__ import annotations

import logging
import signal
import threading
import time
from collections import Counter
from datetime import timedelta
from uuid import uuid4

from sway_core.datetime_utils import from_iso, to_iso, utc_now
from sway_core.reminders import reminder_events_between

from api.push import configured, send_push
from api.supabase_clients import admin_client, close_supabase_clients
from api.tasks import task_from_row

logger = logging.getLogger("uvicorn.error")
PAGE_SIZE = 100
CATCH_UP = timedelta(minutes=10)


def pages(query_factory):
    """Keyset pagination avoids Supabase row limits and offset deletion skips."""
    after = None
    while True:
        query = query_factory().order("id").limit(PAGE_SIZE)
        if after:
            query = query.gt("id", after)
        rows = query.execute().data or []
        if not rows:
            return
        yield rows
        after = rows[-1]["id"]


class PushWorker:
    def __init__(self, client=None, stop=None):
        self.client = client if client is not None else admin_client()
        self.owner = str(uuid4())
        self.stop = stop if stop is not None else threading.Event()
        self.lease_checked = 0.0
        self.last_cleanup = 0.0

    def lease(self, force=False):
        if self.stop.is_set():
            return False
        if not force and time.monotonic() - self.lease_checked < 20:
            return True
        acquired = self.client.rpc("acquire_push_lease", {"p_owner": self.owner}).execute().data
        if acquired:
            self.lease_checked = time.monotonic()
        return bool(acquired)

    def finish(self, delivery, status, **fields):
        # An old attempt must never overwrite a newer claim after a long pause.
        self.client.table("push_deliveries").update({"status": status, **fields}).eq(
            "id", delivery["id"]
        ).eq("attempts", delivery["attempts"]).execute()

    def deliver(self, delivery, counts):
        claimed = self.client.rpc("claim_push_delivery", {"p_id": delivery["id"]}).execute().data
        if not claimed:
            return
        delivery = claimed[0]
        subscriptions = self.client.table("push_subscriptions").select("*").eq("id", delivery["subscription_id"]).execute().data
        if not subscriptions:
            return
        subscription = subscriptions[0]
        tasks = self.client.table("tasks").select("*").eq("id", delivery["task_id"]).eq("user_id", subscription["user_id"]).execute().data
        fire = from_iso(delivery["fire_at"])
        occurrence = from_iso(delivery["occurrence"])
        now = utc_now()
        event = None
        if tasks and fire >= now - CATCH_UP and fire >= from_iso(subscription["created_at"]):
            try:
                task = task_from_row(tasks[0])
                event = next((e for e in reminder_events_between([task], fire, fire) if e.occurrence == occurrence), None)
            except (ValueError, TypeError, OverflowError):
                self.finish(delivery, "cancelled")
                counts["invalid_task"] += 1
                return
            if event and task.is_recurring:
                # Desktop sync may store a skipped/completed occurrence as a child.
                children = self.client.table("tasks").select("id").eq("user_id", subscription["user_id"]).eq(
                    "recurrence_parent_id", task.id
                ).eq("due_at", to_iso(occurrence)).limit(1).execute().data
                if children:
                    event = None
        if not event:
            self.finish(delivery, "cancelled")
            counts["cancelled"] += 1
            return
        if not self.lease():
            return
        ttl = int((fire + CATCH_UP - utc_now()).total_seconds())
        if ttl <= 0:
            self.finish(delivery, "cancelled")
            return
        # Sequential sends intentionally keep concurrency at one on small VMs.
        outcome, delay = send_push(subscription, {
            "title": event.task.title[:160], "body": "Due now" if event.kind == "due" else "Upcoming",
            "tag": f"sway-{delivery['id']}", "expires_at": to_iso(fire + CATCH_UP),
        }, ttl)
        counts[outcome] += 1
        if outcome == "expired":
            self.client.table("push_subscriptions").delete().eq("id", subscription["id"]).execute()
        elif outcome == "accepted":
            self.finish(delivery, "accepted", accepted_at=to_iso(utc_now()))
        elif outcome == "retry":
            retry_at = utc_now() + timedelta(seconds=max(delay, min(300, 60 * 2 ** min(delivery["attempts"] - 1, 3))))
            self.finish(delivery, "pending" if retry_at < fire + CATCH_UP else "failed", next_retry_at=to_iso(retry_at))
        else:
            self.finish(delivery, "failed")

    def tick(self):
        start = time.monotonic()
        counts = Counter()
        if not self.lease(force=True):
            logger.info("push heartbeat lease=standby")
            return
        now = utc_now()
        for subscriptions in pages(lambda: self.client.table("push_subscriptions").select("*")):
            # Page-local grouping avoids unbounded memory. Only subscribed users are read.
            users: dict[str, list[dict]] = {}
            for subscription in subscriptions:
                users.setdefault(subscription["user_id"], []).append(subscription)
            for user_id, devices in users.items():
                if not self.lease():
                    return
                for rows in pages(lambda: self.client.table("tasks").select("*").eq("user_id", user_id).eq(
                    "status", "pending"
                ).is_("deleted_at", "null").not_.is_("due_at", "null")):
                    if not self.lease():
                        return
                    for row in rows:
                        try:
                            events = reminder_events_between([task_from_row(row)], now - CATCH_UP, now)
                        except (ValueError, OverflowError, TypeError):
                            counts["invalid_task"] += 1
                            continue
                        for event in events:
                            for subscription in devices:
                                if event.fire_at < from_iso(subscription["created_at"]):
                                    continue
                                counts["eligible"] += 1
                                identity = {
                                    "subscription_id": subscription["id"], "task_id": event.task.id,
                                    "occurrence": to_iso(event.occurrence), "fire_at": to_iso(event.fire_at),
                                }
                                self.client.table("push_deliveries").upsert(identity, on_conflict="subscription_id,task_id,occurrence,fire_at", ignore_duplicates=True).execute()
        # Also process retries of events whose tasks have since changed: deliver()
        # revalidates them and marks obsolete work cancelled.
        for rows in pages(lambda: self.client.table("push_deliveries").select("*").in_(
            "status", ["pending", "sending"]
        ).gte("fire_at", to_iso(utc_now() - CATCH_UP)).lte("next_retry_at", to_iso(utc_now()))):
            for delivery in rows:
                if not self.lease():
                    return
                self.deliver(delivery, counts)
        if time.monotonic() - self.last_cleanup >= 86400:
            self.client.rpc("cleanup_push_deliveries").execute()
            self.last_cleanup = time.monotonic()
        logger.info("push heartbeat duration_ms=%.1f counts=%s", (time.monotonic() - start) * 1000, dict(counts))


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # HTTPX's INFO access logs include database filters/identifiers. Keep only
    # our sanitized counters and exception categories in the worker journal.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if not configured():
        logger.error("push disabled category=missing_configuration")
        return
    worker = PushWorker()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: worker.stop.set())
    try:
        while not worker.stop.is_set():
            started = time.monotonic()
            try:
                worker.tick()
            except Exception as exc:
                logger.warning("push cycle_failed type=%s", type(exc).__name__)
            worker.stop.wait(max(1, 60 - (time.monotonic() - started)))
    finally:
        try:
            worker.client.table("push_worker_lease").delete().eq("name", "scheduler").eq("owner", worker.owner).execute()
        finally:
            close_supabase_clients()


if __name__ == "__main__":
    main()
