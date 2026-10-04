"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import { announcePushChange, deviceLock, foregroundAllowed, pushRegistration, readPushBinding, setForegroundAllowed, writePushBinding } from "@/lib/push-device";

type PushConfig = { enabled: boolean; public_key: string | null };
type PushContextValue = {
  enrolled: boolean; ready: boolean; busy: boolean; supported: boolean;
  error: string; message: string; foreground: boolean;
  enable: () => Promise<void>; disable: () => Promise<void>; test: () => Promise<void>;
  enableForeground: () => Promise<void>; refresh: () => Promise<void>; beforeSignOut: () => Promise<void>;
};
const PushContext = createContext<PushContextValue | null>(null);

function keyBytes(key: string) {
  const raw = atob(key.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - key.length % 4) % 4));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

export function PushProvider({ children }: { children: React.ReactNode }) {
  const [enrolled, setEnrolled] = useState(false);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [supported, setSupported] = useState(false);
  const [foreground, setForeground] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const userId = useRef<string | null>(null);
  const signingOut = useRef(false);

  const reconcile = useCallback(async () => {
    if (signingOut.current) return;
    const { data } = await supabase.auth.getSession();
    const currentUser = data.session?.user.id ?? null;
    userId.current = currentUser;
    const registration = await pushRegistration();
    const binding = await readPushBinding();
    const subscription = await registration?.pushManager?.getSubscription();
    if (!currentUser || (binding && binding.userId !== currentUser)) {
      await writePushBinding(null);
      setForegroundAllowed(false);
      await subscription?.unsubscribe();
      for (const notification of await registration?.getNotifications() ?? []) notification.close();
      setEnrolled(false);
    } else if (binding && subscription && Notification.permission === "granted") {
      // Conservatively suppress foreground duplicates even during a network outage.
      setEnrolled(true);
      const config = await api<PushConfig>("/notifications/push/config");
      if (!config.enabled) throw new Error("Background push is disabled on the server. You can disable it here and use foreground-only reminders.");
      if (binding.subscriptionId) {
        try {
          await api(`/notifications/push/subscriptions/${binding.subscriptionId}`);
        } catch (exc) {
          if (!(exc instanceof ApiError) || exc.status !== 404) throw exc;
          await writePushBinding(null);
          await subscription.unsubscribe();
          setEnrolled(false);
          throw new Error("This device registration expired. Enable notifications again.");
        }
      }
      // Refresh browser-rotated endpoint/keys, or recover a lost POST response.
      // A known server-side revocation above never silently re-enrolls the device.
      const saved = await api<{ id: string }>("/notifications/push/subscriptions", {
        method: "POST", body: JSON.stringify({ ...subscription.toJSON(), binding_id: binding.bindingId }),
      });
      await writePushBinding({ ...binding, subscriptionId: saved.id });
      if (binding.subscriptionId && binding.subscriptionId !== saved.id) {
        await api(`/notifications/push/subscriptions/${binding.subscriptionId}`, { method: "DELETE" });
      }
    } else {
      if (binding?.subscriptionId) {
        await api(`/notifications/push/subscriptions/${binding.subscriptionId}`, { method: "DELETE" });
      }
      await writePushBinding(null);
      await subscription?.unsubscribe();
      setEnrolled(false);
    }
    setForeground(foregroundAllowed());
  }, []);

  const refresh = useCallback(async () => {
    try { await deviceLock(reconcile); setError(""); }
    catch (exc) { setError(exc instanceof Error ? exc.message : "Unable to check notification settings."); }
    finally { setReady(true); }
  }, [reconcile]);

  useEffect(() => {
    setSupported(window.isSecureContext && "Notification" in window && "PushManager" in window && "serviceWorker" in navigator);
    const update = () => { void refresh(); };
    // Let foreground dashboard data start first. No permission prompt on mount.
    const timer = window.setTimeout(update, 1500);
    const channel = typeof BroadcastChannel !== "undefined" ? new BroadcastChannel("sway-push") : null;
    if (channel) channel.onmessage = update;
    window.addEventListener("sway-push-changed", update);
    window.addEventListener("online", update);
    window.addEventListener("focus", update);
    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session?.user.id !== userId.current) window.setTimeout(update, 0);
    });
    return () => {
      window.clearTimeout(timer); channel?.close(); data.subscription.unsubscribe();
      window.removeEventListener("sway-push-changed", update);
      window.removeEventListener("online", update);
      window.removeEventListener("focus", update);
    };
  }, [refresh]);

  const action = async (work: () => Promise<void>) => {
    setBusy(true); setError(""); setMessage("");
    try { await deviceLock(work); announcePushChange(); }
    catch (exc) { setError(exc instanceof Error ? exc.message : "Notification setup failed. Try again."); }
    finally { setBusy(false); }
  };

  const enable = async () => {
    // Invoke permission immediately within the user gesture (important on iOS).
    if (!supported) { setError("Use a supported browser; on iPhone, add Sway to your Home Screen first."); return; }
    const permission = Notification.requestPermission();
    await action(async () => {
      if (await permission !== "granted") throw new Error("Notifications are blocked or were not allowed. Change Sway’s notification permission in browser/device settings, then try again.");
      const { data } = await supabase.auth.getSession();
      if (!data.session || signingOut.current) throw new Error("Sign in before enabling notifications.");
      const id = data.session.user.id;
      const config = await api<PushConfig>("/notifications/push/config");
      if (!config.enabled || !config.public_key) throw new Error("Push is not configured on this server yet. Foreground-only reminders are still available.");
      const registration = await pushRegistration();
      if (!registration?.active) throw new Error("Sway’s service worker is not ready. Reload the production website and try again.");
      let binding = await readPushBinding();
      let subscription = await registration.pushManager.getSubscription();
      if (!binding || binding.userId !== id) {
        await writePushBinding(null);
        await subscription?.unsubscribe();
        subscription = null;
        binding = { userId: id, bindingId: crypto.randomUUID() };
      }
      subscription ??= await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(config.public_key) });
      await writePushBinding(binding);
      const saved = await api<{ id: string }>("/notifications/push/subscriptions", {
        method: "POST", body: JSON.stringify({ ...subscription.toJSON(), binding_id: binding.bindingId }),
      });
      await writePushBinding({ ...binding, subscriptionId: saved.id });
      setForegroundAllowed(false);
      setEnrolled(true);
      setMessage("Background notifications enabled on this device. Send a test to check delivery.");
    });
  };

  const removeDevice = async () => {
    const binding = await readPushBinding();
    // Fail closed: clearing the worker-visible binding is required before logout.
    await writePushBinding(null);
    setEnrolled(false);
    setForegroundAllowed(false);
    setForeground(false);
    setMessage("Notifications are disabled on this device.");
    const registration = await pushRegistration();
    for (const notification of await registration?.getNotifications() ?? []) notification.close();
    const subscription = await registration?.pushManager?.getSubscription();
    let localFailure = false;
    try { if (subscription) localFailure = !(await subscription.unsubscribe()); }
    catch { localFailure = true; }
    if (binding?.subscriptionId) {
      try { await api(`/notifications/push/subscriptions/${binding.subscriptionId}`, { method: "DELETE" }, { timeoutMs: 5000 }); }
      catch { setMessage("Private notification content is disabled locally. Server cleanup could not be confirmed; expired subscriptions are removed automatically."); }
    }
    if (localFailure) throw new Error("Private notification content is disabled, but unsubscribe failed. Revoke Sway’s notification permission in your browser settings.");
  };

  const beforeSignOut = async () => {
    signingOut.current = true;
    try { await deviceLock(removeDevice); }
    catch (exc) { signingOut.current = false; throw exc; }
    finally { announcePushChange(); }
  };

  return <PushContext.Provider value={{ enrolled, ready, busy, supported, error, message, foreground, refresh,
    enable,
    disable: () => action(removeDevice),
    beforeSignOut,
    test: () => action(async () => {
      const binding = await readPushBinding();
      if (!binding?.subscriptionId) throw new Error("Enable notifications first.");
      const result = await api<{ message: string }>(`/notifications/push/subscriptions/${binding.subscriptionId}/test`, { method: "POST" });
      setMessage(result.message);
    }),
    enableForeground: async () => {
      if (!("Notification" in window)) { setError("This browser does not support notifications."); return; }
      const permission = await Notification.requestPermission();
      if (permission !== "granted") { setError("Allow notifications in browser settings first."); return; }
      await action(async () => { setForegroundAllowed(true); setForeground(true); setMessage("Foreground-only reminders enabled. Keep Sway open to receive them."); });
    },
  }}>{children}</PushContext.Provider>;
}

export function usePush() {
  const context = useContext(PushContext);
  if (!context) throw new Error("usePush requires PushProvider.");
  return context;
}
