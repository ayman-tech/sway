import Link from "next/link";
import { ArrowRight, CalendarDays, CheckCircle2, Bell, RefreshCw, Bot, Check, Link2, Smartphone, ListTodo } from "lucide-react";
import styles from "./landing.module.css";

const features = [
  { icon: ListTodo, title: "Know what needs you today", text: "Overdue, Today, Next 7 Days, and Later keep your next step in view. Give ideas without a deadline a home, too." },
  { icon: CalendarDays, title: "See the whole month", text: "Switch from your task list to your calendar. Select a day to see its agenda, without planning everything twice." },
  { icon: RefreshCw, title: "Bring your Google Calendar along", text: "See imported events beside your tasks. Google stays in charge of event details; Sway helps you plan around them." },
];

export default function LandingPage() {
  return (
    <main>
      <section className={`${styles.hero} min-h-[92vh] px-6 py-6`}>
        <div className={styles.backdrop} aria-hidden="true"><CalendarDays /><CheckCircle2 /><CalendarDays /></div>
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

      <section className={styles.featureSection} aria-labelledby="features-heading">
        <div className={styles.container}>
          <div className={styles.sectionHeading}>
            <h2 id="features-heading">A clearer day<br />starts here.</h2>
            <p>Less keeping track. <br />More getting things done.</p>
          </div>
          <div className={styles.featureLayout}>
            <div className={styles.featureList}>
              {features.map(({ icon: Icon, title, text }) => (
                <div className={styles.feature} key={title}>
                  <span className={styles.featureIcon}><Icon size={23} aria-hidden="true" /></span>
                  <div><h3>{title}</h3><p>{text}</p></div>
                </div>
              ))}
            </div>
            <figure className={styles.preview}>
              <div className={styles.previewHeader}><span><CalendarDays size={18} /> Your day, together</span><span className={styles.example}>Example</span></div>
              <div className={styles.agenda}>
                <p className={styles.agendaLabel}>TODAY</p>
                <div className={styles.agendaRow}><span className={styles.taskCheck}><Check size={14} /></span><div><strong>Send the project proposal</strong><small>One less thing on your mind</small></div></div>
                <div className={styles.calendarEvent}><span>10:00</span><div><strong>Team catch-up</strong><small>Imported from Google Calendar</small></div><CalendarDays size={18} /></div>
                <div className={styles.agendaRow}><span className={styles.emptyCheck} /><div><strong>Prepare for tomorrow’s presentation</strong><small>Today · 2:00 PM</small></div></div>
                <p className={styles.agendaLabel}>NEXT 7 DAYS</p>
                <div className={styles.agendaRow}><span className={styles.emptyCheck} /><div><strong>Make time for the next big idea</strong><small>A little space to think ahead</small></div></div>
              </div>
              <figcaption>Your tasks and imported events, in one place.</figcaption>
            </figure>
          </div>
        </div>
      </section>

      <section className={styles.agentSection} aria-labelledby="agent-heading">
        <div className={`${styles.container} ${styles.agentLayout}`}>
          <div>
            <Bot size={32} className={styles.agentIcon} aria-hidden="true" />
            <h2 id="agent-heading">Say it.<br />Let OpenClaw add it.</h2>
            <p>Turn a conversation into your next task. Connect OpenClaw to Sway to add tasks, check what’s coming up, and mark work complete.</p>
            <a className={styles.agentLink} href="https://github.com/ayman-tech/sway-mcp#install-for-openclaw">Set up OpenClaw <ArrowRight size={18} /></a>
            <p className={styles.agentNote}>Connect with your own Sway API key. Also works with compatible MCP clients.</p>
          </div>
          <figure className={styles.conversation}>
            <figcaption>AN EXAMPLE WITH OPENCLAW</figcaption>
            <div className={styles.prompt}>Add a task to review the proposal tomorrow.</div>
            <div className={styles.reply}><span className={styles.botAvatar}><Bot size={22} /></span><div><p>Added to Sway.</p><div className={styles.createdTask}><CheckCircle2 size={22} /><div><strong>Review the proposal</strong><small>Tomorrow</small></div></div></div></div>
          </figure>
        </div>
      </section>

      <section className={styles.featureSection} aria-labelledby="everyday-heading">
        <div className={styles.container}>
          <div className={styles.sectionHeading}><h2 id="everyday-heading">Fits the way<br />your day works.</h2><p>At your desk. On the go. <br />And when it’s time to make plans.</p></div>
          <div className={styles.benefits}>
            <article><Link2 size={27} /><h3>Share your free time. <br />Skip the back-and-forth.</h3><p>Choose your availability and share a link so others can see when you’re free. No need to share your whole calendar.</p><Link href="/auth">Plan your availability <ArrowRight size={16} /></Link></article>
            <article><Smartphone size={27} /><h3>Your day, <br />within reach.</h3><p>Use Sway in your browser or install it on your home screen. Sign in to the same account to access your tasks across devices.</p><span className={styles.detail}>An internet connection keeps everything current.</span></article>
            <article><Bell size={27} /><h3>A nudge when <br />you need one.</h3><p>Set reminders for timed tasks, with an optional earlier heads-up. Keep Sway open to receive browser reminders.</p><span className={styles.detail}>Make room for the work that matters.</span></article>
          </div>
          <div className={styles.closing}><div><h2>Make space for a better day.</h2><p>Start with one task. Let the rest fall into place.</p></div><Link className="btn btn-primary" href="/auth">Get started <ArrowRight size={18} /></Link></div>
          <footer className={styles.footer}><Link href="/">Sway</Link><span>A little less scattered. A little more done.</span><Link href="/auth?mode=signin">Log in <ArrowRight size={15} /></Link></footer>
        </div>
      </section>
    </main>
  );
}
