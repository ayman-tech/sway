"use client";

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { GoogleSyncResult } from "@/lib/types";

export function GoogleSyncTrigger() {
  const queryClient = useQueryClient();

  useEffect(() => {
    const sync = async () => {
      try {
        const result = await api<GoogleSyncResult>("/integrations/google/sync", { method: "POST" });
        if (result.imported > 0) {
          queryClient.invalidateQueries({ queryKey: ["task-groups"] });
          queryClient.invalidateQueries({ queryKey: ["calendar"] });
          queryClient.invalidateQueries({ queryKey: ["availability-calendar"] });
        }
      } catch {
        // Google may be unconfigured or offline; ordinary dashboard use continues.
      }
    };
    void sync();
    const onFocus = () => void sync();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [queryClient]);

  return null;
}
