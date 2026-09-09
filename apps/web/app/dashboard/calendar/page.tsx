"use client";

import { addDays, addMonths, endOfMonth, endOfWeek, format, isSameDay, startOfMonth, startOfWeek, subMonths } from "date-fns";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Task } from "@/lib/types";
import { LinkedText } from "@/components/linked-text";
import { TaskEditorModal, type TaskEditorPayload } from "@/components/task-editor-modal";

function compareCalendarTasks(a: Task, b: Task) {
  if (Boolean(a.due_at) !== Boolean(b.due_at)) return a.due_at ? -1 : 1;
  if (a.due_at && b.due_at) {
    return new Date(a.due_at!).getTime() - new Date(b.due_at!).getTime();
  }
  return a.title.localeCompare(b.title);
}

export default function CalendarPage() {
  const qc = useQueryClient();
  const [month, setMonth] = useState(() => new Date());
  const [selected, setSelected] = useState(() => new Date());
  const [editing, setEditing] = useState<Task | null>(null);
  const today = useMemo(() => new Date(), []);
  const update = useMutation({
    mutationFn: ({ task, payload }: { task: Task; payload: Partial<TaskEditorPayload> }) =>
      api<Task>(`/tasks/${task.id}`, { method: "PATCH", body: JSON.stringify(payload) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["calendar"] }),
  });
  const range = useMemo(() => {
    const start = startOfWeek(startOfMonth(month), { weekStartsOn: 1 });
    const end = endOfWeek(endOfMonth(month), { weekStartsOn: 1 });
    return { start, end };
  }, [month]);
  const { data } = useQuery({
    queryKey: ["calendar", range.start.toISOString(), range.end.toISOString()],
    queryFn: () => api<Task[]>(
      `/tasks/calendar?start=${encodeURIComponent(range.start.toISOString())}` +
      `&end=${encodeURIComponent(range.end.toISOString())}` +
      `&start_date=${format(range.start, "yyyy-MM-dd")}` +
      `&end_date=${format(addDays(range.end, 1), "yyyy-MM-dd")}`,
    ),
  });
  const days = useMemo(() => {
    const result: Date[] = [];
    const cursor = new Date(range.start);
    while (cursor <= range.end) {
      result.push(new Date(cursor));
      cursor.setDate(cursor.getDate() + 1);
    }
    return result;
  }, [range]);
  const tasksFor = (day: Date) => {
    const dayIso = format(day, "yyyy-MM-dd");
    return (
    (data ?? [])
      .filter((task) => task.due_at
        ? isSameDay(new Date(task.due_at), day)
        : Boolean(task.due_date && task.due_date <= dayIso && (task.end_date ? task.end_date > dayIso : task.due_date === dayIso)))
      .sort(compareCalendarTasks)
    );
  };
  const selectedTasks = tasksFor(selected);

  return (
    <section className="grid gap-6 xl:grid-cols-[1fr_360px]">
      <div>
        <div className="mb-4 flex items-center justify-between lg:mb-5">
          <div>
            <h1 className="hidden text-3xl font-black lg:block">Calendar</h1>
            <p className="text-lg font-bold text-[var(--foreground)] lg:mt-1 lg:text-base lg:font-normal lg:text-[#667085]">{format(month, "MMMM yyyy")}</p>
          </div>
          <div className="flex gap-2">
            <button aria-label="Previous month" className="btn btn-secondary min-w-11 px-2" onClick={() => setMonth(subMonths(month, 1))}>
              <ChevronLeft size={18} />
            </button>
            <button aria-label="Next month" className="btn btn-secondary min-w-11 px-2" onClick={() => setMonth(addMonths(month, 1))}>
              <ChevronRight size={18} />
            </button>
          </div>
        </div>
        <div className="calendar-grid panel grid grid-cols-7 overflow-hidden">
          {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day) => (
            <div className="border-b border-[#dfd7ca] bg-white p-2 text-center text-xs font-bold text-[#667085] lg:p-3 lg:text-left lg:text-sm lg:font-black" key={day}>
              <span className="calendar-weekday-short">{day[0]}</span>
              <span className="calendar-weekday-long">{day}</span>
            </div>
          ))}
          {days.map((day) => {
            const tasks = tasksFor(day);
            const active = isSameDay(day, selected);
            const isToday = isSameDay(day, today);
            return (
              <button
                aria-label={`${format(day, "EEEE, MMMM d")}, ${tasks.length} ${tasks.length === 1 ? "task" : "tasks"}`}
                className={`calendar-day border-b border-r border-[#eee6da] ${
                  active ? "calendar-day-selected" : "bg-white"
                } ${isToday ? "calendar-day-today" : ""}`}
                key={day.toISOString()}
                onClick={() => setSelected(day)}
              >
                <span className="font-black">{format(day, "d")}</span>
                <div aria-hidden="true" className="calendar-mobile-markers lg:hidden">
                  {tasks.length > 3 ? (
                    <span className="calendar-mobile-count">{tasks.length}</span>
                  ) : (
                    tasks.map((task) => <span key={`${task.id}-marker`} />)
                  )}
                </div>
                <div className="mt-2 hidden space-y-1 lg:block">
                  {tasks.slice(0, 3).map((task) => (
                    <p
                      className="truncate rounded bg-[#f2f4f7] px-2 py-1 text-xs font-bold"
                      key={`${task.id}-${task.due_at ?? task.due_date}`}
                    >
                      {task.title}
                    </p>
                  ))}
                </div>
              </button>
            );
          })}
        </div>
      </div>
      <aside className="panel p-4">
        <h2 className="text-xl font-black">{format(selected, "EEE, MMM d")}</h2>
        <div className="mt-4 space-y-3">
          {selectedTasks.length ? (
            selectedTasks.map((task) => (
              <button
                className="min-w-0 w-full rounded-lg border border-[#e6ded2] bg-white p-3 text-left hover:border-[#c9bfb3] transition-colors"
                key={`${task.id}-${task.due_at ?? task.due_date}`}
                onClick={() => setEditing(task)}
              >
                <p className="break-words font-black">{task.title}</p>
                {task.description ? (
                  <p className="mt-1 truncate text-sm text-[#667085]">
                    <LinkedText text={task.description.split("\n")[0]} />
                  </p>
                ) : null}
                <p className="mt-1 text-sm text-[#667085]">
                  {task.due_at ? new Date(task.due_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "All day"}
                </p>
              </button>
            ))
          ) : (
            <p className="text-[#667085]">No tasks for this day.</p>
          )}
        </div>
      </aside>
      <TaskEditorModal
        mode="edit"
        onClose={() => setEditing(null)}
        onSave={(payload) => {
          if (!editing) return Promise.resolve();
          return update.mutateAsync({ task: editing, payload });
        }}
        open={Boolean(editing)}
        task={editing}
      />
    </section>
  );
}
