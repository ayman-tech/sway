"use client";

import { createClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

function required(name: string, value: string | undefined) {
  if (!value?.trim()) throw new Error(`${name} is required.`);
  return value;
}

function normalizeSupabaseUrl(value: string) {
  const cleaned = value.trim().replace(/^['"]|['"]$/g, "");
  try {
    const parsed = new URL(cleaned);
    return `${parsed.protocol}//${parsed.host}`;
  } catch {
    return cleaned;
  }
}

export const supabase = createClient(
  normalizeSupabaseUrl(required("NEXT_PUBLIC_SUPABASE_URL", url)),
  required("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY", key),
);
