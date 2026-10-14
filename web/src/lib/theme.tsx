import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';

type Theme = 'light' | 'dark';

/**
 * Chart colours by role. Validated with the dataviz palette checker against the light (#fcfcfb)
 * and dark (#1a1a19) surfaces: Scope 1 green / Scope 2 violet pass CVD and contrast in both.
 */
export const CHART = {
  light: { scope1: '#1f7a4d', scope2: '#6250d6', muted: '#a8a29e', grid: '#e7e5e4', text: '#57534e', surface: '#ffffff' },
  dark: { scope1: '#3fa877', scope2: '#9085e9', muted: '#78716c', grid: '#292524', text: '#a8a29e', surface: '#1c1917' },
};

function initialTheme(): Theme {
  try {
    const saved = localStorage.getItem('pf-theme');
    if (saved === 'light' || saved === 'dark') return saved;
  } catch {
    /* storage blocked: fall through */
  }
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: dark)').matches
    ? 'dark'
    : 'light';
}

const ThemeContext = createContext<{ theme: Theme; toggle: () => void }>({ theme: 'light', toggle: () => {} });

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(initialTheme);
  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    try {
      localStorage.setItem('pf-theme', theme);
    } catch {
      /* ignore */
    }
  }, [theme]);
  const toggle = useCallback(() => setTheme((t) => (t === 'dark' ? 'light' : 'dark')), []);
  return <ThemeContext.Provider value={{ theme, toggle }}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  return useContext(ThemeContext);
}

export function useChartColors() {
  return CHART[useTheme().theme];
}
