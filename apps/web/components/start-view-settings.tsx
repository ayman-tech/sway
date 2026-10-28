"use client";

import { useEffect, useState } from "react";
import { Home } from "lucide-react";
import { DEFAULT_START_VIEW, isStartView, readStartView, START_VIEWS, writeStartView, type StartView } from "@/lib/start-view";

export function StartViewSettings() {
  const [view, setView] = useState<StartView>(DEFAULT_START_VIEW);
  // Read after mount so the server-rendered markup matches.
  useEffect(() => setView(readStartView()), []);

  return (
    <div className="panel p-4 lg:p-5">
      <h2 className="flex items-center gap-2 text-xl font-black">
        <Home size={20} /> Start page
      </h2>
      <p className="mt-2 text-[var(--muted)]">
        The page Sway opens when you launch it or sign in. This is saved in this browser only, so
        each device can have its own.
      </p>
      <select
        aria-label="Start page"
        className="field mt-4 lg:max-w-xs"
        onChange={(event) => {
          if (!isStartView(event.target.value)) return;
          setView(event.target.value);
          writeStartView(event.target.value);
        }}
        value={view}
      >
        {START_VIEWS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
      </select>
    </div>
  );
}
