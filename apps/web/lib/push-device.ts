"use client";

// Shared schema with sw.js. No task data or authentication tokens are stored.
export type PushBinding = { userId: string; bindingId: string; subscriptionId?: string };
const DB = "sway-push-device-v1";

async function database(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB, 1);
    request.onupgradeneeded = () => request.result.createObjectStore("device");
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(new Error("Device storage is unavailable. Allow site storage to use push notifications."));
  });
}

export async function readPushBinding(): Promise<PushBinding | null> {
  const db = await database();
  try {
    return await new Promise((resolve, reject) => {
      const request = db.transaction("device").objectStore("device").get("binding");
      request.onsuccess = () => resolve(request.result ?? null);
      request.onerror = () => reject(new Error("Unable to read notification settings."));
    });
  } finally { db.close(); }
}

export async function writePushBinding(binding: PushBinding | null) {
  const db = await database();
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = db.transaction("device", "readwrite");
      const store = transaction.objectStore("device");
      if (binding) store.put(binding, "binding"); else store.delete("binding");
      transaction.oncomplete = () => resolve();
      transaction.onerror = transaction.onabort = () => reject(new Error("Unable to save notification settings."));
    });
  } finally { db.close(); }
}

export async function deviceLock<T>(work: () => Promise<T>): Promise<T> {
  if (navigator.locks) return navigator.locks.request("sway-push-device", work);
  return work();
}

export async function pushRegistration() {
  if (!("serviceWorker" in navigator)) return undefined;
  // Do not wait indefinitely on serviceWorker.ready in development or if blocked.
  return navigator.serviceWorker.getRegistration("/");
}

export function announcePushChange() {
  window.dispatchEvent(new Event("sway-push-changed"));
  const channel = typeof BroadcastChannel !== "undefined" ? new BroadcastChannel("sway-push") : null;
  channel?.postMessage("changed");
  channel?.close();
}

export function foregroundAllowed() {
  try { return localStorage.getItem("sway-foreground-notifications") !== "off"; }
  catch { return false; }
}

export function setForegroundAllowed(enabled: boolean) {
  localStorage.setItem("sway-foreground-notifications", enabled ? "on" : "off");
}
