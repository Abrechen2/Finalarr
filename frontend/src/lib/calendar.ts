import { useQuery } from '@tanstack/react-query'
import { apiFetch } from './api'

export type CalendarKind = 'episode' | 'premiere' | 'finale' | 'announcement'

export interface CalendarEntry {
  uid: string
  kind: CalendarKind
  title: string
  season: number
  episode: number | null
  episode_title: string
  start: string
  all_day: boolean
  series_id: number | null
  has_file: boolean
  sequel_title: string | null
  delayed_from?: string | null
}

const pad = (n: number) => String(n).padStart(2, '0')

/** Local calendar day as YYYY-MM-DD. */
export function dayKey(day: Date): string {
  return `${day.getFullYear()}-${pad(day.getMonth() + 1)}-${pad(day.getDate())}`
}

/** 42 days (six weeks, Monday first) covering the given month (0-based). */
export function monthGrid(year: number, month: number): Date[] {
  const first = new Date(year, month, 1)
  const offset = (first.getDay() + 6) % 7
  return Array.from({ length: 42 }, (_, i) => new Date(year, month, 1 - offset + i))
}

export function shiftMonth(year: number, month: number, delta: number): [number, number] {
  const moved = new Date(year, month + delta, 1)
  return [moved.getFullYear(), moved.getMonth()]
}

/** Timed entries fall on the viewer's local day; all-day entries keep their date. */
export function groupByDay<T extends { start: string; all_day: boolean }>(entries: T[]) {
  return entries.reduce<Record<string, T[]>>((acc, entry) => {
    const key = entry.all_day ? entry.start.slice(0, 10) : dayKey(new Date(entry.start))
    return { ...acc, [key]: [...(acc[key] ?? []), entry] }
  }, {})
}

export function useCalendar(start: string, end: string) {
  return useQuery({
    queryKey: ['calendar', start, end],
    queryFn: () =>
      apiFetch<{ entries: CalendarEntry[] }>(`/api/v1/calendar?start=${start}&end=${end}`),
  })
}
