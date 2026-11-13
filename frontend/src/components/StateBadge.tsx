import { useTranslation } from 'react-i18next'
import type { SeasonState } from '../lib/types'

const TONE: Record<SeasonState | 'disputed', string> = {
  unknown: 'border-line text-muted',
  scheduled: 'border-line text-muted',
  airing: 'border-accent text-accent',
  aired: 'border-warn text-warn',
  complete: 'border-ok text-ok',
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
    <span className={`inline-block rounded-card border px-2 py-0.5 text-xs ${TONE[key]}`}>
      {t(`state.${key}`)}
    </span>
  )
}
