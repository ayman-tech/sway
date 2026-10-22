"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { AlertCircle, Check, Loader2 } from "lucide-react";
import { slotLabel } from "@/lib/worklog";

export type SlotStatus = "idle" | "saving" | "saved" | "error";

const AUTOSAVE_DELAY_MS = 800;
export const NOTE_LIMIT = 2000;

type Props = {
  day: string;
  hour: number;
  serverNote: string;
  status: SlotStatus;
  current: boolean;
  onSave: (day: string, hour: number, note: string) => void;
};

export function WorklogSlot({ day, hour, serverNote, status, current, onSave }: Props) {
  const [draft, setDraft] = useState(serverNote);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const focused = useRef(false);
  // Latest values for the flush callbacks below, which run from timers and cleanups.
  const latest = useRef({ draft, serverNote, onSave });
  latest.current = { draft, serverNote, onSave };
  const lastSent = useRef(serverNote);
  const holdDraft = status === "saving" || status === "error";

  // Adopt server changes (initial load, another device) unless the user is mid-edit,
  // a save is in flight, or a failed save still needs its text kept for Retry.
  useEffect(() => {
    if (focused.current || holdDraft) return;
    lastSent.current = serverNote;
    setDraft(serverNote);
  }, [serverNote, holdDraft]);

  useLayoutEffect(() => {
    const el = textarea.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [draft]);

  const flush = useCallback((force = false) => {
    clearTimeout(timer.current);
    const text = latest.current.draft.trim();
    if (!force && text === lastSent.current.trim()) return;
    lastSent.current = text;
    latest.current.onSave(day, hour, text);
  }, [day, hour]);

  // Save pending edits when the tab is hidden, and when leaving the day/slot.
  useEffect(() => {
    const onHide = () => { if (document.visibilityState === "hidden") flush(); };
    document.addEventListener("visibilitychange", onHide);
    window.addEventListener("pagehide", onHide);
    return () => {
      document.removeEventListener("visibilitychange", onHide);
      window.removeEventListener("pagehide", onHide);
      flush();
    };
  }, [flush]);

  const id = `worklog-${day}-${hour}`;

  return (
    <div className={`worklog-slot panel p-3 lg:p-4 ${current ? "worklog-slot-current" : ""}`}>
      <div className="worklog-slot-head">
        <label className="text-sm font-black tabular-nums lg:text-base" htmlFor={id}>
          {slotLabel(hour)}
          {current ? <span className="worklog-now-badge">Now</span> : null}
        </label>
        <span aria-live="polite" className="worklog-slot-status" role="status">
          {status === "saving" ? <><Loader2 className="animate-spin motion-reduce:animate-none" size={14} /> Saving…</> : null}
          {status === "saved" ? <><Check size={14} /> Saved</> : null}
          {status === "error" ? (
            <>
              <AlertCircle size={14} /> Not saved
              <button className="worklog-retry" onClick={() => flush(true)} type="button">Retry</button>
            </>
          ) : null}
        </span>
      </div>
      <textarea
        className="field worklog-note"
        id={id}
        maxLength={NOTE_LIMIT}
        onBlur={() => { focused.current = false; flush(); }}
        onChange={(event) => {
          setDraft(event.target.value);
          clearTimeout(timer.current);
          timer.current = setTimeout(flush, AUTOSAVE_DELAY_MS);
        }}
        onFocus={() => { focused.current = true; }}
        placeholder="What did you work on?"
        ref={textarea}
        rows={1}
        value={draft}
      />
    </div>
  );
}
