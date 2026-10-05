"use client";

import { supabase } from "@/lib/supabase";
import { withDeadline, measureTaskTiming } from "@/lib/request-deadline";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8010";
const DEFAULT_TIMEOUT_MS = 15_000;

export type ApiErrorKind = "aborted" | "http" | "network" | "timeout";

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status?: number;

  constructor(message: string, kind: ApiErrorKind, status?: number) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
  }
}

export type ApiRequestOptions = {
  timeoutMs?: number;
  expectedUserId?: string;
};

async function errorMessage(res: Response) {
  const text = await res.text();
  try {
    const body = JSON.parse(text) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    // The response was not JSON.
  }
  return text || `Request failed: ${res.status}`;
}

export function boundedSession(signal?: AbortSignal) {
  return withDeadline(() => supabase.auth.getSession(), DEFAULT_TIMEOUT_MS, signal);
}

async function request<T>(url: string, init: RequestInit, options: ApiRequestOptions, authenticated = false): Promise<T> {
  try {
    return await withDeadline(async (signal) => {
      const headers = new Headers(init.headers);
      headers.set("Content-Type", "application/json");
      if (authenticated) {
        const started = performance.now();
        const { data, error } = await supabase.auth.getSession();
        measureTaskTiming("token-ready", started);
        signal.throwIfAborted();
        if (error) {
          const unauthorized = error.status === 401 || error.status === 403;
          throw new ApiError("Unable to restore your session. Try again.", unauthorized ? "http" : "network", unauthorized ? error.status : undefined);
        }
        if (!data.session) throw new ApiError("Not signed in.", "http", 401);
        if (options.expectedUserId && data.session.user.id !== options.expectedUserId) throw new ApiError("Account changed. Reload Sway.", "aborted");
        headers.set("Authorization", `Bearer ${data.session.access_token}`);
      }
      signal.throwIfAborted();
      const started = performance.now();
      const res = await fetch(url, { ...init, headers, signal });
      if (url.includes("/tasks/groups")) measureTaskTiming("tasks-api", started, res.headers.get("X-Request-ID"));
      if (!res.ok) {
        throw new ApiError(await errorMessage(res), "http", res.status);
      }
      if (res.status === 204) {
        return undefined as T;
      }
      return (await res.json()) as T;
    }, options.timeoutMs ?? DEFAULT_TIMEOUT_MS, init.signal);
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "TimeoutError") {
      throw new ApiError("Sway took too long to respond.", "timeout");
    }
    if (init.signal?.aborted || error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("Request cancelled.", "aborted");
    }
    throw new ApiError("Unable to reach Sway. Check your connection and try again.", "network");
  }
}

export function isTransientApiError(error: unknown): boolean {
  if (!(error instanceof ApiError)) return false;
  if (error.kind === "network") return true;
  if (error.kind !== "http" || error.status === undefined) return false;
  return error.status === 429 || error.status >= 500;
}

export async function api<T>(
  path: string,
  init: RequestInit = {},
  options: ApiRequestOptions = {},
): Promise<T> {
  return request<T>(`${API_URL}${path}`, init, options, true);
}

export async function publicApi<T>(
  path: string,
  init: RequestInit = {},
  options: ApiRequestOptions = {},
): Promise<T> {
  return request<T>(
    `${API_URL}${path}`,
    {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init.headers ?? {}),
      },
    },
    options,
  );
}
