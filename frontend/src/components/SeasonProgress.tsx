import { useTranslation } from 'react-i18next'
import type { SeasonSummary } from '../lib/types'
import { StateBadge } from './StateBadge'

/** Bar + mono "7/12" label + state badge (PLAN.md 16.4). */
export function SeasonProgress({ season }: { season: SeasonSummary }) {
  const { t } = useTranslation()
  const expected = season.expected ?? 0
  const percent = expected ? Math.min(100, Math.round((season.have / expected) * 100)) : 0
  const label = expected ? `${season.have}/${expected}` : `${season.have}/?`
  return (
    <div className="flex items-center gap-3">
      <span className="w-10 shrink-0 font-mono text-xs text-muted">
        {t('season.short', { n: season.number })}
      </span>
      <div
        role="progressbar"
        aria-label={t('season.label', { n: season.number })}
        aria-valuemin={0}
        aria-valuemax={expected || undefined}
        aria-valuenow={season.have}
        className="h-1.5 min-w-16 flex-1 overflow-hidden rounded-full bg-line"
      >
        <div className="h-full bg-accent" style={{ width: `${percent}%` }} />
      </div>
      <span className="w-12 shrink-0 text-right font-mono text-xs font-extrabold">{label}</span>
      <StateBadge state={season.state} disputed={season.disputed} />
    </div>
  )
}
