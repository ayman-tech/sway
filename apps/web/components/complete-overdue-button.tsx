"use client";

import { CheckCheck, X } from "lucide-react";
import { useRef, useState } from "react";
import type { Task } from "@/lib/types";
import { useTaskData } from "@/components/task-data-provider";
import { useDialogBehavior } from "@/components/use-dialog-behavior";

export function CompleteOverdueButton({ tasks, onBusyChange }: { tasks: Task[]; onBusyChange: (busy: boolean) => void }) {
  const { canWrite, mutate } = useTaskData();
  const [selection, setSelection] = useState<Task[] | null>(null);
  const [busy, setBusy] = useState(false);
  const running = useRef(false);
  const [message, setMessage] = useState("");
  const eligible = [...new Map(tasks.filter((task) => !task.is_preview && task.status === "pending").map((task) => [task.id, task])).values()];
  const currentSelection = selection?.filter((chosen) => eligible.some((task) => task.id === chosen.id && task.due_at === chosen.due_at && task.due_date === chosen.due_date)) ?? [];
  const close = () => { if (!running.current) setSelection(null); };
  const dialog = useDialogBehavior<HTMLDivElement>(Boolean(selection), close);
  const confirm = async () => {
    if (!selection || !currentSelection.length || !canWrite || running.current) return;
    running.current = true; setBusy(true); onBusyChange(true); setMessage("");
    try {
      // The shared provider serializes these writes and refreshes once the queue
      // drains. Each request uses existing auth, snapshot and account fences.
      const results = await Promise.allSettled(currentSelection.map((task) => mutate(`/tasks/${task.id}/complete`, { method: "POST" })));
      const completed = results.filter((result) => result.status === "fulfilled").length;
      const failed = results.length - completed;
      setMessage(failed ? `${completed} completed; ${failed} could not be confirmed. Refresh to check the latest task state before trying again.` : `${completed} overdue task${completed === 1 ? "" : "s"} completed.`);
      setSelection(null);
    } finally { running.current = false; setBusy(false); onBusyChange(false); }
  };
  return <>
    <button className="btn btn-secondary min-h-11 gap-1.5 px-3 text-xs" aria-label="Complete all overdue tasks" disabled={!canWrite || !eligible.length || busy} onClick={() => { setMessage(""); setSelection(eligible); }} type="button"><CheckCheck size={15} aria-hidden="true" />Complete all</button>
    {message ? <p role="status" className="w-full text-xs text-[var(--muted)]">{message}</p> : null}
    {selection ? <div className="responsive-dialog-overlay" onMouseDown={(event) => { if (event.target === event.currentTarget) close(); }}>
      <div ref={dialog} className="responsive-dialog-surface max-w-md" style={{ padding: 20, paddingBottom: "calc(20px + env(safe-area-inset-bottom))" }} role="dialog" aria-modal="true" aria-labelledby="complete-overdue-title" aria-describedby="complete-overdue-description" tabIndex={-1}>
        <div className="flex items-center justify-between gap-3"><h2 id="complete-overdue-title" className="text-xl font-semibold">Complete overdue tasks?</h2><button className="icon-button" disabled={busy} aria-label="Close confirmation" onClick={close}><X size={20} /></button></div>
        <p id="complete-overdue-description" className="my-4 text-sm text-[var(--muted)]">Mark {currentSelection.length} overdue task{currentSelection.length === 1 ? "" : "s"} as completed? You can restore them from Completed. Recurring tasks advance to their next occurrence; Google Calendar events are unchanged.</p>
        <div className="flex flex-wrap justify-end gap-2"><button data-dialog-initial-focus className="btn btn-secondary" onClick={close} disabled={busy}>Cancel</button><button className="btn btn-primary" disabled={busy || !canWrite || !currentSelection.length} onClick={() => void confirm()}>{busy ? "Completing…" : `Complete ${currentSelection.length} task${currentSelection.length === 1 ? "" : "s"}`}</button></div>
      </div>
    </div> : null}
  </>;
}
