"use client";

import { useEffect, useRef, useState } from "react";
import { useIsFetching, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { GoogleSyncResult } from "@/lib/types";

const CLIENT_SYNC_COOLDOWN_MS = 5 * 60 * 1000;
const FOREGROUND_QUIET_PERIOD_MS = 1_000;
const GOOGLE_SYNC_TIMEOUT_MS = 120_000;
const FOREGROUND_QUERY_KEYS = new Set([
  "api-key",
  "availability-calendar",
  "calendar",
  "completed",
  "google-status",
  "settings",
  "task-groups",
]);

function isForegroundQuery(query: { queryKey: readonly unknown[] }) {
  const root = query.queryKey[0];
  return typeof root === "string" && FOREGROUND_QUERY_KEYS.has(root);
}

export function GoogleSyncTrigger({ shellReady }: { shellReady: boolean }) {
  const queryClient = useQueryClient();
  const foregroundFetching = useIsFetching({ predicate: isForegroundQuery });
  const [syncPending, setSyncPending] = useState(true);
  const inFlight = useRef(false);
  const lastAttemptAt = useRef(0);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    const requestSync = () => setSyncPending(true);
    window.addEventListener("focus", requestSync);
    window.addEventListener("online", requestSync);
    return () => {
      window.removeEventListener("focus", requestSync);
      window.removeEventListener("online", requestSync);
    };
  }, []);

  useEffect(() => {
    if (!shellReady || !syncPending || foregroundFetching > 0 || !navigator.onLine || inFlight.current) return;

    const hasSuccessfulForegroundQuery = queryClient
      .getQueryCache()
      .getAll()
      .some((query) => query.isActive() && isForegroundQuery(query) && query.state.status === "success");
    if (!hasSuccessfulForegroundQuery) return;

    if (Date.now() - lastAttemptAt.current < CLIENT_SYNC_COOLDOWN_MS) {
      setSyncPending(false);
      return;
    }

    let active = true;
    const timer = window.setTimeout(() => {
      const stillHasSuccessfulForegroundQuery = queryClient
        .getQueryCache()
        .getAll()
        .some((query) => query.isActive() && isForegroundQuery(query) && query.state.status === "success");
      if (
        !active ||
        !navigator.onLine ||
        queryClient.isFetching({ predicate: isForegroundQuery }) > 0 ||
        !stillHasSuccessfulForegroundQuery
      ) {
        return;
      }

      setSyncPending(false);
      lastAttemptAt.current = Date.now();
      inFlight.current = true;
      void api<GoogleSyncResult>(
        "/integrations/google/sync",
        { method: "POST" },
        { timeoutMs: GOOGLE_SYNC_TIMEOUT_MS },
      )
        .then((result) => {
          if (result.imported > 0) {
            void queryClient.invalidateQueries({ queryKey: ["task-groups"] });
            void queryClient.invalidateQueries({ queryKey: ["calendar"] });
            void queryClient.invalidateQueries({ queryKey: ["availability-calendar"] });
          }
        })
        .catch(() => {
          // Google may be unconfigured or offline; ordinary dashboard use continues.
        })
        .finally(() => {
          inFlight.current = false;
          if (mounted.current) setSyncPending(false);
        });
    }, FOREGROUND_QUIET_PERIOD_MS);

    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [foregroundFetching, queryClient, shellReady, syncPending]);

  return null;
}
