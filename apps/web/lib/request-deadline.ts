// Bound the entire operation, including SDK promises that do not support abort.
export async function withDeadline<T>(work: (signal: AbortSignal) => Promise<T>, timeoutMs: number, caller?: AbortSignal | null): Promise<T> {
  const controller = new AbortController();
  const forward = () => controller.abort(new DOMException("Request cancelled", "AbortError"));
  let timer: ReturnType<typeof setTimeout> | undefined;
  let onAbort: () => void = () => {};
  const stopped = new Promise<never>((_, reject) => {
    onAbort = () => reject(controller.signal.reason);
    controller.signal.addEventListener("abort", onAbort, { once: true });
    if (caller?.aborted) forward();
    else caller?.addEventListener("abort", forward, { once: true });
    timer = setTimeout(() => controller.abort(new DOMException("Request timed out", "TimeoutError")), timeoutMs);
  });
  try {
    if (controller.signal.aborted) throw controller.signal.reason;
    return await Promise.race([Promise.resolve().then(() => work(controller.signal)), stopped]);
  } finally {
    clearTimeout(timer);
    caller?.removeEventListener("abort", forward);
    controller.signal.removeEventListener("abort", onAbort);
    // Observe rejection even when already aborted before work begins.
    void stopped.catch(() => {});
  }
}

export function measureTaskTiming(stage: string, start: number, requestId?: string | null) {
  if (typeof performance === "undefined") return;
  const name = `sway:${stage}`;
  performance.clearMeasures(name);
  performance.measure(name, { start, end: performance.now(), detail: requestId ? { requestId } : undefined });
}
