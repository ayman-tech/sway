"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  CalendarCheck,
  CalendarDays,
  CheckCircle2,
  Home,
  ListTodo,
  LogOut,
  MoreHorizontal,
  Plus,
  Settings,
  X,
} from "lucide-react";
import { supabase } from "@/lib/supabase";
import { ReminderPoller } from "@/components/reminder-poller";
import { GoogleSyncTrigger } from "@/components/google-sync-trigger";
import { api } from "@/lib/api";
import type { Task, UserSettings } from "@/lib/types";
import { useTheme } from "@/components/theme-provider";
import { TaskEditorModal, type TaskEditorPayload } from "@/components/task-editor-modal";
import { useDialogBehavior } from "@/components/use-dialog-behavior";

const items = [
  { href: "/dashboard/tasks", label: "Tasks", icon: ListTodo },
  { href: "/dashboard/calendar", label: "Calendar", icon: CalendarDays },
  { href: "/dashboard/availability", label: "Availability", icon: CalendarCheck },
  { href: "/dashboard/completed", label: "Completed", icon: CheckCircle2 },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
];

const primaryItems = items.slice(0, 3);
const moreItems = items.slice(3);

function itemIsActive(pathname: string, href: string) {
  return pathname === href || (pathname === "/dashboard" && href === "/dashboard/tasks");
}

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [displayName, setDisplayName] = useState("");
  const { setTheme } = useTheme();
  const qc = useQueryClient();
  const moreDialogRef = useDialogBehavior<HTMLElement>(moreOpen, () => setMoreOpen(false));
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

  const pageTitle = items.find((item) => itemIsActive(pathname, item.href))?.label ?? "Tasks";
  const initials = displayName
    ? displayName
        .split(" ")
        .filter(Boolean)
        .slice(0, 2)
        .map((part) => part[0]?.toUpperCase())
        .join("")
    : "S";
  const moreActive = moreItems.some((item) => itemIsActive(pathname, item.href));
  const signOut = async () => {
    await supabase.auth.signOut();
    router.replace("/");
  };

  return (
    <div className="dashboard-shell min-h-screen lg:grid lg:grid-cols-[225px_1fr]">
      <aside className="dashboard-sidebar hidden border-r border-[#dfd7ca] bg-[#fffdf8] px-4 py-5 lg:flex lg:min-h-screen lg:flex-col">
        <Link className="mb-8 flex items-center gap-2 text-2xl font-black" href="/">
          <Home size={22} /> Sway
        </Link>
        <button className="btn btn-primary mb-5 w-full" onClick={() => setCreateOpen(true)} type="button">
          <Plus size={18} /> Add task
        </button>
        <nav className="space-y-2">
          {items.map((item) => {
            const active = pathname === item.href || (pathname === "/dashboard" && item.href.endsWith("tasks"));
            return (
              <Link
                aria-current={active ? "page" : undefined}
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
        <div className="mt-auto pt-8">
          {displayName ? <p className="truncate px-3 text-sm font-bold text-[var(--muted)]">{displayName}</p> : null}
          <button
            className={`btn btn-secondary w-full ${displayName ? "mt-3" : ""}`}
            onClick={signOut}
            type="button"
          >
            <LogOut size={18} /> Sign out
          </button>
        </div>
      </aside>

      <header className="mobile-topbar lg:hidden">
        <h1>{pageTitle}</h1>
        <button aria-label="Open account menu" className="mobile-avatar" onClick={() => setMoreOpen(true)} type="button">
          {initials}
        </button>
      </header>

      <main className="dashboard-main min-w-0 px-4 pt-4 lg:px-8 lg:py-6">
        <ReminderPoller />
        <GoogleSyncTrigger />
        {children}
      </main>

      <button
        aria-label="Add task"
        className="mobile-fab lg:hidden"
        hidden={pathname.startsWith("/dashboard/settings")}
        onClick={() => setCreateOpen(true)}
        type="button"
      >
        <Plus size={28} />
      </button>

      <nav aria-label="Primary navigation" className="mobile-bottom-nav lg:hidden">
        {primaryItems.map((item) => {
          const active = itemIsActive(pathname, item.href);
          return (
            <Link aria-current={active ? "page" : undefined} className={active ? "is-active" : ""} href={item.href} key={item.href}>
              <span className="mobile-nav-icon"><item.icon size={22} /></span>
              <span>{item.label}</span>
            </Link>
          );
        })}
        <button
          aria-expanded={moreOpen}
          className={moreActive || moreOpen ? "is-active" : ""}
          onClick={() => setMoreOpen(true)}
          type="button"
        >
          <span className="mobile-nav-icon"><MoreHorizontal size={23} /></span>
          <span>More</span>
        </button>
      </nav>

      {moreOpen ? (
        <div
          className="responsive-dialog-overlay more-sheet-overlay lg:hidden"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setMoreOpen(false);
          }}
        >
          <section
            aria-labelledby="mobile-more-title"
            aria-modal="true"
            className="responsive-dialog-surface more-sheet"
            ref={moreDialogRef}
            role="dialog"
            tabIndex={-1}
          >
            <div className="more-sheet-handle" aria-hidden="true" />
            <div className="more-sheet-header">
              <div>
                <h2 id="mobile-more-title">More</h2>
                {displayName ? <p>{displayName}</p> : null}
              </div>
              <button aria-label="Close menu" className="icon-button" data-dialog-initial-focus onClick={() => setMoreOpen(false)} type="button">
                <X size={20} />
              </button>
            </div>
            <nav aria-label="More navigation" className="more-sheet-links">
              {moreItems.map((item) => {
                const active = itemIsActive(pathname, item.href);
                return (
                  <Link
                    aria-current={active ? "page" : undefined}
                    className={active ? "is-active" : ""}
                    href={item.href}
                    key={item.href}
                    onClick={() => setMoreOpen(false)}
                  >
                    <item.icon size={20} />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </nav>
            <button className="btn btn-secondary more-sheet-signout" onClick={signOut} type="button">
              <LogOut size={19} /> Sign out
            </button>
          </section>
        </div>
      ) : null}

      <TaskEditorModal
        mode="create"
        onClose={() => setCreateOpen(false)}
        onSave={(payload) => create.mutateAsync(payload)}
        open={createOpen}
      />
    </div>
  );
}
