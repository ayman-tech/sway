"use client";

import { addDays, addMonths, endOfMonth, endOfWeek, format, isSameDay, startOfMonth, startOfWeek, subMonths } from "date-fns";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Task } from "@/lib/types";
import { LinkedText } from "@/components/linked-text";

function compareCalendarTasks(a: Task, b: Task) {
  if (Boolean(a.due_at) !== Boolean(b.due_at)) return a.due_at ? -1 : 1;
  if (a.due_at && b.due_at) {
    return new Date(a.due_at!).getTime() - new Date(b.due_at!).getTime();
  }
  return a.title.localeCompare(b.title);
}

export default function CalendarPage() {
  const [month, setMonth] = useState(() => new Date());
  const [selected, setSelected] = useState(() => new Date());
  const today = useMemo(() => new Date(), []);
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
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-black">Calendar</h1>
            <p className="mt-1 text-[#667085]">{format(month, "MMMM yyyy")}</p>
          </div>
          <div className="flex gap-2">
            <button className="btn btn-secondary min-w-10 px-2" onClick={() => setMonth(subMonths(month, 1))}>
              <ChevronLeft size={18} />
            </button>
            <button className="btn btn-secondary min-w-10 px-2" onClick={() => setMonth(addMonths(month, 1))}>
              <ChevronRight size={18} />
            </button>
          </div>
        </div>
        <div className="panel grid grid-cols-7 overflow-hidden">
          {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day) => (
            <div className="border-b border-[#dfd7ca] bg-white p-3 text-sm font-black text-[#667085]" key={day}>
              {day}
            </div>
          ))}
          {days.map((day) => {
            const tasks = tasksFor(day);
            const active = isSameDay(day, selected);
            const isToday = isSameDay(day, today);
            return (
              <button
                className={`min-h-28 border-b border-r border-[#eee6da] p-2 text-left ${
                  active ? "calendar-day-selected" : "bg-white"
                } ${isToday ? "calendar-day-today" : ""}`}
                key={day.toISOString()}
                onClick={() => setSelected(day)}
              >
                <span className="font-black">{format(day, "d")}</span>
                <div className="mt-2 space-y-1">
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
              <div className="min-w-0 rounded-lg border border-[#e6ded2] bg-white p-3" key={`${task.id}-${task.due_at ?? task.due_date}`}>
                <p className="break-words font-black">{task.title}</p>
                {task.description ? (
                  <p className="mt-1 min-w-0 whitespace-pre-wrap break-words text-sm text-[#667085] [overflow-wrap:anywhere]">
                    <LinkedText text={task.description} />
                  </p>
                ) : null}
                <p className="mt-1 text-sm text-[#667085]">
                  {task.due_at ? new Date(task.due_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "All day"}
                </p>
              </div>
            ))
          ) : (
            <p className="text-[#667085]">No tasks for this day.</p>
          )}
        </div>
      </aside>
    </section>
  );
}
