import { z } from "zod";
import type { TaskGroup } from "./types";

export const SNAPSHOT_TTL = 7 * 24 * 60 * 60 * 1000;
export const SNAPSHOT_LIMIT = 2 * 1024 * 1024;
export const IDLE_LIMIT = 5 * 60 * 1000;
const DB = "sway-task-snapshots-v1";
const quarantineKey = "sway-task-snapshots-quarantined";
const nullable = z.string().nullable();
const taskSchema = z.object({
  id: z.string(), title: z.string(), description: nullable, project_id: nullable,
  priority: z.number(), status: z.enum(["pending", "completed"]), due_at: nullable, due_date: nullable,
  start_at: nullable, end_at: nullable, end_date: nullable, reminder_minutes_before: z.number().nullable(),
  recurrence_rule: nullable, recurrence_timezone: nullable, recurrence_parent_id: nullable,
  google_event_id: nullable, source: z.enum(["sway", "google"]), completed_at: nullable,
  created_at: z.string(), updated_at: z.string(), deleted_at: nullable, is_preview: z.boolean(),
}).strict();
const schema = z.object({
  version: z.literal(1), userId: z.string(), timezone: z.string(), fetchedAt: z.number(),
  groups: z.array(z.object({ label: z.string(), overdue: z.boolean(), tasks: z.array(taskSchema), has_more: z.boolean().optional() }).strict()),
}).strict();
export type TaskSnapshot = z.infer<typeof schema>;
type Meta = { owner: string | null; revision: number; enabled: boolean; pendingUntil: number };
export type SnapshotTicket = { userId: string; revision: number };
const initialMeta: Meta = { owner: null, revision: 0, enabled: true, pendingUntil: 0 };

export function validSnapshot(value: unknown, userId: string, timezone: string, now = Date.now()): TaskSnapshot | null {
  try {
    if (new TextEncoder().encode(JSON.stringify(value)).length > SNAPSHOT_LIMIT) return null;
    const result = schema.safeParse(value);
    if (!result.success) return null;
    const item = result.data;
    return item.userId === userId && item.timezone === timezone && item.fetchedAt <= now && now - item.fetchedAt < SNAPSHOT_TTL ? item : null;
  } catch { return null; }
}

function quarantined() {
  try { return localStorage.getItem(quarantineKey) === "true"; } catch { return true; }
}
export function quarantineSnapshots() {
  try { localStorage.setItem(quarantineKey, "true"); } catch { /* Storage is inaccessible; no saved view is loaded. */ }
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    let expired = false;
    const timer = setTimeout(() => { expired = true; reject(new Error("Saved task storage is unavailable.")); }, 1000);
    let request: IDBOpenDBRequest;
    try { request = indexedDB.open(DB, 1); }
    catch (error) { clearTimeout(timer); reject(error); return; }
    request.onupgradeneeded = () => {
      request.result.createObjectStore("meta");
      request.result.createObjectStore("snapshots");
    };
    request.onerror = request.onblocked = () => { clearTimeout(timer); expired = true; reject(new Error("Saved task storage is unavailable.")); };
    request.onsuccess = () => {
      clearTimeout(timer);
      if (expired) request.result.close(); else resolve(request.result);
    };
  });
}

async function transaction<T>(work: (meta: Meta, saveMeta: (value: Meta) => void, snapshots: IDBObjectStore, finish: (value: T) => void) => void): Promise<T> {
  const db = await openDatabase();
  try {
    return await new Promise<T>((resolve, reject) => {
      const tx = db.transaction(["meta", "snapshots"], "readwrite");
      let result: T;
      const timer = setTimeout(() => { tx.abort(); }, 1000);
      tx.oncomplete = () => { clearTimeout(timer); resolve(result); };
      tx.onerror = tx.onabort = () => { clearTimeout(timer); reject(new Error("Unable to access saved tasks.")); };
      const metaStore = tx.objectStore("meta");
      const request = metaStore.get("state");
      request.onsuccess = () => {
        try { work(request.result ?? { ...initialMeta }, (value) => metaStore.put(value, "state"), tx.objectStore("snapshots"), (value) => { result = value; }); }
        catch { tx.abort(); }
      };
    });
  } finally { db.close(); }
}

export function claimSnapshotOwner(userId: string | null) {
  return transaction<boolean>((meta, save, snapshots, done) => {
    if (meta.owner !== userId || userId === null || quarantined()) {
      snapshots.clear();
      meta = { ...meta, owner: userId, revision: meta.revision + 1, pendingUntil: 0 };
      save(meta);
    }
    // Do not re-enable a quarantined cache until a deliberate Settings toggle.
    const cursor = snapshots.openCursor();
    cursor.onsuccess = () => {
      const entry = cursor.result;
      if (!entry) return;
      if (!userId || !validSnapshot(entry.value, userId, entry.value?.timezone)) entry.delete();
      entry.continue();
    };
    done(meta.enabled && !quarantined());
  });
}

export function readSnapshotTicket(userId: string) {
  return transaction<SnapshotTicket | null>((meta, _save, _snapshots, done) => {
    done(meta.owner === userId && meta.enabled && meta.pendingUntil <= Date.now() && !quarantined() ? { userId, revision: meta.revision } : null);
  });
}

// Independent of the cache preference: this fence also protects live data
// against another tab changing tasks while a request is in flight.
export function readTaskFence() {
  return transaction<Meta>((meta, _save, _snapshots, done) => done(meta));
}

export function loadTaskSnapshot(userId: string, timezone: string) {
  return transaction<TaskSnapshot | null>((meta, _save, snapshots, done) => {
    if (meta.owner !== userId || !meta.enabled || meta.pendingUntil > Date.now() || quarantined()) { done(null); return; }
    const key = JSON.stringify([userId, timezone]);
    const request = snapshots.get(key);
    request.onsuccess = () => {
      const item = validSnapshot(request.result, userId, timezone);
      if (!item) snapshots.delete(key);
      done(item);
    };
  });
}

export function saveTaskSnapshot(ticket: SnapshotTicket, timezone: string, groups: TaskGroup[], fetchedAt: number) {
  const value = validSnapshot({ version: 1, userId: ticket.userId, timezone, groups, fetchedAt }, ticket.userId, timezone);
  return transaction<boolean>((meta, _save, snapshots, done) => {
    if (meta.owner !== ticket.userId || meta.revision !== ticket.revision || !meta.enabled || meta.pendingUntil > Date.now() || quarantined()) { done(false); return; }
    const key = JSON.stringify([ticket.userId, timezone]);
    // Retain only the latest timezone's view, bounding total stored task data.
    snapshots.clear();
    if (value) snapshots.put(value, key);
    done(Boolean(value));
  });
}

export function beginSnapshotMutation(userId: string) {
  return transaction<SnapshotTicket>((meta, save, snapshots, done) => {
    if (meta.owner !== userId) throw new Error("Account changed.");
    snapshots.clear();
    save({ ...meta, revision: meta.revision + 1, pendingUntil: Date.now() + 60_000 });
    done({ userId, revision: meta.revision + 1 });
  });
}

export function finishSnapshotMutation(ticket: SnapshotTicket) {
  return transaction<void>((meta, save, snapshots, done) => {
    if (meta.owner === ticket.userId && meta.revision === ticket.revision) {
      snapshots.clear();
      save({ ...meta, revision: meta.revision + 1, pendingUntil: 0 });
    }
    done();
  });
}

export function setSnapshotPreference(enabled: boolean) {
  return transaction<void>((meta, save, snapshots, done) => {
    snapshots.clear();
    save({ ...meta, enabled, revision: meta.revision + 1 });
    done();
  }).then(() => { try { localStorage.removeItem(quarantineKey); } catch { /* Optional. */ } });
}
