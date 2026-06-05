"use client";

import { createClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

function normalizeSupabaseUrl(value: string | undefined) {
  if (!value) {
    return "http://localhost:54321";
  }
  const cleaned = value.trim().replace(/^['"]|['"]$/g, "");
  try {
    const parsed = new URL(cleaned);
    return `${parsed.protocol}//${parsed.host}`;
  } catch {
    return cleaned;
  }
}

export const supabase = createClient(normalizeSupabaseUrl(url), key ?? "missing-key");
