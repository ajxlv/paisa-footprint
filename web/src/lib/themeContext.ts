import { createContext, useContext } from 'react';

export type Theme = 'light' | 'dark';

/**
 * Chart colours by role. Validated with the dataviz palette checker against the light (#fcfcfb)
 * and dark (#1a1a19) surfaces: Scope 1 green / Scope 2 violet pass CVD and contrast in both.
 */
export const CHART = {
  light: { scope1: '#1f7a4d', scope2: '#6250d6', muted: '#a8a29e', grid: '#e7e5e4', text: '#57534e', surface: '#ffffff' },
  dark: { scope1: '#3fa877', scope2: '#9085e9', muted: '#78716c', grid: '#292524', text: '#a8a29e', surface: '#1c1917' },
};

export const ThemeContext = createContext<{ theme: Theme; toggle: () => void }>({ theme: 'light', toggle: () => {} });

export function useTheme() {
  return useContext(ThemeContext);
}

export function useChartColors() {
  return CHART[useTheme().theme];
}
