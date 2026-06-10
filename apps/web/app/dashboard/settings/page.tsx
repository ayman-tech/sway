"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Bell, CalendarDays, RefreshCw, Save, UserRound } from "lucide-react";
import { api } from "@/lib/api";
import type { GoogleStatus, GoogleSyncResult, UserSettings } from "@/lib/types";
import { useTheme, type ThemePreference } from "@/components/theme-provider";
import { GoogleSetupModal } from "@/components/google-setup-modal";

export default function SettingsPage() {
  const qc = useQueryClient();
  const { theme, resolvedTheme, setTheme } = useTheme();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [googleSetupOpen, setGoogleSetupOpen] = useState(false);
  const [googleMessage, setGoogleMessage] = useState("");
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
    onSuccess: (updated) => {
      setTheme(updated.theme);
      qc.invalidateQueries({ queryKey: ["settings"] });
      window.dispatchEvent(new CustomEvent("sway-profile-updated", { detail: updated }));
    },
  });
  useEffect(() => {
    if (!settings) return;
    setFirstName(settings.first_name ?? "");
    setLastName(settings.last_name ?? "");
  }, [settings]);
  const connectGoogle = async () => {
    setGoogleMessage("");
    if (!google) {
      setGoogleMessage("Google status is still loading.");
      return;
    }
    if (!google.setup_available) {
      setGoogleMessage("Google setup is unavailable until the API encryption key is configured.");
      return;
    }
    if (!google.configured) {
      setGoogleSetupOpen(true);
      return;
    }
    try {
      const res = await api<{ url: string }>("/integrations/google/connect-url");
      window.location.href = res.url;
    } catch (exc) {
      setGoogleMessage(exc instanceof Error ? exc.message : "Unable to connect Google Calendar.");
    }
  };
  const syncGoogle = useMutation({
    mutationFn: () => api<GoogleSyncResult>("/integrations/google/sync?force=true", { method: "POST" }),
    onSuccess: (result) => {
      setGoogleMessage(`Google sync complete. ${result.imported} event${result.imported === 1 ? "" : "s"} changed.`);
      qc.invalidateQueries({ queryKey: ["google-status"] });
      qc.invalidateQueries({ queryKey: ["task-groups"] });
      qc.invalidateQueries({ queryKey: ["calendar"] });
    },
    onError: (error) => setGoogleMessage(error instanceof Error ? error.message : "Google sync failed."),
  });
  const disconnectGoogle = useMutation({
    mutationFn: () => api<void>("/integrations/google", { method: "DELETE" }),
    onSuccess: () => {
      setGoogleMessage("Google Calendar disconnected. Your saved OAuth credentials were retained.");
      qc.invalidateQueries({ queryKey: ["google-status"] });
    },
    onError: (error) => setGoogleMessage(error instanceof Error ? error.message : "Unable to disconnect Google Calendar."),
  });

  return (
    <section className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-3xl font-black">Settings</h1>
        <p className="mt-1 text-[#667085]">Configure the web app experience.</p>
      </div>
      <div className="panel p-5">
        <h2 className="flex items-center gap-2 text-xl font-black">
          <UserRound size={20} /> Profile
        </h2>
        <p className="mt-2 text-[var(--muted)]">
          Your first name appears on new public availability links.
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <input
            className="field"
            maxLength={80}
            onChange={(event) => setFirstName(event.target.value)}
            placeholder="First name"
            value={firstName}
          />
          <input
            className="field"
            maxLength={80}
            onChange={(event) => setLastName(event.target.value)}
            placeholder="Last name"
            value={lastName}
          />
        </div>
        <button
          className="btn btn-primary mt-4"
          disabled={patchSettings.isPending}
          onClick={() => patchSettings.mutate({ first_name: firstName.trim() || null, last_name: lastName.trim() || null })}
        >
          <Save size={18} /> Save profile
        </button>
      </div>
      <div className="panel p-5">
        <h2 className="text-xl font-black">Theme</h2>
        <p className="mt-2 text-[var(--muted)]">
          System follows your browser setting. Current active theme: {resolvedTheme}.
        </p>
        <select
          className="field mt-4 max-w-xs"
          onChange={(event) => {
            const next = event.target.value as ThemePreference;
            setTheme(next);
            patchSettings.mutate({ theme: next });
          }}
          value={theme}
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
        {google?.last_synced_at ? (
          <p className="mt-1 text-sm text-[var(--muted)]">Last synced {new Date(google.last_synced_at).toLocaleString()}.</p>
        ) : null}
        {google?.last_sync_error ? <p className="mt-2 text-sm font-bold text-[#b42318]">{google.last_sync_error}</p> : null}
        {googleMessage ? <p className="mt-2 text-sm font-bold text-[var(--muted)]">{googleMessage}</p> : null}
        <div className="mt-4 flex flex-wrap gap-3">
          {google?.connected ? (
            <>
              <button className="btn btn-primary" onClick={() => syncGoogle.mutate()}>
                <RefreshCw size={18} /> Sync now
              </button>
              <button className="btn btn-secondary" onClick={() => disconnectGoogle.mutate()}>
                Disconnect
              </button>
              <button className="btn btn-secondary" onClick={() => setGoogleSetupOpen(true)}>
                Change credentials
              </button>
            </>
          ) : (
            <>
              <button className="btn btn-primary" disabled={!google} onClick={connectGoogle}>
                Connect Google
              </button>
              {google?.configured ? (
                <button className="btn btn-secondary" onClick={() => setGoogleSetupOpen(true)}>
                  Change credentials
                </button>
              ) : null}
            </>
          )}
        </div>
      </div>
      <GoogleSetupModal
        clientId={google?.client_id}
        onClose={() => setGoogleSetupOpen(false)}
        open={googleSetupOpen}
        redirectUri={google?.redirect_uri ?? ""}
      />
    </section>
  );
}
