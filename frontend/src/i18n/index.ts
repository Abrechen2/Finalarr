import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { readPref, writePref } from '../lib/storage'
import de from './de.json'
import en from './en.json'
import { initialLanguage } from './detect'

export { LANGUAGES, type Language } from './detect'
const LANGUAGE_KEY = 'finalarr.language'

const stored = readPref(LANGUAGE_KEY)
void i18n.use(initReactI18next).init({
  resources: { de: { translation: de }, en: { translation: en } },
  lng: initialLanguage(stored, navigator.language),
  fallbackLng: 'de',
  interpolation: { escapeValue: false },
})

// init has already announced the first language, so it is set here once.
document.documentElement.lang = i18n.language
i18n.on('languageChanged', (lng) => {
  writePref(LANGUAGE_KEY, lng)
  document.documentElement.lang = lng
})

export default i18n
