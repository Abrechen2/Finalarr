export const LANGUAGES = ['de', 'en'] as const
export type Language = (typeof LANGUAGES)[number]

/** A stored choice wins; otherwise German browsers get German, everyone else English. */
export function initialLanguage(stored: string | null, browser: string | undefined): Language {
  if (stored === 'de' || stored === 'en') return stored
  return browser?.toLowerCase().startsWith('de') ? 'de' : 'en'
}
