import { useTranslation } from 'react-i18next'
import { episodeCell, isSeasonFinale, pad } from '../lib/episodes'
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
  now = new Date(),
}: {
  season: number
  episodes: EpisodeDetail[]
  /** First episode number of every split-cour part after the first. */
  partStarts?: number[]
  now?: Date
}) {
  const { t } = useTranslation()
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label={t('season.episodes')}>
      {episodes.map((episode) => {
        const cell = episodeCell(episode, now)
        const finale = isSeasonFinale(episode)
        const code = `S${pad(season)}E${pad(episode.number)}`
        const status = t(`episode.${cell}`) + (finale ? `, ${t('episode.finale')}` : '')
        const accent = finale
          ? cell === 'file'
            ? ' !bg-gold !border-gold !text-bg'
            : ' !border-gold !text-gold'
          : ''
        return (
          <li
            key={episode.id}
            title={`${code} ${episode.title}`.trim()}
            aria-label={`${code}: ${status}`}
            className={`flex h-8 w-8 items-center justify-center rounded-control border text-[11px] font-bold ${CELL[cell]}${accent}${episode.monitored ? '' : ' opacity-40'}${partStarts.includes(episode.number) ? ' ml-3' : ''}`}
          >
            {episode.number}
          </li>
        )
      })}
    </ul>
  )
}
