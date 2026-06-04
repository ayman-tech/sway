"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { CalendarDays, CheckCircle2, Home, ListTodo, LogOut, Settings } from "lucide-react";
import { supabase } from "@/lib/supabase";
import { ReminderPoller } from "@/components/reminder-poller";

const items = [
  { href: "/dashboard/tasks", label: "Tasks", icon: ListTodo },
  { href: "/dashboard/calendar", label: "Calendar", icon: CalendarDays },
  { href: "/dashboard/completed", label: "Completed", icon: CheckCircle2 },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
];

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (!data.session) {
        router.replace("/auth");
      } else {
        setReady(true);
      }
    });
  }, [router]);

  if (!ready) {
    return <div className="grid min-h-screen place-items-center text-[#667085]">Loading Sway...</div>;
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-[260px_1fr]">
      <aside className="border-r border-[#dfd7ca] bg-[#fffdf8] px-4 py-5">
        <Link className="mb-8 flex items-center gap-2 text-2xl font-black" href="/">
          <Home size={22} /> Sway
        </Link>
        <nav className="space-y-2">
          {items.map((item) => {
            const active = pathname === item.href || (pathname === "/dashboard" && item.href.endsWith("tasks"));
            return (
              <Link
                className={`flex items-center gap-3 rounded-lg px-3 py-3 font-bold ${
                  active ? "bg-[#e7f4f1] text-[#0f766e]" : "text-[#475467] hover:bg-white"
                }`}
                href={item.href}
                key={item.href}
              >
                <item.icon size={18} /> {item.label}
              </Link>
            );
          })}
        </nav>
        <button
          className="btn btn-secondary mt-8 w-full"
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
    </div>
  );
}
