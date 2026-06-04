"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Task, TaskGroup } from "@/lib/types";
import { TaskCard } from "@/components/task-card";
import { TaskForm } from "@/components/task-form";

export default function TasksPage() {
  const qc = useQueryClient();
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
    mutationFn: (payload: unknown) => api<Task>("/tasks", { method: "POST", body: JSON.stringify(payload) }),
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
        <h1 className="text-3xl font-black">Tasks</h1>
        <p className="mt-1 text-[#667085]">Create, complete, and organize your active work.</p>
      </div>
      <TaskForm onCreate={(payload) => create.mutateAsync(payload)} />
      {isLoading ? <p className="text-[#667085]">Loading tasks...</p> : null}
      {error ? <p className="rounded-lg bg-[#fff2e8] p-3 font-bold text-[#9a3412]">{String(error)}</p> : null}
      <div className="space-y-6">
        {(data ?? []).map((group) => (
          <section key={group.label}>
            <h2 className={`mb-3 text-xl font-black ${group.overdue ? "text-[#b42318]" : ""}`}>{group.label}</h2>
            <div className="space-y-3">
              {group.tasks.map((task) => (
                <TaskCard key={`${task.id}-${task.due_at ?? ""}-${task.is_preview}`} onComplete={(t) => complete.mutateAsync(t)} onDelete={(t) => remove.mutateAsync(t)} task={task} />
              ))}
            </div>
          </section>
        ))}
      </div>
    </section>
  );
}
