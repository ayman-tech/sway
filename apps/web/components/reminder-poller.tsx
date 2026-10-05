"use client";

import { useEffect, useRef } from "react";
import { api } from "@/lib/api";
import type { Task } from "@/lib/types";
import { usePush } from "@/components/push-provider";
import { deviceLock, foregroundAllowed, pushRegistration, readPushBinding } from "@/lib/push-device";

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
  const { enrolled, ready, foreground } = usePush();

  useEffect(() => {
    if (!ready || enrolled || !foreground) return;
    let alive = true;
    let timer: number;
    const controller = new AbortController();
    const check = async () => {
      try {
        if (!alive || !foregroundAllowed() || await readPushBinding()) return;
        const query = processed.current ? `?since=${encodeURIComponent(processed.current)}` : "";
        const batch = await api<ReminderBatch>(`/reminders/due${query}`, { signal: controller.signal });
        if (!alive || !foregroundAllowed() || await readPushBinding()) return;
        await deviceLock(async () => {
          if (!alive || !foregroundAllowed() || await readPushBinding()) return;
          const registration = await pushRegistration();
          for (const reminder of batch.reminders) {
            const title = reminder.task.title;
            const body = reminder.kind === "due" ? "Due now" : "Upcoming";
            if ("Notification" in window && Notification.permission === "granted") {
              const tag = `sway-foreground-${reminder.task.id}-${reminder.occurrence}-${reminder.fire_at}`;
              if (registration?.active) await registration.showNotification(title, { body, tag, icon: "/icons/sway-192.png", badge: "/icons/sway-badge-96.png" });
              else new Notification(title, { body, tag });
            }
          }
        });
        processed.current = batch.processed_through;
      } catch {
        // Auth redirects and network state are handled by the dashboard shell/query errors.
      }
      if (alive) {
        timer = window.setTimeout(check, 30000);
      }
    };
    timer = window.setTimeout(check, 30000);
    return () => {
      alive = false;
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [enrolled, ready, foreground]);

  return null;
}
