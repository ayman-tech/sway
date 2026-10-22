// Pure work-log helpers. Keep this file free of path-alias imports so `node --test` can load it.

export const WINDOW_DAYS = 7;
export const DEFAULT_WORK_START = 9;
export const DEFAULT_WORK_END = 18;

const pad = (value: number) => String(value).padStart(2, "0");

export function dayIso(date: Date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function parseDay(iso: string) {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export function addDaysIso(iso: string, days: number) {
  const date = parseDay(iso);
  date.setDate(date.getDate() + days);
  return dayIso(date);
}

/** The 7 selectable shift days, oldest first, ending at the local `today`. */
export function windowDays(today: string) {
  return Array.from({ length: WINDOW_DAYS }, (_, i) => addDaysIso(today, i - (WINDOW_DAYS - 1)));
}

export function crossesMidnight(start: number, end: number) {
  return end <= start;
}

/** Clock hours of the schedule in order. `end <= start` wraps past midnight; `end == start` is 24 hours. */
export function scheduleSlots(start: number, end: number) {
  const count = (((end - start) % 24) + 24) % 24 || 24;
  return Array.from({ length: count }, (_, i) => (start + i) % 24);
}

export function slotLabel(hour: number) {
  return `${pad(hour)}:00-${pad((hour + 1) % 24)}:00`;
}

export function hourLabel(hour: number) {
  return `${pad(hour % 24)}:00`;
}

/** The shift day that is in progress: before a midnight-crossing shift ends it is still yesterday's. */
export function currentShiftDay(now: Date, start: number, end: number) {
  const today = dayIso(now);
  return crossesMidnight(start, end) && now.getHours() < end ? addDaysIso(today, -1) : today;
}

export type DayLayout = { scheduled: number[]; extra: number[] };

/** Scheduled hours plus any hours that hold a note but fell outside the schedule (e.g. after changing it). */
export function dayLayout(slots: number[], notes: Map<number, string>): DayLayout {
  const inSchedule = new Set(slots);
  const first = slots[0] ?? 0;
  const extra = [...notes.keys()]
    .filter((hour) => !inSchedule.has(hour) && notes.get(hour)?.trim())
    .sort((a, b) => ((a - first + 24) % 24) - ((b - first + 24) % 24));
  return { scheduled: slots, extra };
}

export function loggedCount(slots: number[], notes: Map<number, string>) {
  return slots.filter((hour) => notes.get(hour)?.trim()).length;
}

export function dayAsText(title: string, layout: DayLayout, notes: Map<number, string>) {
  const lines = [...layout.scheduled, ...layout.extra].flatMap((hour) => {
    const note = notes.get(hour)?.trim();
    if (!note) return [];
    const [first, ...rest] = note.split("\n");
    return [`${slotLabel(hour)} - ${first}`, ...rest.map((line) => `            ${line}`)];
  });
  return [title, ...lines].join("\n");
}
