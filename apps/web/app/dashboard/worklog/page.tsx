"use client";

import { format } from "date-fns";
import { Check, ChevronLeft, ChevronRight, Copy, RefreshCw } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useMutationState, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import type { UserSettings, WorkLogEntry } from "@/lib/types";
import { WorklogSlot, type SlotStatus } from "@/components/worklog-slot";
import {
  currentShiftDay, dayAsText, dayIso, dayLayout, loggedCount, parseDay, scheduleSlots,
  windowDays,
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
  const now = useNow();
  const today = dayIso(now);
  const days = useMemo(() => windowDays(today), [today]);
  const [picked, setPicked] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState("");

  const settingsQuery = useQuery({ queryKey: ["settings"], queryFn: () => api<UserSettings>("/settings") });
  const entriesQuery = useQuery({
    queryKey: ["worklog", days[0], today],
    queryFn: () => api<WorkLogEntry[]>(`/worklog?today=${today}`),
  });
  const start = settingsQuery.data?.work_start_hour;
  const end = settingsQuery.data?.work_end_hour;
  const ready = start !== undefined && end !== undefined && entriesQuery.data !== undefined;

  const shiftDay = start !== undefined && end !== undefined ? currentShiftDay(now, start, end) : today;
  const day = picked && days.includes(picked) ? picked : shiftDay;
  const dayIndex = days.indexOf(day);

  const save = useMutation({
    mutationKey: SAVE_KEY,
    scope: { id: "worklog-save" },
    mutationFn: ({ day, hour, note, today }: SaveVars) =>
      api<WorkLogEntry>(`/worklog/${day}/${hour}`, { method: "PUT", body: JSON.stringify({ note, today }) }),
    // A fetch already in flight could return the note from before this save.
    onMutate: () => qc.cancelQueries({ queryKey: ["worklog"] }),
    onSuccess: (entry) => qc.setQueriesData<WorkLogEntry[]>({ queryKey: ["worklog"] }, (old) => withEntry(old, entry)),
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
    for (const entry of entriesQuery.data ?? []) {
      if (entry.entry_date === day) map.set(entry.hour_slot, entry.note);
    }
    return map;
  }, [entriesQuery.data, day]);
  const slots = useMemo(() => (start !== undefined && end !== undefined ? scheduleSlots(start, end) : []), [start, end]);
  const layout = dayLayout(slots, notes);
  const logged = loggedCount(slots, notes);
  const dayLabel = format(parseDay(day), "EEEE, MMM d");

  // Bring the current hour into view when landing on the in-progress day.
  const nowHour = useRef(now.getHours());
  nowHour.current = now.getHours();
  const scrolledDay = useRef<string | null>(null);
  useEffect(() => {
    if (day !== shiftDay) {
      scrolledDay.current = null;
      return;
    }
    if (!ready || scrolledDay.current === day) return;
    scrolledDay.current = day;
    document.getElementById(`worklog-${day}-${nowHour.current}`)?.closest(".worklog-slot")
      ?.scrollIntoView({ block: "center" });
  }, [ready, day, shiftDay]);

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

  const error = settingsQuery.error ?? entriesQuery.error;
  const waitingForNetwork = !ready && (settingsQuery.fetchStatus === "paused" || entriesQuery.fetchStatus === "paused");
  const retrying = settingsQuery.isFetching || entriesQuery.isFetching;
  const retry = () => {
    if (settingsQuery.error) void settingsQuery.refetch();
    if (entriesQuery.error) void entriesQuery.refetch();
  };

  const renderSlot = (hour: number) => (
    <WorklogSlot
      current={day === shiftDay && hour === now.getHours()}
      day={day}
      hour={hour}
      key={`${day}-${hour}`}
      onSave={saveEntry}
      serverNote={notes.get(hour) ?? ""}
      status={statusFor(day, hour)}
    />
  );

  return (
    <section className="space-y-4 lg:space-y-5">
      <div className="hidden lg:block">
        <h1 className="text-3xl font-black">Work log</h1>
        <p className="mt-1 text-[var(--muted)]">Note what you worked on each hour. The last 7 days are kept.</p>
      </div>

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

      <div className="worklog-days">
        {days.map((value) => {
          const date = parseDay(value);
          return (
            <button
              aria-label={`${format(date, "EEEE, MMMM d")}${value === shiftDay ? ", today" : ""}`}
              aria-pressed={value === day}
              className="worklog-day"
              key={value}
              onClick={() => setPicked(value)}
              type="button"
            >
              <span className="text-xs font-bold">{format(date, "EEE")}</span>
              <span className="text-base font-black">{format(date, "d")}</span>
              <span aria-hidden="true" className={value === shiftDay ? "worklog-day-dot" : "worklog-day-dot invisible"} />
            </button>
          );
        })}
      </div>

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
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm text-[var(--muted)]" role="status">
              {logged} of {slots.length} {slots.length === 1 ? "hour" : "hours"} logged
            </p>
            <button className="btn btn-secondary" disabled={!logged && !layout.extra.length} onClick={() => void copyDay()} type="button">
              {copied ? <Check size={17} /> : <Copy size={17} />} {copied ? "Copied" : "Copy day"}
            </button>
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
    </section>
  );
}
