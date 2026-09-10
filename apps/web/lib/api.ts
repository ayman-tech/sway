"use client";

import { supabase } from "@/lib/supabase";

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

async function token() {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token;
}

async function request<T>(url: string, init: RequestInit, options: ApiRequestOptions): Promise<T> {
  const controller = new AbortController();
  const callerSignal = init.signal;
  let timedOut = false;
  const onCallerAbort = () => controller.abort(callerSignal?.reason);

  if (callerSignal?.aborted) {
    onCallerAbort();
  } else {
    callerSignal?.addEventListener("abort", onCallerAbort, { once: true });
  }

  const timeoutId = window.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, options.timeoutMs ?? DEFAULT_TIMEOUT_MS);

  try {
    const res = await fetch(url, { ...init, signal: controller.signal });
    if (!res.ok) {
      throw new ApiError(await errorMessage(res), "http", res.status);
    }
    if (res.status === 204) {
      return undefined as T;
    }
    return (await res.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (timedOut) {
      throw new ApiError("Sway took too long to respond.", "timeout");
    }
    if (callerSignal?.aborted) {
      throw new ApiError("Request cancelled.", "aborted");
    }
    throw new ApiError("Unable to reach Sway. Check your connection and try again.", "network");
  } finally {
    window.clearTimeout(timeoutId);
    callerSignal?.removeEventListener("abort", onCallerAbort);
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
  const accessToken = await token();
  if (!accessToken) {
    throw new ApiError("Not signed in.", "http", 401);
  }
  return request<T>(
    `${API_URL}${path}`,
    {
      ...init,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
        ...(init.headers ?? {}),
      },
    },
    options,
  );
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
