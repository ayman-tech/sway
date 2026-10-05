"use client";

import Link from "next/link";
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabase";
import { api, ApiError, boundedSession, isTransientApiError } from "@/lib/api";
import type { TaskGroup } from "@/lib/types";
import { measureTaskTiming } from "@/lib/request-deadline";
import { beginSnapshotMutation, claimSnapshotOwner, finishSnapshotMutation, IDLE_LIMIT, loadTaskSnapshot,
  quarantineSnapshots, readSnapshotTicket, readTaskFence, saveTaskSnapshot, setSnapshotPreference,
  type TaskSnapshot, type SnapshotTicket } from "@/lib/task-snapshots";

type TaskData = {
  session: Session; groups: TaskGroup[] | undefined; saved: boolean; fetchedAt: number | null;
  canWrite: boolean; fetching: boolean; error: Error | null; failureCount: number;
  retry: () => void; mutate: <T>(path: string, init: RequestInit) => Promise<T>;
  cacheEnabled: boolean; cacheWarning: string; setCacheEnabled: (enabled: boolean) => Promise<void>;
  beforeSignOut: () => Promise<void>;
  signOutFailed: () => void;
};
const Context = createContext<TaskData | null>(null);
const channelName = "sway-task-view";
type Notice = "logout" | "changed" | "mutation-start" | "mutation-end" | "preference";
function notify(notice: Notice) {
  if (typeof BroadcastChannel !== "undefined") {
    const channel = new BroadcastChannel(channelName); channel.postMessage(notice); channel.close();
  }
  try { localStorage.setItem("sway-task-view-event", JSON.stringify({ notice, nonce: Math.random() })); } catch { /* BroadcastChannel still works. */ }
}

export function TaskDataProvider({ children }: { children: React.ReactNode }) {
  const qc = useQueryClient();
  const [session, setSession] = useState<Session | null>(null);
  const [authPending, setAuthPending] = useState(true);
  const [authError, setAuthError] = useState("");
  const [snapshot, setSnapshot] = useState<TaskSnapshot | null>(null);
  const [timezone, setTimezone] = useState(() => Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC");
  const [locked, setLocked] = useState(true);
  const [online, setOnline] = useState(true);
  const [cacheEnabled, setCacheEnabledState] = useState(true);
  const [cacheWarning, setCacheWarning] = useState("");
  const [fetchedAt, setFetchedAt] = useState<number | null>(null);
  const identity = useRef<string | null>(null);
  const generation = useRef(0);
  const authSequence = useRef(0);
  const writable = useRef(false);
  const busy = useRef(false);
  const loggingOut = useRef(false);
  const mounted = useRef(true);
  const hiddenAt = useRef<number | null>(null);
  const lastActivity = useRef(Date.now());
  const openedAt = useRef(performance.now());
  const queryKey = ["task-groups", session?.user.id, timezone];

  const lock = useCallback(() => { writable.current = false; setLocked(true); }, []);
  const storageWarning = useCallback(() => setCacheWarning("Saved task storage is unavailable. Online task loading still works."), []);

  const acceptSession = useCallback(async (next: Session | null) => {
    if (!mounted.current) return;
    const nextId = next?.user.id ?? null;
    const epoch = ++generation.current;
    identity.current = nextId;
    lock(); setSession(null); setSnapshot(null); setFetchedAt(null);
    await qc.cancelQueries();
    if (!mounted.current || epoch !== generation.current) return;
    qc.clear();
    try { const enabled = await claimSnapshotOwner(nextId); if (epoch === generation.current) setCacheEnabledState(enabled); }
    catch { quarantineSnapshots(); storageWarning(); }
    if (!mounted.current || epoch !== generation.current) return;
    loggingOut.current = false;
    setSession(next); setAuthPending(false);
    setAuthError(next ? "" : "Sign in to view your tasks.");
  }, [lock, qc, storageWarning]);

  const restoreSession = useCallback(async () => {
    const sequence = ++authSequence.current;
    const started = performance.now();
    setAuthPending(true); setAuthError("");
    try {
      const { data, error } = await boundedSession();
      if (sequence !== authSequence.current || !mounted.current) return;
      if (error) throw error;
      await acceptSession(data.session);
      measureTaskTiming("session-ready", started);
    } catch {
      if (sequence === authSequence.current && mounted.current) {
        setAuthPending(false); setAuthError("Couldn’t restore your session. Retry, or sign in again.");
      }
    }
  }, [acceptSession]);

  useEffect(() => {
    mounted.current = true;
    void restoreSession();
    const { data } = supabase.auth.onAuthStateChange((event, next) => {
      if (event === "INITIAL_SESSION" || next?.user.id === identity.current && event !== "SIGNED_OUT") return;
      const sequence = ++authSequence.current;
      // Invalidate request callbacks immediately, outside SDK async work.
      if (!next || next.user.id !== identity.current) { generation.current++; writable.current = false; setSession(null); setSnapshot(null); }
      setTimeout(() => { if (mounted.current && sequence === authSequence.current) void acceptSession(next); }, 0);
    });
    return () => { mounted.current = false; ++authSequence.current; ++generation.current; data.subscription.unsubscribe(); };
  }, [acceptSession, restoreSession]);

  const tasks = useQuery({
    queryKey,
    enabled: Boolean(session) && !authError && !loggingOut.current,
    staleTime: 0, refetchOnMount: "always", refetchOnWindowFocus: false, refetchOnReconnect: false,
    retry: (count, error) => count < 1 && isTransientApiError(error), retryDelay: 1000,
    queryFn: async ({ signal }) => {
      const userId = session!.user.id;
      const epoch = generation.current;
      // Capture the persistent write fence before starting the request. Storage
      // access is bounded independently and failure never prevents online use.
      const ticket = await readSnapshotTicket(userId).catch(() => null);
      const fence = await readTaskFence().catch(() => null);
      signal.throwIfAborted();
      let groups: TaskGroup[];
      try {
        groups = await api<TaskGroup[]>(`/tasks/groups?timezone_name=${encodeURIComponent(timezone)}`, { signal }, { expectedUserId: userId });
      } catch (error) {
        if (!signal.aborted && epoch === generation.current) lock();
        throw error;
      }
      signal.throwIfAborted();
      const currentFence = await readTaskFence().catch(() => null);
      signal.throwIfAborted();
      if (fence && currentFence && (currentFence.owner !== userId || currentFence.revision !== fence.revision || currentFence.pendingUntil > Date.now())) {
        lock();
        throw new ApiError("Tasks changed in another tab. Refresh to get the latest view.", "aborted");
      }
      if (epoch !== generation.current || identity.current !== userId || busy.current || loggingOut.current) throw new ApiError("Request superseded.", "aborted");
      const stamp = Date.now();
      writable.current = navigator.onLine;
      setLocked(!navigator.onLine); setFetchedAt(stamp); setSnapshot(null);
      measureTaskTiming("tasks-unlocked", openedAt.current);
      if (ticket && mounted.current && epoch === generation.current && !busy.current && identity.current === userId) {
        void saveTaskSnapshot(ticket, timezone, groups, stamp).catch(storageWarning);
      }
      return groups;
    },
  });

  useEffect(() => {
    if (!session) return;
    const epoch = generation.current;
    const started = performance.now();
    let active = true;
    void loadTaskSnapshot(session.user.id, timezone).then((saved) => {
      if (active && epoch === generation.current && !writable.current) {
        setSnapshot(saved);
        measureTaskTiming("snapshot-render-ready", started);
      }
    }).catch(storageWarning);
    return () => { active = false; };
  }, [session?.user.id, timezone, storageWarning]);

  useEffect(() => {
    if (!tasks.error) return;
    lock();
    if (tasks.error instanceof ApiError && (tasks.error.status === 401 || tasks.error.status === 403)) {
      generation.current++;
      setSnapshot(null); setAuthError("Your session could not be verified. Sign in again to continue.");
      void claimSnapshotOwner(null).catch(quarantineSnapshots);
      void qc.cancelQueries().then(() => qc.clear());
    }
  }, [tasks.error, lock, qc]);

  const revalidate = useCallback((mustLock = false) => {
    if (mustLock) { lock(); generation.current++; }
    if (identity.current && !loggingOut.current) {
      void qc.cancelQueries({ queryKey: ["task-groups"] }).then(() => qc.invalidateQueries({ queryKey: ["task-groups"] }));
    }
  }, [lock, qc]);

  useEffect(() => {
    setOnline(navigator.onLine);
    const resume = () => {
      const now = Date.now();
      const idle = now - (hiddenAt.current ?? lastActivity.current) >= IDLE_LIMIT;
      hiddenAt.current = null; lastActivity.current = now;
      const zone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
      if (zone !== timezone) { lock(); generation.current++; setSnapshot(null); setFetchedAt(null); setTimezone(zone); }
      revalidate(idle);
    };
    const visibility = () => { if (document.hidden) hiddenAt.current = Date.now(); else resume(); };
    const activity = () => {
      if (Date.now() - lastActivity.current >= IDLE_LIMIT) revalidate(true);
      lastActivity.current = Date.now();
    };
    const offline = () => { setOnline(false); lock(); generation.current++; };
    const reconnect = () => { setOnline(true); revalidate(true); };
    const notice = (value: Notice) => {
      if (value === "logout") { generation.current++; lock(); setSession(null); setSnapshot(null); setAuthError("Signed out in another tab. Sign in again to continue."); void qc.cancelQueries().then(() => qc.clear()); }
      else if (value === "preference") {
        setSnapshot(null);
        if (identity.current) void claimSnapshotOwner(identity.current).then(setCacheEnabledState).catch(storageWarning);
      } else if (value === "mutation-start") { setSnapshot(null); lock(); generation.current++; void qc.cancelQueries({ queryKey: ["task-groups"] }); }
      else revalidate(true);
    };
    const channel = typeof BroadcastChannel !== "undefined" ? new BroadcastChannel(channelName) : null;
    if (channel) channel.onmessage = (event) => notice(event.data);
    const storage = (event: StorageEvent) => {
      if (event.key === "sway-task-view-event" && event.newValue && !channel) {
        try { notice(JSON.parse(event.newValue).notice); } catch { /* Ignore malformed events. */ }
      }
    };
    window.addEventListener("focus", resume); window.addEventListener("online", reconnect); window.addEventListener("offline", offline);
    // Capture before a task control can dispatch a mutation on an idle page.
    window.addEventListener("pointerdown", activity, { passive: true, capture: true }); window.addEventListener("keydown", activity, true);
    window.addEventListener("storage", storage); document.addEventListener("visibilitychange", visibility);
    return () => {
      channel?.close(); window.removeEventListener("focus", resume); window.removeEventListener("online", reconnect); window.removeEventListener("offline", offline);
      window.removeEventListener("pointerdown", activity, true); window.removeEventListener("keydown", activity, true);
      window.removeEventListener("storage", storage); document.removeEventListener("visibilitychange", visibility);
    };
  }, [lock, qc, revalidate, storageWarning, timezone]);

  const mutate = async <T,>(path: string, init: RequestInit): Promise<T> => {
    const userId = identity.current;
    if (Date.now() - lastActivity.current >= IDLE_LIMIT) revalidate(true);
    if (!userId || !writable.current || !navigator.onLine || busy.current || loggingOut.current) throw new Error("Task changes are available after refreshing from Sway. Retry the connection first.");
    const work = async () => {
      if (identity.current !== userId || !writable.current || !navigator.onLine || loggingOut.current || busy.current) throw new Error("Task data needs a fresh connection before saving.");
      busy.current = true; lock(); generation.current++; setSnapshot(null);
      notify("mutation-start");
      await qc.cancelQueries({ queryKey: ["task-groups"] });
      let ticket: SnapshotTicket | null = null;
      try { ticket = await beginSnapshotMutation(userId); } catch { quarantineSnapshots(); storageWarning(); }
      try {
        return await api<T>(path, init, { expectedUserId: userId });
      } finally {
        if (ticket) await finishSnapshotMutation(ticket).catch(() => { quarantineSnapshots(); storageWarning(); });
        busy.current = false;
        if (identity.current === userId && !loggingOut.current) {
          notify("mutation-end");
          revalidate(true);
          for (const key of ["calendar", "completed", "availability-calendar"]) void qc.invalidateQueries({ queryKey: [key] });
        }
      }
    };
    return navigator.locks ? navigator.locks.request("sway-task-mutation", work) : work();
  };

  const rejectedSession = tasks.error instanceof ApiError && (tasks.error.status === 401 || tasks.error.status === 403);
  if (authPending || !session || authError || rejectedSession) return <div className="mx-auto max-w-lg p-6" role="status">
    <p>{authPending ? "Restoring your session…" : authError || "Sign in to continue."}</p>
    {!authPending ? <div className="mt-4 flex gap-3"><button className="btn btn-secondary" onClick={() => void restoreSession()}>Retry</button><Link className="btn btn-primary" href="/auth">Sign in</Link></div> : null}
  </div>;

  return <Context.Provider value={{ session, groups: tasks.data ?? snapshot?.groups, saved: tasks.data === undefined && Boolean(snapshot),
    fetchedAt: tasks.data === undefined ? snapshot?.fetchedAt ?? null : fetchedAt,
    canWrite: !locked && online && !tasks.error && !busy.current, fetching: tasks.isFetching,
    error: tasks.error, failureCount: tasks.failureCount, retry: () => revalidate(true), mutate,
    cacheEnabled, cacheWarning,
    setCacheEnabled: async (enabled) => {
      setSnapshot(null);
      if (!enabled) quarantineSnapshots();
      await setSnapshotPreference(enabled);
      setCacheEnabledState(enabled); setCacheWarning(""); notify("preference");
      if (enabled) revalidate(false);
    },
    beforeSignOut: async () => {
      loggingOut.current = true; generation.current++; lock(); setSnapshot(null);
      notify("logout");
      await qc.cancelQueries(); qc.clear();
      try { await claimSnapshotOwner(null); } catch { quarantineSnapshots(); }
    },
    signOutFailed: () => setAuthError("Sign-out did not finish. Retry restoring your session, then try again."),
  }}>{children}</Context.Provider>;
}

export function useTaskData() {
  const context = useContext(Context);
  if (!context) throw new Error("useTaskData requires TaskDataProvider");
  return context;
}
