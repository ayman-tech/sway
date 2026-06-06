"use client";

import { format } from "date-fns";
import { dateFromIso, shortHourLabel } from "@/lib/availability";
import type { AvailabilitySnapshot } from "@/lib/types";

export function AvailabilityGrid({
  snapshot,
  onPointerDown,
  onPointerEnter,
  onPointerEnd,
}: {
  snapshot: AvailabilitySnapshot;
  onPointerDown?: (dateIso: string, slot: number) => void;
  onPointerEnter?: (dateIso: string, slot: number) => void;
  onPointerEnd?: () => void;
}) {
  const interactive = Boolean(onPointerDown);
  return (
    <div
      className="availability-grid-shell panel overflow-auto"
      onPointerLeave={onPointerEnd}
      onPointerUp={onPointerEnd}
    >
      <div
        className="availability-grid min-w-max"
        style={{
          gridTemplateColumns: `64px repeat(${snapshot.selected_dates.length}, 180px)`,
        }}
      >
        <div className="availability-header" />
        {snapshot.selected_dates.map((dateIso) => (
          <div className="availability-header text-center" key={dateIso}>
            <p className="text-xs font-bold text-[#667085]">{format(dateFromIso(dateIso), "EEE")}</p>
            <p className="font-black">{format(dateFromIso(dateIso), "MMM d")}</p>
          </div>
        ))}
        {Array.from({ length: snapshot.end_hour - snapshot.start_hour }, (_, slot) => (
          <div className="contents" key={slot}>
            <div className="availability-time">{shortHourLabel(snapshot.start_hour + slot)}</div>
            {snapshot.selected_dates.map((dateIso) => {
              const isBusy = snapshot.busy_slots[dateIso]?.includes(slot) ?? false;
              const isAvailable = snapshot.available_slots[dateIso]?.includes(slot) ?? false;
              return (
                <button
                  aria-label={`${format(dateFromIso(dateIso), "MMM d")} ${shortHourLabel(snapshot.start_hour + slot)}`}
                  className={`availability-slot ${isBusy ? "availability-busy" : isAvailable ? "availability-available" : "availability-free"}`}
                  disabled={!interactive || isBusy}
                  key={`${dateIso}-${slot}`}
                  onPointerDown={() => onPointerDown?.(dateIso, slot)}
                  onPointerEnter={() => onPointerEnter?.(dateIso, slot)}
                  title={isBusy ? "Busy" : isAvailable ? "Available" : "Unavailable"}
                  type="button"
                />
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

export function AvailabilityLegend() {
  return (
    <div className="flex flex-wrap gap-4 text-sm font-bold text-[#667085]">
      <span className="availability-legend availability-legend-free">Unavailable</span>
      <span className="availability-legend availability-legend-available">Available</span>
      <span className="availability-legend availability-legend-busy">Busy</span>
    </div>
  );
}
