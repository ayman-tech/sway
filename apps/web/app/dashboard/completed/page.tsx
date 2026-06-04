"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RotateCcw } from "lucide-react";
import { api } from "@/lib/api";
import type { Task, TaskGroup } from "@/lib/types";

export default function CompletedPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["completed"],
    queryFn: () => api<TaskGroup[]>("/tasks/completed"),
  });
  const uncomplete = useMutation({
    mutationFn: (task: Task) => api<Task>(`/tasks/${task.id}/uncomplete`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["completed"] });
      qc.invalidateQueries({ queryKey: ["task-groups"] });
    },
  });

  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-3xl font-black">Completed</h1>
        <p className="mt-1 text-[#667085]">Recently completed tasks are kept for 30 days.</p>
      </div>
      {isLoading ? <p className="text-[#667085]">Loading completed tasks...</p> : null}
      {(data ?? []).map((group) => (
        <section key={group.label}>
          <h2 className="mb-3 text-xl font-black">{group.label}</h2>
          <div className="space-y-3">
            {group.tasks.map((task) => (
              <article className="rounded-lg border border-[#e6ded2] bg-white p-4" key={task.id}>
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h3 className="font-black line-through decoration-[#98a2b3]">{task.title}</h3>
                    <p className="mt-1 text-sm text-[#667085]">
                      {task.completed_at ? new Date(task.completed_at).toLocaleString() : "Completed"}
                    </p>
                  </div>
                  <button className="btn btn-secondary" onClick={() => uncomplete.mutate(task)}>
                    <RotateCcw size={18} /> Restore
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>
      ))}
    </section>
  );
}
