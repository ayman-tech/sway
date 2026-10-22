"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Clock, Save } from "lucide-react";
import { api } from "@/lib/api";
import type { UserSettings } from "@/lib/types";
import { crossesMidnight, DEFAULT_WORK_END, DEFAULT_WORK_START, hourLabel, scheduleSlots } from "@/lib/worklog";

const START_HOURS = Array.from({ length: 24 }, (_, hour) => hour);
const END_HOURS = Array.from({ length: 24 }, (_, i) => i + 1);

export function WorkScheduleSettings() {
  const qc = useQueryClient();
  const [start, setStart] = useState(DEFAULT_WORK_START);
  const [end, setEnd] = useState(DEFAULT_WORK_END);
  const { data: settings } = useQuery({
    queryKey: ["settings"],
    queryFn: () => api<UserSettings>("/settings"),
  });
  const save = useMutation({
    mutationFn: () =>
      api<UserSettings>("/settings", {
        method: "PATCH",
        body: JSON.stringify({ work_start_hour: start, work_end_hour: end }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }),
  });
  useEffect(() => {
    if (!settings) return;
    setStart(settings.work_start_hour);
    setEnd(settings.work_end_hour);
  }, [settings]);

  const hours = scheduleSlots(start, end).length;
  const unchanged = settings?.work_start_hour === start && settings?.work_end_hour === end;

  return (
    <div className="panel p-4 lg:p-5">
      <h2 className="flex items-center gap-2 text-xl font-black">
        <Clock size={20} /> Work schedule
      </h2>
      <p className="mt-2 text-[var(--muted)]">
        The hours shown in the Work log. Pick your shift so unused hours stay out of the way.
      </p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:max-w-lg">
        <label className="grid gap-1 text-sm font-bold">
          Starts
          <select
            className="field font-normal"
            onChange={(event) => { save.reset(); setStart(Number(event.target.value)); }}
            value={start}
          >
            {START_HOURS.map((hour) => <option key={hour} value={hour}>{hourLabel(hour)}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-sm font-bold">
          Ends
          <select
            className="field font-normal"
            onChange={(event) => { save.reset(); setEnd(Number(event.target.value)); }}
            value={end}
          >
            {END_HOURS.map((hour) => <option key={hour} value={hour}>{hourLabel(hour)}</option>)}
          </select>
        </label>
      </div>
      <p className="mt-3 text-sm text-[var(--muted)]">
        {hourLabel(start)} to {hourLabel(end)} · {hours} {hours === 1 ? "hour" : "hours"}
        {crossesMidnight(start, end) ? " · ends the next day" : ""}
      </p>
      {save.isError ? <p role="alert" className="mt-2 text-sm text-[var(--danger)]">Unable to save: {save.error.message}</p> : null}
      {save.isSuccess ? <p role="status" className="mt-2 text-sm text-[var(--muted)]">Work schedule saved.</p> : null}
      <button
        className="btn btn-primary mobile-full mt-4"
        disabled={save.isPending || !settings || unchanged}
        onClick={() => save.mutate()}
      >
        <Save size={18} /> Save schedule
      </button>
    </div>
  );
}
