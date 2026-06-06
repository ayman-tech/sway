"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CalendarCheck, CalendarDays, CheckCircle2, Home, ListTodo, LogOut, Plus, Settings } from "lucide-react";
import { supabase } from "@/lib/supabase";
import { ReminderPoller } from "@/components/reminder-poller";
import { api } from "@/lib/api";
import type { Task, UserSettings } from "@/lib/types";
import { useTheme } from "@/components/theme-provider";
import { TaskEditorModal, type TaskEditorPayload } from "@/components/task-editor-modal";

const items = [
  { href: "/dashboard/tasks", label: "Tasks", icon: ListTodo },
  { href: "/dashboard/calendar", label: "Calendar", icon: CalendarDays },
  { href: "/dashboard/availability", label: "Availability", icon: CalendarCheck },
  { href: "/dashboard/completed", label: "Completed", icon: CheckCircle2 },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
];

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [displayName, setDisplayName] = useState("");
  const { setTheme } = useTheme();
  const qc = useQueryClient();
  const create = useMutation({
    mutationFn: (payload: Partial<TaskEditorPayload>) =>
      api<Task>("/tasks", { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["task-groups"] });
      qc.invalidateQueries({ queryKey: ["completed"] });
      qc.invalidateQueries({ queryKey: ["calendar"] });
      qc.invalidateQueries({ queryKey: ["availability-calendar"] });
    },
  });

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (!data.session) {
        router.replace("/auth");
      } else {
        setReady(true);
        api<UserSettings>("/settings")
          .then(async (settings) => {
            let active = settings;
            const metadata = data.session.user.user_metadata;
            if (!settings.first_name && metadata?.first_name) {
              active = await api<UserSettings>("/settings", {
                method: "PATCH",
                body: JSON.stringify({
                  first_name: metadata.first_name,
                  last_name: metadata.last_name ?? null,
                }),
              });
            }
            setTheme(active.theme);
            setDisplayName([active.first_name, active.last_name].filter(Boolean).join(" "));
          })
          .catch(() => undefined);
      }
    });
  }, [router, setTheme]);

  useEffect(() => {
    const updateName = (event: Event) => {
      const settings = (event as CustomEvent<UserSettings>).detail;
      setDisplayName([settings.first_name, settings.last_name].filter(Boolean).join(" "));
    };
    window.addEventListener("sway-profile-updated", updateName);
    return () => window.removeEventListener("sway-profile-updated", updateName);
  }, []);

  if (!ready) {
    return <div className="grid min-h-screen place-items-center text-[#667085]">Loading Sway...</div>;
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-[225px_1fr]">
      <aside className="border-r border-[#dfd7ca] bg-[#fffdf8] px-4 py-5">
        <Link className="mb-8 flex items-center gap-2 text-2xl font-black" href="/">
          <Home size={22} /> Sway
        </Link>
        <button className="btn btn-primary mb-5 w-full" onClick={() => setCreateOpen(true)}>
          <Plus size={18} /> Add task
        </button>
        <nav className="space-y-2">
          {items.map((item) => {
            const active = pathname === item.href || (pathname === "/dashboard" && item.href.endsWith("tasks"));
            return (
              <Link
                className={`flex items-center gap-3 rounded-lg px-3 py-3 font-bold ${
                  active
                    ? "bg-[var(--nav-active)] text-[var(--nav-active-text)]"
                    : "text-[#475467] hover:bg-[var(--nav-hover)]"
                }`}
                href={item.href}
                key={item.href}
              >
                <item.icon size={18} /> {item.label}
              </Link>
            );
          })}
        </nav>
        {displayName ? <p className="mt-8 truncate px-3 text-sm font-bold text-[var(--muted)]">{displayName}</p> : null}
        <button
          className={`btn btn-secondary w-full ${displayName ? "mt-3" : "mt-8"}`}
          onClick={async () => {
            await supabase.auth.signOut();
            router.replace("/");
          }}
        >
          <LogOut size={18} /> Sign out
        </button>
      </aside>
      <main className="min-w-0 px-5 py-6 lg:px-8">
        <ReminderPoller />
        {children}
      </main>
      <TaskEditorModal
        mode="create"
        onClose={() => setCreateOpen(false)}
        onSave={(payload) => create.mutateAsync(payload)}
        open={createOpen}
      />
    </div>
  );
}
