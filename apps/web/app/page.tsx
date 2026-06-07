import Link from "next/link";
import { ArrowRight, CalendarDays, CheckCircle2, Cloud, Bell, RefreshCw } from "lucide-react";

const features = [
  { icon: CheckCircle2, title: "Tasks that stay organized", text: "Group work by overdue, today, next seven days, untimed, and later." },
  { icon: CalendarDays, title: "Calendar-first planning", text: "See the same tasks in a month view without creating a second system." },
  { icon: Bell, title: "Useful reminders", text: "Timed tasks can remind at the due time and with an optional earlier nudge." },
  { icon: Cloud, title: "Sync across devices", text: "Supabase keeps your web and desktop tasks aligned behind user-scoped security." },
  { icon: RefreshCw, title: "Google Calendar import", text: "Bring events into Sway as read-only tasks while keeping Google as one-way input." },
];

export default function LandingPage() {
  return (
    <main>
      <section className="min-h-[92vh] px-6 py-6">
        <nav className="mx-auto flex max-w-6xl items-center justify-between">
          <Link className="text-2xl font-black tracking-normal" href="/">
            Sway
          </Link>
          <Link className="btn btn-secondary" href="/auth">
            Log in
          </Link>
        </nav>

        <div className="mx-auto grid max-w-6xl gap-10 py-16 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
          <div>
            <h1 className="max-w-2xl text-5xl font-black leading-tight tracking-normal text-[#18212f] md:text-7xl">
              Sway
            </h1>
            <p className="mt-5 max-w-xl text-xl leading-8 text-[#4a5565]">
              A focused productivity app for tasks, reminders, calendar planning, and one-way Google Calendar import.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link className="btn btn-primary" href="/auth">
                Get started <ArrowRight size={18} />
              </Link>
              <Link className="btn btn-secondary" href="/auth?mode=signin">
                Log in
              </Link>
            </div>
          </div>

          <div className="panel overflow-hidden shadow-xl">
            <div className="border-b border-[#dfd7ca] bg-white px-5 py-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-bold text-[var(--accent)]">Today</p>
                  <h2 className="text-2xl font-black">Plan the day</h2>
                </div>
                <span className="rounded-full bg-[var(--soft-accent)] px-3 py-1 text-sm font-bold text-[var(--accent)]">
                  Synced
                </span>
              </div>
            </div>
            <div className="grid gap-4 p-5 md:grid-cols-[1fr_0.9fr]">
              <div className="space-y-3">
                {["Design dashboard shell", "Review calendar import", "Write launch notes"].map((task, idx) => (
                  <div className="rounded-lg border border-[#e6ded2] bg-white p-4" key={task}>
                    <div className="flex items-start gap-3">
                      <span className="mt-1 h-4 w-4 rounded-full border-2 border-[var(--accent)]" />
                      <div>
                        <p className="font-bold">{task}</p>
                        <p className="mt-1 text-sm text-[#667085]">{idx === 0 ? "9:30 AM" : idx === 1 ? "Next 7 Days" : "Untimed"}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              <div className="rounded-lg border border-[#e6ded2] bg-white p-4">
                <div className="mb-4 flex items-center justify-between">
                  <p className="font-black">June</p>
                  <CalendarDays size={18} />
                </div>
                <div className="grid grid-cols-7 gap-2 text-center text-sm">
                  {Array.from({ length: 35 }).map((_, index) => (
                    <div
                      className={`aspect-square rounded-md border text-xs leading-7 ${
                        [4, 11, 18].includes(index)
                          ? "border-[var(--accent)] bg-[var(--soft-accent)] font-black text-[var(--accent)]"
                          : "border-[#eee6da] text-[#667085]"
                      }`}
                      key={index}
                    >
                      {index + 1 <= 30 ? index + 1 : ""}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="border-t border-[#dfd7ca] bg-white px-6 py-14">
        <div className="mx-auto grid max-w-6xl gap-4 md:grid-cols-2 lg:grid-cols-5">
          {features.map((feature) => (
            <div className="rounded-lg border border-[#e6ded2] p-5" key={feature.title}>
              <feature.icon className="text-[var(--accent)]" size={24} />
              <h3 className="mt-4 font-black">{feature.title}</h3>
              <p className="mt-2 text-sm leading-6 text-[#667085]">{feature.text}</p>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
