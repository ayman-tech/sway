import { format } from "date-fns";
import type { AvailabilitySnapshot, AvailabilitySlots } from "@/lib/types";

export function todayIso() {
  return toDateIso(new Date());
}

export function toDateIso(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function dateFromIso(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export function hourLabel(hour: number) {
  if (hour === 0 || hour === 24) return "12:00 AM";
  if (hour === 12) return "12:00 PM";
  return `${hour % 12}:00 ${hour < 12 ? "AM" : "PM"}`;
}

export function shortHourLabel(hour: number) {
  if (hour === 0 || hour === 24) return "12 AM";
  if (hour === 12) return "12 PM";
  return `${hour % 12} ${hour < 12 ? "AM" : "PM"}`;
}

export function selectedLabel(dates: string[]) {
  const parsed = dates.map(dateFromIso).sort((a, b) => a.getTime() - b.getTime());
  if (parsed.length <= 5) {
    return parsed.map((date) => format(date, "MMM d")).join(", ");
  }
  return `${format(parsed[0], "MMM d")} to ${format(parsed[parsed.length - 1], "MMM d")} · ${parsed.length} selected dates`;
}

export function makeSnapshot(
  selectedDates: string[],
  startHour: number,
  endHour: number,
  availableSlots: AvailabilitySlots,
  busySlots: AvailabilitySlots,
): AvailabilitySnapshot {
  const selected = [...selectedDates].sort();
  const sanitizedBusy = Object.fromEntries(
    selected.map((dateIso) => [dateIso, [...(busySlots[dateIso] ?? [])].sort((a, b) => a - b)]),
  );
  return {
    selected_dates: selected,
    start_hour: startHour,
    end_hour: endHour,
    available_slots: Object.fromEntries(
      selected.map((dateIso) => {
        const blocked = new Set(sanitizedBusy[dateIso]);
        return [
          dateIso,
          [...(availableSlots[dateIso] ?? [])].filter((slot) => !blocked.has(slot)).sort((a, b) => a - b),
        ];
      }),
    ),
    busy_slots: sanitizedBusy,
  };
}
