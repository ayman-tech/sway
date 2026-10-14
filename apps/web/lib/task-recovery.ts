import type { QueryClient, QueryKey } from "@tanstack/react-query";

// Only task reads opt in. The shared API client and mutations do not retry.
export function shouldRetryTaskRead(count: number, error: unknown): boolean {
  if (count >= 2 || !(error instanceof Error) || error.name !== "ApiError") return false;
  const failure = error as Error & { kind?: string; status?: number };
  return failure.kind === "timeout" || failure.kind === "network"
    || (failure.kind === "http" && (failure.status === 429 || (failure.status !== undefined && failure.status >= 500 && failure.status < 600)));
}

export function taskRetryDelay(attempt: number): number {
  return attempt === 0 ? 2000 : 5000;
}

export async function resumeTaskRead(client: QueryClient, queryKey: QueryKey): Promise<void> {
  const state = client.getQueryState(queryKey);
  // Fetching includes backoff; paused includes waiting for connectivity. Neither
  // should be restarted by another focus/visibility/online event.
  if (state && state.fetchStatus !== "idle") return;
  await client.invalidateQueries({ queryKey, exact: true }, { cancelRefetch: false });
}
