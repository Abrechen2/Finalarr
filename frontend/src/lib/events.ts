import { useInfiniteQuery } from '@tanstack/react-query'
import type { TFunction } from 'i18next'
import { apiFetch } from './api'
import { pad } from './episodes'
import type { Page } from './types'

export const EVENT_TYPES = [
  'season_announced',
  'episodes_available',
  'finale_available',
  'season_complete',
  'part_complete',
  'sequel_announced',
] as const
export type EventType = (typeof EVENT_TYPES)[number]

export interface EventPayload {
  title?: string
  season?: number
  episodes?: number[]
  have?: number
  expected?: number | null
  finale_number?: number
  first_air?: string | null
  part?: number
  part_title?: string
  sequel_title?: string
  parts_mode?: 'season' | 'parts'
}

export interface DeliveryView {
  id: number
  channel_id: number
  channel_name: string
  status: 'pending' | 'sent' | 'failed'
  attempts: number
  last_error: string | null
  sent_at: string | null
}

export interface EventView {
  id: number
  type: EventType
  created_at: string
  series_id: number | null
  season_id: number | null
  fingerprint: string
  payload: EventPayload
  deliveries: DeliveryView[]
}

/** [1,2,3,5,7,8] → "E01–E03, E05, E07–E08" */
export function episodeRanges(numbers: number[]): string {
  const sorted = [...new Set(numbers)].sort((a, b) => a - b)
  const parts: string[] = []
  let start = sorted[0]
  for (let i = 0; i < sorted.length; i++) {
    const current = sorted[i]
    if (sorted[i + 1] === current + 1) continue
    parts.push(start === current ? `E${pad(start)}` : `E${pad(start)}–E${pad(current)}`)
    start = sorted[i + 1]
  }
  return parts.join(', ')
}

export function formatEvent(
  t: TFunction,
  type: EventType,
  payload: EventPayload,
  language = 'de',
): string {
  const base = {
    title: payload.title ?? '?',
    s: pad(payload.season ?? 0),
    have: payload.have ?? 0,
    expected: payload.expected ?? '?',
  }
  switch (type) {
    case 'season_announced': {
      const text = t('event.announced', { ...base, s: payload.season })
      if (!payload.first_air) return text
      const date = new Date(payload.first_air).toLocaleDateString(
        language === 'en' ? 'en-GB' : 'de-DE',
      )
      return `${text} (${t('event.announcedDetail', { date, expected: base.expected })})`
    }
    case 'episodes_available':
      return t('event.available', { ...base, episodes: episodeRanges(payload.episodes ?? []) })
    case 'finale_available':
      return t('event.finale', { ...base, e: pad(payload.finale_number ?? 0) })
    case 'season_complete':
      return t('event.complete', { ...base, s: payload.season })
    case 'sequel_announced': {
      const text = t('event.sequelAnnounced', {
        title: base.title,
        sequel: payload.sequel_title ?? '?',
      })
      if (!payload.first_air) return text
      const day = new Date(payload.first_air)
      const date =
        day.getUTCMonth() === 0 && day.getUTCDate() === 1
          ? String(day.getUTCFullYear())
          : day.toLocaleDateString(language === 'en' ? 'en-GB' : 'de-DE')
      return `${text} (${t('event.sequelDetail', { date })})`
    }
    case 'part_complete':
      if (payload.parts_mode === 'parts' && payload.part_title) {
        return t('event.partCompleteAsSeason', { part: payload.part_title })
      }
      return t('event.partComplete', { ...base, s: payload.season, part: payload.part })
  }
}

export function useEvents(query: string) {
  return useInfiniteQuery({
    queryKey: ['events', query],
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams(query)
      if (pageParam) params.set('cursor', pageParam)
      const qs = params.toString()
      return apiFetch<Page<EventView>>(`/api/v1/events${qs ? `?${qs}` : ''}`)
    },
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  })
}
