"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { readStartView, startViewHref } from "@/lib/start-view";

// Sign-in and the installed app both land here, then move on to the preferred start view.
export default function DashboardIndex() {
  const router = useRouter();
  useEffect(() => {
    router.replace(startViewHref(readStartView()));
  }, [router]);
  return <p className="sr-only" role="status">Opening Sway…</p>;
}
