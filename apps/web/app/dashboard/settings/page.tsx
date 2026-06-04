"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, CalendarDays, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import type { GoogleStatus, UserSettings } from "@/lib/types";

export default function SettingsPage() {
  const qc = useQueryClient();
  const { data: settings } = useQuery({
    queryKey: ["settings"],
    queryFn: () => api<UserSettings>("/settings"),
  });
  const { data: google } = useQuery({
    queryKey: ["google-status"],
    queryFn: () => api<GoogleStatus>("/integrations/google/status"),
  });
  const patchSettings = useMutation({
    mutationFn: (payload: Partial<UserSettings>) => api<UserSettings>("/settings", { method: "PATCH", body: JSON.stringify(payload) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }),
  });
  const connectGoogle = async () => {
    const res = await api<{ url: string }>("/integrations/google/connect-url");
    window.location.href = res.url;
  };
  const syncGoogle = useMutation({
    mutationFn: () => api<{ imported: number }>("/integrations/google/sync", { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["google-status"] });
      qc.invalidateQueries({ queryKey: ["task-groups"] });
      qc.invalidateQueries({ queryKey: ["calendar"] });
    },
  });
  const disconnectGoogle = useMutation({
    mutationFn: () => api<void>("/integrations/google", { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["google-status"] }),
  });

  return (
    <section className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-3xl font-black">Settings</h1>
        <p className="mt-1 text-[#667085]">Configure the web app experience.</p>
      </div>
      <div className="panel p-5">
        <h2 className="text-xl font-black">Theme</h2>
        <select
          className="field mt-4 max-w-xs"
          onChange={(event) => patchSettings.mutate({ theme: event.target.value as UserSettings["theme"] })}
          value={settings?.theme ?? "system"}
        >
          <option value="system">System</option>
          <option value="light">Light</option>
          <option value="dark">Dark</option>
        </select>
      </div>
      <div className="panel p-5">
        <h2 className="flex items-center gap-2 text-xl font-black">
          <Bell size={20} /> Browser notifications
        </h2>
        <p className="mt-2 text-[#667085]">Reminders can show browser notifications while the web app is open.</p>
        <button
          className="btn btn-secondary mt-4"
          onClick={async () => {
            if ("Notification" in window) {
              const permission = await Notification.requestPermission();
              patchSettings.mutate({ browser_notifications_enabled: permission === "granted" });
            }
          }}
        >
          Enable notifications
        </button>
      </div>
      <div className="panel p-5">
        <h2 className="flex items-center gap-2 text-xl font-black">
          <CalendarDays size={20} /> Google Calendar
        </h2>
        <p className="mt-2 text-[#667085]">
          {google?.connected ? `Connected as ${google.account ?? "Google Calendar"}` : "Connect Google Calendar to import visible events as read-only tasks."}
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          {google?.connected ? (
            <>
              <button className="btn btn-primary" onClick={() => syncGoogle.mutate()}>
                <RefreshCw size={18} /> Sync now
              </button>
              <button className="btn btn-secondary" onClick={() => disconnectGoogle.mutate()}>
                Disconnect
              </button>
            </>
          ) : (
            <button className="btn btn-primary" onClick={connectGoogle}>
              Connect Google
            </button>
          )}
        </div>
      </div>
    </section>
  );
}
