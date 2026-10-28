// Which page Sway opens first. A per-device display preference, kept in this browser only.

export const START_VIEWS = [
  { value: "tasks", label: "Tasks", href: "/dashboard/tasks" },
  { value: "calendar", label: "Calendar", href: "/dashboard/calendar" },
  { value: "worklog", label: "Work log", href: "/dashboard/worklog" },
  { value: "availability", label: "Availability", href: "/dashboard/availability" },
  { value: "completed", label: "Completed", href: "/dashboard/completed" },
] as const;

export type StartView = (typeof START_VIEWS)[number]["value"];

export const DEFAULT_START_VIEW: StartView = "tasks";
const STORAGE_KEY = "sway-start-view";

export function isStartView(value: unknown): value is StartView {
  return START_VIEWS.some((view) => view.value === value);
}

export function readStartView(): StartView {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return isStartView(stored) ? stored : DEFAULT_START_VIEW;
  } catch {
    return DEFAULT_START_VIEW;
  }
}

export function writeStartView(view: StartView) {
  try {
    window.localStorage.setItem(STORAGE_KEY, view);
  } catch {
    // Storage can be blocked; the preference then simply doesn't persist.
  }
}

export function startViewHref(view: StartView) {
  return (START_VIEWS.find((item) => item.value === view) ?? START_VIEWS[0]).href;
}
