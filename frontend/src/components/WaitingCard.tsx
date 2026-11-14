import { Hourglass } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { WaitingState } from '../lib/types'

// Colours carry their DESIGN.md meaning: gold = finished, sky = files missing,
// red = count disputed, rose = airing.
const TONE: Partial<Record<WaitingState['key'], string>> = {
  airing: 'text-accent',
  scheduled: 'text-accent',
  missing: 'text-sky',
  disputed: 'text-bad',
  complete_no_sequel: 'text-gold',
  ended: 'text-gold',
}

function startText(firstAir: string, language: string): string {
  const day = new Date(firstAir)
  // AniList often knows only the year (stored as 1 January).
  if (day.getUTCMonth() === 0 && day.getUTCDate() === 1) return String(day.getUTCFullYear())
  return day.toLocaleDateString(language === 'en' ? 'en-GB' : 'de-DE', { dateStyle: 'medium' })
}

/** One sentence: what the user is waiting for on this series. */
export function WaitingCard({ waiting }: { waiting: WaitingState | undefined }) {
  const { t, i18n } = useTranslation()
  if (!waiting || waiting.key === 'not_followed') return null
  const sequel = waiting.sequel_title && ['announced', 'renewed_open'].includes(waiting.key)
  const key = `waiting.${waiting.key}${sequel ? '_sequel' : ''}`
  const text = t(key, {
    season: waiting.season,
    have: waiting.have,
    expected: waiting.expected ?? '?',
    anilist: waiting.anilist ?? '?',
    count: waiting.missing,
    sequel: waiting.sequel_title,
    date: waiting.first_air ? startText(waiting.first_air, i18n.language) : '',
  })
  return (
    <section
      aria-labelledby="waiting-title"
      className="mb-4 flex items-start gap-3 rounded-card border border-line bg-surface p-4"
    >
      <Hourglass
        size={20}
        aria-hidden="true"
        className={`mt-0.5 shrink-0 ${TONE[waiting.key] ?? 'text-muted'}`}
      />
      <div>
        <h2 id="waiting-title" className="text-xs text-muted">
          {t('waiting.title')}
        </h2>
        <p className="font-bold">{text}</p>
      </div>
    </section>
  )
}
