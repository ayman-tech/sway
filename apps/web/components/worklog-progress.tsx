"use client";

import { format } from "date-fns";
import { Info, Pencil, X } from "lucide-react";
import { useState } from "react";
import { parseDay, worklogProgress } from "@/lib/worklog";
import { useDialogBehavior } from "@/components/use-dialog-behavior";

export function WorklogProgress({ days, day, logged, scheduled, extra, progress, goal, canEdit, onSelect, onGoal, celebration }: {
  days: string[]; day: string; logged: number; scheduled: number; extra: number;
  progress: ReturnType<typeof worklogProgress>; goal: number | null; canEdit: boolean;
  onSelect: (day: string) => void; onGoal: (goal: number | null) => Promise<void>; celebration: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const close = () => { if (!saving) setOpen(false); };
  const dialog = useDialogBehavior<HTMLDivElement>(open, close);
  const radius = 43, circumference = 2 * Math.PI * radius;
  const ratio = scheduled ? Math.min(logged / scheduled, 1) : 0;
  const max = Math.max(1, ...progress.counts.map((item) => item.count));
  const saveGoal = async (next: number | null) => {
    if (!canEdit || saving) return;
    setSaving(true); setError("");
    try { await onGoal(next); setOpen(false); }
    catch (failure) { setError(failure instanceof Error ? failure.message : "Unable to save goal."); }
    finally { setSaving(false); }
  };
  return <aside className="worklog-summary" aria-label="Work log progress">
    <section className="worklog-progress-card">
      <div className="worklog-ring-row">
        <div className="worklog-ring" role="img" aria-label={`${logged} of ${scheduled} scheduled hours logged`}>
          <svg viewBox="0 0 100 100" aria-hidden="true"><circle className="ring-track" cx="50" cy="50" r={radius} /><circle className="ring-value" cx="50" cy="50" r={radius} strokeDasharray={circumference} strokeDashoffset={circumference * (1 - ratio)} /></svg>
          <strong>{logged}<span>/{scheduled}</span></strong>
        </div>
        <div><h2>{format(parseDay(day), "EEEE")}’s progress</h2><p>{logged} of {scheduled} scheduled hours logged</p>{extra > 0 ? <p className="worklog-extra-count">+{extra} outside your schedule</p> : null}</div>
      </div>
      <div className="worklog-metrics"><div><strong>{progress.total}</strong><span>Hours logged ·<br />last 7 days</span></div><div><strong>{progress.activeDays}</strong><span>Days with<br />entries</span></div></div>
      <p className="worklog-count-note"><Info size={14} aria-hidden="true" />Each filled hourly slot counts as one hour logged.</p>
    </section>
    <section className="worklog-progress-card">
      <div className="worklog-card-heading"><h2>Last 7 days</h2><span>{format(parseDay(days[0]), "d MMM")}–{format(parseDay(days[6]), "d MMM")}</span></div>
      <div className="worklog-chart" aria-label="Select a day to view its work log">
        {progress.counts.map((item) => <button key={item.day} className="worklog-chart-day" aria-pressed={item.day === day} aria-label={`${format(parseDay(item.day), "EEEE, MMMM d")}: ${item.count} hours logged`} onClick={() => onSelect(item.day)}>
          <span className="worklog-chart-column"><span className="worklog-chart-count">{item.count}</span><span className="worklog-chart-bar" style={{ height: `${Math.max(3, item.count / max * 76)}px` }} /></span>
          <span className="worklog-chart-label">{format(parseDay(item.day), "EEE")}<small>{format(parseDay(item.day), "d")}</small></span>
        </button>)}
      </div>
    </section>
    <section className={`worklog-progress-card worklog-goal ${celebration ? "goal-celebrate" : ""}`}>
      <div className="worklog-card-heading"><h2>Weekly goal</h2><button className="icon-button" aria-label={goal ? "Edit weekly goal" : "Set weekly goal"} disabled={!canEdit} onClick={() => { setValue(goal?.toString() ?? ""); setError(""); setOpen(true); }}><Pencil size={17} /></button></div>
      {goal ? <><div className="worklog-goal-label"><span>{progress.total} / {goal} hours</span><span>{Math.min(100, Math.round(progress.total / goal * 100))}%</span></div><div className="worklog-goal-track" role="progressbar" aria-label="Weekly logged hours goal" aria-valuemin={0} aria-valuemax={goal} aria-valuenow={Math.min(progress.total, goal)} aria-valuetext={`${progress.total} of ${goal} hours logged`}><div style={{ width: `${Math.min(100, progress.total / goal * 100)}%` }} /></div><p className="worklog-goal-success" role="status">{celebration ? "Weekly goal reached. Nicely done!" : progress.total >= goal ? "Goal reached" : ""}</p></> : <p className="worklog-goal-empty">Set an optional goal for your last 7 days.</p>}
    </section>
    {open ? <div className="responsive-dialog-overlay" onMouseDown={(event) => { if (event.target === event.currentTarget) close(); }}><div className="responsive-dialog-surface p-5 max-w-md" ref={dialog} role="dialog" aria-modal="true" aria-labelledby="weekly-goal-title" tabIndex={-1}>
      <div className="flex items-center justify-between"><h2 id="weekly-goal-title" className="text-xl font-semibold">Weekly goal</h2><button className="icon-button" aria-label="Close" disabled={saving} onClick={close}><X size={20} /></button></div>
      <p className="my-3 text-sm text-[var(--muted)]">Choose a target for hours logged over the last 7 days. Your goal follows your account across devices.</p>
      <form onSubmit={(event) => { event.preventDefault(); const number = Number(value); if (!Number.isInteger(number) || number < 1 || number > 168) { setError("Enter a whole number from 1 to 168."); return; } void saveGoal(number); }}>
        <label className="grid gap-2 text-sm">Hours<input data-dialog-initial-focus className="field" type="number" min={1} max={168} step={1} required value={value} disabled={saving || !canEdit} onChange={(event) => setValue(event.target.value)} /></label>
        {error ? <p role="alert" className="mt-3 text-sm text-[var(--danger)]">{error}</p> : null}
        <div className="mt-5 flex flex-wrap gap-2"><button className="btn btn-primary" type="submit" disabled={saving || !canEdit}>{saving ? "Saving…" : "Save goal"}</button><button className="btn btn-secondary" type="button" disabled={saving || !canEdit || goal === null} onClick={() => void saveGoal(null)}>Remove goal</button></div>
      </form>
    </div></div> : null}
  </aside>;
}
