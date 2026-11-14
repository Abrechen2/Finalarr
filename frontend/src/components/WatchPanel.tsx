import { Eye } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { pad } from '../lib/episodes'
import { formatDate } from '../lib/format'
import { useSeriesPatch } from '../lib/series'
import type { FollowMode, SeriesDetail } from '../lib/types'

const MODES: FollowMode[] = ['auto', 'always', 'never']

/** Who watched how much, what is still unwatched, and how Finalarr decides to follow. */
export function WatchPanel({ series }: { series: SeriesDetail }) {
  const { t, i18n } = useTranslation()
  const patch = useSeriesPatch()
  const watch = series.watch
  const mode = series.follow_mode ?? 'always'
  const choose = (next: FollowMode) => {
    if (next === mode) return
    if (next === 'auto') patch.mutate({ id: series.id, follow_mode: 'auto' })
    else patch.mutate({ id: series.id, followed: next === 'always' })
  }
  const next = watch?.next_unwatched
  if (!watch?.enabled) return null
  return (
    <section
      aria-labelledby="watch-title"
      className="mb-4 flex flex-col gap-3 rounded-card border border-line bg-surface p-4"
    >
      <h2 id="watch-title" className="flex items-center gap-2 font-display font-semibold">
        <Eye size={18} aria-hidden="true" className="text-muted" />
        {t('watch.title')}
      </h2>
      {watch && watch.users.length > 0 ? (
        <ul className="flex flex-col gap-0.5 text-sm">
          {watch.users.map((user) => (
            <li key={`${user.server}-${user.name}`}>
              {user.last_watched
                ? t('watch.user', {
                    name: user.name,
                    watched: user.watched,
                    date: formatDate(user.last_watched, i18n.language),
                  })
                : t('watch.userNoDate', { name: user.name, watched: user.watched })}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted">{t('watch.nobody')}</p>
      )}
      {watch && watch.users.length > 0 && (
        <p className="text-sm font-bold">
          {next
            ? t('watch.unwatched', {
                count: watch.unwatched_on_disk,
                next: `S${pad(next.season)}E${pad(next.episode)}`,
              })
            : t('watch.caughtUp')}
        </p>
      )}
      <fieldset>
        <legend className="mb-1 text-xs text-muted">{t('watch.mode')}</legend>
        <div className="flex w-fit overflow-hidden rounded-card border border-line">
          {MODES.map((option) => (
            <button
              key={option}
              type="button"
              aria-pressed={mode === option}
              disabled={patch.isPending}
              onClick={() => choose(option)}
              className={`px-3 py-1.5 text-sm ${mode === option ? 'bg-accent font-bold text-on-accent' : 'text-muted hover:text-ink'}`}
            >
              {t(`watch.modes.${option}`)}
            </button>
          ))}
        </div>
        <p className="mt-1 text-xs text-muted">{t(`watch.modeHint.${mode}`)}</p>
      </fieldset>
    </section>
  )
}
