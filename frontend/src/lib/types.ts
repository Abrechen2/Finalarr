export type SeasonState = 'unknown' | 'scheduled' | 'airing' | 'aired' | 'complete'
export type SeriesType = 'standard' | 'anime' | 'daily'

export interface SeasonSummary {
  id: number
  number: number
  state: SeasonState
  expected: number | null
  have: number
  disputed: boolean
}

export interface SeriesSummary {
  id: number
  instance_id: number
  title: string
  year: number | null
  series_type: SeriesType
  status: string
  poster_url: string | null
  monitored: boolean
  followed: boolean
  include_specials: boolean
  respect_monitoring: boolean
  anilist_id: number | null
  anilist_resolution: 'auto' | 'manual' | 'unresolved' | 'none'
  seasons: SeasonSummary[]
}

export interface EpisodeDetail {
  id: number
  number: number
  absolute_number: number | null
  title: string
  air_date: string | null
  monitored: boolean
  has_file: boolean
  finale_type: string | null
}

export interface SeasonDetail extends SeasonSummary {
  expected_source: 'sonarr' | 'anilist' | 'override' | null
  expected_override: number | null
  anilist_count: number | null
  parts_mode: 'season' | 'parts'
  anilist_ids: number[]
  anilist_pinned: boolean
  anilist_start: string | null
  monitored: boolean
  state_since: string | null
  episodes: EpisodeDetail[]
  parts: { index: number; from: number; to: number; title: string }[]
}

export interface SeriesDetail extends Omit<SeriesSummary, 'seasons'> {
  sonarr_url: string
  seasons: SeasonDetail[]
}

export interface Page<T> {
  items: T[]
  next_cursor: string | null
}
