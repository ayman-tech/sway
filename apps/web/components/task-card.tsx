"use client";

import { Check, Trash2 } from "lucide-react";
import type { Task } from "@/lib/types";

function taskTime(task: Task) {
  if (!task.due_at) return "Untimed";
  const due = new Date(task.due_at);
  if (!task.has_time) return due.toLocaleDateString();
  return due.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

export function TaskCard({
  task,
  onComplete,
  onDelete,
}: {
  task: Task;
  onComplete: (task: Task) => Promise<unknown>;
  onDelete: (task: Task) => Promise<void>;
}) {
  return (
    <article className="rounded-lg border border-[#e6ded2] bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-black">{task.title}</h3>
            {task.source === "google" ? (
              <span className="rounded-full bg-[#eef4ff] px-2 py-1 text-xs font-bold text-[#3538cd]">Google</span>
            ) : null}
            {task.recurrence_rule ? (
              <span className="rounded-full bg-[#f2f4f7] px-2 py-1 text-xs font-bold text-[#475467]">Repeats</span>
            ) : null}
          </div>
          {task.description ? <p className="mt-1 whitespace-pre-wrap text-sm text-[#667085]">{task.description}</p> : null}
          <p className="mt-2 text-sm font-bold text-[#0f766e]">{taskTime(task)}</p>
        </div>
        <div className="flex gap-2">
          {!task.is_preview ? (
            <button className="btn btn-secondary min-w-10 px-2" onClick={() => onComplete(task)} title="Complete">
              <Check size={18} />
            </button>
          ) : null}
          {task.source !== "google" && !task.is_preview ? (
            <button className="btn btn-secondary min-w-10 px-2" onClick={() => onDelete(task)} title="Delete">
              <Trash2 size={18} />
            </button>
          ) : null}
        </div>
      </div>
    </article>
  );
}
