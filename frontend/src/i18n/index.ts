import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { readPref, writePref } from '../lib/storage'
import de from './de.json'
import en from './en.json'

export const LANGUAGES = ['de', 'en'] as const
export type Language = (typeof LANGUAGES)[number]
const LANGUAGE_KEY = 'finalarr.language'

const stored = readPref(LANGUAGE_KEY)
void i18n.use(initReactI18next).init({
  resources: { de: { translation: de }, en: { translation: en } },
  lng: stored === 'en' ? 'en' : 'de',
  fallbackLng: 'de',
  interpolation: { escapeValue: false },
})

i18n.on('languageChanged', (lng) => {
  writePref(LANGUAGE_KEY, lng)
  document.documentElement.lang = lng
})

export default i18n
