"use client";

import { Bell } from "lucide-react";
import { usePwa } from "@/components/pwa-provider";
import { usePush } from "@/components/push-provider";

export function PushSettingsCard() {
  const push = usePush();
  const { isIos, isInstalled } = usePwa();
  const needsInstall = isIos && !isInstalled;
  return <section className="panel p-4 lg:p-5" aria-labelledby="push-title">
    <h2 id="push-title" className="flex items-center gap-2 text-xl font-black"><Bell size={20} /> Notifications on this device</h2>
    <p className="mt-2 text-[var(--muted)]">Receive task reminders even when Sway is closed. Task titles appear on your lock screen; delivery depends on your connection and device settings.</p>
    <p className="mt-2 text-sm text-[var(--muted)]" role="status">
      {!push.ready ? "Checking this device…" : push.enrolled ? "Background notifications are enrolled on this device." : "Background notifications are not enabled on this device."}
    </p>
    {needsInstall ? <p className="mt-2 text-sm">On iPhone/iPad, open Sway in Safari → Share → Add to Home Screen. Open the installed app, then enable notifications here.</p> : null}
    {push.ready && !push.supported && !needsInstall ? <p className="mt-2 text-sm">Background push is unavailable in this browser. Try an up-to-date browser with notification support.</p> : null}
    <div className="mobile-action-row mt-4 flex flex-wrap gap-3">
      {!push.enrolled ? <button className="btn btn-primary" disabled={!push.ready || push.busy || !push.supported || needsInstall} onClick={() => void push.enable()}>Enable notifications</button> : <button className="btn btn-secondary" disabled={push.busy} onClick={() => void push.test()}>Send test notification</button>}
      <button className="btn btn-secondary" disabled={!push.ready || push.busy} onClick={() => void push.disable()}>Disable on this device</button>
    </div>
    {!push.enrolled ? <div className="mt-3 text-sm text-[var(--muted)]">
      <p>Foreground-only reminders require Sway to stay open. {push.foreground ? "They can appear when browser permission is granted." : "They are disabled on this device."}</p>
      <button className="btn btn-secondary mt-2" disabled={!push.ready || push.busy || needsInstall} onClick={() => void push.enableForeground()}>Enable foreground-only reminders</button>
    </div> : null}
    {push.error ? <div className="mt-3 text-sm" role="alert"><p>{push.error}</p><button className="btn btn-secondary mt-2" disabled={push.busy} onClick={() => void push.refresh()}>Check again</button></div> : null}
    <p className="mt-3 text-sm text-[var(--muted)]" role="status">{push.busy ? "Updating notification settings…" : push.message}</p>
  </section>;
}
