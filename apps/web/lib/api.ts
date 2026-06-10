"use client";

import { supabase } from "@/lib/supabase";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const accessToken = await token();
  if (!accessToken) {
    throw new Error("Not signed in.");
  }
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) {
    throw new Error(await errorMessage(res));
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

export async function publicApi<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) {
    throw new Error(await errorMessage(res));
  }
  return res.json() as Promise<T>;
}
