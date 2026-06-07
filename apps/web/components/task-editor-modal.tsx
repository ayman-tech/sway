"use client";

import { useEffect, useState } from "react";
import { Loader2, X } from "lucide-react";
import { formatInTimeZone, fromZonedTime } from "date-fns-tz";
import type { Task } from "@/lib/types";

export type TaskEditorPayload = {
  title: string;
  description?: string | null;
  due_at?: string | null;
  due_date?: string | null;
  end_at?: string | null;
  end_date?: string | null;
  reminder_minutes_before?: number | null;
  recurrence_rule?: string | null;
  recurrence_timezone?: string | null;
};

const reminderOptions = [
  ["No heads up", ""],
  ["10 min before", "10"],
  ["30 min before", "30"],
  ["1 hr before", "60"],
  ["3 hr before", "180"],
  ["1 day early", "1440"],
] as const;

const durationOptions = [
  ["Duration", ""],
  ["30 min", "30"],
  ["1 hr", "60"],
  ["2 hr", "120"],
  ["3 hr", "180"],
] as const;

const repeatOptions = [
  ["Don't repeat", ""],
  ["Daily", "FREQ=DAILY"],
  ["Weekly", "FREQ=WEEKLY"],
  ["Every 2 weeks", "FREQ=WEEKLY;INTERVAL=2"],
  ["Monthly", "FREQ=MONTHLY"],
  ["Yearly", "FREQ=YEARLY"],
] as const;

function dateValue(task?: Task | null) {
  if (task?.due_date) return task.due_date;
  if (!task?.due_at) return "";
  return formatInTimeZone(task.due_at, task.recurrence_timezone || deviceTimezone(), "yyyy-MM-dd");
}

function timeValue(value?: string | null, timezone?: string | null) {
  if (!value) return "";
  return formatInTimeZone(value, timezone || deviceTimezone(), "HH:mm");
}

function deviceTimezone() {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
}

function zonedDateTimeIso(date: string, time: string, timezone: string) {
  return fromZonedTime(`${date}T${time}:00`, timezone).toISOString();
}

function durationFromTask(task?: Task | null) {
  if (!task?.due_at || !task.end_at) return "";
  const minutes = Math.round((new Date(task.end_at).getTime() - new Date(task.due_at).getTime()) / 60000);
  return durationOptions.some(([, value]) => value === String(minutes)) ? String(minutes) : "";
}

function repeatBase(rule: string | null | undefined) {
  if (!rule) return "";
  return rule
    .split(";")
    .filter((part) => !part.startsWith("UNTIL="))
    .join(";");
}

function repeatUntilValue(rule: string | null | undefined, timezone?: string | null) {
  const until = rule?.split(";").find((part) => part.startsWith("UNTIL="))?.split("=")[1];
  if (!until) return "";
  const normalized = until.replace("Z", "");
  const year = normalized.slice(0, 4);
  const month = normalized.slice(4, 6);
  const day = normalized.slice(6, 8);
  if (normalized.includes("T")) {
    const hour = normalized.slice(9, 11);
    const minute = normalized.slice(11, 13);
    const second = normalized.slice(13, 15);
    return formatInTimeZone(`${year}-${month}-${day}T${hour}:${minute}:${second}Z`, timezone || deviceTimezone(), "yyyy-MM-dd");
  }
  return year && month && day ? `${year}-${month}-${day}` : "";
}

function withRepeatUntil(rule: string, untilDate: string, timed: boolean, timezone: string) {
  if (!rule || !untilDate) return rule || null;
  if (!timed) return `${rule};UNTIL=${untilDate.replaceAll("-", "")}`;
  const until = fromZonedTime(`${untilDate}T23:59:59`, timezone).toISOString();
  const stamp = `${until.replaceAll("-", "").replaceAll(":", "").split(".")[0]}Z`;
  return `${rule};UNTIL=${stamp}`;
}

export function TaskEditorModal({
  mode,
  task,
  open,
  onClose,
  onSave,
}: {
  mode: "create" | "edit";
  task?: Task | null;
  open: boolean;
  onClose: () => void;
  onSave: (payload: Partial<TaskEditorPayload>) => Promise<unknown>;
}) {
  const readOnly = Boolean(task?.is_preview || task?.source === "google");
  const allowReminderOnly = Boolean(task?.source === "google" && task?.due_at && !task?.is_preview);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  const [duration, setDuration] = useState("");
  const [reminder, setReminder] = useState("");
  const [repeat, setRepeat] = useState("");
  const [repeatUntil, setRepeatUntil] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setTitle(task?.title ?? "");
    setDescription(task?.description ?? "");
    setDate(dateValue(task));
    setTime(task?.due_at ? timeValue(task.due_at, task.recurrence_timezone) : "");
    setDuration(durationFromTask(task));
    setReminder(task?.reminder_minutes_before?.toString() ?? "");
    setRepeat(repeatBase(task?.recurrence_rule));
    setRepeatUntil(repeatUntilValue(task?.recurrence_rule, task?.recurrence_timezone));
    setError("");
  }, [open, task]);

  if (!open) return null;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    if (readOnly && !allowReminderOnly) {
      onClose();
      return;
    }
    if (!readOnly && !title.trim()) {
      setError("Task title cannot be empty.");
      return;
    }
    setSaving(true);
    try {
      if (allowReminderOnly) {
        await onSave({ reminder_minutes_before: reminder ? Number(reminder) : null });
      } else {
        const timed = Boolean(date && time);
        const recurrenceTimezone = timed && repeat ? task?.recurrence_timezone || deviceTimezone() : null;
        const interpretationTimezone = task?.recurrence_timezone || recurrenceTimezone || deviceTimezone();
        const dueAt = timed ? zonedDateTimeIso(date, time, interpretationTimezone) : null;
        const endAt =
          dueAt && duration
            ? new Date(new Date(dueAt).getTime() + Number(duration) * 60000).toISOString()
            : null;
        await onSave({
          title: title.trim(),
          description: description.trim() || null,
          due_at: dueAt,
          due_date: date && !timed ? date : null,
          end_at: endAt,
          end_date: null,
          reminder_minutes_before: timed && reminder ? Number(reminder) : null,
          recurrence_rule: date && repeat ? withRepeatUntil(repeat, repeatUntil, timed, interpretationTimezone) : null,
          recurrence_timezone: recurrenceTimezone,
        });
      }
      onClose();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Unable to save task.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/45 px-4 py-8">
      <form className="panel task-editor max-h-[92vh] w-full max-w-[460px] overflow-auto p-5 shadow-2xl" onSubmit={submit}>
        <div className="mb-3 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-black">
              {mode === "create" ? "New Task" : readOnly ? "Google Calendar event" : "Edit Task"}
            </h2>
            {task?.source === "google" ? (
              <p className="mt-1 text-sm text-[var(--muted)]">
                Google Calendar tasks are read-only, but you can set an extra reminder.
              </p>
            ) : null}
          </div>
          <button className="btn btn-secondary min-w-10 px-2" onClick={onClose} type="button">
            <X size={18} />
          </button>
        </div>

        <div className="space-y-2">
          <label className="block">
            <input
              className="field"
              disabled={readOnly}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Title"
              required={!readOnly}
              value={title}
            />
          </label>
          <label className="block">
            <textarea
              className="field task-editor-notes resize-y"
              disabled={readOnly}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Notes"
              value={description}
            />
          </label>
          <div className="grid grid-cols-2 gap-2">
            <label className="block">
              <input className="field" disabled={readOnly} onChange={(event) => setDate(event.target.value)} type="date" value={date} />
            </label>
            <label className="block">
              <input className="field" disabled={readOnly || !date} onChange={(event) => setTime(event.target.value)} type="time" value={time} />
            </label>
            <label className="block">
              <select className="field" disabled={readOnly || !date || !time} onChange={(event) => setDuration(event.target.value)} value={duration}>
                {durationOptions.map(([label, value]) => (
                  <option key={label} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <select className="field" disabled={(!date || !time) && !allowReminderOnly} onChange={(event) => setReminder(event.target.value)} value={reminder}>
                {reminderOptions.map(([label, value]) => (
                  <option key={label} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <select className="field" disabled={readOnly || !date} onChange={(event) => setRepeat(event.target.value)} value={repeat}>
                {repeatOptions.map(([label, value]) => (
                  <option key={label} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <input
                className="field"
                disabled={readOnly || !repeat}
                onChange={(event) => setRepeatUntil(event.target.value)}
                placeholder="Repeat until"
                type="date"
                value={repeatUntil}
              />
            </label>
          </div>
        </div>

        {error ? <p className="mt-4 rounded-lg bg-[#fff2e8] p-3 text-sm font-bold text-[#9a3412]">{error}</p> : null}

        <div className="mt-5 flex flex-wrap justify-end gap-3">
          <button className="btn btn-secondary" onClick={onClose} type="button">
            Cancel
          </button>
          {readOnly && !allowReminderOnly ? null : (
            <button className="btn btn-primary" disabled={saving} type="submit">
              {saving ? <Loader2 className="animate-spin" size={18} /> : null}
              {mode === "create" ? "Add task" : "Save changes"}
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
