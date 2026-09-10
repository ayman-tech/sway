"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

type InstallOutcome = "accepted" | "dismissed" | "unavailable";

type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed"; platform: string }>;
};

type NavigatorWithStandalone = Navigator & { standalone?: boolean };

type PwaContextValue = {
  canInstall: boolean;
  install: () => Promise<InstallOutcome>;
  isInstalled: boolean;
  isIos: boolean;
  ready: boolean;
};

const PwaContext = createContext<PwaContextValue | null>(null);

function standaloneMode() {
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    Boolean((navigator as NavigatorWithStandalone).standalone)
  );
}

export function PwaProvider({ children }: { children: React.ReactNode }) {
  const [installPrompt, setInstallPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [isInstalled, setIsInstalled] = useState(false);
  const [isIos, setIsIos] = useState(false);
  const [isOnline, setIsOnline] = useState(true);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const displayMode = window.matchMedia("(display-mode: standalone)");
    const updateInstalled = () => setIsInstalled(standaloneMode());
    const updateOnline = () => setIsOnline(navigator.onLine);
    const captureInstallPrompt = (event: Event) => {
      event.preventDefault();
      setInstallPrompt(event as BeforeInstallPromptEvent);
    };
    const handleInstalled = () => {
      setInstallPrompt(null);
      setIsInstalled(true);
    };

    setIsIos(
      /iPad|iPhone|iPod/.test(navigator.userAgent) ||
        (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1),
    );
    updateInstalled();
    updateOnline();
    setReady(true);

    displayMode.addEventListener("change", updateInstalled);
    window.addEventListener("online", updateOnline);
    window.addEventListener("offline", updateOnline);
    window.addEventListener("beforeinstallprompt", captureInstallPrompt);
    window.addEventListener("appinstalled", handleInstalled);

    if (process.env.NODE_ENV === "production" && "serviceWorker" in navigator) {
      navigator.serviceWorker
        .register("/sw.js", { scope: "/", updateViaCache: "none" })
        .then((registration) => registration.update())
        .catch(() => {
          // Installation remains optional if service-worker registration is blocked.
        });
    }

    return () => {
      displayMode.removeEventListener("change", updateInstalled);
      window.removeEventListener("online", updateOnline);
      window.removeEventListener("offline", updateOnline);
      window.removeEventListener("beforeinstallprompt", captureInstallPrompt);
      window.removeEventListener("appinstalled", handleInstalled);
    };
  }, []);

  const install = useCallback(async (): Promise<InstallOutcome> => {
    if (!installPrompt) return "unavailable";
    try {
      await installPrompt.prompt();
      const choice = await installPrompt.userChoice;
      setInstallPrompt(null);
      return choice.outcome;
    } catch {
      setInstallPrompt(null);
      return "unavailable";
    }
  }, [installPrompt]);

  const value = useMemo(
    () => ({ canInstall: Boolean(installPrompt) && !isInstalled, install, isInstalled, isIos, ready }),
    [installPrompt, install, isInstalled, isIos, ready],
  );

  return (
    <PwaContext.Provider value={value}>
      {children}
      {!isOnline ? (
        <div aria-live="polite" className="pwa-offline-banner" role="status">
          You’re offline. Reconnect to view or change Sway data.
        </div>
      ) : null}
    </PwaContext.Provider>
  );
}

export function usePwa() {
  const context = useContext(PwaContext);
  if (!context) throw new Error("usePwa must be used within PwaProvider.");
  return context;
}
