import type { EpisodeDetail } from './types'

export type EpisodeCell = 'file' | 'missing' | 'future'

/** How an episode square looks: on disk, aired without file, not aired yet. */
export function episodeCell(episode: EpisodeDetail, now: Date): EpisodeCell {
  if (episode.has_file) return 'file'
  if (episode.air_date && new Date(episode.air_date) <= now) return 'missing'
  return 'future'
}

export function isSeasonFinale(episode: EpisodeDetail): boolean {
  return episode.finale_type === 'season' || episode.finale_type === 'series'
}

export function pad(n: number): string {
  return String(n).padStart(2, '0')
}
