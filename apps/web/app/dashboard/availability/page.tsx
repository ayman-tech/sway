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
import { ChevronLeft, ChevronRight, Copy, Download, Edit3 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Task } from "@/lib/types";

type AvailabilitySetup = {
  selectedDates: string[];
  startHour: number;
  endHour: number;
};

type AvailabilityState = Record<string, number[]>;
type BusyMap = Record<string, Record<number, string>>;

const SETUP_KEY = "sway.availability.setup";
const STATE_KEY = "sway.availability.state";
const MAX_DATES = 14;

function todayIso() {
  return toDateIso(new Date());
}

function toDateIso(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function dateFromIso(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function hourLabel(hour: number) {
  if (hour === 0 || hour === 24) return "12:00 AM";
  if (hour === 12) return "12:00 PM";
  return `${hour % 12}:00 ${hour < 12 ? "AM" : "PM"}`;
}

function shortHourLabel(hour: number) {
  if (hour === 0 || hour === 24) return "12 AM";
  if (hour === 12) return "12 PM";
  return `${hour % 12} ${hour < 12 ? "AM" : "PM"}`;
}

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

function selectedLabel(dates: string[]) {
  const parsed = dates.map(dateFromIso).sort((a, b) => a.getTime() - b.getTime());
  if (parsed.length <= 5) {
    return parsed.map((date) => format(date, "MMM d")).join(", ");
  }
  return `${format(parsed[0], "MMM d")} to ${format(parsed[parsed.length - 1], "MMM d")} · ${parsed.length} selected dates`;
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
        busy[dateIso] = { ...(busy[dateIso] ?? {}), [row]: task.title };
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
    const busySlots = new Set(Object.keys(busy[dateIso] ?? {}).map(Number));
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
          const cls = busy[dateIso]?.[row] ? "busy" : availability[dateIso]?.includes(row) ? "available" : "free";
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
  const [drag, setDrag] = useState<{ mark: boolean; last: string } | null>(null);
  const today = useMemo(() => new Date(), []);
  const gridRef = useRef<HTMLDivElement | null>(null);

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

  const toggleDate = (date: Date) => {
    const iso = toDateIso(date);
    setSetupDraft((current) => {
      const selected = new Set(current.selectedDates);
      if (selected.has(iso)) {
        selected.delete(iso);
      } else if (selected.size < MAX_DATES) {
        selected.add(iso);
      } else {
        setMessage(`Choose ${MAX_DATES} dates or fewer.`);
      }
      const selectedDates = Array.from(selected).sort();
      return { ...current, selectedDates };
    });
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
      if (!setup || busy[dateIso]?.[slot]) return;
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
    if (!setup || busy[dateIso]?.[slot]) return;
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

  const days = useMemo(() => monthDays(month), [month]);

  return (
    <section>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-black">Availability</h1>
          <p className="mt-1 text-[#667085]">
            Pick dates and mark your free hours. Timed tasks show as busy blocks.
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
            <div className="grid grid-cols-7">
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
                    key={iso}
                    onClick={() => toggleDate(day)}
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
            <button className="btn btn-secondary" onClick={downloadHtml}>
              <Download size={17} /> Export HTML
            </button>
          </div>
          {message ? <p className="text-sm font-bold text-[#667085]">{message}</p> : null}
          <div className="availability-grid-shell panel overflow-auto" onPointerLeave={() => setDrag(null)} onPointerUp={() => setDrag(null)} ref={gridRef}>
            <div
              className="availability-grid min-w-max"
              style={{
                gridTemplateColumns: `64px repeat(${setup.selectedDates.length}, 180px)`,
              }}
            >
              <div className="availability-header" />
              {setup.selectedDates.map((dateIso) => (
                <div className="availability-header text-center" key={dateIso}>
                  <p className="text-xs font-bold text-[#667085]">{format(dateFromIso(dateIso), "EEE")}</p>
                  <p className="font-black">{format(dateFromIso(dateIso), "MMM d")}</p>
                </div>
              ))}
              {Array.from({ length: setup.endHour - setup.startHour }, (_, slot) => (
                <div className="contents" key={slot}>
                  <div className="availability-time">{shortHourLabel(setup.startHour + slot)}</div>
                  {setup.selectedDates.map((dateIso) => {
                    const isBusy = Boolean(busy[dateIso]?.[slot]);
                    const isAvailable = (availability[dateIso] ?? []).includes(slot);
                    return (
                      <button
                        aria-label={`${format(dateFromIso(dateIso), "MMM d")} ${shortHourLabel(setup.startHour + slot)}`}
                        className={`availability-slot ${isBusy ? "availability-busy" : isAvailable ? "availability-available" : "availability-free"}`}
                        disabled={isBusy}
                        key={`${dateIso}-${slot}`}
                        onPointerDown={() => handlePointerDown(dateIso, slot)}
                        onPointerEnter={() => handlePointerEnter(dateIso, slot)}
                        title={isBusy ? "Busy from a timed task" : isAvailable ? "Available" : "Unavailable"}
                        type="button"
                      />
                    );
                  })}
                </div>
              ))}
            </div>
          </div>
          <div className="flex flex-wrap gap-4 text-sm font-bold text-[#667085]">
            <span className="availability-legend availability-legend-free">Unavailable</span>
            <span className="availability-legend availability-legend-available">Available</span>
            <span className="availability-legend availability-legend-busy">Busy task</span>
          </div>
        </div>
      ) : null}
    </section>
  );
}
