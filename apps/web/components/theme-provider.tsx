"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";

export type ThemePreference = "light" | "dark" | "system";

type ThemeContextValue = {
  theme: ThemePreference;
  resolvedTheme: "light" | "dark";
  setTheme: (theme: ThemePreference) => void;
  setLandingTheme: (theme: ThemePreference) => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

function resolvedTheme(theme: ThemePreference) {
  if (theme !== "system") return theme;
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyTheme(theme: ThemePreference) {
  const active = resolvedTheme(theme);
  document.documentElement.dataset.theme = active;
  document.documentElement.dataset.themePreference = theme;
  return active;
}

function validTheme(value: string | null): ThemePreference {
  return value === "light" || value === "dark" || value === "system" ? value : "system";
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [theme, setThemeState] = useState<ThemePreference>("system");
  const [landingTheme, setLandingThemeState] = useState<ThemePreference>("system");
  const [activeTheme, setActiveTheme] = useState<"light" | "dark">("light");
  const setTheme = useCallback((next: ThemePreference) => {
    try { window.localStorage.setItem("sway-theme", next); } catch { /* Keep working when storage is blocked. */ }
    setThemeState(next);
  }, []);
  const setLandingTheme = useCallback((next: ThemePreference) => {
    try { window.localStorage.setItem("sway-landing-theme", next); } catch { /* Keep working when storage is blocked. */ }
    setLandingThemeState(next);
  }, []);
  const effectiveTheme = pathname === "/" ? landingTheme : theme;

  useEffect(() => {
    try {
      setThemeState(validTheme(window.localStorage.getItem("sway-theme")));
      setLandingThemeState(validTheme(window.localStorage.getItem("sway-landing-theme")));
    } catch { /* Default to system when storage is blocked. */ }
  }, []);

  useEffect(() => {
    setActiveTheme(applyTheme(effectiveTheme));
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const listener = () => setActiveTheme(applyTheme(effectiveTheme));
    media.addEventListener("change", listener);
    return () => media.removeEventListener("change", listener);
  }, [effectiveTheme]);

  const value = useMemo(
    () => ({
      theme,
      resolvedTheme: activeTheme,
      setTheme,
      setLandingTheme,
    }),
    [theme, activeTheme, setTheme, setLandingTheme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme must be used within ThemeProvider.");
  }
  return ctx;
}
