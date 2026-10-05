"use client";

import { useState } from "react";
import { useTaskData } from "@/components/task-data-provider";

export function TaskCacheSettings() {
  const { cacheEnabled, cacheWarning, setCacheEnabled } = useTaskData();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return <section className="panel p-4 lg:p-5">
    <h2 className="text-xl font-black">Saved task view</h2>
    <label className="mt-3 flex min-h-11 items-center gap-3">
      <input type="checkbox" checked={cacheEnabled} disabled={busy} onChange={async (event) => {
        const enabled = event.target.checked;
        setBusy(true); setError("");
        try { await setCacheEnabled(enabled); }
        catch { setError("Unable to update device storage. Clear this site’s browser data if you need to remove all local content."); }
        finally { setBusy(false); }
      }} />
      <span>Keep a saved task view on this device</span>
    </label>
    <p className="mt-2 text-sm text-[var(--muted)]">Task content is stored in this browser for up to seven days to make reopening faster. It stays read-only until refreshed. Disable this on shared devices. Signing out clears the saved view; your actual tasks are never deleted.</p>
    <p role="status" className="mt-2 text-sm text-[var(--muted)]">{busy ? "Updating…" : cacheWarning}</p>
    {error ? <p role="alert" className="mt-2 text-sm">{error}</p> : null}
  </section>;
}
