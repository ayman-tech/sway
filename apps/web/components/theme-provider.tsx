"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

export type ThemePreference = "light" | "dark" | "system";

type ThemeContextValue = {
  theme: ThemePreference;
  resolvedTheme: "light" | "dark";
  setTheme: (theme: ThemePreference) => void;
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
  const [theme, setThemeState] = useState<ThemePreference>("system");
  const [activeTheme, setActiveTheme] = useState<"light" | "dark">("light");
  const setTheme = useCallback((next: ThemePreference) => {
    window.localStorage.setItem("sway-theme", next);
    setActiveTheme(applyTheme(next));
    setThemeState(next);
  }, []);

  useEffect(() => {
    const stored = validTheme(window.localStorage.getItem("sway-theme"));
    setActiveTheme(applyTheme(stored));
    setThemeState(stored);
  }, []);

  useEffect(() => {
    setActiveTheme(applyTheme(theme));
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const listener = () => setActiveTheme(applyTheme(theme));
    media.addEventListener("change", listener);
    return () => media.removeEventListener("change", listener);
  }, [theme]);

  const value = useMemo(
    () => ({
      theme,
      resolvedTheme: activeTheme,
      setTheme,
    }),
    [theme, activeTheme, setTheme],
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
