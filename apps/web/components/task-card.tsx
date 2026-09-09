"use client";

import { Check, Trash2 } from "lucide-react";
import type { Task } from "@/lib/types";
import { LinkedText } from "@/components/linked-text";
import { OverflowMenu } from "@/components/overflow-menu";

function taskTime(task: Task) {
  if (task.due_at) return new Date(task.due_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
  if (task.due_date) {
    const start = new Date(`${task.due_date}T00:00:00`);
    if (!task.end_date || task.end_date === task.due_date) return start.toLocaleDateString();
    const inclusiveEnd = new Date(`${task.end_date}T00:00:00`);
    inclusiveEnd.setDate(inclusiveEnd.getDate() - 1);
    return `${start.toLocaleDateString()} - ${inclusiveEnd.toLocaleDateString()}`;
  }
  return "Untimed";
}

export function TaskCard({
  task,
  onOpen,
  onComplete,
  onDelete,
}: {
  task: Task;
  onOpen: (task: Task) => void;
  onComplete: (task: Task) => Promise<unknown>;
  onDelete: (task: Task) => Promise<void>;
}) {
  return (
    <article className="task-card rounded-xl border border-[#e6ded2] bg-white transition hover:border-[var(--accent)]">
      <div className="flex items-start gap-2 sm:gap-3">
        {!task.is_preview ? (
          <button
            aria-label={`Complete ${task.title}`}
            className="task-complete-button"
            onClick={() => onComplete(task)}
            type="button"
          >
            <Check size={18} />
          </button>
        ) : null}
        <div className="min-w-0 flex-1">
          <button aria-label={`Open ${task.title}`} className="task-card-open" onClick={() => onOpen(task)} type="button">
          <div className="flex flex-wrap items-center gap-2 text-left">
            <h3 className="font-bold">{task.title}</h3>
            {task.source === "google" ? (
              <span className="rounded-full bg-[#eef4ff] px-2 py-1 text-xs font-bold text-[#3538cd]">Google</span>
            ) : null}
            {task.recurrence_rule ? (
              <span className="rounded-full bg-[#f2f4f7] px-2 py-1 text-xs font-bold text-[#475467]">Repeats</span>
            ) : null}
          </div>
          <p className="mt-2 text-left text-sm font-bold text-[var(--accent)]">{taskTime(task)}</p>
          </button>
          {task.description ? (
            <p className="task-card-description mt-1 whitespace-pre-wrap text-sm text-[#667085]">
              <LinkedText text={task.description} />
            </p>
          ) : null}
        </div>
        {task.source !== "google" && !task.is_preview ? (
          <OverflowMenu
            actions={[{ label: "Delete task", icon: Trash2, danger: true, onSelect: () => onDelete(task) }]}
            label={`Actions for ${task.title}`}
          />
        ) : null}
      </div>
    </article>
  );
}
