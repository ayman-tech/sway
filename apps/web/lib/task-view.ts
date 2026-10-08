import type { Task, TaskGroup } from "./types";

function dayFormatter(timezone: string) {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: timezone, year: "numeric", month: "2-digit", day: "2-digit",
  });
}

function dateKey(date: Date, formatter: Intl.DateTimeFormat): string {
  const parts = formatter.formatToParts(date);
  const get = (type: string) => parts.find((part) => part.type === type)!.value;
  return `${get("year")}-${get("month")}-${get("day")}`;
}

export function localDay(date: Date, timezone: string): string {
  return dateKey(date, dayFormatter(timezone));
}

export function formatLastSync(timestamp: number, timezone: string): string {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: timezone, year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23",
  }).formatToParts(new Date(timestamp));
  const get = (type: string) => parts.find((part) => part.type === type)!.value;
  return `${get("day")}/${get("month")}/${get("year")} ${get("hour")}:${get("minute")}:${get("second")}`;
}

// Reclassify only known occurrences: no fetching, recurrence expansion, or
// mutation of the authoritative response / persisted snapshot.
export function regroupSavedTasks(groups: TaskGroup[], today: string, timezone: string): TaskGroup[] {
  const formatter = dayFormatter(timezone);
  const weekEnd = new Date(`${today}T00:00:00Z`);
  weekEnd.setUTCDate(weekEnd.getUTCDate() + 7);
  const lastDay = weekEnd.toISOString().slice(0, 10);
  const labels = ["Overdue", "Today", "Next 7 Days", "Untimed", "Later"];
  const buckets = new Map(labels.map((label) => [label, [] as { task: Task; day: string | null }[]]));
  for (const group of groups) {
    for (const task of group.tasks) {
      const instant = task.due_at ? new Date(task.due_at) : null;
      const day = task.due_date ?? (instant && Number.isFinite(instant.getTime()) ? dateKey(instant, formatter) : null);
      const label = !day ? "Untimed" : day < today ? "Overdue" : day === today ? "Today" : day <= lastDay ? "Next 7 Days" : "Later";
      buckets.get(label)!.push({ task, day });
    }
  }
  return labels.flatMap((label) => {
    const bucket = buckets.get(label)!;
    if (!bucket.length) return [];
    bucket.sort((a, b) => label === "Untimed"
      ? Date.parse(b.task.created_at) - Date.parse(a.task.created_at)
      : a.day!.localeCompare(b.day!) || Number(!a.task.due_at) - Number(!b.task.due_at)
        || (a.task.due_at && b.task.due_at ? Date.parse(a.task.due_at) - Date.parse(b.task.due_at) : 0));
    return [{ label, overdue: label === "Overdue", tasks: bucket.map(({ task }) => task) }];
  });
}
