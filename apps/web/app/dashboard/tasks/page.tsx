"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import type { Task, TaskGroup } from "@/lib/types";
import { TaskCard } from "@/components/task-card";
import { TaskEditorModal, type TaskEditorPayload } from "@/components/task-editor-modal";

export default function TasksPage() {
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<Task | null>(null);
  const { data, isLoading, error } = useQuery({
    queryKey: ["task-groups"],
    queryFn: () => api<TaskGroup[]>("/tasks/groups"),
  });
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["task-groups"] });
    qc.invalidateQueries({ queryKey: ["completed"] });
    qc.invalidateQueries({ queryKey: ["calendar"] });
  };
  const create = useMutation({
    mutationFn: (payload: Partial<TaskEditorPayload>) => api<Task>("/tasks", { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: refresh,
  });
  const update = useMutation({
    mutationFn: ({ task, payload }: { task: Task; payload: Partial<TaskEditorPayload> }) =>
      api<Task>(`/tasks/${task.id}`, { method: "PATCH", body: JSON.stringify(payload) }),
    onSuccess: refresh,
  });
  const complete = useMutation({
    mutationFn: (task: Task) => api<Task>(`/tasks/${task.id}/complete`, { method: "POST" }),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: (task: Task) => api<void>(`/tasks/${task.id}`, { method: "DELETE" }),
    onSuccess: refresh,
  });

  return (
    <section className="space-y-6">
      <div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-3xl font-black">Tasks</h1>
            <p className="mt-1 text-[var(--muted)]">Create, complete, and organize your active work.</p>
          </div>
          <button className="btn btn-primary" onClick={() => setCreateOpen(true)}>
            <Plus size={18} /> Add task
          </button>
        </div>
      </div>
      {isLoading ? <p className="text-[var(--muted)]">Loading tasks...</p> : null}
      {error ? <p className="rounded-lg bg-[#fff2e8] p-3 font-bold text-[#9a3412]">{String(error)}</p> : null}
      <div className="space-y-6">
        {(data ?? []).map((group) => (
          <section key={group.label}>
            <h2 className={`mb-3 text-xl font-black ${group.overdue ? "text-[#b42318]" : ""}`}>{group.label}</h2>
            <div className="space-y-3">
              {group.tasks.map((task) => (
                <TaskCard
                  key={`${task.id}-${task.due_at ?? ""}-${task.is_preview}`}
                  onComplete={(t) => complete.mutateAsync(t)}
                  onDelete={(t) => remove.mutateAsync(t)}
                  onOpen={setEditing}
                  task={task}
                />
              ))}
            </div>
          </section>
        ))}
      </div>
      <TaskEditorModal
        mode="create"
        onClose={() => setCreateOpen(false)}
        onSave={(payload) => create.mutateAsync(payload)}
        open={createOpen}
      />
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
