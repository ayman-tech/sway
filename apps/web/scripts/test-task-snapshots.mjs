import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";
import { IDBFactory } from "fake-indexeddb";
import { beginSnapshotMutation, claimSnapshotOwner, finishSnapshotMutation, loadTaskSnapshot,
  quarantineSnapshots, readSnapshotTicket, saveTaskSnapshot, setSnapshotPreference,
  validSnapshot, SNAPSHOT_TTL, SNAPSHOT_LIMIT } from "../lib/task-snapshots.ts";
import { withDeadline } from "../lib/request-deadline.ts";

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
