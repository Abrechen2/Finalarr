import { useTranslation } from 'react-i18next'
import wordmark from '../assets/abrechen2-wordmark.svg?raw'

// Outlined wordmark paths (brand guide: never typeset the logo). The SVG holds
// three paths: "<", the name, "/>"; only the brackets carry the accent.
const [OPEN, NAME, CLOSE] = [...wordmark.matchAll(/ d="([^"]+)"/g)].map((m) => m[1])
const HUB = { de: 'https://www.abrechen2.de/', en: 'https://www.abrechen2.de/en/' }

export function A2Credit() {
  const { t, i18n } = useTranslation()
  const href = i18n.language === 'en' ? HUB.en : HUB.de
  return (
    <a
      href={href}
      className="inline-flex min-h-6 items-center gap-2 text-sm text-muted hover:text-ink"
    >
      <span>{t('brand.credit')}</span>
      <svg viewBox="60 40 820 120" width="128" height="19" role="img" aria-label="abrechen2">
        <path d={OPEN} className="fill-a2" />
        <path d={NAME} className="fill-ink" />
        <path d={CLOSE} className="fill-a2" />
      </svg>
    </a>
  )
}
