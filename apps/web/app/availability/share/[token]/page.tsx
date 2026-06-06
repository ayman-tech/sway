"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { CalendarClock, Home } from "lucide-react";
import { AvailabilityGrid, AvailabilityLegend } from "@/components/availability-grid";
import { hourLabel, selectedLabel } from "@/lib/availability";
import { publicApi } from "@/lib/api";
import type { AvailabilityShare } from "@/lib/types";

export default function PublicAvailabilityPage() {
  const params = useParams<{ token: string }>();
  const token = params.token;
  const { data, error, isLoading } = useQuery({
    enabled: Boolean(token),
    queryKey: ["public-availability-share", token],
    queryFn: () => publicApi<AvailabilityShare>(`/availability-shares/${encodeURIComponent(token)}`),
    retry: false,
  });

  return (
    <main className="min-h-screen px-4 py-6 sm:px-7 lg:px-10">
      <div className="mx-auto max-w-7xl">
        <Link className="mb-8 inline-flex items-center gap-2 text-xl font-black" href="/">
          <Home size={20} /> Sway
        </Link>

        {isLoading ? <p className="text-[var(--muted)]">Loading shared availability...</p> : null}

        {error ? (
          <section className="panel max-w-xl p-5">
            <h1 className="text-2xl font-black">This availability link is unavailable</h1>
            <p className="mt-2 text-[var(--muted)]">
              It may have expired, been replaced by a newer link, or the address may be incorrect.
            </p>
          </section>
        ) : null}

        {data ? (
          <section className="grid gap-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h1 className="text-3xl font-black">
                  {data.first_name ? `${data.first_name}'s Availability` : "Shared availability"}
                </h1>
                <p className="mt-1 text-[var(--muted)]">
                  {selectedLabel(data.snapshot.selected_dates)} · {hourLabel(data.snapshot.start_hour)} to{" "}
                  {hourLabel(data.snapshot.end_hour)}
                </p>
              </div>
              <div className="panel flex items-start gap-3 p-3 text-sm">
                <CalendarClock className="mt-0.5 text-[var(--accent)]" size={18} />
                <div>
                  <p className="font-bold">{data.creator_timezone}</p>
                  <p className="mt-1 text-[var(--muted)]">
                    Expires {new Date(data.expires_at).toLocaleString()}
                  </p>
                </div>
              </div>
            </div>
            <AvailabilityGrid snapshot={data.snapshot} />
            <AvailabilityLegend />
          </section>
        ) : null}
      </div>
    </main>
  );
}
