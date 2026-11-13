import { useTranslation } from 'react-i18next'
import type { SeasonState } from '../lib/types'

// Rose = in progress, sky = waiting on the library, gold = finished (docs/DESIGN.md).
const TONE: Record<SeasonState | 'disputed', string> = {
  unknown: 'border-line text-muted',
  scheduled: 'border-line text-muted',
  airing: 'border-accent text-accent',
  aired: 'border-sky text-sky',
  complete: 'border-gold text-gold',
  disputed: 'border-bad text-bad',
}

export function StateBadge({
  state,
  disputed = false,
}: {
  state: SeasonState
  disputed?: boolean
}) {
  const { t } = useTranslation()
  const key = disputed ? 'disputed' : state
  return (
    <span className={`inline-block rounded-full border px-2 py-0.5 text-xs ${TONE[key]}`}>
      {t(`state.${key}`)}
    </span>
  )
}
