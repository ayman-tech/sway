"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { TriangleAlert } from "lucide-react";
import { useIsFetching, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import type { GoogleStatus, GoogleSyncResult } from "@/lib/types";
import { useTaskData } from "@/components/task-data-provider";

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
  "task-later",
  "worklog",
]);

function isForegroundQuery(query: { queryKey: readonly unknown[] }) {
  const root = query.queryKey[0];
  return typeof root === "string" && FOREGROUND_QUERY_KEYS.has(root);
}

export function GoogleSyncTrigger({ shellReady }: { shellReady: boolean }) {
  const queryClient = useQueryClient();
  const { firstLoadSettled, session } = useTaskData();
  const [syncFailure, setSyncFailure] = useState<"reconnect" | "temporary" | null>(null);
  const status = useQuery({
    queryKey: ["google-status"],
    enabled: shellReady && firstLoadSettled,
    queryFn: ({ signal }) => api<GoogleStatus>("/integrations/google/status", { signal }, { expectedUserId: session.user.id }),
    staleTime: 60_000,
    retry: false,
  });
  const foregroundFetching = useIsFetching({ predicate: isForegroundQuery });
  const [syncPending, setSyncPending] = useState(true);
  const inFlight = useRef(false);
  const lastAttemptAt = useRef(0);
  const mounted = useRef(true);

  useEffect(() => {
    if (status.isSuccess && !status.data.needs_reconnect && !status.data.last_sync_error) {
      setSyncFailure(null);
    }
  }, [status.dataUpdatedAt, status.isSuccess, status.data]);

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
          if (mounted.current) setSyncFailure(null);
          if (result.imported > 0) {
            void queryClient.invalidateQueries({ queryKey: ["task-later"] });
            void queryClient.invalidateQueries({ queryKey: ["task-groups"] });
            void queryClient.invalidateQueries({ queryKey: ["calendar"] });
            void queryClient.invalidateQueries({ queryKey: ["availability-calendar"] });
          }
        })
        .catch((error: unknown) => {
          if (!mounted.current) return;
          if (error instanceof ApiError && error.status === 409) setSyncFailure("reconnect");
          else if (queryClient.getQueryData<GoogleStatus>(["google-status"])?.connected) setSyncFailure("temporary");
        })
        .finally(() => {
          inFlight.current = false;
          void queryClient.invalidateQueries({ queryKey: ["google-status"] });
          if (mounted.current) setSyncPending(false);
        });
    }, FOREGROUND_QUIET_PERIOD_MS);

    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [foregroundFetching, queryClient, shellReady, syncPending]);

  const google = status.data;
  const reconnect = google?.needs_reconnect || syncFailure === "reconnect";
  const failed = google?.last_sync_error || syncFailure === "temporary" || (status.isError && google?.connected);
  if (!reconnect && !(google?.connected && failed)) return null;
  return <div role="status" aria-live="polite" className="mb-4 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-[var(--line)] bg-[var(--warning-bg)] px-3 py-2 text-sm text-[var(--warning-text)]">
    <TriangleAlert size={17} aria-hidden="true" className="shrink-0" />
    <span className="min-w-0 flex-1">{reconnect ? "Reconnect Google Calendar to keep events up to date." : "Google Calendar couldn’t sync. Events may be out of date."}</span>
    <Link className="inline-flex min-h-11 items-center rounded px-2 font-semibold underline focus-visible:outline focus-visible:outline-2" href="/dashboard/settings#google-calendar">{reconnect ? "Reconnect" : "Review connection"}</Link>
  </div>;
}
