"use client";

import { format } from "date-fns";
import { Check, ChevronLeft, ChevronRight, Copy, RefreshCw } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useMutationState, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import type { UserSettings, WorkLogEntry } from "@/lib/types";
import { useReleaseTasksWhen } from "@/components/use-task-load-order";
import { WorklogSlot, type SlotStatus } from "@/components/worklog-slot";
import { useTaskData } from "@/components/task-data-provider";
import { beginSnapshotMutation, finishSnapshotMutation, loadWorklogSnapshot, quarantineSnapshots, readSnapshotTicket, saveWorklogSnapshot, type WorklogSnapshot } from "@/lib/task-snapshots";
import { shouldRetryTaskRead, taskRetryDelay } from "@/lib/task-recovery";
import { WorklogProgress } from "@/components/worklog-progress";
import {
  currentShiftDay, dayAsText, dayIso, dayLayout, loggedCount, parseDay, scheduleSlots,
  windowDays, worklogProgress,
} from "@/lib/worklog";

type SaveVars = { day: string; hour: number; note: string; today: string };

const SAVE_KEY = ["worklog-save"];

function useNow() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const tick = () => setNow(new Date());
    const timer = setInterval(tick, 60_000);
    const onVisible = () => { if (document.visibilityState === "visible") tick(); };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, []);
  return now;
}

function withEntry(entries: WorkLogEntry[] | undefined, entry: WorkLogEntry) {
  const rest = (entries ?? []).filter((e) => !(e.entry_date === entry.entry_date && e.hour_slot === entry.hour_slot));
  return entry.note ? [...rest, entry] : rest;
}

export default function WorklogPage() {
  const qc = useQueryClient();
  const { session, cacheEnabled } = useTaskData();
  const userId = session.user.id;
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  const [snapshot, setSnapshot] = useState<WorklogSnapshot | null>(null);
  const [online, setOnline] = useState(true);
  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    update(); window.addEventListener("online", update); window.addEventListener("offline", update);
    return () => { window.removeEventListener("online", update); window.removeEventListener("offline", update); };
  }, []);
  useEffect(() => {
    let active = true;
    setSnapshot(null);
    if (cacheEnabled) void loadWorklogSnapshot(userId, timezone).then((value) => { if (active) setSnapshot(value); }).catch(() => {});
    return () => { active = false; };
  }, [userId, timezone, cacheEnabled]);
  const now = useNow();
  const today = dayIso(now);
  const days = useMemo(() => windowDays(today), [today]);
  const [picked, setPicked] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState("");
  const [celebration, setCelebration] = useState(false);
  const celebrated = useRef(new Set<string>());
  useEffect(() => { if (!celebration) return; const timer = setTimeout(() => setCelebration(false), 4500); return () => clearTimeout(timer); }, [celebration]);

  // Shares the cache entry the dashboard shell fills, so settings load once.
  const workQuery = useQuery({
    queryKey: ["worklog", userId, timezone, days[0], today],
    retry: shouldRetryTaskRead, retryDelay: taskRetryDelay,
    queryFn: async ({ signal }) => {
      const ticket = await readSnapshotTicket(userId).catch(() => null);
      const [settings, entries] = await Promise.all([
        qc.fetchQuery({ queryKey: ["settings"], queryFn: () => api<UserSettings>("/settings", {}, { expectedUserId: userId }), staleTime: 30_000 }),
        api<WorkLogEntry[]>(`/worklog?today=${today}`, { signal }, { expectedUserId: userId }),
      ]);
      signal.throwIfAborted();
      const value: WorklogSnapshot = { version: 1, userId, timezone, today, fetchedAt: Date.now(), start: settings.work_start_hour, end: settings.work_end_hour, goal: settings.work_weekly_goal_hours ?? null, entries };
      if (ticket) await saveWorklogSnapshot(ticket, value).catch(() => {});
      return value;
    },
  });
  // This page's data goes first; the task list loads once it has arrived (or failed).
  useReleaseTasksWhen(workQuery.isFetched);
  const rejected = workQuery.error instanceof ApiError && (workQuery.error.status === 401 || workQuery.error.status === 403);
  const view = rejected ? null : workQuery.data ?? (cacheEnabled && snapshot?.userId === userId && snapshot.timezone === timezone ? snapshot : null);
  const start = view?.start;
  const end = view?.end;
  const ready = Boolean(view);
  const canEdit = Boolean(workQuery.data && !workQuery.error && online);

  const shiftDay = start !== undefined && end !== undefined ? currentShiftDay(now, start, end) : today;
  const day = picked && days.includes(picked) ? picked : shiftDay;
  const dayIndex = days.indexOf(day);

  const save = useMutation({
    mutationKey: SAVE_KEY,
    scope: { id: "worklog-save" },
    mutationFn: async ({ day, hour, note, today }: SaveVars) => {
      if (!canEdit || !navigator.onLine) throw new Error("Refresh the work log before saving.");
      const ticket = await beginSnapshotMutation(userId).catch(() => { quarantineSnapshots(); return null; });
      try { return await api<WorkLogEntry>(`/worklog/${day}/${hour}`, { method: "PUT", body: JSON.stringify({ note, today }) }, { expectedUserId: userId }); }
      finally { if (ticket) await finishSnapshotMutation(ticket).catch(quarantineSnapshots); }
    },
    // A fetch already in flight could return the note from before this save.
    onMutate: () => { setSnapshot(null); return qc.cancelQueries({ queryKey: ["worklog"] }); },
    onSuccess: (entry) => {
      const key = ["worklog", userId, timezone, days[0], today];
      const old = qc.getQueryData<WorklogSnapshot>(key);
      if (!old) return;
      const entries = withEntry(old.entries, entry);
      const badge = `${userId}:${today}:${old.goal}`;
      if (old.goal && worklogProgress(days, old.entries).total < old.goal && worklogProgress(days, entries).total >= old.goal && !celebrated.current.has(badge)) {
        celebrated.current.add(badge); setCelebration(true);
      }
      qc.setQueryData(key, { ...old, entries });
    },
    onSettled: () => { void qc.invalidateQueries({ queryKey: ["worklog"] }); },
  });
  const saveEntry = (entryDay: string, hour: number, note: string) =>
    save.mutate({ day: entryDay, hour, note, today });

  const saves = useMutationState({
    filters: { mutationKey: SAVE_KEY },
    select: (mutation) => ({ status: mutation.state.status, vars: mutation.state.variables as SaveVars | undefined }),
  });
  const statusFor = (entryDay: string, hour: number): SlotStatus => {
    let result: SlotStatus = "idle";
    for (const { status, vars } of saves) {
      if (vars?.day !== entryDay || vars.hour !== hour) continue;
      result = status === "pending" ? "saving" : status === "error" ? "error" : status === "success" ? "saved" : result;
    }
    return result;
  };

  const notes = useMemo(() => {
    const map = new Map<number, string>();
    for (const entry of view?.entries ?? []) {
      if (entry.entry_date < days[0] || entry.entry_date > today) continue;
      if (entry.entry_date === day) map.set(entry.hour_slot, entry.note);
    }
    return map;
  }, [view?.entries, day, days, today]);
  const slots = useMemo(() => (start !== undefined && end !== undefined ? scheduleSlots(start, end) : []), [start, end]);
  const layout = dayLayout(slots, notes);
  const logged = loggedCount(slots, notes);
  const dayLabel = format(parseDay(day), "EEEE, MMM d");
  const progress = useMemo(() => worklogProgress(days, view?.entries ?? []), [days, view?.entries]);

  const [jumpHour, setJumpHour] = useState(false);
  useEffect(() => {
    if (!jumpHour) return;
    document.getElementById(`worklog-${shiftDay}-${now.getHours()}`)?.closest(".worklog-slot")?.scrollIntoView({ block: "center", behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
    setJumpHour(false);
  }, [jumpHour, shiftDay, now]);
  const saveGoal = async (goal: number | null) => {
    if (!canEdit || !navigator.onLine) throw new Error("Refresh your work log before changing the goal.");
    const ticket = await beginSnapshotMutation(userId).catch(() => { quarantineSnapshots(); return null; });
    try {
      const settings = await api<UserSettings>("/settings", { method: "PATCH", body: JSON.stringify({ work_weekly_goal_hours: goal }) }, { expectedUserId: userId });
      qc.setQueryData(["settings"], settings);
      qc.setQueryData<WorklogSnapshot>(["worklog", userId, timezone, days[0], today], (old) => old ? { ...old, goal: settings.work_weekly_goal_hours } : old);
      setSnapshot(null); setCelebration(false);
    } finally {
      if (ticket) await finishSnapshotMutation(ticket).catch(quarantineSnapshots);
      void qc.invalidateQueries({ queryKey: ["worklog"] });
    }
  };

  const copyDay = async () => {
    setCopyError("");
    try {
      await navigator.clipboard.writeText(dayAsText(`Work log - ${dayLabel}`, layout, notes));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopyError("Unable to copy. Check clipboard permission and try again.");
    }
  };

  const error = workQuery.error;
  const waitingForNetwork = !online || workQuery.fetchStatus === "paused";
  const retrying = workQuery.isFetching;
  const retry = () => { void workQuery.refetch(); };

  const renderSlot = (hour: number) => (
    <WorklogSlot
      current={day === shiftDay && hour === now.getHours()}
      day={day}
      hour={hour}
      key={`${day}-${hour}`}
      onSave={saveEntry}
      serverNote={notes.get(hour) ?? ""}
      status={statusFor(day, hour)}
      readOnly={!canEdit}
    />
  );

  return (
    <section className="worklog-page space-y-4 lg:space-y-5">
      <div className="hidden lg:block">
        <h1 className="text-3xl font-black">Work log</h1>
        <p className="mt-1 text-[var(--muted)]">A little progress, made visible.</p>
      </div>

      <div className="worklog-layout">
      {ready ? <WorklogProgress days={days} day={day} logged={logged} scheduled={slots.length} extra={layout.extra.length} progress={progress} goal={view?.goal ?? null} canEdit={canEdit} onSelect={setPicked} onGoal={saveGoal} celebration={celebration} /> : null}
      <div className="worklog-editor space-y-4">
      <div className="flex items-center justify-between gap-3">
        <p className="min-w-0 truncate text-lg font-bold text-[var(--foreground)]">{dayLabel}</p>
        <div className="flex gap-2">
          <button
            aria-label="Previous day"
            className="btn btn-secondary min-w-11 px-2"
            disabled={dayIndex <= 0}
            onClick={() => setPicked(days[dayIndex - 1])}
          >
            <ChevronLeft size={18} />
          </button>
          <button
            aria-label="Next day"
            className="btn btn-secondary min-w-11 px-2"
            disabled={dayIndex < 0 || dayIndex >= days.length - 1}
            onClick={() => setPicked(days[dayIndex + 1])}
          >
            <ChevronRight size={18} />
          </button>
        </div>
      </div>

      {ready && (!canEdit || retrying) ? <div role="status" className="flex flex-wrap items-center gap-2 text-xs text-[var(--muted)]">
        <span>{waitingForNetwork ? "Saved work log · Waiting for connection…" : retrying ? "Syncing work log…" : "Saved work log · Couldn’t sync"} · Last sync: {new Date(view!.fetchedAt).toLocaleString()}</span>
        {!retrying && !waitingForNetwork ? <button className="btn btn-secondary" onClick={retry}>Retry</button> : null}
        {!canEdit ? <span>Read-only until refreshed.</span> : null}
      </div> : null}

      {!ready && !error ? (
        <div aria-busy="true" aria-live="polite" className="space-y-3" role="status">
          <p className="text-sm font-medium text-[var(--muted)]">
            {waitingForNetwork ? "Waiting for connection…" : "Loading work log..."}
          </p>
          {[0, 1, 2, 3].map((item) => (
            <div
              aria-hidden="true"
              className="panel h-[96px] animate-pulse bg-[var(--nav-hover)] motion-reduce:animate-none"
              key={item}
            />
          ))}
        </div>
      ) : null}

      {error && !ready ? (
        <div aria-live="polite" className="rounded-xl border border-[#f2c6a8] bg-[#fff2e8] p-4 text-[#9a3412]" role="alert">
          <p className="font-bold">{error instanceof ApiError ? error.message : "Unable to load your work log."}</p>
          <button className="btn btn-secondary mt-3 min-h-11" disabled={retrying} onClick={retry} type="button">
            <RefreshCw className={retrying ? "animate-spin motion-reduce:animate-none" : ""} size={17} />
            {retrying ? "Retrying..." : "Retry"}
          </button>
        </div>
      ) : null}

      {ready ? (
        <>
          <div className="grid gap-2 sm:flex sm:items-center sm:justify-between sm:gap-3">
            <p className="shrink-0 text-sm text-[var(--muted)]" role="status">
              {logged} of {slots.length} {slots.length === 1 ? "hour" : "hours"} logged
            </p>
            <div className="grid grid-cols-2 gap-2 sm:flex sm:justify-end">
            <button className="btn btn-secondary" disabled={!ready} onClick={() => { setPicked(shiftDay); setJumpHour(true); }} type="button">Current hour</button>
            <button className="btn btn-secondary" disabled={!logged && !layout.extra.length} onClick={() => void copyDay()} type="button">
              {copied ? <Check size={17} /> : <Copy size={17} />} {copied ? "Copied" : "Copy day"}
            </button>
            </div>
          </div>
          {copyError ? <p className="text-sm text-[var(--danger)]" role="alert">{copyError}</p> : null}
          <div className="space-y-2.5 lg:space-y-3">{layout.scheduled.map(renderSlot)}</div>
          {layout.extra.length ? (
            <section>
              <h2 className="mb-1 text-lg font-bold lg:text-xl lg:font-black">Outside your work schedule</h2>
              <p className="mb-2.5 text-sm text-[var(--muted)] lg:mb-3">
                These hours have notes but are no longer in your schedule.
              </p>
              <div className="space-y-2.5 lg:space-y-3">{layout.extra.map(renderSlot)}</div>
            </section>
          ) : null}
        </>
      ) : null}
      </div>
      </div>
    </section>
  );
}
