"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import { ApiError } from "@/lib/api";
import type { Task } from "@/lib/types";
import { useTaskData } from "@/components/task-data-provider";
import { TaskCard } from "@/components/task-card";
import { TaskEditorModal, type TaskEditorPayload } from "@/components/task-editor-modal";
import { formatLastSync, localDay, regroupSavedTasks } from "@/lib/task-view";

function currentDateContext() {
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  return { timezone, today: localDay(new Date(), timezone) };
}

export default function TasksPage() {
  const qc = useQueryClient();
  const [editing, setEditing] = useState<Task | null>(null);
  const taskData = useTaskData();
  const { groups: data, fetching: isFetching, error, failureCount, retry: refetch, canWrite, saved, fetchedAt } = taskData;
  const [dateContext, setDateContext] = useState(currentDateContext);
  useEffect(() => {
    const refreshDate = () => {
      const next = currentDateContext();
      setDateContext((previous) => previous.today === next.today && previous.timezone === next.timezone ? previous : next);
    };
    const timer = window.setInterval(refreshDate, 60_000);
    window.addEventListener("focus", refreshDate);
    document.addEventListener("visibilitychange", refreshDate);
    return () => {
      clearInterval(timer);
      window.removeEventListener("focus", refreshDate);
      document.removeEventListener("visibilitychange", refreshDate);
    };
  }, []);
  const displayGroups = useMemo(() => data && (saved || !canWrite)
    ? regroupSavedTasks(data, dateContext.today, dateContext.timezone) : data,
  [data, saved, canWrite, dateContext]);
  const isPending = data === undefined && !error;
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["task-groups"] });
    qc.invalidateQueries({ queryKey: ["completed"] });
    qc.invalidateQueries({ queryKey: ["calendar"] });
  };
  const update = useMutation({
    mutationFn: ({ task, payload }: { task: Task; payload: Partial<TaskEditorPayload> }) =>
      taskData.mutate<Task>(`/tasks/${task.id}`, { method: "PATCH", body: JSON.stringify(payload) }),
    onSuccess: refresh,
  });
  const complete = useMutation({
    mutationFn: (task: Task) => taskData.mutate<Task>(`/tasks/${task.id}/complete`, { method: "POST" }),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: (task: Task) => taskData.mutate<void>(`/tasks/${task.id}`, { method: "DELETE" }),
    onSuccess: refresh,
  });
  const hasData = data !== undefined;
  const reconnecting = !hasData && isPending && failureCount > 0;
  const errorMessage = error instanceof ApiError ? error.message : "Unable to load tasks.";

  return (
    <section className="space-y-5 lg:space-y-6">
      <div className="hidden lg:block">
        <h1 className="text-3xl font-black">Tasks</h1>
        <p className="mt-1 text-[var(--muted)]">Create, complete, and organize your active work.</p>
      </div>
      {!hasData && isPending ? (
        <div aria-live="polite" aria-busy="true" className="space-y-3" role="status">
          <p className="text-sm font-medium text-[var(--muted)]">
            {reconnecting ? "Reconnecting to Sway..." : "Loading tasks..."}
          </p>
          {[0, 1, 2].map((item) => (
            <div
              aria-hidden="true"
              className="panel h-[76px] animate-pulse bg-[var(--nav-hover)] motion-reduce:animate-none"
              key={item}
            />
          ))}
        </div>
      ) : null}
      {hasData && (isFetching || !canWrite || error) ? <div role="status" aria-live="polite" className="flex flex-wrap items-center gap-x-2 text-xs text-[var(--muted)]">
        <span>{isFetching ? "Sync in progress" : error ? "Saved tasks · Couldn’t sync" : "Saved tasks · Waiting to sync"}</span>
        {fetchedAt !== null ? <span>· Last sync: <time dateTime={new Date(fetchedAt).toISOString()}>{formatLastSync(fetchedAt, dateContext.timezone)}</time></span> : null}
        {!canWrite ? <span className="sr-only">Tasks are read-only until refresh succeeds.</span> : null}
        {!isFetching ? <button className="min-h-11 min-w-11 rounded px-2 font-semibold underline focus-visible:outline focus-visible:outline-2" onClick={refetch} type="button">Retry</button> : null}
      </div> : null}
      {complete.error || remove.error ? <p role="alert" className="panel p-3 text-sm">{complete.error?.message || remove.error?.message} No change has been confirmed. Refresh to check the latest task state.</p> : null}
      {error && !hasData ? (
        <div aria-live="polite" className="rounded-xl border border-[#f2c6a8] bg-[#fff2e8] p-4 text-[#9a3412]" role="alert">
          <p className="font-bold">{errorMessage}</p>
          <button
            className="btn btn-secondary mt-3 min-h-11"
            disabled={isFetching}
            onClick={() => void refetch()}
            type="button"
          >
            <RefreshCw className={isFetching ? "animate-spin motion-reduce:animate-none" : ""} size={17} />
            {isFetching ? "Retrying..." : "Retry"}
          </button>
        </div>
      ) : null}
      {hasData && !error && !(data ?? []).some((group) => group.tasks.length) ? (
        <div className="panel px-5 py-8 text-center">
          <h2 className="text-lg font-bold">Your task list is clear</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">{canWrite ? "Use the + button to add your next task." : "This saved list is empty. Refresh before adding tasks."}</p>
        </div>
      ) : null}
      <div className="space-y-5 lg:space-y-6">
        {(displayGroups ?? []).map((group) => (
          <section key={group.label}>
            <h2 className={`mb-2.5 text-lg font-bold lg:mb-3 lg:text-xl lg:font-black ${group.overdue ? "text-[#b42318]" : ""}`}>{group.label}</h2>
            <div className="space-y-2.5 lg:space-y-3">
              {group.tasks.map((task) => (
                <TaskCard
                  key={`${task.id}-${task.due_at ?? task.due_date ?? ""}-${task.is_preview}`}
                  onComplete={(t) => complete.mutateAsync(t).catch(() => undefined)}
                  onDelete={(t) => remove.mutateAsync(t).catch(() => undefined)}
                  onOpen={setEditing}
                  task={task}
                  disabled={!canWrite}
                />
              ))}
            </div>
          </section>
        ))}
      </div>
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
