"use client";

import {
  addMonths,
  endOfMonth,
  endOfWeek,
  format,
  isSameDay,
  parseISO,
  startOfMonth,
  startOfWeek,
  subMonths,
} from "date-fns";
import { ChevronLeft, ChevronRight, Copy, Download, Edit3, Loader2, Share2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AvailabilityShareCreated, AvailabilitySlots, Task } from "@/lib/types";
import {
  dateFromIso,
  hourLabel,
  makeSnapshot,
  selectedLabel,
  shortHourLabel,
  todayIso,
  toDateIso,
} from "@/lib/availability";
import { AvailabilityGrid, AvailabilityLegend } from "@/components/availability-grid";

type AvailabilitySetup = {
  selectedDates: string[];
  startHour: number;
  endHour: number;
};

type AvailabilityState = AvailabilitySlots;
type BusyMap = AvailabilitySlots;

const SETUP_KEY = "sway.availability.setup";
const STATE_KEY = "sway.availability.state";
const MAX_DATES = 14;

function readSetup(): AvailabilitySetup {
  if (typeof window === "undefined") {
    return { selectedDates: [todayIso()], startHour: -1, endHour: -1 };
  }
  try {
    const saved = JSON.parse(window.localStorage.getItem(SETUP_KEY) ?? "{}") as Partial<AvailabilitySetup>;
    return {
      selectedDates: [todayIso()],
      startHour: typeof saved.startHour === "number" ? saved.startHour : -1,
      endHour: typeof saved.endHour === "number" ? saved.endHour : -1,
    };
  } catch {
    return { selectedDates: [todayIso()], startHour: -1, endHour: -1 };
  }
}

function readAvailabilityState(): AvailabilityState {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(window.localStorage.getItem(STATE_KEY) ?? "{}") as AvailabilityState;
  } catch {
    return {};
  }
}

function monthDays(month: Date) {
  const start = startOfWeek(startOfMonth(month), { weekStartsOn: 1 });
  const end = endOfWeek(endOfMonth(month), { weekStartsOn: 1 });
  const days: Date[] = [];
  const cursor = new Date(start);
  while (cursor <= end) {
    days.push(new Date(cursor));
    cursor.setDate(cursor.getDate() + 1);
  }
  return days;
}

function setupRange(dates: string[]) {
  const sorted = [...dates].sort();
  const start = dateFromIso(sorted[0]);
  const end = dateFromIso(sorted[sorted.length - 1]);
  start.setHours(0, 0, 0, 0);
  end.setDate(end.getDate() + 1);
  end.setHours(0, 0, 0, 0);
  return { start, end };
}

function computeBusy(tasks: Task[], setup: AvailabilitySetup): BusyMap {
  const dateSet = new Set(setup.selectedDates);
  const busy: BusyMap = {};
  for (const task of tasks) {
    if (!task.due_at || !task.has_time) continue;
    const start = parseISO(task.due_at);
    const end = task.end_at ? parseISO(task.end_at) : new Date(start.getTime() + 60 * 60 * 1000);
    const dateIso = toDateIso(start);
    if (!dateSet.has(dateIso)) continue;

    for (let row = 0; row < setup.endHour - setup.startHour; row += 1) {
      const slotStart = dateFromIso(dateIso);
      slotStart.setHours(setup.startHour + row, 0, 0, 0);
      const slotEnd = new Date(slotStart.getTime() + 60 * 60 * 1000);
      if (start < slotEnd && end > slotStart) {
        busy[dateIso] = Array.from(new Set([...(busy[dateIso] ?? []), row])).sort((a, b) => a - b);
      }
    }
  }
  return busy;
}

function initialAvailability(setup: AvailabilitySetup, saved: AvailabilityState, busy: BusyMap): AvailabilityState {
  const next: AvailabilityState = {};
  for (const dateIso of setup.selectedDates) {
    if (Array.isArray(saved[dateIso])) {
      next[dateIso] = saved[dateIso].filter((slot) => slot >= 0 && slot < setup.endHour - setup.startHour);
      continue;
    }
    const busySlots = new Set(busy[dateIso] ?? []);
    next[dateIso] = Array.from({ length: setup.endHour - setup.startHour }, (_, index) => index).filter(
      (slot) => !busySlots.has(slot),
    );
  }
  return next;
}

function buildAvailabilityHtml(setup: AvailabilitySetup, availability: AvailabilityState, busy: BusyMap) {
  const dates = setup.selectedDates;
  const rows = Array.from({ length: setup.endHour - setup.startHour }, (_, index) => index);
  const css = `
    body{font-family:Arial,sans-serif;margin:28px;color:#1d2129;background:#f4f5f7}
    h1{margin:0 0 4px;font-size:24px}
    p{margin:0 0 20px;color:#667085}
    table{border-collapse:collapse;background:#fff;border:1px solid #dcdfe4}
    th,td{border:1px solid #dcdfe4;padding:0;text-align:center}
    th{height:42px;background:#eef1f5;font-size:13px}
    td.time{width:72px;padding:8px;color:#667085;background:#fff;font-size:13px}
    td.slot{width:96px;height:30px}
    .available{background:#bfe8cf}.busy{background:#cbd6ee}.free{background:#f8fafc}
  `;
  const body = rows
    .map((row) => {
      const cells = dates
        .map((dateIso) => {
          const cls = busy[dateIso]?.includes(row) ? "busy" : availability[dateIso]?.includes(row) ? "available" : "free";
          return `<td class="slot ${cls}"></td>`;
        })
        .join("");
      return `<tr><td class="time">${shortHourLabel(setup.startHour + row)}</td>${cells}</tr>`;
    })
    .join("");
  const headers = dates.map((dateIso) => `<th>${format(dateFromIso(dateIso), "EEE")}<br>${format(dateFromIso(dateIso), "MMM d")}</th>`).join("");
  return `<!doctype html><html><head><meta charset="utf-8"><title>Sway Availability</title><style>${css}</style></head><body><h1>My Availability</h1><p>${selectedLabel(dates)} · ${hourLabel(setup.startHour)} to ${hourLabel(setup.endHour)}</p><table><thead><tr><th></th>${headers}</tr></thead><tbody>${body}</tbody></table></body></html>`;
}

export default function AvailabilityPage() {
  const [mode, setMode] = useState<"setup" | "grid">("setup");
  const [setupDraft, setSetupDraft] = useState<AvailabilitySetup>(() => ({
    selectedDates: [todayIso()],
    startHour: -1,
    endHour: -1,
  }));
  const [setup, setSetup] = useState<AvailabilitySetup | null>(null);
  const [month, setMonth] = useState(() => new Date());
  const [availability, setAvailability] = useState<AvailabilityState>({});
  const [savedState, setSavedState] = useState<AvailabilityState>({});
  const [message, setMessage] = useState("");
  const [shareResult, setShareResult] = useState<AvailabilityShareCreated | null>(null);
  const [drag, setDrag] = useState<{ mark: boolean; last: string } | null>(null);
  const dateGridRef = useRef<HTMLDivElement>(null);
  const dateDragRef = useRef<{ pointerId: number; mark: boolean; visited: Set<string> } | null>(null);
  const suppressDateClickRef = useRef(false);
  const today = useMemo(() => new Date(), []);
  const createShare = useMutation({
    mutationFn: (snapshot: ReturnType<typeof makeSnapshot>) =>
      api<AvailabilityShareCreated>("/availability-shares", {
        method: "POST",
        body: JSON.stringify({
          snapshot,
          creator_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        }),
      }),
    onSuccess: async (result) => {
      setShareResult(result);
      try {
        await navigator.clipboard.writeText(result.url);
        setMessage("Share link copied.");
      } catch {
        setMessage("Share link created. Use the Copy button below.");
      }
    },
    onError: (error) => setMessage(error instanceof Error ? error.message : "Unable to create share link."),
  });

  useEffect(() => {
    const saved = readSetup();
    setSetupDraft(saved);
    setMonth(dateFromIso(saved.selectedDates[0]));
    setSavedState(readAvailabilityState());
  }, []);

  const range = useMemo(() => (setup ? setupRange(setup.selectedDates) : null), [setup]);
  const { data: tasks = [], isLoading } = useQuery({
    enabled: Boolean(range),
    queryKey: ["availability-calendar", range?.start.toISOString(), range?.end.toISOString()],
    queryFn: () =>
      api<Task[]>(
        `/tasks/calendar?start=${encodeURIComponent(range!.start.toISOString())}&end=${encodeURIComponent(range!.end.toISOString())}`,
      ),
  });
  const busy = useMemo(() => (setup ? computeBusy(tasks, setup) : {}), [tasks, setup]);

  useEffect(() => {
    if (!setup || isLoading) return;
    setAvailability(initialAvailability(setup, savedState, busy));
  }, [busy, isLoading, savedState, setup]);

  const setDateSelected = (iso: string, selected: boolean) => {
    setSetupDraft((current) => {
      const selectedDates = new Set(current.selectedDates);
      if (selectedDates.has(iso) === selected) return current;
      if (!selected) {
        selectedDates.delete(iso);
      } else if (selectedDates.size < MAX_DATES) {
        selectedDates.add(iso);
        setMessage("");
      } else {
        setMessage(`Choose ${MAX_DATES} dates or fewer.`);
      }
      return { ...current, selectedDates: Array.from(selectedDates).sort() };
    });
  };

  const toggleDate = (iso: string) => {
    setDateSelected(iso, !setupDraft.selectedDates.includes(iso));
  };

  const paintDate = (iso: string) => {
    const dateDrag = dateDragRef.current;
    if (!dateDrag || dateDrag.visited.has(iso)) return;
    dateDrag.visited.add(iso);
    setDateSelected(iso, dateDrag.mark);
  };

  const handleDatePointerDown = (event: React.PointerEvent<HTMLButtonElement>, iso: string, selected: boolean) => {
    if (event.button !== 0) return;
    event.preventDefault();
    dateGridRef.current?.setPointerCapture(event.pointerId);
    dateDragRef.current = { pointerId: event.pointerId, mark: !selected, visited: new Set() };
    suppressDateClickRef.current = true;
    paintDate(iso);
  };

  const handleDatePointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (dateDragRef.current?.pointerId !== event.pointerId) return;
    const target = document.elementFromPoint(event.clientX, event.clientY)?.closest<HTMLElement>("[data-date-iso]");
    const iso = target?.dataset.dateIso;
    if (iso && dateGridRef.current?.contains(target)) paintDate(iso);
  };

  const handleDatePointerEnd = (event: React.PointerEvent<HTMLDivElement>) => {
    if (dateDragRef.current?.pointerId !== event.pointerId) return;
    dateDragRef.current = null;
    if (event.type === "pointercancel") {
      suppressDateClickRef.current = false;
    } else {
      window.setTimeout(() => {
        suppressDateClickRef.current = false;
      }, 0);
    }
    if (dateGridRef.current?.hasPointerCapture(event.pointerId)) {
      dateGridRef.current.releasePointerCapture(event.pointerId);
    }
  };

  const confirmSetup = () => {
    setMessage("");
    if (!setupDraft.selectedDates.length) {
      setMessage("Choose at least one date.");
      return;
    }
    if (setupDraft.startHour < 0 || setupDraft.endHour < 0) {
      setMessage("Pick a start and end time.");
      return;
    }
    if (setupDraft.endHour <= setupDraft.startHour) {
      setMessage("End time must be after start time.");
      return;
    }
    const next = { ...setupDraft, selectedDates: [...setupDraft.selectedDates].sort() };
    window.localStorage.setItem(SETUP_KEY, JSON.stringify(next));
    setSetup(next);
    setMode("grid");
  };

  const persistAvailability = useCallback((next: AvailabilityState) => {
    setAvailability(next);
    setSavedState((current) => {
      const merged = { ...current, ...next };
      window.localStorage.setItem(STATE_KEY, JSON.stringify(merged));
      return merged;
    });
  }, []);

  const setSlot = useCallback(
    (dateIso: string, slot: number, mark: boolean) => {
      if (!setup || busy[dateIso]?.includes(slot)) return;
      persistAvailability({
        ...availability,
        [dateIso]: mark
          ? Array.from(new Set([...(availability[dateIso] ?? []), slot])).sort((a, b) => a - b)
          : (availability[dateIso] ?? []).filter((item) => item !== slot),
      });
    },
    [availability, busy, persistAvailability, setup],
  );

  const handlePointerDown = (dateIso: string, slot: number) => {
    if (!setup || busy[dateIso]?.includes(slot)) return;
    const mark = !(availability[dateIso] ?? []).includes(slot);
    setDrag({ mark, last: `${dateIso}:${slot}` });
    setSlot(dateIso, slot, mark);
  };

  const handlePointerEnter = (dateIso: string, slot: number) => {
    if (!drag) return;
    const key = `${dateIso}:${slot}`;
    if (drag.last === key) return;
    setDrag({ ...drag, last: key });
    setSlot(dateIso, slot, drag.mark);
  };

  const downloadHtml = () => {
    if (!setup) return;
    const html = buildAvailabilityHtml(setup, availability, busy);
    const url = URL.createObjectURL(new Blob([html], { type: "text/html" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `availability_${todayIso()}.html`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const copySummary = async () => {
    if (!setup) return;
    const lines = setup.selectedDates.map((dateIso) => {
      const slots = availability[dateIso] ?? [];
      if (!slots.length) return `${format(dateFromIso(dateIso), "EEE, MMM d")}: unavailable`;
      return `${format(dateFromIso(dateIso), "EEE, MMM d")}: ${slots
        .map((slot) => `${shortHourLabel(setup.startHour + slot)}-${shortHourLabel(setup.startHour + slot + 1)}`)
        .join(", ")}`;
    });
    await navigator.clipboard.writeText(lines.join("\n"));
    setMessage("Availability copied.");
  };

  const shareAvailability = () => {
    if (!setup) return;
    setMessage("");
    setShareResult(null);
    createShare.mutate(
      makeSnapshot(setup.selectedDates, setup.startHour, setup.endHour, availability, busy),
    );
  };

  const copyShareLink = async () => {
    if (!shareResult) return;
    try {
      await navigator.clipboard.writeText(shareResult.url);
      setMessage("Share link copied.");
    } catch {
      setMessage("Copy was blocked. Select the visible share link instead.");
    }
  };

  const days = useMemo(() => monthDays(month), [month]);

  return (
    <section>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-black">Availability</h1>
          <p className="mt-1 text-[#667085]">
            Click or drag to pick dates, then mark your free hours. Timed tasks show as busy blocks.
          </p>
        </div>
        {mode === "grid" ? (
          <button className="btn btn-secondary" onClick={() => setMode("setup")}>
            <Edit3 size={17} /> Edit dates
          </button>
        ) : null}
      </div>

      {mode === "setup" ? (
        <div className="grid gap-5 xl:grid-cols-[minmax(360px,640px)_360px]">
          <div className="panel overflow-hidden">
            <div className="flex items-center justify-between border-b border-[#dfd7ca] bg-white px-4 py-3">
              <button className="btn btn-secondary min-w-10 px-2" onClick={() => setMonth(subMonths(month, 1))}>
                <ChevronLeft size={18} />
              </button>
              <h2 className="text-lg font-black">{format(month, "MMMM yyyy")}</h2>
              <button className="btn btn-secondary min-w-10 px-2" onClick={() => setMonth(addMonths(month, 1))}>
                <ChevronRight size={18} />
              </button>
            </div>
            <div
              className="availability-date-grid grid grid-cols-7"
              onPointerCancel={handleDatePointerEnd}
              onPointerMove={handleDatePointerMove}
              onPointerUp={handleDatePointerEnd}
              ref={dateGridRef}
            >
              {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day) => (
                <div className="border-b border-[#dfd7ca] p-3 text-center text-sm font-black text-[#667085]" key={day}>
                  {day}
                </div>
              ))}
              {days.map((day) => {
                const iso = toDateIso(day);
                const selected = setupDraft.selectedDates.includes(iso);
                const inMonth = day.getMonth() === month.getMonth();
                const isToday = isSameDay(day, today);
                return (
                  <button
                    className={`availability-date ${selected ? "availability-date-selected" : ""} ${
                      isToday ? "availability-date-today" : ""
                    } ${inMonth ? "" : "availability-date-muted"}`}
                    data-date-iso={iso}
                    key={iso}
                    onClick={() => {
                      if (suppressDateClickRef.current) {
                        suppressDateClickRef.current = false;
                        return;
                      }
                      toggleDate(iso);
                    }}
                    onPointerDown={(event) => handleDatePointerDown(event, iso, selected)}
                  >
                    {format(day, "d")}
                  </button>
                );
              })}
            </div>
          </div>

          <aside className="panel p-4">
            <h2 className="text-xl font-black">Setup</h2>
            <p className="mt-1 text-sm text-[#667085]">{selectedLabel(setupDraft.selectedDates)}</p>
            <div className="mt-4 grid gap-3">
              <select
                className="field"
                onChange={(event) => setSetupDraft((current) => ({ ...current, startHour: Number(event.target.value) }))}
                value={setupDraft.startHour}
              >
                <option value={-1}>Start time</option>
                {Array.from({ length: 25 }, (_, hour) => (
                  <option key={hour} value={hour}>
                    {hourLabel(hour)}
                  </option>
                ))}
              </select>
              <select
                className="field"
                onChange={(event) => setSetupDraft((current) => ({ ...current, endHour: Number(event.target.value) }))}
                value={setupDraft.endHour}
              >
                <option value={-1}>End time</option>
                {Array.from({ length: 25 }, (_, hour) => (
                  <option key={hour} value={hour}>
                    {hourLabel(hour)}
                  </option>
                ))}
              </select>
              <button className="btn btn-primary" onClick={confirmSetup}>
                View availability
              </button>
              {message ? <p className="rounded-lg bg-[#fff2e8] px-3 py-2 text-sm font-bold text-[#9a3412]">{message}</p> : null}
            </div>
          </aside>
        </div>
      ) : setup ? (
        <div className="grid gap-4">
          <div className="flex flex-wrap items-center gap-2">
            <p className="mr-auto font-bold text-[#667085]">
              {selectedLabel(setup.selectedDates)} · {hourLabel(setup.startHour)} to {hourLabel(setup.endHour)}
            </p>
            <button className="btn btn-secondary" onClick={copySummary}>
              <Copy size={17} /> Copy summary
            </button>
            <button className="btn btn-secondary" disabled={createShare.isPending} onClick={shareAvailability}>
              {createShare.isPending ? <Loader2 className="animate-spin" size={17} /> : <Share2 size={17} />}
              Share link
            </button>
            <button className="btn btn-secondary" onClick={downloadHtml}>
              <Download size={17} /> Export HTML
            </button>
          </div>
          {message ? <p className="text-sm font-bold text-[#667085]">{message}</p> : null}
          {shareResult ? (
            <div className="panel flex max-w-3xl flex-wrap items-center gap-3 p-3">
              <div className="min-w-0 flex-1">
                <p className="break-all text-sm font-bold">{shareResult.url}</p>
                <p className="mt-1 text-xs text-[var(--muted)]">
                  Expires {new Date(shareResult.expires_at).toLocaleString()}
                </p>
              </div>
              <button className="btn btn-secondary" onClick={copyShareLink}>
                <Copy size={17} /> Copy
              </button>
            </div>
          ) : null}
          <AvailabilityGrid
            onPointerDown={handlePointerDown}
            onPointerEnd={() => setDrag(null)}
            onPointerEnter={handlePointerEnter}
            snapshot={makeSnapshot(setup.selectedDates, setup.startHour, setup.endHour, availability, busy)}
          />
          <AvailabilityLegend />
        </div>
      ) : null}
    </section>
  );
}
