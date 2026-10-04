const CACHE_PREFIX = "sway-pwa-";
const CACHE_NAME = `${CACHE_PREFIX}v2`;
const OFFLINE_URL = "/offline.html";
const PRECACHE_URLS = [
  OFFLINE_URL,
  "/icons/sway-icon.svg",
  "/icons/sway-180.png",
  "/icons/sway-192.png",
  "/icons/sway-512.png",
  "/icons/sway-maskable-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE_URLS.map((url) => new Request(url, { cache: "reload" }))))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key.startsWith(CACHE_PREFIX) && key !== CACHE_NAME)
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === "navigate") {
    event.respondWith(fetch(request, { cache: "no-store" }).catch(() => caches.match(OFFLINE_URL)));
    return;
  }

  if (PRECACHE_URLS.includes(url.pathname)) {
    event.respondWith(caches.match(request).then((cached) => cached ?? fetch(request)));
  }
});

function readPushBinding() {
  return new Promise((resolve) => {
    const request = indexedDB.open("sway-push-device-v1", 1);
    request.onupgradeneeded = () => request.result.createObjectStore("device");
    request.onerror = () => resolve(null);
    request.onsuccess = () => {
      const db = request.result;
      const read = db.transaction("device").objectStore("device").get("binding");
      read.onsuccess = () => { db.close(); resolve(read.result ?? null); };
      read.onerror = () => { db.close(); resolve(null); };
    };
  });
}

self.addEventListener("push", (event) => {
  const display = async () => {
    let payload = {};
    try { payload = event.data?.json() ?? {}; } catch { /* Show a safe fallback. */ }
    if (typeof payload !== "object" || payload === null) payload = {};
    const binding = await readPushBinding();
    const matches = binding && binding.bindingId === payload.binding_id;
    const fresh = !payload.expires_at || Date.parse(payload.expires_at) > Date.now();
    // A visible generic fallback satisfies userVisibleOnly without disclosing
    // another account's task when logout/revocation raced an in-flight push.
    await self.registration.showNotification(matches && fresh ? String(payload.title || "Sway reminder").slice(0, 160) : "Sway", {
      body: matches && fresh ? String(payload.body || "Task reminder").slice(0, 160) : "Open Sway to check your notification settings.",
      icon: "/icons/sway-192.png",
      badge: "/icons/sway-192.png",
      tag: matches ? String(payload.tag || "sway-reminder") : "sway-notification-settings",
      data: { url: "/dashboard/tasks" },
    });
  };
  // Serialize against enrollment/logout where Web Locks are supported so logout
  // can close any notification shown immediately before its binding was cleared.
  event.waitUntil(self.navigator?.locks ? self.navigator.locks.request("sway-push-device", display) : display());
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil((async () => {
    // Never navigate to a URL supplied by a push payload.
    const target = new URL("/dashboard/tasks", self.location.origin).href;
    const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    const existing = windows.find((client) => new URL(client.url).origin === self.location.origin);
    if (existing) {
      await existing.navigate(target);
      await existing.focus();
    } else await self.clients.openWindow(target);
  })());
});
