import { Check } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { episodeCell, isSeasonFinale, pad } from '../lib/episodes'
import { formatDate } from '../lib/format'
import type { EpisodeDetail } from '../lib/types'

const CELL = {
  file: 'bg-accent border-accent text-on-accent',
  missing: 'border-ink text-ink',
  future: 'border-dashed border-muted text-muted',
} as const

/** One square per episode (docs/DESIGN.md): rose = on disk, outlined = aired without
 *  file, dashed = not aired yet; the season finale is gold. */
export function EpisodeGrid({
  season,
  episodes,
  partStarts = [],
  watched = {},
  corrected = [],
  selected,
  onSelect,
  now = new Date(),
}: {
  season: number
  episodes: EpisodeDetail[]
  /** First episode number of every split-cour part after the first. */
  partStarts?: number[]
  /** "season x episode" → who watched it (media servers). */
  watched?: Record<string, string[]>
  /** Episodes whose watched state was corrected by hand ("season x episode"). */
  corrected?: string[]
  selected?: number
  /** Makes every square a button, e.g. to correct its watched state. */
  onSelect?: (episode: number) => void
  now?: Date
}) {
  const { t, i18n } = useTranslation()
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label={t('season.episodes')}>
      {episodes.map((episode) => {
        const cell = episodeCell(episode, now)
        const finale = isSeasonFinale(episode)
        const code = `S${pad(season)}E${pad(episode.number)}`
        const delayed = episode.delayed_from
          ? t('episode.delayed', { date: formatDate(episode.delayed_from, i18n.language) })
          : ''
        const viewers = watched[`${season}x${episode.number}`] ?? []
        const seen = viewers.length ? t('episode.watchedBy', { names: viewers.join(', ') }) : ''
        const fixed = corrected.includes(`${season}x${episode.number}`) ? t('watch.corrected') : ''
        const status = [t(`episode.${cell}`), finale && t('episode.finale'), delayed, seen, fixed]
          .filter(Boolean)
          .join(', ')
        const accent = finale
          ? cell === 'file'
            ? ' !bg-gold !border-gold !text-bg'
            : ' !border-gold !text-gold'
          : ''
        const label = `${code}: ${status}`
        const square = `relative flex h-8 w-8 items-center justify-center rounded-control border text-[11px] font-bold ${CELL[cell]}${accent}${episode.monitored ? '' : ' opacity-40'}${selected === episode.number ? ' ring-2 ring-accent' : ''}`
        const content = (
          <>
            {episode.number}
            {seen && (
              <span
                aria-hidden="true"
                className="absolute -right-1 -top-1 flex h-3.5 w-3.5 items-center justify-center rounded-full border border-line bg-surface text-ink"
              >
                <Check size={9} strokeWidth={3} />
              </span>
            )}
            {delayed && (
              <span aria-hidden="true" className="ml-px text-[9px] text-sky">
                ⏸
              </span>
            )}
          </>
        )
        const title =
          `${code} ${episode.title}${delayed ? ` (${delayed})` : ''}${seen ? ` – ${seen}` : ''}`.trim()
        const gap = partStarts.includes(episode.number) ? 'ml-3' : ''
        return onSelect ? (
          <li key={episode.id} className={gap}>
            <button
              type="button"
              title={title}
              aria-label={label}
              aria-pressed={selected === episode.number}
              onClick={() => onSelect(episode.number)}
              className={square}
            >
              {content}
            </button>
          </li>
        ) : (
          <li key={episode.id} title={title} aria-label={label} className={`${square} ${gap}`}>
            {content}
          </li>
        )
      })}
    </ul>
  )
}
