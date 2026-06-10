"use client";

import * as React from "react";
import { defaultThemeId, themeToCssVariables, themes, type ThemeDefinition, type ThemeId } from "@/lib/theme";

type ThemeContextValue = {
  themeId: ThemeId;
  theme: ThemeDefinition;
  themes: typeof themes;
  setThemeId: (themeId: ThemeId) => void;
};

const themeStorageKey = "careerpilot-theme";
const ThemeContext = React.createContext<ThemeContextValue | null>(null);

function resolveThemeId(value: string | null | undefined): ThemeId {
  return value && value in themes ? (value as ThemeId) : defaultThemeId;
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [themeId, setThemeIdState] = React.useState<ThemeId>(defaultThemeId);
  const [isHydrated, setIsHydrated] = React.useState(false);

  React.useEffect(() => {
    setThemeIdState(resolveThemeId(window.localStorage.getItem(themeStorageKey)));
    setIsHydrated(true);
  }, []);

  React.useEffect(() => {
    const root = document.documentElement;
    const theme = themes[themeId];

    root.dataset.theme = themeId;
    for (const [name, value] of Object.entries(themeToCssVariables(theme))) {
      root.style.setProperty(name, value);
    }

    if (isHydrated) {
      window.localStorage.setItem(themeStorageKey, themeId);
    }
  }, [isHydrated, themeId]);

  const setThemeId = React.useCallback((nextThemeId: ThemeId) => {
    setThemeIdState(resolveThemeId(nextThemeId));
  }, []);

  const value = React.useMemo(
    () => ({
      themeId,
      theme: themes[themeId],
      themes,
      setThemeId
    }),
    [setThemeId, themeId]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = React.useContext(ThemeContext);

  if (!context) {
    throw new Error("useTheme must be used inside ThemeProvider.");
  }

  return context;
}
