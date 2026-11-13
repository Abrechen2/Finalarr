import { readPref, writePref } from './storage'

export const THEMES = ['system', 'dark', 'light'] as const
export type Theme = (typeof THEMES)[number]
const THEME_KEY = 'finalarr.theme'

export function storedTheme(): Theme {
  const value = readPref(THEME_KEY)
  return THEMES.includes(value as Theme) ? (value as Theme) : 'system'
}

export function applyTheme(theme: Theme): void {
  const root = document.documentElement
  if (theme === 'system') root.removeAttribute('data-theme')
  else root.setAttribute('data-theme', theme)
  writePref(THEME_KEY, theme)
}
