"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useTaskData } from "@/components/task-data-provider";

const FALLBACK_MS = 15_000;

/**
 * True once the first task load has finished (or failed), so background work such as
 * settings and push checks does not compete with the request the user is waiting on.
 * A fallback timer keeps that work from being held back forever, e.g. while offline.
 */
export function useAfterFirstTaskLoad() {
  const { firstLoadSettled } = useTaskData();
  const [timedOut, setTimedOut] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setTimedOut(true), FALLBACK_MS);
    return () => clearTimeout(timer);
  }, []);
  return firstLoadSettled || timedOut;
}

/**
 * For pages that don't show tasks: the task list waits until this page's own data has
 * loaded (or failed), so the two don't compete on a slow server. See HOLD_PATHS in
 * task-data-provider.tsx; a page must be listed there to be held.
 */
export function useReleaseTasksWhen(ready: boolean) {
  const { releaseTasks } = useTaskData();
  const pathname = usePathname();
  useEffect(() => {
    if (ready) releaseTasks(pathname);
  }, [ready, pathname, releaseTasks]);
}
