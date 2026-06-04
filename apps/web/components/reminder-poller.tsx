"use client";

import { useEffect, useRef } from "react";
import { api } from "@/lib/api";
import type { Task } from "@/lib/types";

type Reminder = {
  fire_at: string;
  occurrence: string;
  kind: "due" | "extra";
  task: Task;
};

export function ReminderPoller() {
  const processed = useRef(new Date().toISOString());

  useEffect(() => {
    let alive = true;
    const check = async () => {
      try {
        const reminders = await api<Reminder[]>(`/reminders/due?since=${encodeURIComponent(processed.current)}`);
        processed.current = new Date().toISOString();
        for (const reminder of reminders) {
          const title = reminder.task.title;
          const body = reminder.kind === "due" ? "Due now" : "Upcoming";
          if ("Notification" in window && Notification.permission === "granted") {
            new Notification(title, { body });
          }
        }
      } catch {
        // Auth redirects and network state are handled by the dashboard shell/query errors.
      }
      if (alive) {
        window.setTimeout(check, 30000);
      }
    };
    const id = window.setTimeout(check, 30000);
    return () => {
      alive = false;
      window.clearTimeout(id);
    };
  }, []);

  return null;
}
