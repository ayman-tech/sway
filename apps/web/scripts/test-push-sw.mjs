import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("../public/sw.js", import.meta.url), "utf8");

function worker(binding = null) {
  const handlers = {};
  const notifications = [];
  const opened = [];
  const requests = [];
  const state = { binding, windows: [] };
  const context = {
    URL, Date, Promise,
    indexedDB: {
      open() {
        const request = {};
        request.result = {
          close() {},
          transaction() {
            return { objectStore() { return { get() {
              const read = {};
              queueMicrotask(() => { read.result = state.binding; read.onsuccess(); });
              return read;
            } }; } };
          },
        };
        queueMicrotask(() => request.onsuccess());
        return request;
      },
    },
    caches: { match: async (url) => url === "/offline.html" ? "offline-page" : undefined },
    fetch: async (request, options) => { requests.push([request, options]); throw new Error("offline"); },
    self: {
      location: { origin: "https://sway.test" },
      addEventListener(name, handler) { handlers[name] = handler; },
      registration: { showNotification: async (title, options) => notifications.push({ title, ...options }) },
      clients: {
        matchAll: async () => state.windows,
        openWindow: async (url) => opened.push(url),
      },
    },
  };
  vm.runInNewContext(source, context);
  return {
    state, notifications, opened, handlers, requests,
    async push(payload) {
      let done;
      handlers.push({ data: { json: () => payload }, waitUntil(promise) { done = promise; } });
      await done;
    },
    async click() {
      let done;
      handlers.notificationclick({ notification: { close() {}, data: { url: "https://attacker.test" } }, waitUntil(promise) { done = promise; } });
      await done;
    },
  };
}

test("matching enrollment displays title but no description or supplied URL", async () => {
  const w = worker({ bindingId: "binding" });
  await w.push({ binding_id: "binding", title: "Meeting", body: "Upcoming", description: "secret", tag: "one", url: "https://attacker.test" });
  assert.equal(w.notifications[0].title, "Meeting");
  assert.equal(w.notifications[0].body, "Upcoming");
  assert.equal(w.notifications[0].data.url, "/dashboard/tasks");
  assert.equal(w.notifications[0].description, undefined);
});

test("logout and a different account suppress private title", async () => {
  for (const binding of [null, { bindingId: "different" }]) {
    const w = worker(binding);
    await w.push({ binding_id: "old", title: "Private task" });
    assert.equal(w.notifications[0].title, "Sway");
    assert.ok(!JSON.stringify(w.notifications).includes("Private task"));
  }
});

test("stale and malformed pushes use a visible generic fallback", async () => {
  const w = worker({ bindingId: "binding" });
  for (const payload of [null, "invalid", { binding_id: "binding", title: "Stale", expires_at: "2000-01-01T00:00:00Z" }]) {
    await w.push(payload);
    assert.equal(w.notifications.at(-1).title, "Sway");
  }
});

test("stable tags replace duplicate visible notifications", async () => {
  const w = worker({ bindingId: "binding" });
  const payload = { binding_id: "binding", title: "Task", tag: "delivery-id" };
  await w.push(payload); await w.push(payload);
  assert.equal(w.notifications[0].tag, w.notifications[1].tag);
});

test("notification click opens a fixed same-origin path", async () => {
  const w = worker(); await w.click();
  assert.deepEqual(w.opened, ["https://sway.test/dashboard/tasks"]);
});

test("notification click focuses and navigates an existing app window", async () => {
  const w = worker();
  let navigated, focused = false;
  w.state.windows = [{ url: "https://sway.test/dashboard/settings", async navigate(url) { navigated = url; }, async focus() { focused = true; } }];
  await w.click();
  assert.equal(navigated, "https://sway.test/dashboard/tasks");
  assert.equal(focused, true);
  assert.equal(w.opened.length, 0);
});

test("API calls and mutations remain unintercepted; navigation retains fallback", async () => {
  const w = worker();
  for (const request of [
    { method: "POST", url: "https://sway.test/tasks" },
    { method: "GET", url: "https://api.sway.test/tasks" },
    { method: "GET", url: "https://sway.test/private-data", mode: "cors" },
  ]) w.handlers.fetch({ request, respondWith() { assert.fail("Must not intercept data"); } });
  let response;
  w.handlers.fetch({ request: { method: "GET", mode: "navigate", url: "https://sway.test/dashboard/tasks" }, respondWith(promise) { response = promise; } });
  assert.equal(await response, "offline-page");
  assert.equal(w.requests[0][1].cache, "no-store");
});
