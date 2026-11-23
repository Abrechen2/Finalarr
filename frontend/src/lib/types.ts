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

export type FollowMode = 'auto' | 'always' | 'never'

export interface WatchState {
  /** A media server is connected; without one the UI hides watch state. */
  enabled: boolean
  users: { name: string; server: string; watched: number; last_watched: string | null }[]
  /** "season x episode" → ids of the users who watched it. */
  episodes: Record<string, number[]>
  /** Selected media server users who count. */
  viewers: { id: number; name: string; server: string }[]
  /** Episodes corrected by hand ("season x episode"). */
  corrected: string[]
  unwatched_on_disk: number
  next_unwatched: { season: number; episode: number } | null
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
  follow_mode?: FollowMode
  /** Most regular episodes one selected media server user has watched. */
  watched?: number
  include_specials: boolean
  respect_monitoring: boolean
  calendar: boolean
  anilist_id: number | null
  anilist_resolution: 'auto' | 'manual' | 'unresolved' | 'none'
  tags: string[]
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
  delayed_from?: string | null
}

export interface SeasonDetail extends SeasonSummary {
  expected_source: 'sonarr' | 'anilist' | 'override' | 'tvmaze' | 'tmdb' | 'trakt' | null
  expected_override: number | null
  anilist_count: number | null
  external_count?: number | null
  external_source?: 'tvmaze' | 'tmdb' | 'trakt' | null
  parts_mode: 'season' | 'parts'
  anilist_ids: number[]
  anilist_pinned: boolean
  anilist_start: string | null
  monitored: boolean
  state_since: string | null
  episodes: EpisodeDetail[]
  parts: { index: number; from: number; to: number; title: string }[]
}

export interface SeriesDetails {
  overview: string
  network: string
  runtime: number | null
  genres: string[]
  fanart_url: string | null
}

export type WaitingKey =
  | 'airing'
  | 'scheduled'
  | 'missing'
  | 'disputed'
  | 'count_unknown'
  | 'renewed_open'
  | 'announced'
  | 'complete_no_sequel'
  | 'ended'
  | 'nothing_known'
  | 'not_followed'

export interface WaitingState {
  key: WaitingKey
  season?: number | null
  have?: number
  expected?: number | null
  missing?: number
  anilist?: number | null
  sequel_title?: string | null
  first_air?: string | null
}

export interface SeriesDetail extends Omit<SeriesSummary, 'seasons'> {
  sonarr_url: string
  seasons: SeasonDetail[]
  details?: SeriesDetails
  waiting?: WaitingState
  watch?: WatchState
}

export interface NextEpisode {
  season: number | null
  episode: number
  at: string
  source: 'sonarr' | 'anilist' | 'tvmaze'
}

export interface SeriesExtras {
  next_episode: NextEpisode | null
  trailer: { youtube_id: string } | null
  channel: string | null
  watch: { name: string; url: string | null; source: 'anilist' | 'tmdb' }[]
  watch_region: string | null
  dub: {
    premiere: string | null
    next: string | null
    delayed_until: string | null
    delay_note: string
    url: string
  } | null
  errors: string[]
  /** Source pages to credit and link back to, by source id. */
  source_links?: Record<string, string>
}

export interface Page<T> {
  items: T[]
  next_cursor: string | null
}
