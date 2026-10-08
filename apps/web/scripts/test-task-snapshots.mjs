import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";
import { IDBFactory } from "fake-indexeddb";
import { beginSnapshotMutation, claimSnapshotOwner, finishSnapshotMutation, loadTaskSnapshot,
  quarantineSnapshots, readSnapshotTicket, saveTaskSnapshot, setSnapshotPreference,
  validSnapshot, SNAPSHOT_TTL, SNAPSHOT_LIMIT } from "../lib/task-snapshots.ts";
import { withDeadline } from "../lib/request-deadline.ts";
import { formatLastSync, localDay, regroupSavedTasks } from "../lib/task-view.ts";

beforeEach(() => {
  globalThis.indexedDB = new IDBFactory();
  const values = new Map();
  Object.defineProperty(globalThis, "localStorage", { configurable: true, value: {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  } });
});

const task = {
  id: "task", title: "Example", description: null, project_id: null,
  priority: 0, status: "pending", due_at: null, due_date: null, start_at: null,
  end_at: null, end_date: null, reminder_minutes_before: null, recurrence_rule: null,
  recurrence_timezone: null, recurrence_parent_id: null, google_event_id: null,
  source: "sway", completed_at: null, created_at: "2026-10-01T00:00:00Z",
  updated_at: "2026-10-01T00:00:00Z", deleted_at: null, is_preview: false,
};
const groups = [{ label: "Today", overdue: false, tasks: [task], has_more: false }];
const snapshot = () => ({ version: 1, userId: "a", timezone: "UTC", fetchedAt: Date.now(), groups });

test("saved tasks regroup against today without changing the saved response", () => {
  const original = [{ label: "Today", overdue: false, tasks: [
    { ...task, id: "yesterday", due_date: "2026-10-06" },
    { ...task, id: "today", due_date: "2026-10-07" },
    { ...task, id: "week-end", due_date: "2026-10-14" },
    { ...task, id: "later", due_date: "2026-10-15" },
    { ...task, id: "untimed" },
  ] }];
  const before = structuredClone(original);
  const result = regroupSavedTasks(original, "2026-10-07", "America/New_York");
  assert.deepEqual(result.map((group) => [group.label, group.tasks[0].id]), [
    ["Overdue", "yesterday"], ["Today", "today"], ["Next 7 Days", "week-end"], ["Untimed", "untimed"], ["Later", "later"],
  ]);
  assert.equal(result[0].overdue, true);
  assert.deepEqual(original, before);
});
test("timed tasks use local dates; date-only tasks never shift across timezones", () => {
  const input = [{ label: "Today", overdue: false, tasks: [
    { ...task, id: "utc-today-local-yesterday", due_at: "2026-10-07T01:00:00Z" },
    { ...task, id: "date-only", due_date: "2026-10-07" },
    { ...task, id: "earlier-today", due_at: "2026-10-07T04:00:00Z" },
  ] }];
  const result = regroupSavedTasks(input, "2026-10-07", "America/New_York");
  assert.equal(result[0].tasks[0].id, "utc-today-local-yesterday");
  assert.deepEqual(result[1].tasks.map((item) => item.id), ["earlier-today", "date-only"]);
});
test("calendar-day week boundary survives DST and year rollover", () => {
  const group = (dates) => [{ label: "Later", overdue: false, tasks: dates.map((due_date) => ({ ...task, due_date })) }];
  const dst = regroupSavedTasks(group(["2026-11-07", "2026-11-08"]), "2026-10-31", "America/New_York");
  assert.deepEqual(dst.map((item) => item.label), ["Next 7 Days", "Later"]);
  const year = regroupSavedTasks(group(["2027-01-06", "2027-01-07"]), "2026-12-30", "UTC");
  assert.deepEqual(year.map((item) => item.label), ["Next 7 Days", "Later"]);
});
test("sorts timed tasks chronologically and untimed tasks newest-first", () => {
  const input = [{ label: "old", overdue: false, tasks: [
    { ...task, id: "late", due_at: "2026-10-07T16:00:00Z" },
    { ...task, id: "early", due_at: "2026-10-07T08:00:00Z" },
    { ...task, id: "old" },
    { ...task, id: "new", created_at: "2026-10-06T00:00:00Z" },
  ] }];
  const result = regroupSavedTasks(input, "2026-10-07", "UTC");
  assert.deepEqual(result[0].tasks.map((item) => item.id), ["early", "late"]);
  assert.deepEqual(result[1].tasks.map((item) => item.id), ["new", "old"]);
});
test("retains known recurring previews without generating new occurrences", () => {
  const input = [{ label: "Today", overdue: false, tasks: [
    { ...task, due_date: "2026-10-06", recurrence_rule: "FREQ=DAILY" },
    { ...task, due_date: "2026-10-07", recurrence_rule: "FREQ=DAILY", is_preview: true },
  ] }];
  const result = regroupSavedTasks(input, "2026-10-07", "UTC");
  assert.equal(result.flatMap((group) => group.tasks).length, 2);
  assert.equal(result[1].tasks[0].is_preview, true);
  assert.deepEqual(regroupSavedTasks([], "2026-10-07", "UTC"), []);
});
test("formats last sync with explicit local DD/MM/YYYY and 24-hour seconds", () => {
  assert.equal(formatLastSync(Date.parse("2026-10-07T13:30:15Z"), "America/New_York"), "07/10/2026 09:30:15");
  assert.equal(formatLastSync(Date.parse("2026-10-07T00:00:00Z"), "UTC"), "07/10/2026 00:00:00");
  assert.equal(localDay(new Date("2026-10-07T01:00:00Z"), "America/New_York"), "2026-10-06");
});
async function seed() {
  await claimSnapshotOwner("a");
  const ticket = await readSnapshotTicket("a");
  assert.ok(ticket);
  assert.equal(await saveTaskSnapshot(ticket, "UTC", groups, Date.now()), true);
  return ticket;
}

test("validates schema, size, timestamp, account and timezone", () => {
  const value = snapshot();
  assert.ok(validSnapshot(value, "a", "UTC"));
  assert.equal(validSnapshot(value, "b", "UTC"), null);
  assert.equal(validSnapshot(value, "a", "America/New_York"), null);
  assert.equal(validSnapshot({ ...value, version: 2 }, "a", "UTC"), null);
  assert.equal(validSnapshot({ ...value, token: "not permitted" }, "a", "UTC"), null);
  assert.equal(validSnapshot({ ...value, fetchedAt: Date.now() + 60_000 }, "a", "UTC"), null);
  assert.equal(validSnapshot({ ...value, fetchedAt: Date.now() - SNAPSHOT_TTL }, "a", "UTC"), null);
  assert.equal(validSnapshot({ ...value, groups: [{ label: "x".repeat(SNAPSHOT_LIMIT), overdue: false, tasks: [] }] }, "a", "UTC"), null);
});
test("stores only a valid account-scoped snapshot; repeated opening retains it", async () => {
  await seed();
  await claimSnapshotOwner("a");
  assert.deepEqual((await loadTaskSnapshot("a", "UTC")).groups, groups);
  assert.equal(await loadTaskSnapshot("b", "UTC"), null);
  assert.equal(await loadTaskSnapshot("a", "America/New_York"), null);
});
test("an empty authoritative result replaces old tasks", async () => {
  const ticket = await seed();
  await saveTaskSnapshot(ticket, "UTC", [], Date.now());
  assert.deepEqual((await loadTaskSnapshot("a", "UTC")).groups, []);
});
test("logout clears data and rejects a late response", async () => {
  const ticket = await seed();
  await claimSnapshotOwner(null);
  assert.equal(await saveTaskSnapshot(ticket, "UTC", groups, Date.now()), false);
  await claimSnapshotOwner("a");
  assert.equal(await loadTaskSnapshot("a", "UTC"), null);
});
test("switching accounts invalidates old requests, even after switching back", async () => {
  const ticket = await seed();
  await claimSnapshotOwner("b");
  await claimSnapshotOwner("a");
  assert.equal(await saveTaskSnapshot(ticket, "UTC", groups, Date.now()), false);
  assert.equal(await loadTaskSnapshot("a", "UTC"), null);
});
test("mutation clears snapshot before writing and fences both sides of completion", async () => {
  const before = await seed();
  const mutation = await beginSnapshotMutation("a");
  assert.equal(await loadTaskSnapshot("a", "UTC"), null);
  assert.equal(await readSnapshotTicket("a"), null);
  assert.equal(await saveTaskSnapshot(before, "UTC", groups, Date.now()), false);
  await finishSnapshotMutation(mutation);
  assert.equal(await saveTaskSnapshot(mutation, "UTC", groups, Date.now()), false);
  const fresh = await readSnapshotTicket("a");
  assert.equal(await saveTaskSnapshot(fresh, "UTC", [], Date.now()), true);
});
test("an old mutation finishing cannot delete a new account's data", async () => {
  await seed();
  const mutation = await beginSnapshotMutation("a");
  await claimSnapshotOwner("b");
  const fresh = await readSnapshotTicket("b");
  await saveTaskSnapshot(fresh, "UTC", [], Date.now());
  await finishSnapshotMutation(mutation);
  assert.ok(await loadTaskSnapshot("b", "UTC"));
});
test("opt-out persists across accounts, clears snapshots, and rejects in-flight writes", async () => {
  const ticket = await seed();
  await setSnapshotPreference(false);
  assert.equal(await readSnapshotTicket("a"), null);
  assert.equal(await loadTaskSnapshot("a", "UTC"), null);
  assert.equal(await saveTaskSnapshot(ticket, "UTC", groups, Date.now()), false);
  assert.equal(await claimSnapshotOwner("b"), false);
  await setSnapshotPreference(true);
  assert.ok(await readSnapshotTicket("b"));
});
test("quarantine prevents stale data exposure after a failed purge", async () => {
  await seed();
  quarantineSnapshots();
  assert.equal(await loadTaskSnapshot("a", "UTC"), null);
  assert.equal(await claimSnapshotOwner("a"), false);
  await setSnapshotPreference(true);
  assert.equal(await loadTaskSnapshot("a", "UTC"), null);
});
test("only the latest timezone snapshot is retained", async () => {
  const ticket = await seed();
  await saveTaskSnapshot(ticket, "America/New_York", groups, Date.now());
  assert.equal(await loadTaskSnapshot("a", "UTC"), null);
  assert.ok(await loadTaskSnapshot("a", "America/New_York"));
});
test("unavailable IndexedDB fails without retaining task data", async () => {
  globalThis.indexedDB = { open() { throw new Error("Denied"); } };
  await assert.rejects(claimSnapshotOwner("a"));
});
test("deadline bounds non-abortable SDK work and aborts its signal", async () => {
  let signal;
  await assert.rejects(withDeadline((value) => {
    signal = value;
    return new Promise(() => {});
  }, 10), { name: "TimeoutError" });
  assert.equal(signal.aborted, true);
});
test("caller abort interrupts pending work", async () => {
  const controller = new AbortController();
  const result = withDeadline(() => new Promise(() => {}), 5000, controller.signal);
  controller.abort();
  await assert.rejects(result, { name: "AbortError" });
});
test("already-aborted requests never start work", async () => {
  const controller = new AbortController();
  controller.abort();
  let called = false;
  await assert.rejects(withDeadline(async () => { called = true; }, 1000, controller.signal), { name: "AbortError" });
  assert.equal(called, false);
});
test("completed work cleans up its timeout and caller listener", async () => {
  const controller = new AbortController();
  let signal;
  assert.equal(await withDeadline(async (value) => { signal = value; return 42; }, 10, controller.signal), 42);
  controller.abort();
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.equal(signal.aborted, false);
});
