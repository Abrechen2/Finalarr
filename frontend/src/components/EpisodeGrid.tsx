import { useTranslation } from 'react-i18next'
import { episodeCell, isSeasonFinale, pad } from '../lib/episodes'
import type { EpisodeDetail } from '../lib/types'

const CELL = {
  file: 'bg-ink border-ink text-bg',
  missing: 'border-ink text-ink',
  future: 'border-dashed border-muted text-muted',
} as const

/** One square per episode: filled = on disk, outlined = aired without file,
 *  dashed = not aired yet; the season finale carries the accent. */
export function EpisodeGrid({
  season,
  episodes,
  now = new Date(),
}: {
  season: number
  episodes: EpisodeDetail[]
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
            ? ' !bg-accent !border-accent'
            : ' !border-accent'
          : ''
        return (
          <li
            key={episode.id}
            title={`${code} ${episode.title}`.trim()}
            aria-label={`${code}: ${status}`}
            className={`flex h-8 w-8 items-center justify-center rounded border font-mono text-[11px] ${CELL[cell]}${accent}${episode.monitored ? '' : ' opacity-40'}`}
          >
            {episode.number}
          </li>
        )
      })}
    </ul>
  )
}
