"use client";

import { supabase } from "@/lib/supabase";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
    const message = await res.text();
    throw new Error(message || `Request failed: ${res.status}`);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}
