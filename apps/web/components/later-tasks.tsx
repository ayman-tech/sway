"use client";

import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { addTaskDays, taskOccurrenceKey } from "@/lib/task-view";
import { shouldRetryTaskRead, taskRetryDelay } from "@/lib/task-recovery";
import type { Task } from "@/lib/types";
import { useTaskData } from "@/components/task-data-provider";
import { TaskCard } from "@/components/task-card";

export function LaterTasks({ today, timezone, primaryTasks, onOpen, onComplete, onDelete }: {
  today: string; timezone: string; primaryTasks: Task[];
  onOpen: (task: Task) => void; onComplete: (task: Task) => Promise<unknown>; onDelete: (task: Task) => Promise<unknown>;
}) {
  const qc = useQueryClient();
  const { session, canWrite, canQueue, waitingForNetwork } = useTaskData();
  const stateKey = ["task-later", session.user.id, timezone, today, "ranges"];
  // Memory only, retained across dashboard navigation. Identity/date changes use
  // a new key; a full reload or account cleanup clears this expansion state.
  const { data: count } = useQuery({ queryKey: stateKey, queryFn: () => 0, initialData: 0, enabled: false, gcTime: Infinity });
  const batches = useQueries({ queries: Array.from({ length: count }, (_, index) => {
    const start = addTaskDays(today, index === 0 ? 8 : index * 30 + 1);
    const end = addTaskDays(today, (index + 1) * 30);
    return {
      queryKey: ["task-later", session.user.id, timezone, today, start, end],
      queryFn: ({ signal }: { signal: AbortSignal }) => api<Task[]>(`/tasks/later?start_date=${start}&end_date=${end}&timezone_name=${encodeURIComponent(timezone)}`, { signal }, { expectedUserId: session.user.id }),
      enabled: canWrite && !waitingForNetwork,
      retry: shouldRetryTaskRead, retryDelay: taskRetryDelay,
    };
  }) });
  const seen = new Set(primaryTasks.map(taskOccurrenceKey));
  const fetching = batches.some((batch) => batch.isFetching || batch.fetchStatus === "paused");
  const failed = batches.some((batch) => batch.isError);
  return <section className="space-y-3" aria-label="Later tasks">
    {count > 0 ? <><h2 className="text-lg font-bold lg:text-xl">Later</h2><p className="text-xs text-[var(--muted)]">Requested range: {addTaskDays(today, 8)} – {addTaskDays(today, count * 30)}</p></> : null}
    {batches.map((batch, index) => {
      const tasks = (batch.data ?? []).filter((task) => { const key = taskOccurrenceKey(task); if (seen.has(key)) return false; seen.add(key); return true; });
      const start = addTaskDays(today, index === 0 ? 8 : index * 30 + 1);
      const end = addTaskDays(today, (index + 1) * 30);
      return <div key={`${start}:${end}`}>
        {tasks.map((task) => <TaskCard key={taskOccurrenceKey(task)} task={task} onOpen={onOpen} onComplete={onComplete} onDelete={async (value) => { await onDelete(value); }} disabled={!canWrite || batch.isError} completeDisabled={!canQueue || batch.isError} />)}
        {batch.isFetching || batch.fetchStatus === "paused" ? <p role="status" className="py-2 text-sm text-[var(--muted)]">{waitingForNetwork ? "Waiting for connection…" : batch.failureCount > 0 ? "Reconnecting…" : "Loading later tasks…"}</p> : null}
        {batch.isError && !batch.isFetching ? <div role="alert" className="panel p-3 text-sm"><p>Couldn’t refresh tasks for {start} – {end}.</p><button className="btn btn-secondary mt-2" disabled={!canWrite || waitingForNetwork} onClick={() => void batch.refetch()}>Retry later tasks</button></div> : null}
        {batch.isSuccess && !batch.isFetching && !tasks.length ? <p className="py-2 text-sm text-[var(--muted)]">No tasks found for {start} – {end}.</p> : null}
      </div>;
    })}
    <button className="btn btn-secondary min-h-11" disabled={!canWrite || waitingForNetwork || fetching || failed} onClick={() => qc.setQueryData(stateKey, count + 1)}>{count ? "Load next 30 days" : "Load later tasks"}</button>
    {!canWrite && !count ? <p className="text-xs text-[var(--muted)]">Refresh tasks to load future dates.</p> : null}
  </section>;
}
