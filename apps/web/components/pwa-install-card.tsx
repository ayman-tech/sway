"use client";

import { CheckCircle2, Download, Share2, Smartphone } from "lucide-react";
import { useState } from "react";
import { usePwa } from "@/components/pwa-provider";

export function PwaInstallCard() {
  const { canInstall, install, isInstalled, isIos, ready } = usePwa();
  const [message, setMessage] = useState("");

  const requestInstall = async () => {
    setMessage("");
    const outcome = await install();
    if (outcome === "dismissed") {
      setMessage("Installation was dismissed. You can try again from your browser’s install menu.");
    }
    if (outcome === "unavailable") {
      setMessage("Use your browser’s install menu to add Sway to this device.");
    }
  };

  return (
    <div className="panel p-4 lg:p-5">
      <h2 className="flex items-center gap-2 text-xl font-black">
        <Smartphone size={20} /> Install Sway
      </h2>
      {!ready ? <p className="mt-2 text-[var(--muted)]">Checking installation support…</p> : null}
      {ready && isInstalled ? (
        <p className="mt-3 flex items-center gap-2 font-bold text-[var(--accent-strong)]">
          <CheckCircle2 size={19} /> Sway is installed on this device.
        </p>
      ) : null}
      {ready && !isInstalled && canInstall ? (
        <>
          <p className="mt-2 text-[var(--muted)]">
            Install Sway for a standalone, home-screen app experience.
          </p>
          <button className="btn btn-primary mobile-full mt-4" onClick={requestInstall} type="button">
            <Download size={18} /> Install Sway
          </button>
        </>
      ) : null}
      {ready && !isInstalled && !canInstall && isIos ? (
        <p className="mt-3 flex items-start gap-2 text-[var(--muted)]">
          <Share2 className="mt-0.5 shrink-0" size={18} /> In Safari, tap Share, then choose Add to Home Screen.
        </p>
      ) : null}
      {ready && !isInstalled && !canInstall && !isIos ? (
        <p className="mt-2 text-[var(--muted)]">
          Use your browser’s install option to add Sway to this device.
        </p>
      ) : null}
      {message ? (
        <p aria-live="polite" className="mt-3 text-sm font-bold text-[var(--muted)]">
          {message}
        </p>
      ) : null}
    </div>
  );
}
