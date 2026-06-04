"use client";

import { useState } from "react";
import { Plus } from "lucide-react";

type Payload = {
  title: string;
  description?: string | null;
  due_at?: string | null;
  has_time?: boolean;
  end_at?: string | null;
  reminder_minutes_before?: number | null;
  recurrence_rule?: string | null;
};

export function TaskForm({ onCreate }: { onCreate: (payload: Payload) => Promise<unknown> }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  const [reminder, setReminder] = useState("");
  const [repeat, setRepeat] = useState("");
  const [saving, setSaving] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    const dueAt = date ? new Date(`${date}T${time || "00:00"}`).toISOString() : null;
    await onCreate({
      title,
      description: description || null,
      due_at: dueAt,
      has_time: Boolean(date && time),
      reminder_minutes_before: reminder ? Number(reminder) : null,
      recurrence_rule: repeat || null,
    });
    setSaving(false);
    setTitle("");
    setDescription("");
    setDate("");
    setTime("");
    setReminder("");
    setRepeat("");
  };

  return (
    <form className="panel grid gap-3 p-4 lg:grid-cols-[1.4fr_1fr_130px_130px_150px_150px_auto]" onSubmit={submit}>
      <input className="field" onChange={(e) => setTitle(e.target.value)} placeholder="New task" required value={title} />
      <input className="field" onChange={(e) => setDescription(e.target.value)} placeholder="Description" value={description} />
      <input className="field" onChange={(e) => setDate(e.target.value)} type="date" value={date} />
      <input className="field" disabled={!date} onChange={(e) => setTime(e.target.value)} type="time" value={time} />
      <select className="field" disabled={!date || !time} onChange={(e) => setReminder(e.target.value)} value={reminder}>
        <option value="">No early reminder</option>
        <option value="5">5 min before</option>
        <option value="15">15 min before</option>
        <option value="30">30 min before</option>
        <option value="60">1 hour before</option>
      </select>
      <select className="field" disabled={!date} onChange={(e) => setRepeat(e.target.value)} value={repeat}>
        <option value="">No repeat</option>
        <option value="FREQ=DAILY">Daily</option>
        <option value="FREQ=WEEKLY">Weekly</option>
        <option value="FREQ=WEEKLY;INTERVAL=2">Every 2 weeks</option>
        <option value="FREQ=MONTHLY">Monthly</option>
        <option value="FREQ=YEARLY">Yearly</option>
      </select>
      <button className="btn btn-primary" disabled={saving} type="submit">
        <Plus size={18} /> Add
      </button>
    </form>
  );
}
