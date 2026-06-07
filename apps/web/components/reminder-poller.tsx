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

type ReminderBatch = {
  processed_through: string;
  reminders: Reminder[];
};

export function ReminderPoller() {
  const processed = useRef<string | null>(null);

  useEffect(() => {
    let alive = true;
    const check = async () => {
      try {
        const query = processed.current ? `?since=${encodeURIComponent(processed.current)}` : "";
        const batch = await api<ReminderBatch>(`/reminders/due${query}`);
        for (const reminder of batch.reminders) {
          const title = reminder.task.title;
          const body = reminder.kind === "due" ? "Due now" : "Upcoming";
          if ("Notification" in window && Notification.permission === "granted") {
            new Notification(title, { body });
          }
        }
        processed.current = batch.processed_through;
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
